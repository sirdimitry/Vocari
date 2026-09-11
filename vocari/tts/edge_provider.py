"""Default TTS provider: Microsoft Edge's free neural voices via edge-tts.
No API key required."""
from __future__ import annotations

import edge_tts

from vocari.logging_setup import get_logger
from vocari.tts.base import SynthesisResult, TTSProvider

logger = get_logger("tts.edge")


class EdgeTTSProvider(TTSProvider):
    async def synthesize(
        self,
        text: str,
        voice: str,
        lang: str,
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> SynthesisResult:
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.extend(chunk["data"])
        logger.debug("edge-tts: синтезировано %d байт (voice=%s, rate=%s, volume=%s)", len(chunks), voice, rate, volume)
        return SynthesisResult(audio=bytes(chunks), format="mp3")
