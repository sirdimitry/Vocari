"""Runs TTSProvider.synthesize() call(s) on a background QThread — shared
between the manual Test tab (one-shot) and the Twitch TTS queue (chained).

Takes a *list* of SynthesisPart, not just one: a single voice/language can
only pronounce text in the language it was built for, so anything from a
nick announcement mixing languages with the message down to a single
foreign word embedded mid-sentence needs its *own* voice — see
tts_queue.py's _voice_runs, which does the actual language-run splitting;
this module just knows how to turn a list of (already-split) parts into one
continuous audio buffer. Each part is synthesized on its own and the
results are concatenated (with each part's own `gap_after` silence) into
one buffer, so everything downstream (AudioPlayer.play(), the `finished`
signal) still only ever deals with a single audio blob, same as before any
of this multi-part splitting existed.
"""
from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from PySide6.QtCore import QObject, Signal

from vocari.logging_setup import get_logger
from vocari.tts.base import SynthesisResult, TTSProvider

logger = get_logger("tts.synthesis_worker")


@dataclass
class SynthesisPart:
    text: str
    voice: str
    lang: str
    gap_after: float = 0.0  # seconds of silence to insert after this part (ignored for the last one)


def _concatenate(results: list[SynthesisResult], gaps: list[float]) -> bytes:
    chunks: list[np.ndarray] = []
    samplerate: int | None = None
    for i, result in enumerate(results):
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
        if i < len(results) - 1:
            chunks.append(np.zeros(int(gaps[i] * (samplerate or sr)), dtype=np.float32))

    buffer = io.BytesIO()
    sf.write(buffer, np.concatenate(chunks), samplerate, format="WAV")
    return buffer.getvalue()


class SynthesisWorker(QObject):
    finished = Signal(bytes, str)  # audio bytes, error message ("" on success)

    def __init__(self, provider: TTSProvider, parts: list[SynthesisPart], rate: str):
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
        for part in self.parts:
            # EdgeTTSProvider-specific `rate` kwarg — SileroTTSProvider
            # accepts and ignores it, so this call stays generic.
            results.append(await self.provider.synthesize(part.text, part.voice, part.lang, rate=self.rate))
        if len(results) == 1:
            return results[0].audio
        return _concatenate(results, [p.gap_after for p in self.parts[:-1]])
