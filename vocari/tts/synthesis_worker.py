"""Runs TTSProvider.synthesize() call(s) on a background QThread — shared
between the manual Test tab (one-shot) and the Twitch TTS queue (chained).

Takes a *list* of (text, voice, lang) parts, not just one, because the nick
announcement (see tts_queue.py's _synthesis_parts) needs its own voice: a
single voice/language can only pronounce text in the language it was built
for, so a Russian announce phrase glued onto an English message and sent to
one English voice would just drop or mangle the Russian half — that's
exactly what happened before this took separate voices per part. Each part
is synthesized on its own and the resulting audio is concatenated (with a
short silence between parts) into one buffer, so everything downstream
(AudioPlayer.play(), the `finished` signal) still only ever deals with a
single audio blob, same as before.
"""
from __future__ import annotations

import asyncio
import io

import numpy as np
import soundfile as sf
from PySide6.QtCore import QObject, Signal

from vocari.logging_setup import get_logger
from vocari.tts.base import SynthesisResult, TTSProvider

logger = get_logger("tts.synthesis_worker")

GAP_SECONDS = 0.25  # silence between parts (e.g. between a nick announcement and the message)


def _concatenate(results: list[SynthesisResult]) -> bytes:
    chunks: list[np.ndarray] = []
    samplerate: int | None = None
    for result in results:
        data, sr = sf.read(io.BytesIO(result.audio), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if samplerate is None:
            samplerate = sr
        elif sr != samplerate:
            # Every part of one utterance goes through the same provider (see
            # tts_queue.py), so in practice these always match - if they ever
            # don't, gluing the raw samples together still plays (just at a
            # slightly wrong pitch/speed for the mismatched part) rather than
            # failing the whole utterance over a proper resample.
            logger.warning(
                "Части синтеза с разной частотой дискретизации (%d и %d Гц) — склеиваю как есть", samplerate, sr
            )
        chunks.append(data)
        chunks.append(np.zeros(int(GAP_SECONDS * (samplerate or sr)), dtype=np.float32))
    chunks.pop()  # no trailing silence after the last part

    buffer = io.BytesIO()
    sf.write(buffer, np.concatenate(chunks), samplerate, format="WAV")
    return buffer.getvalue()


class SynthesisWorker(QObject):
    finished = Signal(bytes, str)  # audio bytes, error message ("" on success)

    def __init__(self, provider: TTSProvider, parts: list[tuple[str, str, str]], rate: str):
        super().__init__()
        self.provider = provider
        self.parts = parts
        self.rate = rate

    def run(self) -> None:
        try:
            audio = asyncio.run(self._synthesize_all())
            self.finished.emit(audio, "")
        except Exception as exc:  # noqa: BLE001 - surface any provider/network error to the caller
            logger.exception("Ошибка синтеза TTS")
            self.finished.emit(b"", str(exc))

    async def _synthesize_all(self) -> bytes:
        results = []
        for text, voice, lang in self.parts:
            # EdgeTTSProvider-specific `rate` kwarg — SileroTTSProvider
            # accepts and ignores it, so this call stays generic.
            results.append(await self.provider.synthesize(text, voice, lang, rate=self.rate))
        return results[0].audio if len(results) == 1 else _concatenate(results)
