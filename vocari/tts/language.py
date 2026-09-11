"""Tiny heuristic language detector — Cyrillic vs Latin letter counts. Good
enough to pick an RU/EN voice automatically (see TTSConfig.auto_detect_language);
not meant to handle other languages."""
from __future__ import annotations


def detect_language(text: str) -> str:
    cyrillic = sum(1 for ch in text if "Ѐ" <= ch <= "ӿ")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "ru" if cyrillic >= latin else "en"
