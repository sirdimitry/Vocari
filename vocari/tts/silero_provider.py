"""Local, fully offline TTS provider using Silero's free pretrained models
(https://github.com/snakers4/silero-models). Deliberately CPU-only — this
must work the same on any machine regardless of GPU vendor or presence
(NVIDIA/AMD/none, powerful or weak), and Silero is specifically built to run
fast on CPU, so there's no real reason to need a GPU for it at all.

Unlike EdgeTTSProvider, a model has to be downloaded once (~40-57 MB per
language, cached under silero_cache/) and loaded into memory before
synthesis is fast — see preload().

torch is a heavy dependency deliberately left out of requirements.txt and
the packaged build (see the comment there, and vocari/runtime_deps.py) —
importing it happens lazily inside preload()/synthesize(), not at module
import time, so the rest of the app (and this module itself) stays usable
without it installed; only actually using Silero requires it. Settings ->
Silero downloads it on demand (runtime_deps.TORCH_CPU) instead of asking
the user to run pip themselves.
"""
from __future__ import annotations

import asyncio
import io
import os
import threading
from pathlib import Path

import numpy as np
import soundfile as sf

from vocari.logging_setup import get_logger
from vocari.paths import app_root
from vocari.runtime_deps import TORCH_CPU, download_raw_file, ensure_on_path, verify_file
from vocari.tts.base import SynthesisResult, TTSProvider

logger = get_logger("tts.silero")

SAMPLE_RATE = 48000
MAX_TORCH_THREADS = 4
MODEL_ID_BY_LANG = {"ru": "v4_ru", "en": "v3_en"}
# Official model packages, pinned by content as well as their versioned URL.
# Load the package directly: torch.hub's repository code would otherwise
# download executable model content without verifying it.
MODEL_SHA256_BY_LANG = {
    "ru": "896ab96347d5bd781ab97959d4fd6885620e5aab52405d3445626eb7c1414b00",
    "en": "02b71034d9f13bc4001195017bac9db1c6bb6115e03fea52983e8abcff13b665",
}
WARMUP_TEXT = {"ru": "Проверка.", "en": "Check."}

# Kept inside the project (not torch's default ~/.cache/torch/hub) so
# everything the app downloads lives in one place — gitignored, same as
# config.json/logs/.
CACHE_DIR = app_root() / "silero_cache"

TORCH_MISSING_HINT = (
    "откройте вкладку Silero в настройках и нажмите \"Скачать офлайн-голоса\""
)


def recommended_torch_threads(cpu_count: int | None = None) -> int:
    """Leave CPU capacity for OBS, the game, and Vocari's UI."""
    cores = max(1, cpu_count if cpu_count is not None else (os.cpu_count() or 1))
    return max(1, min(MAX_TORCH_THREADS, cores // 2))


class SileroTTSProvider(TTSProvider):
    def __init__(self):
        self._models: dict[str, object] = {}
        self._device = None  # created lazily once torch is confirmed importable
        self._load_lock = threading.Lock()

    def is_loaded(self, lang: str) -> bool:
        return lang in self._models

    def preload(self, lang: str) -> None:
        """Blocking (network + CPU-bound) — call from a background thread,
        not the Qt main thread. Loads the model for `lang` and runs one
        throwaway synthesis to warm up its JIT graph, so the user's actual
        first message is fast too (see Settings -> Silero)."""
        # A UI preload and incoming speech can request the same download.
        with self._load_lock:
            self._preload(lang)

    def _preload(self, lang: str) -> None:
        if lang in self._models:
            return
        model_id = MODEL_ID_BY_LANG.get(lang)
        if not model_id:
            raise ValueError(f"Silero: язык '{lang}' не поддерживается")

        ensure_on_path(TORCH_CPU)  # picks up a previously-downloaded torch even if
        # this is the very first call this run (e.g. main.py hasn't run yet in a test)
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                f"PyTorch не установлен — Silero работает только с ним. Чтобы установить: {TORCH_MISSING_HINT}"
            ) from exc

        if self._device is None:
            self._device = torch.device("cpu")
            threads = recommended_torch_threads()
            torch.set_num_threads(threads)
            logger.info("Silero: PyTorch использует %d поток(а/ов) CPU", threads)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Silero: загрузка модели %s (%s)...", model_id, lang)
        model_path = self._verified_model_path(lang)
        model = torch.package.PackageImporter(str(model_path)).load_pickle("tts_models", "model")
        model.to(self._device)
        model.apply_tts(text=WARMUP_TEXT.get(lang, "Test."), speaker=model.speakers[0], sample_rate=SAMPLE_RATE)
        self._models[lang] = model
        logger.info("Silero: модель %s готова (%d голосов)", model_id, len(model.speakers))

    def _verified_model_path(self, lang: str) -> Path:
        model_id = MODEL_ID_BY_LANG[lang]
        sha256 = MODEL_SHA256_BY_LANG[lang]
        path = CACHE_DIR / "verified" / f"{model_id}.pt"
        # Reuse old downloads only after checking their bytes. No Python from
        # the old torch.hub repository/cache is imported or executed.
        legacy = CACHE_DIR / "snakers4_silero-models_master" / "src" / "silero" / "model" / f"{model_id}.pt"
        for candidate in (path, legacy):
            if candidate.is_file():
                try:
                    verify_file(candidate, sha256)
                except ValueError:
                    logger.warning("Silero: контрольная сумма кеша не совпала (%s)", candidate.name)
                else:
                    return candidate
        download_raw_file(
            f"https://models.silero.ai/models/tts/{lang}/{model_id}.pt",
            path, lambda _d, _t: None, sha256=sha256,
        )
        return path

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
