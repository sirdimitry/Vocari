"""Bridges chat/test requests to the stage (vocari/rendering/stage.py) and
the actual TTS synthesis+playback. A message doesn't get synthesized the
instant it arrives — only once its avatar instance has finished sliding into
the speaking slot (Stage's speaker_ready callback) — so the jump-in
animation naturally covers the synthesis/model-load latency instead of a
separate fixed delay. Exactly one thing plays at a time by construction:
Stage only has one current speaker. Skipping can leave an older synthesis
running in the background; its result carries its original instance id
and is discarded once that instance is no longer speaking.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Slot

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.rendering.overlay_window import OverlayWindow
from vocari.rendering.stage import AvatarInstance
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.tts.language import detect_language, split_by_script
from vocari.tts.piper_provider import PiperTTSProvider
from vocari.tts.registry import get_active_provider
from vocari.tts.service import pick_voice, resolve_lang
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.tts.synthesis_worker import SynthesisPart, SynthesisWorker

logger = get_logger("tts.queue")

# Between the nick announcement and the message itself — long enough to read
# as a deliberate pause, not a stutter.
ANNOUNCE_GAP_SECONDS = 0.25
# Between two runs *within* the same phrase/message that just switched
# script (a foreign word or two mid-sentence) — short, more like a breath
# than a pause, since these can happen several times in one sentence.
SCRIPT_SWITCH_GAP_SECONDS = 0.08

MAX_QUEUE_WAIT_SECONDS = 120.0


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
        self._backlog: deque[tuple[str, str, float]] = deque()  # text, author, deadline
        # Keep skipped jobs alive until their threads finish as well.
        self._synthesis_jobs: dict[QThread, SynthesisWorker] = {}
        self._shutting_down = False
        # When the current speaker arrived in the slot — the pre-speech pause
        # is measured from here, so slow synthesis eats into it instead of
        # adding on top of it.
        self._speaker_arrived_at = 0.0
        self._deferred_timers: list[QTimer] = []
        # Settings → Облачко's "Держать облачко на экране для настройки"
        # parks a non-speaking preview in the speaking slot indefinitely.
        # enqueue() below auto-dismisses it so a real message is never stuck
        # waiting behind it forever; this lets the settings UI know that
        # happened so its toggle button can un-check itself instead of
        # silently going stale.
        self._on_preview_dismissed: Callable[[], None] | None = None

        window.stage.on_speaker_ready(self._on_speaker_ready)
        window.stage.on_slot_freed(self._on_slot_freed)

    def set_on_preview_dismissed(self, callback: Callable[[], None]) -> None:
        self._on_preview_dismissed = callback

    def _defer(self, delay_ms: int, callback) -> None:
        """QTimer.singleShot that can be cancelled by skip_current()."""
        timer = QTimer(self)
        timer.setSingleShot(True)

        def fire() -> None:
            self._deferred_timers.remove(timer)
            try:
                callback()
            finally:
                # Single-shot timers stop automatically, but remain children
                # of this queue until deleted, retaining the callback's audio.
                timer.deleteLater()

        timer.timeout.connect(fire)
        self._deferred_timers.append(timer)
        timer.start(delay_ms)

    def _cancel_deferred(self) -> None:
        for timer in self._deferred_timers:
            timer.stop()
            timer.deleteLater()
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

    def enqueue(self, text: str, author: str = "") -> bool:
        """Accept a message, or return False when the waiting reserve is full."""
        if self._shutting_down:
            return False
        # The bubble-settings preview parks an instance in the speaking slot
        # with no synthesis and no auto-exit — if it's still up (the user
        # left "Держать облачко на экране" checked), a real message would
        # otherwise queue up behind it and simply never get its turn, which
        # reads as "the test button doesn't do anything" or "it's stuck".
        if self.window.has_bubble_preview():
            self.window.hide_bubble_preview()
            logger.info("TTS-очередь: снял превью облачка, чтобы освободить место для реального сообщения")
            if self._on_preview_dismissed:
                self._on_preview_dismissed()

        # Move older requests first, and discard expired ones before checking
        # capacity. A fresh arrival must never overtake the existing reserve.
        self._on_slot_freed()
        deadline = time.monotonic() + MAX_QUEUE_WAIT_SECONDS
        if not self._backlog:
            inst = self.window.add_speaker(text, author)
            if inst is not None:
                inst.queue_deadline = deadline
                return True
        # Read the shared config at admission so UI changes apply immediately.
        # Lowering the limit preserves accepted messages while blocking new ones.
        limit = max(1, min(1000, self.config.tts.max_backlog_messages))
        if len(self._backlog) >= limit:
            logger.warning("TTS-очередь: резерв заполнен (лимит %d), новое сообщение отклонено", limit)
            return False
        self._backlog.append((text, author, deadline))
        logger.debug("TTS-очередь: сообщение ждёт в резерве (%d в резерве)", len(self._backlog))
        return True

    def show_bubble_preview(self, message: tuple[str, str]) -> None:
        """Settings-window preview: park an avatar with its bubble up, no
        synthesis and no auto-exit, so bubble settings can be judged live."""
        text, author = message
        self.window.show_bubble_preview(text, author)

    def update_bubble_preview(self, message: tuple[str, str]) -> None:
        text, author = message
        self.window.update_preview_message(text, author)

    def hide_bubble_preview(self) -> None:
        self.window.hide_bubble_preview()

    def _on_slot_freed(self) -> None:
        now = time.monotonic()
        expired = 0
        while self._backlog and self._backlog[0][2] <= now:
            self._backlog.popleft()
            expired += 1
        if expired:
            logger.warning("TTS-очередь: истекло время ожидания, удалено из резерва: %d", expired)
        while self._backlog:
            text, author, deadline = self._backlog[0]
            inst = self.window.add_speaker(text, author)
            if inst is None:
                break
            self._backlog.popleft()
            inst.queue_deadline = deadline
            logger.debug(
                "TTS-очередь: сообщение из резерва выходит на сцену (%d осталось в резерве)",
                len(self._backlog),
            )

    def _on_speaker_ready(self, instance_id: int) -> None:
        if self._shutting_down:
            return
        inst = self.window.stage.get(instance_id)
        if inst is None:
            return
        if inst.queue_deadline is not None and time.monotonic() >= inst.queue_deadline:
            logger.warning("TTS-очередь: истекло время ожидания сообщения на сцене (id=%d)", instance_id)
            self.window.retire_speaker(instance_id)
            return
        try:
            self._start_synthesis(instance_id)
        except Exception:
            # This runs inside Stage.tick(); letting anything escape would
            # break the animation tick and leave the avatar stuck on stage
            # forever. Log it and send this one off instead.
            logger.exception("TTS-очередь: не удалось запустить синтез (id=%d)", instance_id)
            self.window.retire_speaker(instance_id)

    def _voice_runs(self, text: str) -> list[tuple[str, str, str]]:
        """`text` split into (chunk, voice, lang) runs — one run per
        contiguous stretch that stays in one script (Cyrillic/Latin), each
        independently voiced. A single voice can only pronounce the
        language it was built for: a foreign nickname or a few words in the
        "other" language embedded in an otherwise single-language string
        would otherwise get silently dropped or badly mangled by whichever
        one voice the *whole* string happened to be sent to — see
        tts/language.py's split_by_script(). Same voice is reused for every
        run that lands on the same language, so e.g. "Случайный голос"
        doesn't flicker between different random picks mid-sentence just
        because the language briefly switched and switched back.

        In manual-language mode (auto_detect_language off) there's nothing
        to detect per run — the user pinned one language for everything —
        so this stays a single run, same as before splitting existed."""
        tts_config = self.config.tts
        if not tts_config.auto_detect_language:
            lang = resolve_lang(text, tts_config)
            voice, _ = pick_voice(text, tts_config, manual_lang=lang, pool=self._voice_pool(lang))
            return [(text, voice, lang)]

        voice_by_lang: dict[str, str] = {}
        runs = []
        for chunk, lang in split_by_script(text, detect_language(text)):
            if lang not in voice_by_lang:
                voice_by_lang[lang] = pick_voice(chunk, tts_config, manual_lang=lang, pool=self._voice_pool(lang))[0]
            runs.append((chunk, voice_by_lang[lang], lang))
        return runs

    def _voice_pool(self, lang: str) -> list[str] | None:
        """The real pool "Случайный голос" should draw from for `lang`, if
        one is actually known right now, instead of pick_voice()'s small
        built-in static sample:
        - Silero: the model for `lang` has to have actually been loaded
          (preloaded from Settings -> Silero, or lazily by a previous
          synthesize() call) to report its true speaker list (e.g. all 119
          v3_en names).
        - Piper: whatever voices have actually been downloaded for `lang`
          (Settings -> Piper) - voice ids are named "<lang>_<REGION>-...",
          so filtering by that prefix buckets them by language without
          needing a separate per-voice language tag anywhere.
        Returns None (defer to the static fallback) if nothing's loaded/
        downloaded yet, or for edge-tts (whose small curated list is already
        the real, complete option set)."""
        provider_name = self.config.tts.provider
        if provider_name == "silero":
            provider = self.providers.get("silero")
            if isinstance(provider, SileroTTSProvider) and provider.is_loaded(lang):
                return provider.speakers(lang) or None
        elif provider_name == "piper":
            provider = self.providers.get("piper")
            if isinstance(provider, PiperTTSProvider):
                voices = [v for v in provider.available_voices() if v.startswith(f"{lang}_")]
                return voices or None
        return None

    def _synthesis_parts(self, inst: AvatarInstance) -> list[SynthesisPart]:
        """Every text segment to synthesize for this instance, in order,
        each already paired with its own voice/lang and the silence to
        leave after it. The bubble's own displayed text (inst.text) stays
        just the message — the sender's name is already shown there
        separately, so the announcement is audio-only, prepended here."""
        config = self.config.bubble
        parts: list[SynthesisPart] = []

        if config.announce_nick and inst.author:
            phrase = config.announce_phrase.replace("Ник", inst.author).strip()
            if phrase:
                parts.extend(
                    SynthesisPart(chunk, voice, lang, SCRIPT_SWITCH_GAP_SECONDS)
                    for chunk, voice, lang in self._voice_runs(phrase)
                )
                if parts:
                    parts[-1].gap_after = ANNOUNCE_GAP_SECONDS

        parts.extend(
            SynthesisPart(chunk, voice, lang, SCRIPT_SWITCH_GAP_SECONDS)
            for chunk, voice, lang in self._voice_runs(inst.text)
        )
        if parts:
            parts[-1].gap_after = 0.0  # no trailing silence after the very last part
        return parts

    def _start_synthesis(self, instance_id: int) -> None:
        if self._shutting_down:
            return
        inst = self.window.stage.get(instance_id)
        if inst is None:
            return
        parts = self._synthesis_parts(inst)
        rate = f"{self.config.tts.rate_percent:+d}%"
        provider = get_active_provider(self.config.tts, self.providers)
        logger.info(
            "TTS-очередь: синтез %s provider=%s",
            " + ".join(f"'{p.text}' voice={p.voice}" for p in parts),
            self.config.tts.provider,
        )

        self._speaker_arrived_at = time.monotonic()

        thread = QThread(self)
        worker = SynthesisWorker(provider, parts, rate, instance_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # A plain bound QObject-method slot, NOT a lambda/functools.partial:
        # PySide6 only auto-queues a cross-thread connection onto the
        # receiver's own thread when it can recognize the slot as a bound
        # method of a QObject. Wrapping it (lambda capturing instance_id,
        # partial, etc.) defeats that detection and the slot runs directly
        # on the emitting worker thread instead — which silently breaks
        # anything Qt-affine downstream (e.g. audio_player's QTimer.start()
        # becomes a no-op because it's called from the wrong thread).
        worker.finished.connect(self._on_synthesized)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_synthesis_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._synthesis_jobs[thread] = worker
        thread.start()

    def shutdown(self) -> None:
        """Cancel active synthesis and synchronously release every QThread."""
        self._shutting_down = True
        self._backlog.clear()
        self._cancel_deferred()
        self.audio_player.stop()
        jobs = list(self._synthesis_jobs.items())
        for thread, worker in jobs:
            worker.cancel()
            thread.requestInterruption()
            thread.quit()
        for thread, _worker in jobs:
            if thread.isRunning():
                thread.wait()
            self._synthesis_jobs.pop(thread, None)

    @Slot()
    def _on_synthesis_thread_finished(self) -> None:
        self._synthesis_jobs.pop(self.sender(), None)

    def _is_stale(self, instance_id: int) -> bool:
        """True once this instance is gone or already heading off stage —
        i.e. the skip hotkey got to it while synthesis was still in flight on
        a worker thread (which can't be aborted mid-request), so whatever
        comes back should simply be dropped."""
        inst = self.window.stage.get(instance_id)
        return inst is None or inst.phase == "exiting"

    @Slot(int, bytes, str)
    def _on_synthesized(self, instance_id: int, audio: bytes, error: str) -> None:
        if self._shutting_down:
            return
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
        # Bubble goes up with the first word and comes down the moment the
        # line ends — the avatar then holds its pose for post_speech_hold_ms
        # before leaving, so the text is always gone before it turns to go.
        self.window.set_bubble_shown(instance_id, True)

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
        self.window.set_bubble_shown(instance_id, False)
        self._defer(
            self.config.render.post_speech_hold_ms,
            lambda: self.window.retire_speaker(instance_id),
        )
