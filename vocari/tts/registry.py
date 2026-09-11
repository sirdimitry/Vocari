"""Resolves which TTSProvider instance is "active" per config.tts.provider.
Used by the Test tab now, and by the Twitch bot in Stage 5."""
from __future__ import annotations

from vocari.config.settings import TTSConfig
from vocari.tts.base import TTSProvider


def get_active_provider(config: TTSConfig, providers: dict[str, TTSProvider]) -> TTSProvider:
    return providers.get(config.provider, providers["edge"])
