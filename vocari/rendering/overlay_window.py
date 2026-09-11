"""Transparent, frameless, always-on-top overlay window that renders the avatar."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QMouseEvent, QPainter, QPixmap, QWheelEvent
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

# Procedural idle sway (e.g. the ahoge) and talk bounce (the whole avatar,
# triggered by set_talking() once Stage 3 wires up TTS playback) — no extra
# art needed, just a small per-frame offset. Both are gated by the "Покачивание"
# toggle in settings.
ANIMATION_INTERVAL_MS = 33  # ~30 FPS, matches the spec's render timer cap
TWO_PI = 2 * math.pi
SWAY_AMPLITUDE_PX = 6.0
SWAY_PERIOD_S = 2.6
SWAY_PHASE_STEP = TWO_PI * ANIMATION_INTERVAL_MS / 1000 / SWAY_PERIOD_S
BOUNCE_AMPLITUDE_PX = 10.0
BOUNCE_PERIOD_S = 0.5
BOUNCE_PHASE_STEP = TWO_PI * ANIMATION_INTERVAL_MS / 1000 / BOUNCE_PERIOD_S


class OverlayWindow(QWidget):
    def __init__(self, model: AvatarModel, config: OverlayConfig, render_config: RenderConfig):
        super().__init__()
        self.model = model
        self.config = config
        self.render_config = render_config

        self._z_order = model.build_z_order()
        self._pixmaps: dict[str, QPixmap] = self._load_pixmaps()
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
        self._sway_phase = 0.0
        self._bounce_phase = 0.0
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
        """Called during TTS playback (Stage 3) to trigger the talk bounce."""
        if self._talking != talking:
            self._talking = talking
            self._update_animation_timer()

    def _animation_active(self) -> bool:
        return self._sway_enabled and (bool(self._sway_layer_phase) or self._talking)

    def _update_animation_timer(self) -> None:
        should_run = self._animation_active()
        if should_run and not self._anim_timer.isActive():
            self._anim_timer.start(ANIMATION_INTERVAL_MS)
        elif not should_run and self._anim_timer.isActive():
            self._anim_timer.stop()
            self.update()  # repaint once more to clear any residual offset

    def _on_animation_tick(self) -> None:
        self._sway_phase = (self._sway_phase + SWAY_PHASE_STEP) % TWO_PI
        self._bounce_phase = (self._bounce_phase + BOUNCE_PHASE_STEP) % TWO_PI
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
            if self._sway_enabled and self._talking:
                bounce_offset = BOUNCE_AMPLITUDE_PX * math.sin(self._bounce_phase)

            for kind, ref in self._z_order:
                pixmap = self._resolve_pixmap(kind, ref)
                if pixmap is None or pixmap.isNull():
                    continue
                y_offset = bounce_offset
                if self._sway_enabled and kind == "layer" and ref in self._sway_layer_phase:
                    y_offset += SWAY_AMPLITUDE_PX * math.sin(self._sway_phase + self._sway_layer_phase[ref])
                painter.drawPixmap(0, round(y_offset), pixmap)
        finally:
            painter.end()

    def _resolve_pixmap(self, kind: str, ref: str) -> QPixmap | None:
        if kind == "layer":
            return self._pixmaps.get(ref)
        group = self.model.states[ref]
        frame_name = self._active_frame.get(ref, next(iter(group.frames)))
        filename = group.frames.get(frame_name)
        return self._pixmaps.get(filename) if filename else None

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
