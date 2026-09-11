"""Serializes TTS requests so multiple chat messages don't talk over each
other — exactly one plays at a time, in arrival order, per spec: "сообщения
из чата обрабатываются последовательно (не перебивают друг друга)"."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QThread

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.tts.registry import get_active_provider
from vocari.tts.service import pick_voice
from vocari.tts.synthesis_worker import SynthesisWorker

logger = get_logger("tts.queue")


class TTSQueue(QObject):
    def __init__(self, config: AppConfig, providers: dict[str, TTSProvider], audio_player: AudioPlayer):
        super().__init__()
        self.config = config
        self.providers = providers
        self.audio_player = audio_player

        self._pending: deque[str] = deque()
        self._busy = False
        self._thread: QThread | None = None
        self._worker: SynthesisWorker | None = None

    def enqueue(self, text: str) -> None:
        self._pending.append(text)
        logger.debug("TTS-очередь: добавлено сообщение (в очереди: %d)", len(self._pending))
        self._pump()

    def _pump(self) -> None:
        if self._busy or not self._pending:
            return
        text = self._pending.popleft()
        self._busy = True

        voice, lang = pick_voice(text, self.config.tts)
        rate = f"{self.config.tts.rate_percent:+d}%"
        provider = get_active_provider(self.config.tts, self.providers)
        logger.info("TTS-очередь: синтез '%s' provider=%s voice=%s", text, self.config.tts.provider, voice)

        self._thread = QThread(self)
        self._worker = SynthesisWorker(provider, text, voice, lang, rate)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_synthesized)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_synthesized(self, audio: bytes, error: str) -> None:
        if error:
            logger.error("TTS-очередь: синтез не удался, пропускаю сообщение: %s", error)
            self._busy = False
            self._pump()
            return

        volume_gain = max(0.0, 1.0 + self.config.tts.volume_percent / 100.0)
        self.audio_player.play(audio, volume_gain, self._on_playback_finished)

    def _on_playback_finished(self) -> None:
        self._busy = False
        self._pump()
