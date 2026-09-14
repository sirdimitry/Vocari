"""Tiny heuristic language detector — Cyrillic vs Latin letter counts. Good
enough to pick an RU/EN voice automatically (see TTSConfig.auto_detect_language);
not meant to handle other languages."""
from __future__ import annotations


def detect_language(text: str) -> str:
    cyrillic = sum(1 for ch in text if "Ѐ" <= ch <= "ӿ")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "ru" if cyrillic >= latin else "en"


def _char_lang(ch: str) -> str | None:
    if "Ѐ" <= ch <= "ӿ":
        return "ru"
    if ch.isascii() and ch.isalpha():
        return "en"
    return None  # digits, punctuation, whitespace, emoji... — no language of its own


def split_by_script(text: str, fallback_lang: str) -> list[tuple[str, str]]:
    """Splits `text` into consecutive runs that each stay in one language
    (ru/en), instead of detect_language()'s single verdict for the whole
    string. A single TTS voice can only pronounce the language it was built
    for — a foreign word or phrase embedded in an otherwise single-language
    string (a nickname like "whyaya" inside a Russian announce phrase, or a
    stray English word in a Russian sentence) gets silently dropped or badly
    mangled if it's forced through the *other* language's voice along with
    everything else. Splitting means each run gets its own, correctly-
    detected voice at synthesis time (see tts_queue.py's _voice_runs) — the
    accent/seam between runs is an accepted tradeoff for actually reading
    every word instead of quietly skipping whichever language lost the vote.

    Neutral characters (digits, punctuation, whitespace, emoji...) join
    whichever lettered run they're adjacent to rather than starting a run of
    their own, so "text 123 текст" comes back as two runs, not four; a
    fully-neutral string (no letters at all) comes back as one run in
    `fallback_lang`, since there's nothing to detect a language from."""
    if not text:
        return []

    chars = list(text)
    char_langs = [_char_lang(ch) for ch in chars]

    # Each neutral char inherits the language of the nearest lettered char —
    # preferring the one before it, falling back to the one after for a
    # neutral run at the very start (so leading punctuation joins whatever
    # comes after it rather than getting an arbitrary default).
    resolved: list[str | None] = list(char_langs)
    last_seen: str | None = None
    for i, lang in enumerate(char_langs):
        if lang is not None:
            last_seen = lang
        elif last_seen is not None:
            resolved[i] = last_seen
    next_seen: str | None = None
    for i in range(len(char_langs) - 1, -1, -1):
        if char_langs[i] is not None:
            next_seen = char_langs[i]
        elif resolved[i] is None:
            resolved[i] = next_seen

    if all(lang is None for lang in resolved):
        return [(text, fallback_lang)]

    runs: list[tuple[str, str]] = []
    current_lang = resolved[0] or fallback_lang
    current_chars: list[str] = []
    for ch, lang in zip(chars, resolved):
        lang = lang or fallback_lang
        if lang != current_lang and current_chars:
            runs.append(("".join(current_chars), current_lang))
            current_chars = []
            current_lang = lang
        current_chars.append(ch)
    if current_chars:
        runs.append(("".join(current_chars), current_lang))
    return runs
