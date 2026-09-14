"""A small curated catalog of downloadable Piper voices, each hosted at its
real, stable URL on Hugging Face (rhasspy/piper-voices) — not re-hosted,
same reasoning as vocari/runtime_deps.py's PIPER_ENGINE pointing straight at
Piper's own GitHub release.

Deliberately not the *entire* piper-voices catalog (dozens of languages,
several quality tiers each) — that would need a real browsable catalog UI
to be usable at all. A handful of solid RU/EN picks covers "try Piper and
see how it sounds" without needing that yet; more can be added here later,
same shape, no code changes needed elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass

_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


@dataclass(frozen=True)
class PiperVoice:
    voice_id: str  # e.g. "ru_RU-irina-medium" — matches the .onnx filename (no extension)
    lang: str  # "ru" | "en"
    label: str  # shown in the UI
    approx_size_mb: int

    @property
    def onnx_url(self) -> str:
        lang_region, name, quality = self.voice_id.split("-")
        lang_code = lang_region.split("_")[0]
        return f"{_HF_BASE}/{lang_code}/{lang_region}/{name}/{quality}/{self.voice_id}.onnx"

    @property
    def config_url(self) -> str:
        return f"{self.onnx_url}.json"


PIPER_VOICES = [
    PiperVoice("ru_RU-irina-medium", "ru", "Ирина (RU, женский)", 63),
    PiperVoice("ru_RU-denis-medium", "ru", "Денис (RU, мужской)", 63),
    PiperVoice("en_US-lessac-medium", "en", "Lessac (EN, мужской)", 63),
    PiperVoice("en_US-amy-medium", "en", "Amy (EN, женский)", 63),
]
