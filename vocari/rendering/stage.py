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

MAX_WAITING_SLOTS = 6  # + 1 speaking slot = 7 on stage at once, per spec
SLOT_SPACING_FRACTION = 0.5  # each waiting slot, as a fraction of canvas width, left of the previous
ENTRY_BUFFER_FRACTION = 0.35  # extra off-screen room so entrances/exits don't teleport into view
APPROACH_LAG_COEFF = 0.33  # per-tick fraction of the remaining distance closed (lower = slower/floatier)
ARRIVAL_EPSILON_PX = 2.0
POST_SPEECH_HOLD_MS = 500

_id_counter = itertools.count(1)


@dataclass
class AvatarInstance:
    id: int
    text: str
    x_offset: float  # current position, canvas-relative px, 0 == speaking slot
    target_x_offset: float
    slot: int  # 0 (speaking) .. MAX_WAITING_SLOTS, purely for bookkeeping which waiting spot is "claimed"
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


class Stage:
    def __init__(self, canvas_width: int, entrance_from_right: bool = False):
        self.instances: list[AvatarInstance] = []
        self._occupied_slots: set[int] = set()
        self._on_speaker_ready: Callable[[int], None] | None = None
        self._on_slot_freed: Callable[[], None] | None = None
        # Which side the queue/entrance/exit corridor is on — everyone jumps
        # in and back out on the same side, so this one flag mirrors the
        # whole layout (see _sign/_base_mirrored) rather than being a
        # per-instance choice.
        self.entrance_from_right = entrance_from_right
        self.set_canvas_width(canvas_width)

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
        self.stage_origin_x = MAX_WAITING_SLOTS * self.slot_spacing + self.entry_buffer
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

    def _next_free_slot(self) -> int | None:
        for slot in range(MAX_WAITING_SLOTS + 1):
            if slot not in self._occupied_slots:
                return slot
        return None

    def add(self, text: str) -> AvatarInstance | None:
        """Creates and places a new instance if a stage slot (0..6) is free;
        returns None if the stage is already full (caller keeps the text in
        its own backlog and retries via the on_slot_freed callback)."""
        slot = self._next_free_slot()
        if slot is None:
            return None
        instance = AvatarInstance(
            id=next(_id_counter),
            text=text,
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

    def retire(self, instance_id: int) -> None:
        """Always the same: mirror and slide off toward the entrance side,
        then remove. Called POST_SPEECH_HOLD_MS after playback finishes (or
        immediately, if the skip hotkey cut it short) — see TTSQueue for the
        actual timer, this just does the animation part.

        Mirrors to the *opposite* of _base_mirrored: entering/speaking used
        whichever orientation matches the entrance-side travel direction, so
        leaving — which travels the same corridor in reverse — needs the
        other one."""
        inst = self.get(instance_id)
        if inst is None:
            return
        inst.mirrored = not self._base_mirrored
        inst.phase = "exiting"
        inst.target_x_offset = self._exit_x_offset

    def _promote_next(self) -> None:
        if 0 in self._occupied_slots:
            return
        waiting = [inst for inst in self.instances if inst.slot == 1]
        if not waiting:
            return
        inst = waiting[0]
        self._occupied_slots.discard(1)
        inst.slot = 0
        self._occupied_slots.add(0)
        inst.target_x_offset = self._slot_x_offset(0)
        inst.phase = "entering"  # re-arms speaker_ready once it arrives at slot 0

    def tick(self) -> None:
        finished_exit_ids = []
        for inst in self.instances:
            if abs(inst.target_x_offset - inst.x_offset) >= ARRIVAL_EPSILON_PX:
                inst.x_offset += (inst.target_x_offset - inst.x_offset) * APPROACH_LAG_COEFF
                continue
            inst.x_offset = inst.target_x_offset
            if inst.phase == "entering":
                if inst.slot == 0:
                    inst.phase = "speaking"
                    if self._on_speaker_ready:
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
