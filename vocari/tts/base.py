"""Common interface every TTS backend implements.

Stage 3 ships EdgeTTSProvider only (free, no API key). Silero (local/offline)
and ElevenLabs (paid, higher quality) plug in later behind this same
interface — see README "TTS-провайдеры" once Stage 4 settings land.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SynthesisResult:
    audio: bytes
    format: str = "mp3"


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str, lang: str) -> SynthesisResult:
        """Synthesize `text` with the given voice/lang, returning encoded audio bytes."""
