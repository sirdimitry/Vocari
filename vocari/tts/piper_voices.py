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

_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/8914c16824264dfe6425deffca679ce9bb1ab371"


@dataclass(frozen=True)
class PiperVoice:
    voice_id: str  # e.g. "ru_RU-irina-medium" — matches the .onnx filename (no extension)
    lang: str  # "ru" | "en"
    label: str  # shown in the UI
    approx_size_mb: int
    onnx_sha256: str
    config_sha256: str

    @property
    def onnx_url(self) -> str:
        lang_region, name, quality = self.voice_id.split("-")
        lang_code = lang_region.split("_")[0]
        return f"{_HF_BASE}/{lang_code}/{lang_region}/{name}/{quality}/{self.voice_id}.onnx"

    @property
    def config_url(self) -> str:
        return f"{self.onnx_url}.json"


PIPER_VOICES = [
    PiperVoice("ru_RU-irina-medium", "ru", "Ирина (RU, женский)", 63,
               "8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa",
               "c2ec28bb38e2b59e93b959b3e40348c1afebbd272f30fed5d41205d08e98a9d7"),
    PiperVoice("ru_RU-denis-medium", "ru", "Денис (RU, мужской)", 63,
               "15fab56e11a097858ee115545d0f697fc2a316c41a291a5362349fb870411b0a",
               "831c860dac0b5073eaa81610a0a638ec23d90a6cf8e5f871b4485c2cec3767c8"),
    PiperVoice("en_US-lessac-medium", "en", "Lessac (EN, мужской)", 63,
               "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f",
               "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0"),
    PiperVoice("en_US-amy-medium", "en", "Amy (EN, женский)", 63,
               "b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18",
               "95a23eb4d42909d38df73bb9ac7f45f597dbfcde2d1bf9526fdeaf5466977d77"),
]
