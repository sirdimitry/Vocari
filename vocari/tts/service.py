"""Ties config + language detection together: given raw chat/test text,
decide which voice to use and apply the shared length limit. Used by the
Stage 3 test tab now, and by the Twitch bot in Stage 5."""
from __future__ import annotations

import random

from vocari.config.settings import TTSConfig
from vocari.tts.language import detect_language
from vocari.tts.voices import EN_VOICES, RU_VOICES


def pick_voice(text: str, config: TTSConfig, manual_lang: str | None = None) -> tuple[str, str]:
    """Returns (voice_name, lang). `manual_lang` ("ru"/"en") overrides
    auto-detection when given; otherwise follows config.auto_detect_language.
    When config.random_voice is on, a random voice from the language's pool
    is picked instead of the configured voice_ru/voice_en — a fresh roll on
    every call, so each utterance can sound different."""
    if manual_lang:
        lang = manual_lang
    elif config.auto_detect_language:
        lang = detect_language(text)
    else:
        lang = config.manual_lang

    if config.random_voice:
        pool = RU_VOICES if lang == "ru" else EN_VOICES
        voice = random.choice(pool)
    else:
        voice = config.voice_ru if lang == "ru" else config.voice_en
    return voice, lang


def enforce_length_limit(text: str, config: TTSConfig) -> tuple[str, bool]:
    """Returns (possibly-truncated text, was_truncated)."""
    if len(text) <= config.max_chars:
        return text, False
    return text[: config.max_chars], True
