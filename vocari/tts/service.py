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


def pick_voice(
    text: str, config: TTSConfig, manual_lang: str | None = None, pool: list[str] | None = None
) -> tuple[str, str]:
    """Returns (voice_name, lang) for whichever provider is selected
    (config.provider). `manual_lang` ("ru"/"en") overrides auto-detection
    when given; otherwise follows config.auto_detect_language.

    When config.random_voice is on, a random voice from `pool` is picked
    instead of the configured voice — a fresh roll on every call, so each
    utterance can sound different. `pool` defaults to a small static sample
    per provider/language (vocari/tts/voices.py) when not given; callers
    that know the *real* list (e.g. tts_queue.py, once Silero has actually
    loaded a model and its full speaker list is known) should pass it in
    instead — Silero's v3_en has 119 real speakers, and randomizing among
    only the 5-name static sample would silently ignore the other 114."""
    lang = resolve_lang(text, config, manual_lang)

    if config.provider == "silero":
        pool = pool if pool is not None else (SILERO_RU_VOICES if lang == "ru" else SILERO_EN_VOICES)
        fixed_voice = config.silero_voice_ru if lang == "ru" else config.silero_voice_en
    elif config.provider == "piper":
        # No small built-in sample here (unlike edge/silero) - a Piper
        # voice id is only meaningful once its .onnx has actually been
        # downloaded (see tts_queue.py's _voice_pool, which supplies the
        # real downloaded list); with nothing downloaded yet, `pool`
        # legitimately has nothing to offer, so random mode just falls back
        # to whatever fixed voice is configured.
        pool = pool if pool is not None else []
        fixed_voice = config.piper_voice_ru if lang == "ru" else config.piper_voice_en
    else:
        pool = pool if pool is not None else (EDGE_RU_VOICES if lang == "ru" else EDGE_EN_VOICES)
        fixed_voice = config.voice_ru if lang == "ru" else config.voice_en

    # `pool` guard: Piper legitimately can have an empty pool (nothing
    # downloaded for this language yet) - fall back to the fixed voice
    # rather than crashing random.choice() on an empty sequence.
    voice = random.choice(pool) if config.random_voice and pool else fixed_voice
    return voice, lang


def enforce_length_limit(text: str, config: TTSConfig) -> tuple[str, bool]:
    """Returns (possibly-truncated text, was_truncated)."""
    if len(text) <= config.max_chars:
        return text, False
    return text[: config.max_chars], True
