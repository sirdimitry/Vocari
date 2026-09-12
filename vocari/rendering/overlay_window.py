"""Transparent, frameless overlay window that renders the "stage" — zero or
more avatar instances (see rendering/stage.py) that jump in to speak and
jump back out. The window is sized for the worst case (a full queue of 7),
so it's much wider than a single avatar and mostly transparent/empty most
of the time; the avatar's configured X/Y position is where the *speaker*
slot lands on screen, not the window's own top-left corner — see
_stage_offset_px()."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QWidget

from vocari.config.settings import BubbleConfig, OverlayConfig, RenderConfig
from vocari.logging_setup import get_logger
from vocari.rendering import bubble
from vocari.rendering.model import AvatarModel, EffectSpec, SwaySpec
from vocari.rendering.stage import AvatarInstance, Stage

logger = get_logger("overlay")

MIN_SCALE = 0.1
MAX_SCALE = 5.0
SCALE_STEP = 1.1

BLINK_MIN_INTERVAL_MS = 2000
BLINK_MAX_INTERVAL_MS = 6000
BLINK_CLOSED_DURATION_MS = 150

# Procedural idle sway (e.g. the ahoge, swinging like a real strand of hair
# from where it's rooted) — no extra art needed — plus an audio-reactive talk
# bounce driven by whatever level AudioPlayer reports (see set_speaker_bounce_level):
# louder/sharper audio pushes the whole avatar further, quiet passages let it
# settle back down. Both are gated by the "Покачивание" toggle in settings.
ANIMATION_INTERVAL_MS = 33  # ~30 FPS, matches the spec's render timer cap
TWO_PI = 2 * math.pi
SWAY_ROTATION_DEG = 11.0
SWAY_PERIOD_S = 1.8
SWAY_PHASE_STEP = TWO_PI * ANIMATION_INTERVAL_MS / 1000 / SWAY_PERIOD_S
BOUNCE_AMPLITUDE_PX = 16.0  # vertical hop at bounce_level == 1.0 (loudest)
IDLE_BOB_AMPLITUDE_PX = 4.0  # subtle breathing-like bob, applied to every instance on stage
IDLE_BOB_PERIOD_S = 2.4
IDLE_BOB_PHASE_STEP = TWO_PI * ANIMATION_INTERVAL_MS / 1000 / IDLE_BOB_PERIOD_S

# bounce_react_layers (e.g. ears): on top of the shared translation above,
# these also rotate around their own attachment point, with the rotation
# *lagging* behind the current bounce via exponential smoothing — the edge
# at the pivot moves exactly with the body (zero lag, it's the anchor);
# the far tip swings and visibly catches up a few frames later, instead of
# translating in rigid lockstep with everything else.
BOUNCE_REACT_DEG_PER_PX = 0.45  # target rotation per px of current bounce offset
BOUNCE_REACT_LAG_COEFF = 0.25  # how much of the gap to target angle closes per tick (lower = laggier)

ALPHA_THRESHOLD = 10

# Space reserved above the avatars for the speech bubble, as a fraction of the
# canvas height. The window grows upward by this; without it a bubble drawn
# above the head would simply be clipped off by the window edge.
BUBBLE_HEADROOM_FRACTION = 0.85


def _to_alpha_array(pixmap: QPixmap) -> np.ndarray | None:
    """Alpha channel of `pixmap` as a (height, width) uint8 array, or None
    for an empty/null pixmap."""
    if pixmap.isNull():
        return None
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    if width == 0 or height == 0:
        return None
    buffer = image.constBits()
    stride = image.bytesPerLine()
    arr = np.frombuffer(buffer, dtype=np.uint8, count=stride * height).reshape(height, stride)
    # .copy(): `image` is local and goes out of scope on return, freeing the
    # buffer `arr` views into — without a copy the caller gets a dangling
    # pointer (crashes with an access violation, not a Python exception).
    return arr[:, : width * 4].reshape(height, width, 4)[:, :, 3].copy()  # ARGB32 is B,G,R,A in memory


def _sway_pivot(pixmap: QPixmap, mode: str = "bottom") -> tuple[float, float] | None:
    """Where a sway layer is "rooted" so it can rotate from there instead of
    just translating — e.g. the ahoge should swing from the point where it
    meets the scalp, not slide up and down as a rigid block.

    "bottom" (the default) takes the horizontal center of the opaque pixels at
    their lowest row, which is right for anything sticking up out of the head.
    "top" does the same at the highest row, for parts that hang down from their
    attachment instead (drool, a goatee, a loose strand) — those would otherwise
    swing their root around their own tip. "center" is the opaque centroid.
    Returns None if the layer is fully transparent."""
    alpha = _to_alpha_array(pixmap)
    if alpha is None:
        return None
    ys, xs = np.where(alpha > ALPHA_THRESHOLD)
    if len(ys) == 0:
        return None
    if mode == "center":
        return float(xs.mean()), float(ys.mean())
    edge_y = int(ys.min()) if mode == "top" else int(ys.max())
    xs_at_edge = xs[ys == edge_y]
    return float(xs_at_edge.mean()), float(edge_y)


def _effect_offset(spec: EffectSpec, t: float) -> tuple[float, float]:
    """Opacity (and, for shimmer, a small sideways drift) for one effect layer
    at time `t` (seconds, already includes the instance's own phase offset so
    several avatars with the same effect don't blink in unison)."""
    phase = (t / spec.period) % 1.0
    span = spec.max_opacity - spec.min_opacity
    if spec.effect == "sparkle":
        if phase >= spec.duty:
            return spec.min_opacity, 0.0
        triangle = 1.0 - abs(phase / spec.duty - 0.5) * 2
        return spec.min_opacity + span * triangle, 0.0
    if spec.effect == "shimmer":
        wave = 0.5 + 0.5 * math.sin(TWO_PI * phase)
        dx = spec.drift * math.sin(TWO_PI * phase * 2)
        return spec.min_opacity + span * wave, dx
    # "pulse" and "emit" (the emitting layer itself also breathes gently).
    wave = 0.5 + 0.5 * math.sin(TWO_PI * phase)
    return spec.min_opacity + span * wave, 0.0


@dataclass
class ModelPack:
    """Everything needed to draw one model: the manifest plus the pixmaps and
    auto-detected pivots derived from it. Several are kept loaded at once so
    the random-avatar mode can put different characters on stage side by side
    without reloading anything mid-animation."""
    model: AvatarModel
    pixmaps: dict[str, QPixmap]
    z_order: list[tuple[str, str]]
    sway_phase: dict[str, float]
    sway_pivot: dict[str, tuple[float, float]]
    sway_spec: dict[str, SwaySpec]
    bounce_pivot: dict[str, tuple[float, float]]
    effect_spec: dict[str, EffectSpec]
    effect_origin: dict[str, tuple[float, float]]

    @classmethod
    def build(cls, model: AvatarModel) -> "ModelPack":
        pixmaps = {
            filename: QPixmap(str(model.layer_path(filename)))
            for filename in model.all_filenames()
        }
        sway_pivot: dict[str, tuple[float, float]] = {}
        sway_spec: dict[str, SwaySpec] = {}
        for spec in model.sway:
            filename = spec.file
            if filename not in pixmaps:
                continue
            pivot = _sway_pivot(pixmaps[filename], spec.pivot)
            if pivot is not None:
                sway_pivot[filename] = pivot
                sway_spec[filename] = spec

        center_x = model.canvas_size[0] / 2
        bounce_pivot: dict[str, tuple[float, float]] = {}
        for filename in model.bounce_react_layers:
            pivot = _attachment_pivot(pixmaps[filename], center_x) if filename in pixmaps else None
            if pivot is not None:
                bounce_pivot[filename] = pivot

        effect_spec: dict[str, EffectSpec] = {}
        effect_origin: dict[str, tuple[float, float]] = {}
        for spec in model.effects:
            if spec.file not in pixmaps:
                continue
            effect_spec[spec.file] = spec
            origin = _sway_pivot(pixmaps[spec.file], "center")
            if origin is not None:
                effect_origin[spec.file] = origin

        return cls(
            model=model,
            pixmaps=pixmaps,
            z_order=model.build_z_order(),
            sway_phase={name: i * 0.9 for i, name in enumerate(sway_pivot)},
            sway_pivot=sway_pivot,
            sway_spec=sway_spec,
            bounce_pivot=bounce_pivot,
            effect_spec=effect_spec,
            effect_origin=effect_origin,
        )


def _attachment_pivot(pixmap: QPixmap, canvas_center_x: float) -> tuple[float, float] | None:
    """Where a bounce_react layer (e.g. an ear) is "attached": the opaque
    pixels closest to the canvas's horizontal center — a generic proxy for
    "the side facing the head", regardless of whether the layer sits on the
    left or right. None if the layer is fully transparent."""
    alpha = _to_alpha_array(pixmap)
    if alpha is None:
        return None
    ys, xs = np.where(alpha > ALPHA_THRESHOLD)
    if len(xs) == 0:
        return None
    distance_to_center = np.abs(xs.astype(np.float64) - canvas_center_x)
    nearest = distance_to_center <= (distance_to_center.min() + 3)  # small tolerance band
    return float(xs[nearest].mean()), float(ys[nearest].mean())


class OverlayWindow(QWidget):
    def __init__(
        self,
        model: AvatarModel,
        config: OverlayConfig,
        render_config: RenderConfig,
        bubble_config: BubbleConfig | None = None,
    ):
        super().__init__()
        self.model = model
        self.config = config
        self.render_config = render_config
        self.bubble_config = bubble_config if bubble_config is not None else BubbleConfig()
        self._bubble_pixmap: QPixmap | None = None
        self.reload_bubble_image()

        # name -> ModelPack. The active model is always present; the random
        # mode adds the rest lazily via set_available_models().
        self._packs: dict[str, ModelPack] = {model.name: ModelPack.build(model)}
        self.random_model = False
        self._drag_offset: QPoint | None = None
        self.stage = Stage(
            canvas_width=model.canvas_size[0],
            entrance_from_right=render_config.entrance_from_right,
            exit_speed=render_config.exit_speed,
            bubble_speed=self.bubble_config.appear_speed,
        )

        # Deliberately NOT Qt.WindowType.Tool: that sets WS_EX_TOOLWINDOW,
        # which OBS filters out of its Window Capture source list entirely —
        # the window becomes uncapturable, which defeats the whole point of
        # the app. A plain frameless window shows up in the list (and in the
        # taskbar/alt-tab, which is also how the user finds it again).
        base_flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(
            base_flags | Qt.WindowType.WindowStaysOnTopHint
            if render_config.always_on_top
            else base_flags
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowTitle(f"Vocari - {model.name}")

        self._apply_geometry()

        # -- procedural sway/bounce (cosmetic; gated by "Покачивание") -----
        self._sway_enabled = render_config.enable_sway
        self._sway_phase = 0.0
        self._idle_bob_phase = 0.0
        self._sway_layer_phase: dict[str, float] = {}
        self._sway_layer_pivot: dict[str, tuple[float, float]] = {}
        self._bounce_react_pivot: dict[str, tuple[float, float]] = {}
        # Free-running clock (seconds) for effect layers (pulse/shimmer/
        # sparkle/emit) — unlike _sway_phase this never wraps, since effect
        # periods can be much longer than the sway cycle.
        self._clock_s = 0.0
        self._recompute_sway_layers()

        # Runs continuously — 30 FPS repaint of a mostly-transparent widget
        # is cheap, and it's needed for the stage slide animation regardless
        # of whether cosmetic sway is on, so there's no real upside to
        # starting/stopping it.
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_animation_tick)
        self._anim_timer.start(ANIMATION_INTERVAL_MS)

    def set_model(self, model: AvatarModel) -> None:
        """Hot-swap the displayed model (used by the settings "Модель" tab
        after an import, so the overlay updates without restarting the app)."""
        self.model = model
        self._packs[model.name] = ModelPack.build(model)
        self.stage.set_canvas_width(model.canvas_size[0])
        self._apply_geometry()
        self.setWindowTitle(f"Vocari - {model.name}")
        self._recompute_sway_layers()
        self.update()

    def _recompute_sway_layers(self) -> None:
        """Pivots live on the ModelPack now; kept as a hook for callers that
        rebuild the active model in place."""
        self._packs[self.model.name] = ModelPack.build(self.model)

    # -- stage geometry ---------------------------------------------------

    def _stage_offset_px(self) -> int:
        """Screen-pixel distance from the window's left edge to the speaking
        slot (the stage's draw_origin_x, scaled) — depends on which side the
        entrance is on (see Stage.draw_origin_x)."""
        return round(self.stage.draw_origin_x * self.config.scale)

    def _bubble_side_margins(self) -> tuple[float, float]:
        """(left, right) canvas-space padding so a bubble wider than the
        avatar isn't clipped by the window edge. The queue corridor already
        provides room on the entrance side, so the margin only goes on the
        opposite side — which also means the window still grows away from
        config.pos_x rather than moving the avatar."""
        if not self.bubble_config.enabled:
            return 0.0, 0.0
        margin = self.model.canvas_size[0] * self.bubble_config.max_width_fraction
        return (margin, 0.0) if self.stage.entrance_from_right else (0.0, margin)

    def _bubble_headroom(self) -> float:
        """Extra canvas-space height above the avatars for the speech bubble.
        The window grows upward by this much and the avatars are drawn shifted
        down by it, so config.pos_x/pos_y keeps meaning "where the avatar
        stands" — adding a bubble must not move the avatar."""
        if not self.bubble_config.enabled:
            return 0.0
        return self.model.canvas_size[1] * BUBBLE_HEADROOM_FRACTION

    def _apply_geometry(self) -> None:
        """Resizes for the (fixed, worst-case-7) stage width and repositions
        so the *speaking slot* — not the window's own top-left — stays at
        config.pos_x/pos_y regardless of scale."""
        canvas_w, canvas_h = self.model.canvas_size
        left_margin, right_margin = self._bubble_side_margins()
        stage_w = left_margin + self.stage.stage_origin_x + canvas_w + right_margin
        headroom = self._bubble_headroom()
        self.resize(
            max(1, round(stage_w * self.config.scale)),
            max(1, round((canvas_h + headroom) * self.config.scale)),
        )
        self.move(
            self.config.pos_x - self._stage_offset_px() - round(left_margin * self.config.scale),
            self.config.pos_y - round(headroom * self.config.scale),
        )

    def set_scale(self, scale: float) -> None:
        """From Settings → Модель, as an alternative to the mouse wheel."""
        self.config.scale = max(MIN_SCALE, min(MAX_SCALE, scale))
        self._apply_geometry()

    def set_position(self, x: int, y: int) -> None:
        """From Settings → Модель, as an alternative to dragging the window.
        x/y here are the *speaking slot's* screen position, same meaning as
        config.pos_x/pos_y — not the window's own top-left."""
        self.config.pos_x = x
        self.config.pos_y = y
        self.move(x - self._stage_offset_px(), y)

    def set_always_on_top(self, enabled: bool) -> None:
        """Live-toggle from Settings → Рендер — lets a game/other app cover
        the avatar on the streamer's own screen; OBS Window Capture still
        grabs the window's contents by handle regardless of z-order."""
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.show()  # Qt requires re-showing after a window flag change

    def reload_bubble_image(self) -> None:
        """(Re)loads the user's own bubble artwork after they pick a file."""
        path = self.bubble_config.custom_image
        self._bubble_pixmap = QPixmap(path) if path else None

    def apply_bubble_settings(self) -> None:
        """Called after anything in the bubble tab changes — the headroom (and
        therefore the window size/position) depends on whether bubbles are on."""
        self.reload_bubble_image()
        self.stage.set_bubble_speed(self.bubble_config.appear_speed)
        self._apply_geometry()
        self.update()

    def set_bubble_shown(self, instance_id: int, shown: bool) -> None:
        self.stage.set_bubble_shown(instance_id, shown)
        self.update()

    def set_entrance_from_right(self, enabled: bool) -> None:
        """Live-toggle from Settings → Модель: queue/entrance/exit all move
        to the right side instead of the left. The speaking slot must stay
        put (config.pos_x/pos_y), so the window geometry is recomputed —
        the stage's draw_origin_x has moved to the other side."""
        self.stage.set_entrance_from_right(enabled)
        self._apply_geometry()
        self.update()

    # -- stage / speaker control (used by TTSQueue) ------------------------

    def _pack_for(self, inst: AvatarInstance | None) -> ModelPack:
        """The model an instance was created with — it keeps its own character
        for its whole time on stage even if the active model changes, and in
        random mode neighbours on stage are different characters entirely."""
        if inst is not None and inst.model_name in self._packs:
            return self._packs[inst.model_name]
        return self._packs[self.model.name]

    def set_available_models(self, models: list[AvatarModel]) -> None:
        """Preloads every model that random mode may pick from."""
        for model in models:
            if model.name not in self._packs:
                self._packs[model.name] = ModelPack.build(model)

    def set_random_model(self, enabled: bool) -> None:
        self.random_model = enabled

    def _pick_model_name(self) -> str:
        if self.random_model and len(self._packs) > 1:
            return random.choice(list(self._packs))
        return self.model.name

    def show_bubble_preview(self, text: str, author: str) -> None:
        """Parks a non-speaking avatar with its bubble up so the bubble
        settings can be tweaked against the real overlay. Replaces whatever
        preview was already there rather than stacking them up."""
        self.hide_bubble_preview()
        inst = self.stage.add(text, author, preview=True, model_name=self._pick_model_name())
        if inst is not None:
            self._schedule_next_blink(inst.id)
        self.update()

    def hide_bubble_preview(self) -> None:
        for inst in list(self.stage.instances):
            if inst.is_preview:
                self.stage.retire(inst.id)
        self.update()

    def update_preview_message(self, text: str, author: str) -> None:
        """Live-edits the text/nick of a preview that's already on stage."""
        for inst in self.stage.instances:
            if inst.is_preview:
                inst.text, inst.author = text, author
        self.update()

    def has_bubble_preview(self) -> bool:
        return any(i.is_preview and i.phase != "exiting" for i in self.stage.instances)

    def add_speaker(self, text: str, author: str = "") -> AvatarInstance | None:
        """Requests a new avatar instance for `text`; it immediately claims
        a stage slot (speaking if free, else the next waiting slot) and
        starts sliding in from off-screen, or returns None if all 7 slots
        are taken (caller should keep `text` in its own backlog)."""
        inst = self.stage.add(text, author, model_name=self._pick_model_name())
        if inst is not None:
            self._schedule_next_blink(inst.id)
        self.update()
        return inst

    def retire_speaker(self, instance_id: int) -> None:
        """Always the same: mirror + slide off-screen-left, then remove —
        called once playback finishes (see Stage.retire's docstring for why
        there's no "stay put if nobody's queued" branch)."""
        self.stage.retire(instance_id)
        self.update()

    def set_speaker_mouth(self, instance_id: int, is_open: bool) -> None:
        self.stage.set_mouth(instance_id, is_open)
        self.update()

    def set_speaker_talking(self, instance_id: int, talking: bool) -> None:
        self.stage.set_talking(instance_id, talking)
        self.update()

    def set_speaker_bounce_level(self, instance_id: int, level: float) -> None:
        self.stage.set_bounce_level(instance_id, level)
        self.update()

    # -- blinking (independent schedule per instance, so simultaneous ------
    # avatars don't all blink in lockstep)

    def _schedule_next_blink(self, instance_id: int) -> None:
        inst = self.stage.get(instance_id)
        model = self._pack_for(inst).model if inst is not None else self.model
        if "eyes" not in model.states:
            return
        delay_ms = random.randint(BLINK_MIN_INTERVAL_MS, BLINK_MAX_INTERVAL_MS)
        QTimer.singleShot(delay_ms, lambda: self._start_blink(instance_id))

    def _start_blink(self, instance_id: int) -> None:
        inst = self.stage.get(instance_id)
        if inst is None:
            return  # exited before its next blink came due
        inst.active_frame["eyes"] = "closed"
        self.update()
        QTimer.singleShot(BLINK_CLOSED_DURATION_MS, lambda: self._end_blink(instance_id))

    def _end_blink(self, instance_id: int) -> None:
        inst = self.stage.get(instance_id)
        if inst is None:
            return
        inst.active_frame["eyes"] = "open"
        self.update()
        self._schedule_next_blink(instance_id)

    # -- procedural sway / talk bounce -----------------------------------------

    def set_sway_enabled(self, enabled: bool) -> None:
        """Live-toggle from Settings → Рендер → "Покачивание"."""
        self._sway_enabled = enabled
        self.update()

    def _instance_bounce_offset(self, inst: AvatarInstance) -> float:
        if not self._sway_enabled:
            return 0.0
        # Subtle always-on idle bob (breathing-like), for anyone currently on
        # stage, plus — only for the current speaker — an upward hop scaled
        # by how loud/sharp the audio is, not a fixed-rate oscillation. Each
        # instance adds its own random phase offset so several avatars on
        # stage at once don't bob in lockstep.
        offset = IDLE_BOB_AMPLITUDE_PX * math.sin(self._idle_bob_phase + inst.motion_phase_offset)
        if inst.phase == "speaking" and inst.bounce_level > 0.0:
            offset += -inst.bounce_level * BOUNCE_AMPLITUDE_PX
        return offset

    def _on_animation_tick(self) -> None:
        self.stage.tick()  # entrance/exit/promotion — independent of "Покачивание"
        self._clock_s += ANIMATION_INTERVAL_MS / 1000  # drives effect layers; never gated on sway

        if self._sway_enabled:
            self._sway_phase = (self._sway_phase + SWAY_PHASE_STEP) % TWO_PI
            self._idle_bob_phase = (self._idle_bob_phase + IDLE_BOB_PHASE_STEP) % TWO_PI

            for inst in self.stage.instances:
                pack = self._pack_for(inst)
                if pack.bounce_pivot:
                    target_angle = BOUNCE_REACT_DEG_PER_PX * self._instance_bounce_offset(inst)
                    for filename in pack.bounce_pivot:
                        current = inst.bounce_react_angle.get(filename, 0.0)
                        inst.bounce_react_angle[filename] = (
                            current + (target_angle - current) * BOUNCE_REACT_LAG_COEFF
                        )
                if pack.model.eye_dart:
                    self._update_eye_dart(inst, pack)

        self.update()

    def _update_eye_dart(self, inst: AvatarInstance, pack: "ModelPack") -> None:
        """Nudges the whole eye layer a few pixels toward a randomly-picked
        glance target, holding it there for a bit before rolling a new one —
        a wandering gaze instead of a fixed stare. Cheap: it only shifts where
        the already-drawn eye pixmap is painted, no extra art needed."""
        eye_h = None
        eyes_group = pack.model.states.get("eyes")
        if eyes_group is not None:
            sample = next(iter(eyes_group.frames.values()), None)
            pixmap = pack.pixmaps.get(sample) if sample else None
            if pixmap is not None:
                eye_h = pixmap.height()
        amplitude = (eye_h or pack.model.canvas_size[1] * 0.1) * 0.05

        inst.eye_look_hold_s -= ANIMATION_INTERVAL_MS / 1000
        if inst.eye_look_hold_s <= 0:
            inst.eye_look_target = (
                random.uniform(-amplitude, amplitude),
                random.uniform(-amplitude * 0.5, amplitude * 0.5),
            )
            inst.eye_look_hold_s = random.uniform(0.8, 2.6)

        cur_x, cur_y = inst.eye_look
        tgt_x, tgt_y = inst.eye_look_target
        inst.eye_look = (cur_x + (tgt_x - cur_x) * 0.12, cur_y + (tgt_y - cur_y) * 0.12)

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
            left_margin, right_margin = self._bubble_side_margins()
            stage_w = left_margin + self.stage.stage_origin_x + canvas_w + right_margin
            headroom = self._bubble_headroom()
            stage_h = canvas_h + headroom
            if self.width() and self.height():
                painter.scale(self.width() / stage_w, self.height() / stage_h)
            # Shift into the stage's own coordinates: bubbles get headroom
            # above and a side margin on the non-corridor side.
            painter.translate(left_margin, headroom)

            for inst in self.stage.instances:
                self._paint_instance(painter, inst, canvas_w)
            # Bubbles last, so one never ends up behind a neighbouring avatar.
            for inst in self.stage.instances:
                self._paint_bubble(painter, inst, canvas_w, canvas_h)
        finally:
            painter.end()

    def _paint_bubble(self, painter: QPainter, inst: AvatarInstance, canvas_w: int, canvas_h: int) -> None:
        config = self.bubble_config
        if not config.enabled or inst.bubble_progress <= 0.01 or not inst.text:
            return

        layout = bubble.measure(config, self.model.canvas_size, inst.author, inst.text)
        slot_scale = self.stage.slot_scale(inst.slot)
        avatar_left = self.stage.draw_origin_x + inst.x_offset + canvas_w * (1 - slot_scale) / 2
        avatar_width = canvas_w * slot_scale
        avatar_top = canvas_h * (1 - slot_scale)

        # Anchor per the configured position, then apply the user's nudge.
        if config.position == "left":
            x = avatar_left - layout.width - 20
            y = avatar_top + 40
        elif config.position == "right":
            x = avatar_left + avatar_width + 20
            y = avatar_top + 40
        elif config.position == "top-left":
            x = avatar_left - layout.width * 0.55
            y = avatar_top - layout.height - bubble.TAIL_HEIGHT
        elif config.position == "top-right":
            x = avatar_left + avatar_width - layout.width * 0.45
            y = avatar_top - layout.height - bubble.TAIL_HEIGHT
        else:  # "top"
            x = avatar_left + (avatar_width - layout.width) / 2
            y = avatar_top - layout.height - bubble.TAIL_HEIGHT
        x += config.offset_x
        y += config.offset_y

        avatar_center_x = avatar_left + avatar_width / 2
        tail_at = avatar_center_x if config.position.startswith("top") else None

        painter.save()
        # Pop in/out from the side nearest the avatar, so it grows out of the
        # character rather than materialising in mid-air.
        progress = inst.bubble_progress
        pivot_x, pivot_y = avatar_center_x, y + layout.height
        painter.translate(pivot_x, pivot_y)
        painter.scale(progress * config.scale, progress * config.scale)
        painter.translate(-pivot_x, -pivot_y)
        painter.setOpacity(min(1.0, progress * 1.4))

        bubble.paint(
            painter, config, layout, QPointF(x, y), inst.author, inst.text, tail_at,
            self._bubble_pixmap,
        )
        painter.restore()

    def _paint_instance(self, painter: QPainter, inst: AvatarInstance, canvas_w: int) -> None:
        painter.save()
        painter.translate(self.stage.draw_origin_x + inst.x_offset, 0)

        # Perspective shrink for anyone further back in the queue, anchored
        # to the bottom center so the whole queue keeps standing on the same
        # floor line instead of shrinking toward the canvas's top-left.
        slot_scale = self.stage.slot_scale(inst.slot)
        if slot_scale != 1.0:
            canvas_h = self.model.canvas_size[1]
            painter.translate(canvas_w * (1 - slot_scale) / 2, canvas_h * (1 - slot_scale))
            painter.scale(slot_scale, slot_scale)

        if inst.mirrored:
            painter.translate(canvas_w, 0)
            painter.scale(-1, 1)

        bounce_offset = self._instance_bounce_offset(inst)

        pack = self._pack_for(inst)
        for kind, ref in pack.z_order:
            pixmap = self._resolve_layer(pack, kind, ref, inst.active_frame)
            if pixmap is None or pixmap.isNull():
                continue
            y_offset = bounce_offset
            x_offset = 0.0

            # Wandering gaze: shifts the whole eye pixmap by a few px instead
            # of needing separate iris art — see _update_eye_dart().
            if kind == "state" and ref == "eyes" and self._sway_enabled and pack.model.eye_dart:
                x_offset += inst.eye_look[0]
                y_offset += inst.eye_look[1]

            sway_pivot = pack.sway_pivot.get(ref) if (self._sway_enabled and kind == "layer") else None
            react_pivot = pack.bounce_pivot.get(ref) if (self._sway_enabled and kind == "layer") else None
            if sway_pivot is not None:
                spec = pack.sway_spec.get(ref)
                degrees = spec.degrees if (spec and spec.degrees is not None) else SWAY_ROTATION_DEG
                period = spec.period if (spec and spec.period is not None) else SWAY_PERIOD_S
                angle = degrees * math.sin(
                    TWO_PI * self._clock_s / period + pack.sway_phase[ref] + inst.motion_phase_offset
                )
            elif react_pivot is not None:
                angle = inst.bounce_react_angle.get(ref, 0.0)
            else:
                angle = None

            pivot = sway_pivot if sway_pivot is not None else react_pivot

            effect_spec = pack.effect_spec.get(ref) if kind == "layer" else None
            opacity = 1.0
            if effect_spec is not None:
                opacity, extra_dx = _effect_offset(effect_spec, self._clock_s + inst.motion_phase_offset)
                x_offset += extra_dx
                if opacity <= 0.003:
                    continue

            if pivot is not None:
                # Rotate around (pivot_x, pivot_y) in the pixmap's own
                # coordinates, then shift the whole result by (x_offset,
                # y_offset) — i.e. translate to the (offset) pivot, rotate,
                # then translate back by the *unshifted* pivot so the offset
                # isn't applied twice.
                painter.save()
                if opacity != 1.0:
                    painter.setOpacity(opacity)
                painter.translate(pivot[0] + x_offset, pivot[1] + y_offset)
                painter.rotate(angle)
                painter.translate(-pivot[0], -pivot[1])
                painter.drawPixmap(0, 0, pixmap)
                painter.restore()
            elif opacity != 1.0:
                painter.save()
                painter.setOpacity(opacity)
                painter.drawPixmap(round(x_offset), round(y_offset), pixmap)
                painter.restore()
            else:
                painter.drawPixmap(round(x_offset), round(y_offset), pixmap)

            if effect_spec is not None and effect_spec.effect in ("emit", "drip"):
                self._paint_effect_echoes(painter, pack, ref, pixmap, effect_spec,
                                          self._clock_s + inst.motion_phase_offset)

        painter.restore()

    def _paint_effect_echoes(self, painter: QPainter, pack: "ModelPack", ref: str,
                             pixmap: QPixmap, spec: "EffectSpec", t: float) -> None:
        """Repeating echoes of the source pixmap, evenly spaced across one
        period so they read as a continuous stream rather than one instance
        popping in and out.

        "emit" grows the echo outward from its own center and fades it —
        a radio-wave / radar-ping look, e.g. a signal spreading from an
        antenna tip. "drip" instead slides the echo straight down while
        fading, e.g. a droplet detaching and falling from a drool strand."""
        origin = pack.effect_origin.get(ref)
        if origin is None:
            return
        ox, oy = origin
        canvas_h = pack.model.canvas_size[1]
        for i in range(spec.copies):
            phase = ((t / spec.period) + i / spec.copies) % 1.0
            fade = max(0.0, 1.0 - phase) * spec.max_opacity
            if fade <= 0.01:
                continue
            painter.save()
            painter.setOpacity(fade)
            if spec.effect == "emit":
                grow = 1.0 + phase * spec.spread * 6
                painter.translate(ox, oy)
                painter.scale(grow, grow)
                painter.translate(-ox, -oy)
            else:  # drip
                painter.translate(0, phase * spec.spread * canvas_h)
                shrink = 1.0 - phase * 0.35
                painter.translate(ox, oy)
                painter.scale(shrink, shrink)
                painter.translate(-ox, -oy)
            painter.drawPixmap(0, 0, pixmap)
            painter.restore()

    def _resolve_layer(self, pack: ModelPack, kind: str, ref: str,
                       active_frame: dict[str, str]) -> QPixmap | None:
        if kind == "layer":
            return pack.pixmaps.get(ref)
        group = pack.model.states[ref]
        frame_name = active_frame.get(ref, next(iter(group.frames)))
        filename = group.frames.get(frame_name)
        return pack.pixmaps.get(filename) if filename else None

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
        self._apply_geometry()
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
        self.config.pos_x = self.x() + self._stage_offset_px()
        self.config.pos_y = self.y()
