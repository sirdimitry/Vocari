"""Local, fully offline TTS provider using Silero's free pretrained models
(https://github.com/snakers4/silero-models). Deliberately CPU-only — this
must work the same on any machine regardless of GPU vendor or presence
(NVIDIA/AMD/none, powerful or weak), and Silero is specifically built to run
fast on CPU, so there's no real reason to need a GPU for it at all.

Unlike EdgeTTSProvider, a model has to be downloaded once (~35-90 MB per
language, cached under ~/.cache/torch/hub) and loaded into memory before
synthesis is fast — see preload().

torch is a heavy dependency deliberately left out of requirements.txt (see
the comment there) — importing it happens lazily inside preload()/synthesize(),
not at module import time, so the rest of the app (and this module itself)
stays usable without it installed; only actually using Silero requires it.
"""
from __future__ import annotations

import asyncio
import io
import os

import numpy as np
import soundfile as sf

from vocari.logging_setup import get_logger
from vocari.tts.base import SynthesisResult, TTSProvider

logger = get_logger("tts.silero")

SAMPLE_RATE = 48000
REPO = "snakers4/silero-models"
MODEL_ID_BY_LANG = {"ru": "v4_ru", "en": "v3_en"}
WARMUP_TEXT = {"ru": "Проверка.", "en": "Check."}

TORCH_INSTALL_HINT = "pip install torch --index-url https://download.pytorch.org/whl/cpu"


class SileroTTSProvider(TTSProvider):
    def __init__(self):
        self._models: dict[str, object] = {}
        self._device = None  # created lazily once torch is confirmed importable

    def is_loaded(self, lang: str) -> bool:
        return lang in self._models

    def preload(self, lang: str) -> None:
        """Blocking (network + CPU-bound) — call from a background thread,
        not the Qt main thread. Loads the model for `lang` and runs one
        throwaway synthesis to warm up its JIT graph, so the user's actual
        first message is fast too (see Settings -> Silero)."""
        if lang in self._models:
            return
        model_id = MODEL_ID_BY_LANG.get(lang)
        if not model_id:
            raise ValueError(f"Silero: язык '{lang}' не поддерживается")

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                f"PyTorch не установлен — Silero работает только с ним. Установите: {TORCH_INSTALL_HINT}"
            ) from exc

        if self._device is None:
            self._device = torch.device("cpu")
            torch.set_num_threads(max(1, os.cpu_count() or 4))

        logger.info("Silero: загрузка модели %s (%s)...", model_id, lang)
        model, _ = torch.hub.load(
            repo_or_dir=REPO,
            model="silero_tts",
            language=lang,
            speaker=model_id,
            trust_repo=True,
        )
        model.to(self._device)
        model.apply_tts(text=WARMUP_TEXT.get(lang, "Test."), speaker=model.speakers[0], sample_rate=SAMPLE_RATE)
        self._models[lang] = model
        logger.info("Silero: модель %s готова (%d голосов)", model_id, len(model.speakers))

    def speakers(self, lang: str) -> list[str]:
        model = self._models.get(lang)
        return list(model.speakers) if model else []

    async def synthesize(
        self,
        text: str,
        voice: str,
        lang: str,
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> SynthesisResult:
        # Silero's apply_tts has no rate/volume knobs — accepted only so
        # every TTSProvider can be called the same way; playback volume is
        # applied by AudioPlayer's gain regardless of provider.
        if lang not in self._models:
            await asyncio.to_thread(self.preload, lang)
        model = self._models[lang]

        audio_tensor = await asyncio.to_thread(
            model.apply_tts, text=text, speaker=voice, sample_rate=SAMPLE_RATE
        )
        buffer = io.BytesIO()
        sf.write(buffer, audio_tensor.numpy().astype(np.float32), SAMPLE_RATE, format="WAV")
        return SynthesisResult(audio=buffer.getvalue(), format="wav")
