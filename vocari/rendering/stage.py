"""Manages the "stage": zero or more AvatarInstance sprites that jump in from
off-screen left to speak, hold for a beat, then mirror and jump back out —
plus a queue of up to 6 waiting instances that visually stack up while
someone else is talking.

This is deliberately independent of Qt threading concerns (no QThread/QObject
signal here) — OverlayWindow owns the QTimer tick and calls into this, and
TTSQueue is told via a plain callback when an instance is ready to be spoken
(has finished sliding into the speaking slot) or when a slot frees up.
"""
from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Callable

# Stage layout, front to back:
#   slot 0            the speaker
#   slot 1            deliberately left empty — a visual gap that sets the
#                     speaker apart from everyone waiting
#   slots 2..7        the queue itself, packed with no holes
# The queue always closes up: when the speaker leaves, the front waiter takes
# slot 0 and everybody behind shuffles one step forward, so the only gap on
# stage is ever the fixed one at slot 1.
SPEAKER_SLOT = 0
FIRST_WAITING_SLOT = 2
MAX_WAITING = 6  # + the speaker = 7 avatars visible at once, per spec
LAST_SLOT = FIRST_WAITING_SLOT + MAX_WAITING - 1

SLOT_SPACING_FRACTION = 0.5  # each slot, as a fraction of canvas width, behind the previous
ENTRY_BUFFER_FRACTION = 0.35  # extra off-screen room so entrances/exits don't teleport into view
APPROACH_LAG_COEFF = 0.33  # per-tick fraction of the remaining distance closed (lower = slower/floatier)
ARRIVAL_EPSILON_PX = 2.0

# Perspective: the speaker is "closest" at full size, the first waiter is
# 90%, and each spot further back drops another 5% — so an avatar visibly
# grows as it advances up the queue.
SPEAKER_SCALE = 1.0
FIRST_WAITING_SCALE = 0.90
WAITING_SCALE_STEP = 0.05

# Exit speed is exposed to the user as an absolute 1..100 dial rather than a
# lag coefficient: 1 crawls off, 100 vanishes in a single tick.
MIN_EXIT_SPEED = 1
MAX_EXIT_SPEED = 100


def exit_speed_to_coeff(speed: int) -> float:
    """Maps the settings dial (1..100) to a per-tick approach fraction."""
    return max(MIN_EXIT_SPEED, min(MAX_EXIT_SPEED, speed)) / 100.0

_id_counter = itertools.count(1)


@dataclass
class AvatarInstance:
    id: int
    text: str
    x_offset: float  # current position, canvas-relative px, 0 == speaking slot
    target_x_offset: float
    slot: int  # SPEAKER_SLOT, or FIRST_WAITING_SLOT..LAST_SLOT for a queued one
    author: str = ""  # who sent the message, shown in the speech bubble
    model_name: str = ""  # which avatar model draws this one (random mode mixes them)
    # A live preview from the settings window: it parks in the speaking slot
    # with its bubble up and stays there (no synthesis, no auto-exit) so the
    # bubble settings can be adjusted against the real thing.
    is_preview: bool = False
    # 0 = no bubble, 1 = fully popped in; animated by tick() so the bubble
    # scales in and back out instead of blinking on and off.
    bubble_progress: float = 0.0
    bubble_shown: bool = False
    mirrored: bool = False
    phase: str = "entering"  # entering | speaking | waiting | exiting
    active_frame: dict[str, str] = field(default_factory=lambda: {"eyes": "open", "mouth": "closed"})
    talking: bool = False
    bounce_level: float = 0.0
    bounce_react_angle: dict[str, float] = field(default_factory=dict)
    # Random per-instance offset added to the shared sway/idle-bob clocks so
    # multiple avatars on stage at once don't all breathe/sway in lockstep —
    # each rolls its own offset when created, independent of how many others
    # are around.
    motion_phase_offset: float = field(default_factory=lambda: random.uniform(0.0, 2 * math.pi))
    # Wandering gaze (see AvatarModel.gaze_layer): current/target offset applied
    # to the whole eye layer, plus a countdown to the next glance so each
    # instance drifts on its own schedule instead of in lockstep.
    eye_look: tuple[float, float] = (0.0, 0.0)
    eye_look_target: tuple[float, float] = (0.0, 0.0)
    eye_look_hold_s: float = field(default_factory=lambda: random.uniform(0.6, 2.2))


class Stage:
    def __init__(
        self,
        canvas_width: int,
        entrance_from_right: bool = False,
        exit_speed: int = 33,
        bubble_speed: int = 50,
    ):
        self.instances: list[AvatarInstance] = []
        self._occupied_slots: set[int] = set()
        self._on_speaker_ready: Callable[[int], None] | None = None
        self._on_slot_freed: Callable[[], None] | None = None
        # Which side the queue/entrance/exit corridor is on — everyone jumps
        # in and back out on the same side, so this one flag mirrors the
        # whole layout (see _sign/_base_mirrored) rather than being a
        # per-instance choice.
        self.entrance_from_right = entrance_from_right
        self.exit_lag_coeff = exit_speed_to_coeff(exit_speed)
        self.bubble_lag_coeff = exit_speed_to_coeff(bubble_speed)
        self.set_canvas_width(canvas_width)

    def set_exit_speed(self, speed: int) -> None:
        """Live-settable from Settings → Модель (1..100 dial)."""
        self.exit_lag_coeff = exit_speed_to_coeff(speed)

    @property
    def _sign(self) -> float:
        return 1.0 if self.entrance_from_right else -1.0

    @property
    def _base_mirrored(self) -> bool:
        """Orientation while entering/waiting/speaking. Left-side (default)
        entrances move left-to-right, so the unmirrored art (assumed to face
        right) already looks correct; right-side entrances move right-to-
        left, so they need the mirrored art instead — see retire()'s docstring
        for why exiting always uses the opposite of this."""
        return self.entrance_from_right

    @property
    def draw_origin_x(self) -> float:
        """Model-space X where the speaking slot (x_offset=0) is drawn — the
        runway for the queue/off-screen corridor sits on whichever side of
        this point entrance_from_right selects. OverlayWindow uses this (not
        stage_origin_x) to keep the speaking slot pinned at the user's
        configured screen position regardless of side."""
        return 0.0 if self.entrance_from_right else self.stage_origin_x

    def set_entrance_from_right(self, enabled: bool) -> None:
        """A live toggle (Settings -> Модель), not something that happens as
        part of the normal per-tick animation — so instead of trying to
        smoothly re-route whoever's already on stage through the new
        corridor, just snap them straight to where they belong under the new
        side. Without this they'd keep their old x_offset/target/mirrored,
        computed under the old sign, which draw_origin_x (now flipped) would
        render at the wrong spot entirely."""
        self.entrance_from_right = enabled
        self.set_canvas_width(self.canvas_width)  # recompute _exit_x_offset's sign
        for inst in self.instances:
            if inst.phase == "exiting":
                inst.x_offset = self._exit_x_offset
                inst.target_x_offset = self._exit_x_offset
                inst.mirrored = not self._base_mirrored
            else:
                inst.target_x_offset = self._slot_x_offset(inst.slot)
                inst.x_offset = inst.target_x_offset
                inst.mirrored = self._base_mirrored

    def set_canvas_width(self, canvas_width: int) -> None:
        self.canvas_width = canvas_width
        self.slot_spacing = canvas_width * SLOT_SPACING_FRACTION
        self.entry_buffer = canvas_width * ENTRY_BUFFER_FRACTION
        # How far the window needs to extend beyond the speaking slot (on the
        # entrance side) to show every waiting slot plus a buffer for
        # off-screen entry/exit.
        self.stage_origin_x = LAST_SLOT * self.slot_spacing + self.entry_buffer
        self._exit_x_offset = self._sign * (self.stage_origin_x + canvas_width + 50)

    def on_speaker_ready(self, callback: Callable[[int], None]) -> None:
        """callback(instance_id) fires once that instance finishes sliding
        into the speaking slot — the cue to start TTS synthesis for it."""
        self._on_speaker_ready = callback

    def on_slot_freed(self, callback: Callable[[], None]) -> None:
        """callback() fires whenever an instance finishes exiting — the cue
        for the caller to try moving a backlogged message onto the stage."""
        self._on_slot_freed = callback

    def _slot_x_offset(self, slot: int) -> float:
        return self._sign * slot * self.slot_spacing

    def slot_scale(self, slot: int) -> float:
        """Draw scale for a slot — see SPEAKER_SCALE/FIRST_WAITING_SCALE."""
        if slot <= SPEAKER_SLOT:
            return SPEAKER_SCALE
        position = max(0, slot - FIRST_WAITING_SLOT)
        return max(0.1, FIRST_WAITING_SCALE - WAITING_SCALE_STEP * position)

    def _waiting_instances(self) -> list[AvatarInstance]:
        """Everyone queued behind the speaker, front-most first."""
        return sorted(
            (i for i in self.instances if i.phase != "exiting" and i.slot != SPEAKER_SLOT),
            key=lambda i: i.slot,
        )

    def _next_queue_slot(self) -> int | None:
        """Where a newly-arrived message joins: the back of the queue, which
        is always packed — so this is simply "one past however many are
        already waiting", never a numerically-free hole."""
        waiting = self._waiting_instances()
        if SPEAKER_SLOT not in self._occupied_slots and not waiting:
            return SPEAKER_SLOT
        slot = FIRST_WAITING_SLOT + len(waiting)
        return slot if slot <= LAST_SLOT else None

    def add(self, text: str, author: str = "", preview: bool = False,
            model_name: str = "") -> AvatarInstance | None:
        """Creates and places a new instance at the back of the queue;
        returns None if the stage is full (caller keeps the text in its own
        backlog and retries via the on_slot_freed callback)."""
        slot = self._next_queue_slot()
        if slot is None:
            return None
        instance = AvatarInstance(
            id=next(_id_counter),
            text=text,
            author=author,
            model_name=model_name,
            is_preview=preview,
            x_offset=self._exit_x_offset,
            target_x_offset=self._slot_x_offset(slot),
            slot=slot,
            mirrored=self._base_mirrored,
            phase="entering",
        )
        self._occupied_slots.add(slot)
        self.instances.append(instance)
        return instance

    def get(self, instance_id: int) -> AvatarInstance | None:
        return next((inst for inst in self.instances if inst.id == instance_id), None)

    def set_mouth(self, instance_id: int, is_open: bool) -> None:
        inst = self.get(instance_id)
        if inst is not None:
            inst.active_frame["mouth"] = "open" if is_open else "closed"

    def set_talking(self, instance_id: int, talking: bool) -> None:
        inst = self.get(instance_id)
        if inst is not None:
            inst.talking = talking

    def set_bounce_level(self, instance_id: int, level: float) -> None:
        inst = self.get(instance_id)
        if inst is not None:
            inst.bounce_level = max(0.0, min(1.0, level))

    def set_bubble_shown(self, instance_id: int, shown: bool) -> None:
        """Speech bubble on/off for one instance. tick() animates the actual
        pop in/out, so callers just flip the flag at the right moment (see
        TTSQueue: on when the line starts, off before the avatar leaves)."""
        inst = self.get(instance_id)
        if inst is not None:
            inst.bubble_shown = shown

    def set_bubble_speed(self, speed: int) -> None:
        self.bubble_lag_coeff = exit_speed_to_coeff(speed)

    def retire(self, instance_id: int) -> None:
        """Always the same: mirror and slide off toward the entrance side,
        then remove. Called POST_SPEECH_HOLD_MS after playback finishes (or
        immediately, if the skip hotkey cut it short) — see TTSQueue for the
        actual timer, this just does the animation part.

        Mirrors to the *opposite* of _base_mirrored: entering/speaking used
        whichever orientation matches the entrance-side travel direction, so
        leaving — which travels the same corridor in reverse — needs the
        other one.

        If this was the speaker, the next waiter is promoted right away
        instead of waiting for this one to finish sliding fully off-screen —
        so the handoff overlaps (next one advancing while this one leaves)
        instead of running back-to-back, which used to add a second silent,
        motionless stretch (~exit duration) on top of whatever synthesis
        latency the promoted speaker already needs before it can talk."""
        inst = self.get(instance_id)
        if inst is None:
            return
        inst.mirrored = not self._base_mirrored
        inst.phase = "exiting"
        inst.target_x_offset = self._exit_x_offset

        if inst.slot == SPEAKER_SLOT:
            self._occupied_slots.discard(SPEAKER_SLOT)
            self._promote_next()
            if self._on_slot_freed:
                self._on_slot_freed()

    def _promote_next(self) -> None:
        """The whole queue steps forward: the front waiter takes the speaking
        slot and everyone behind closes up one place (which is also what makes
        them grow a little — see slot_scale). Re-packing from scratch rather
        than nudging individual slots keeps the queue hole-free no matter what
        happened before (skips, failed synthesis, a live side-toggle)."""
        if SPEAKER_SLOT in self._occupied_slots:
            return
        waiting = self._waiting_instances()
        if not waiting:
            return

        front, rest = waiting[0], waiting[1:]
        self._occupied_slots = {SPEAKER_SLOT}
        front.slot = SPEAKER_SLOT
        front.target_x_offset = self._slot_x_offset(SPEAKER_SLOT)
        front.phase = "entering"  # re-arms speaker_ready once it arrives

        for index, inst in enumerate(rest):
            inst.slot = FIRST_WAITING_SLOT + index
            inst.target_x_offset = self._slot_x_offset(inst.slot)
            self._occupied_slots.add(inst.slot)

    def tick(self) -> None:
        finished_exit_ids = []
        for inst in self.instances:
            target_progress = 1.0 if inst.bubble_shown and inst.phase != "exiting" else 0.0
            inst.bubble_progress += (target_progress - inst.bubble_progress) * self.bubble_lag_coeff
            if abs(target_progress - inst.bubble_progress) < 0.01:
                inst.bubble_progress = target_progress

            if abs(inst.target_x_offset - inst.x_offset) >= ARRIVAL_EPSILON_PX:
                # Leaving uses the user's own speed dial; arriving keeps the
                # fixed pace, since that one doubles as the window that hides
                # synthesis latency.
                coeff = self.exit_lag_coeff if inst.phase == "exiting" else APPROACH_LAG_COEFF
                inst.x_offset += (inst.target_x_offset - inst.x_offset) * coeff
                continue
            inst.x_offset = inst.target_x_offset
            if inst.phase == "entering":
                if inst.slot == 0:
                    inst.phase = "speaking"
                    if inst.is_preview:
                        inst.bubble_shown = True  # and no synthesis, it just waits
                    elif self._on_speaker_ready:
                        self._on_speaker_ready(inst.id)
                else:
                    inst.phase = "waiting"
            elif inst.phase == "exiting":
                finished_exit_ids.append(inst.id)

        if finished_exit_ids:
            for instance_id in finished_exit_ids:
                inst = self.get(instance_id)
                if inst is not None:
                    self._occupied_slots.discard(inst.slot)
                    self.instances.remove(inst)
            self._promote_next()
            if self._on_slot_freed:
                self._on_slot_freed()

    def has_speaker(self) -> bool:
        return 0 in self._occupied_slots
