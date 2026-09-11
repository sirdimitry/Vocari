"""Transparent, frameless, always-on-top overlay window that renders the avatar."""
from __future__ import annotations

import math
import random

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QWidget

from vocari.config.settings import OverlayConfig, RenderConfig
from vocari.logging_setup import get_logger
from vocari.rendering.model import AvatarModel

logger = get_logger("overlay")

MIN_SCALE = 0.1
MAX_SCALE = 5.0
SCALE_STEP = 1.1

BLINK_MIN_INTERVAL_MS = 2000
BLINK_MAX_INTERVAL_MS = 6000
BLINK_CLOSED_DURATION_MS = 150

# Procedural idle sway (e.g. the ahoge) — no extra art needed, just a small
# per-frame offset — plus an audio-reactive talk bounce driven by whatever
# level AudioPlayer reports (see set_bounce_level): louder/sharper audio
# pushes the whole avatar further, quiet passages let it settle back down.
# Both are gated by the "Покачивание" toggle in settings.
ANIMATION_INTERVAL_MS = 33  # ~30 FPS, matches the spec's render timer cap
TWO_PI = 2 * math.pi
SWAY_AMPLITUDE_PX = 6.0
SWAY_PERIOD_S = 2.6
SWAY_PHASE_STEP = TWO_PI * ANIMATION_INTERVAL_MS / 1000 / SWAY_PERIOD_S
BOUNCE_AMPLITUDE_PX = 16.0  # vertical hop at bounce_level == 1.0 (loudest)
BOTTOM_EDGE_CHECK_ROWS = 4  # a layer with opaque pixels this close to the
# canvas bottom is treated as "flush with the frame" (e.g. a torso/long hair
# cropped by the canvas edge, no art below it) and excluded from the bounce —
# otherwise moving it up would tear it away from the window's bottom edge and
# leave a transparent gap where a streamer framed the source flush at the bottom.


def _touches_bottom_edge(pixmap: QPixmap, rows: int = BOTTOM_EDGE_CHECK_ROWS) -> bool:
    if pixmap.isNull():
        return False
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    if width == 0 or height == 0:
        return False
    buffer = image.constBits()
    stride = image.bytesPerLine()
    arr = np.frombuffer(buffer, dtype=np.uint8, count=stride * height).reshape(height, stride)
    arr = arr[:, : width * 4].reshape(height, width, 4)
    bottom_rows = arr[max(0, height - rows) :, :, 3]  # alpha channel (ARGB32 is B,G,R,A in memory)
    return bool((bottom_rows > 10).any())


class OverlayWindow(QWidget):
    def __init__(self, model: AvatarModel, config: OverlayConfig, render_config: RenderConfig):
        super().__init__()
        self.model = model
        self.config = config
        self.render_config = render_config

        self._z_order = model.build_z_order()
        self._pixmaps: dict[str, QPixmap] = self._load_pixmaps()
        self._bottom_anchored: set[str] = self._compute_bottom_anchored()
        # Stage 1 default state: eyes open, mouth closed (per spec).
        self._active_frame: dict[str, str] = {"eyes": "open", "mouth": "closed"}
        self._drag_offset: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowTitle(f"Vocari - {model.name}")

        self._apply_scale()
        self.move(self.config.pos_x, self.config.pos_y)

        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._start_blink)
        self._schedule_next_blink()

        # -- procedural sway/bounce ---------------------------------------
        self._sway_enabled = render_config.enable_sway
        self._talking = False
        self._bounce_level = 0.0  # 0..1, driven by AudioPlayer via set_bounce_level()
        self._sway_phase = 0.0
        self._sway_layer_phase: dict[str, float] = {}
        self._recompute_sway_layers()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_animation_tick)
        self._update_animation_timer()

    def set_model(self, model: AvatarModel) -> None:
        """Hot-swap the displayed model (used by the settings "Модель" tab
        after an import, so the overlay updates without restarting the app)."""
        self.model = model
        self._z_order = model.build_z_order()
        self._pixmaps = self._load_pixmaps()
        self._bottom_anchored = self._compute_bottom_anchored()
        self._active_frame = {"eyes": "open", "mouth": "closed"}
        self._apply_scale()
        self.setWindowTitle(f"Vocari - {model.name}")
        self._schedule_next_blink()
        self._recompute_sway_layers()
        self._update_animation_timer()
        self.update()

    def _recompute_sway_layers(self) -> None:
        self._sway_layer_phase = {
            filename: index * 0.9 for index, filename in enumerate(self.model.sway_layers)
        }

    def _load_pixmaps(self) -> dict[str, QPixmap]:
        pixmaps: dict[str, QPixmap] = {}
        for filename in self.model.all_filenames():
            pixmaps[filename] = QPixmap(str(self.model.layer_path(filename)))
        return pixmaps

    def _compute_bottom_anchored(self) -> set[str]:
        anchored = {fn for fn, pm in self._pixmaps.items() if _touches_bottom_edge(pm)}
        if anchored:
            logger.debug("Слои у нижнего края холста (не участвуют в подпрыгивании): %s", ", ".join(sorted(anchored)))
        return anchored

    def _apply_scale(self) -> None:
        width, height = self.model.canvas_size
        self.resize(
            max(1, round(width * self.config.scale)),
            max(1, round(height * self.config.scale)),
        )

    def set_active_frame(self, state_key: str, frame_name: str) -> None:
        if self._active_frame.get(state_key) != frame_name:
            self._active_frame[state_key] = frame_name
            self.update()

    # -- blinking -------------------------------------------------------------

    def _schedule_next_blink(self) -> None:
        if "eyes" not in self.model.states:
            return
        delay_ms = random.randint(BLINK_MIN_INTERVAL_MS, BLINK_MAX_INTERVAL_MS)
        self._blink_timer.start(delay_ms)

    def _start_blink(self) -> None:
        self.set_active_frame("eyes", "closed")
        QTimer.singleShot(BLINK_CLOSED_DURATION_MS, self._end_blink)

    def _end_blink(self) -> None:
        self.set_active_frame("eyes", "open")
        self._schedule_next_blink()

    # -- procedural sway / talk bounce -----------------------------------------

    def set_sway_enabled(self, enabled: bool) -> None:
        """Live-toggle from Settings → Рендер → "Покачивание"."""
        self._sway_enabled = enabled
        self._update_animation_timer()
        self.update()

    def set_talking(self, talking: bool) -> None:
        """Marks whether TTS playback is active — mostly informational; the
        actual bounce motion comes from set_bounce_level()."""
        self._talking = talking
        if not talking:
            self.set_bounce_level(0.0)

    def set_bounce_level(self, level: float) -> None:
        """Called by AudioPlayer on every playback tick with a smoothed 0..1
        loudness level — see audio_player.py's envelope follower. Repaints
        immediately rather than waiting on the idle-sway timer, since this is
        meant to track the audio closely."""
        self._bounce_level = max(0.0, min(1.0, level))
        self.update()

    def _animation_active(self) -> bool:
        return self._sway_enabled and bool(self._sway_layer_phase)

    def _update_animation_timer(self) -> None:
        should_run = self._animation_active()
        if should_run and not self._anim_timer.isActive():
            self._anim_timer.start(ANIMATION_INTERVAL_MS)
        elif not should_run and self._anim_timer.isActive():
            self._anim_timer.stop()
            self.update()  # repaint once more to clear any residual offset

    def _on_animation_tick(self) -> None:
        self._sway_phase = (self._sway_phase + SWAY_PHASE_STEP) % TWO_PI
        self.update()

    # -- painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        try:
            # If anything below raises mid-paint (e.g. a KeyboardInterrupt
            # delivered while Ctrl+C-ing the app in a terminal — the ~30 FPS
            # animation timer is what lets Python notice SIGINT at all in a Qt
            # app), an unclosed QPainter leaves the backing store thinking a
            # paint is still in progress, which cascades into endless
            # "Painter not active" errors. The try/finally guarantees end()
            # still runs.
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            canvas_w, canvas_h = self.model.canvas_size
            if self.width() and self.height():
                painter.scale(self.width() / canvas_w, self.height() / canvas_h)

            bounce_offset = 0.0
            if self._sway_enabled and self._bounce_level > 0.0:
                # Negative = upward hop, scaled by how loud/sharp the current
                # audio is — not a fixed-rate oscillation.
                bounce_offset = -self._bounce_level * BOUNCE_AMPLITUDE_PX

            for kind, ref in self._z_order:
                pixmap, filename = self._resolve_layer(kind, ref)
                if pixmap is None or pixmap.isNull():
                    continue
                y_offset = 0.0 if filename in self._bottom_anchored else bounce_offset
                if self._sway_enabled and kind == "layer" and ref in self._sway_layer_phase:
                    y_offset += SWAY_AMPLITUDE_PX * math.sin(self._sway_phase + self._sway_layer_phase[ref])
                painter.drawPixmap(0, round(y_offset), pixmap)
        finally:
            painter.end()

    def _resolve_layer(self, kind: str, ref: str) -> tuple[QPixmap | None, str | None]:
        if kind == "layer":
            return self._pixmaps.get(ref), ref
        group = self.model.states[ref]
        frame_name = self._active_frame.get(ref, next(iter(group.frames)))
        filename = group.frames.get(frame_name)
        return (self._pixmaps.get(filename) if filename else None), filename

    # -- drag to move -------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.sync_geometry_to_config()

    # -- scale with mouse wheel ---------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = SCALE_STEP if event.angleDelta().y() > 0 else 1 / SCALE_STEP
        self.config.scale = max(MIN_SCALE, min(MAX_SCALE, self.config.scale * factor))
        self._apply_scale()
        self.update()

    # -- misc -----------------------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # The window is frameless (needed for a clean OBS capture), so it has no
        # title bar close button. Escape hides it; use the tray icon to show it
        # again or quit the app entirely.
        if event.key() == Qt.Key.Key_Escape:
            self.hide()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.sync_geometry_to_config()
        super().closeEvent(event)

    def sync_geometry_to_config(self) -> None:
        self.config.pos_x = self.x()
        self.config.pos_y = self.y()
