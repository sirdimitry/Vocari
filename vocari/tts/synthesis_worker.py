"""Runs one TTSProvider.synthesize() call on a background QThread — shared
between the manual Test tab (one-shot) and the Twitch TTS queue (chained)."""
from __future__ import annotations

import asyncio

from PySide6.QtCore import QObject, Signal

from vocari.logging_setup import get_logger
from vocari.tts.base import TTSProvider

logger = get_logger("tts.synthesis_worker")


class SynthesisWorker(QObject):
    finished = Signal(bytes, str)  # audio bytes, error message ("" on success)

    def __init__(self, provider: TTSProvider, text: str, voice: str, lang: str, rate: str):
        super().__init__()
        self.provider = provider
        self.text = text
        self.voice = voice
        self.lang = lang
        self.rate = rate

    def run(self) -> None:
        try:
            # EdgeTTSProvider-specific `rate` kwarg — SileroTTSProvider
            # accepts and ignores it, so this call stays generic.
            result = asyncio.run(self.provider.synthesize(self.text, self.voice, self.lang, rate=self.rate))
            self.finished.emit(result.audio, "")
        except Exception as exc:  # noqa: BLE001 - surface any provider/network error to the caller
            logger.exception("Ошибка синтеза TTS")
            self.finished.emit(b"", str(exc))
