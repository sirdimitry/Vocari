"""Ties config + language detection together: given raw chat/test text,
decide which provider/voice to use and apply the shared length limit."""
from __future__ import annotations

import random

from vocari.config.settings import TTSConfig
from vocari.tts.language import detect_language
from vocari.tts.voices import EDGE_EN_VOICES, EDGE_RU_VOICES, SILERO_EN_VOICES, SILERO_RU_VOICES


def resolve_lang(text: str, config: TTSConfig, manual_lang: str | None = None) -> str:
    if manual_lang:
        return manual_lang
    if config.auto_detect_language:
        return detect_language(text)
    return config.manual_lang


def pick_voice(text: str, config: TTSConfig, manual_lang: str | None = None) -> tuple[str, str]:
    """Returns (voice_name, lang) for whichever provider is selected
    (config.provider). `manual_lang` ("ru"/"en") overrides auto-detection
    when given; otherwise follows config.auto_detect_language.

    When config.random_voice is on, a random voice from that provider's
    language pool is picked instead of the configured voice — a fresh roll
    on every call, so each utterance can sound different."""
    lang = resolve_lang(text, config, manual_lang)

    if config.provider == "silero":
        pool = SILERO_RU_VOICES if lang == "ru" else SILERO_EN_VOICES
        fixed_voice = config.silero_voice_ru if lang == "ru" else config.silero_voice_en
    else:
        pool = EDGE_RU_VOICES if lang == "ru" else EDGE_EN_VOICES
        fixed_voice = config.voice_ru if lang == "ru" else config.voice_en

    voice = random.choice(pool) if config.random_voice else fixed_voice
    return voice, lang


def enforce_length_limit(text: str, config: TTSConfig) -> tuple[str, bool]:
    """Returns (possibly-truncated text, was_truncated)."""
    if len(text) <= config.max_chars:
        return text, False
    return text[: config.max_chars], True
