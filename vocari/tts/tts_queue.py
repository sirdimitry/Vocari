"""Bridges chat/test requests to the stage (vocari/rendering/stage.py) and
the actual TTS synthesis+playback. A message doesn't get synthesized the
instant it arrives — only once its avatar instance has finished sliding into
the speaking slot (Stage's speaker_ready callback) — so the jump-in
animation naturally covers the synthesis/model-load latency instead of a
separate fixed delay. Exactly one thing plays at a time by construction:
Stage only ever promotes the next waiter after the current speaker has
fully exited, so speaker_ready can't fire for two instances concurrently.
"""
from __future__ import annotations

import time
from collections import deque

from PySide6.QtCore import QObject, QThread, QTimer

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.rendering.overlay_window import OverlayWindow
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.tts.registry import get_active_provider
from vocari.tts.service import pick_voice
from vocari.tts.synthesis_worker import SynthesisWorker

logger = get_logger("tts.queue")


class TTSQueue(QObject):
    def __init__(
        self,
        config: AppConfig,
        providers: dict[str, TTSProvider],
        audio_player: AudioPlayer,
        window: OverlayWindow,
    ):
        super().__init__()
        self.config = config
        self.providers = providers
        self.audio_player = audio_player
        self.window = window

        # Messages that arrived while all 7 stage slots were taken — tried
        # again (via add_speaker) whenever a slot frees up.
        self._backlog: deque[str] = deque()
        self._thread: QThread | None = None
        self._worker: SynthesisWorker | None = None
        self._pending_instance_id = 0
        # When the current speaker arrived in the slot — the pre-speech pause
        # is measured from here, so slow synthesis eats into it instead of
        # adding on top of it.
        self._speaker_arrived_at = 0.0
        self._deferred_timers: list[QTimer] = []

        window.stage.on_speaker_ready(self._on_speaker_ready)
        window.stage.on_slot_freed(self._on_slot_freed)

    def _defer(self, delay_ms: int, callback) -> None:
        """QTimer.singleShot that can be cancelled by skip_current()."""
        timer = QTimer(self)
        timer.setSingleShot(True)

        def fire() -> None:
            self._deferred_timers.remove(timer)
            callback()

        timer.timeout.connect(fire)
        self._deferred_timers.append(timer)
        timer.start(delay_ms)

    def _cancel_deferred(self) -> None:
        for timer in self._deferred_timers:
            timer.stop()
        self._deferred_timers.clear()

    def skip_current(self) -> None:
        """Skip hotkey: drop whatever the current speaker is doing — talking
        mid-word, waiting on synthesis, or still sliding in — and send it
        straight off stage with the normal mirror-and-leave animation, rather
        than letting it vanish or hang around."""
        speaker = next((i for i in self.window.stage.instances if i.slot == 0), None)
        if speaker is None or speaker.phase == "exiting":
            return

        self._cancel_deferred()  # a pending playback start or post-speech hold
        self.audio_player.stop()  # silent, and unlike skip() it won't re-trigger on_finished
        logger.info("Пропуск фразы по хоткею: '%s' (id=%d)", speaker.text, speaker.id)
        self.window.retire_speaker(speaker.id)

    def enqueue(self, text: str) -> None:
        inst = self.window.add_speaker(text)
        if inst is None:
            self._backlog.append(text)
            logger.debug("TTS-очередь: сцена занята (7/7), сообщение ждёт в резерве (%d в резерве)", len(self._backlog))

    def _on_slot_freed(self) -> None:
        if self._backlog:
            text = self._backlog.popleft()
            logger.debug(
                "TTS-очередь: сообщение из резерва выходит на сцену (%d осталось в резерве)",
                len(self._backlog),
            )
            self.enqueue(text)

    def _on_speaker_ready(self, instance_id: int) -> None:
        try:
            self._start_synthesis(instance_id)
        except Exception:
            # This runs inside Stage.tick(); letting anything escape would
            # break the animation tick and leave the avatar stuck on stage
            # forever. Log it and send this one off instead.
            logger.exception("TTS-очередь: не удалось запустить синтез (id=%d)", instance_id)
            self.window.retire_speaker(instance_id)

    def _start_synthesis(self, instance_id: int) -> None:
        inst = self.window.stage.get(instance_id)
        if inst is None:
            return
        text = inst.text
        voice, lang = pick_voice(text, self.config.tts)
        rate = f"{self.config.tts.rate_percent:+d}%"
        provider = get_active_provider(self.config.tts, self.providers)
        logger.info("TTS-очередь: синтез '%s' provider=%s voice=%s", text, self.config.tts.provider, voice)

        # Only one synthesis is ever in flight at a time (Stage guarantees
        # speaker_ready can't fire again until the current speaker has fully
        # exited), so it's safe to stash the instance_id here rather than
        # capture it in a per-call lambda — see the note on the connect()
        # below for why that matters.
        self._pending_instance_id = instance_id
        self._speaker_arrived_at = time.monotonic()

        self._thread = QThread(self)
        self._worker = SynthesisWorker(provider, text, voice, lang, rate)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # A plain bound QObject-method slot, NOT a lambda/functools.partial:
        # PySide6 only auto-queues a cross-thread connection onto the
        # receiver's own thread when it can recognize the slot as a bound
        # method of a QObject. Wrapping it (lambda capturing instance_id,
        # partial, etc.) defeats that detection and the slot runs directly
        # on the emitting worker thread instead — which silently breaks
        # anything Qt-affine downstream (e.g. audio_player's QTimer.start()
        # becomes a no-op because it's called from the wrong thread).
        self._worker.finished.connect(self._on_synthesized_slot)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_synthesized_slot(self, audio: bytes, error: str) -> None:
        self._on_synthesized(self._pending_instance_id, audio, error)

    def _is_stale(self, instance_id: int) -> bool:
        """True once this instance is gone or already heading off stage —
        i.e. the skip hotkey got to it while synthesis was still in flight on
        a worker thread (which can't be aborted mid-request), so whatever
        comes back should simply be dropped."""
        inst = self.window.stage.get(instance_id)
        return inst is None or inst.phase == "exiting"

    def _on_synthesized(self, instance_id: int, audio: bytes, error: str) -> None:
        if self._is_stale(instance_id):
            return

        if error:
            inst = self.window.stage.get(instance_id)
            text = inst.text if inst is not None else "?"
            logger.error(
                "TTS-очередь: синтез не удался для '%s' (id=%d), пропускаю сообщение: %s",
                text, instance_id, error,
            )
            self.window.retire_speaker(instance_id)
            return

        # Hold the pose for the configured beat before speaking — measured
        # from arrival, so synthesis time counts toward it rather than being
        # added to it (fast synthesis waits, slow synthesis starts at once).
        elapsed_ms = (time.monotonic() - self._speaker_arrived_at) * 1000
        remaining_ms = max(0, round(self.config.render.pre_speech_delay_ms - elapsed_ms))
        self._defer(remaining_ms, lambda: self._start_playback(instance_id, audio))

    def _start_playback(self, instance_id: int, audio: bytes) -> None:
        if self._is_stale(instance_id):
            return
        volume_gain = max(0.0, 1.0 + self.config.tts.volume_percent / 100.0)
        self.audio_player.play(
            audio,
            volume_gain,
            on_finished=lambda iid=instance_id: self._retire_after_hold(iid),
            on_mouth_state=lambda is_open, iid=instance_id: self.window.set_speaker_mouth(iid, is_open),
            on_talking=lambda talking, iid=instance_id: self.window.set_speaker_talking(iid, talking),
            on_audio_level=lambda level, iid=instance_id: self.window.set_speaker_bounce_level(iid, level),
        )

    def _retire_after_hold(self, instance_id: int) -> None:
        self._defer(
            self.config.render.post_speech_hold_ms,
            lambda: self.window.retire_speaker(instance_id),
        )
