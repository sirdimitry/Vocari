"""Curated voice lists per provider — used both for the settings dropdowns
(which stay editable, so any other voice id works too) and as the pool for
"случайный голос" mode. Silero's own full speaker list is available at
runtime via SileroTTSProvider.speakers() once a model is loaded; these are
just reasonable static defaults for the UI before that."""
from __future__ import annotations

EDGE_RU_VOICES = ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"]
EDGE_EN_VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-US-AriaNeural"]

# Silero v4_ru speakers (excludes its own "random" pseudo-speaker — pick that
# manually in the dropdown if you want Silero's internal randomization
# instead of Vocari's "Случайный голос" toggle).
SILERO_RU_VOICES = ["aidar", "baya", "kseniya", "xenia", "eugene"]
# Silero v3_en has 119 numbered speakers (en_0..en_118); a small sample here.
SILERO_EN_VOICES = ["en_0", "en_1", "en_2", "en_3", "en_4"]
