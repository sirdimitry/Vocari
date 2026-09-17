"""Local, fully offline TTS provider using Piper (https://github.com/rhasspy/piper)
— a fast ONNX-based neural engine, much lighter than Silero (no PyTorch, just
onnxruntime bundled inside Piper's own release) and noticeably faster on CPU
(real-time factor ~0.1 in testing: synthesizing 3s of speech takes ~0.3s).

Runs the actual `piper.exe` binary as a subprocess (text on stdin, WAV out to
a temp file) rather than a Python ONNX binding — keeps this provider free of
any new pip dependency, since Piper's own release already ships a self-
contained Windows binary plus its own onnxruntime/espeak-ng DLLs it needs.

Like Silero, both the engine (piper.exe + DLLs, ~25 MB) and every voice model
(~60 MB each) are downloaded on demand (see vocari/runtime_deps.py) rather
than bundled with the app — the installer stays small, and only users who
actually want a given Piper voice pay for its download.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from vocari.logging_setup import get_logger
from vocari.paths import app_root
from vocari.runtime_deps import PIPER_ENGINE, download_raw_file, is_downloaded, verify_file
from vocari.tts.base import SynthesisResult, TTSProvider
from vocari.tts.piper_voices import PIPER_VOICES, PiperVoice

logger = get_logger("tts.piper")

# Piper's own release archive has everything under a top-level "piper/"
# folder on every platform (see vocari/runtime_deps.py's PIPER_ENGINE) -
# ENGINE_DIR points one level deeper than the download target itself to land
# inside it. Only the binary's own filename differs per platform.
ENGINE_DIR = app_root() / "runtime_deps" / "piper_engine" / "piper"
VOICES_DIR = app_root() / "runtime_deps" / "piper_voices"
BINARY_NAME = "piper.exe" if sys.platform == "win32" else "piper"

PIPER_MISSING_HINT = 'откройте вкладку "Piper" в настройках и нажмите "Скачать движок Piper"'
_VOICES_BY_ID = {voice.voice_id: voice for voice in PIPER_VOICES}
# Provider instances are used by both the settings tab and speech queue. Share
# successful checks for unchanged files so a 60 MB model is hashed only once
# per process, while replacements/truncated files invalidate the fingerprint.
_VOICE_CHECK_CACHE: dict[str, tuple[tuple[int, int, int, int], str]] = {}


def _voice_paths(voice_id: str) -> tuple[Path, Path]:
    return VOICES_DIR / f"{voice_id}.onnx", VOICES_DIR / f"{voice_id}.onnx.json"


def _fingerprint(model_path: Path, config_path: Path) -> tuple[int, int, int, int]:
    model_stat = model_path.stat()
    config_stat = config_path.stat()
    return model_stat.st_size, model_stat.st_mtime_ns, config_stat.st_size, config_stat.st_mtime_ns


class PiperTTSProvider(TTSProvider):
    def is_engine_available(self) -> bool:
        return is_downloaded(PIPER_ENGINE) and (ENGINE_DIR / BINARY_NAME).exists()

    def is_voice_available(self, voice_id: str) -> bool:
        return self.voice_state(voice_id) == "ready"

    def voice_state(self, voice_id: str) -> str:
        """Return missing, incomplete, corrupt, or ready for a catalog voice."""
        voice = _VOICES_BY_ID.get(voice_id)
        model_path, config_path = _voice_paths(voice_id)
        model_exists, config_exists = model_path.is_file(), config_path.is_file()
        if not model_exists and not config_exists:
            return "missing"
        if not model_exists or not config_exists:
            return "incomplete"
        if voice is None:
            return "corrupt"  # no pinned hashes means it cannot be trusted
        try:
            fingerprint = _fingerprint(model_path, config_path)
        except OSError:
            return "incomplete"
        cached = _VOICE_CHECK_CACHE.get(voice_id)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]
        try:
            verify_file(model_path, voice.onnx_sha256)
            verify_file(config_path, voice.config_sha256)
        except (OSError, ValueError):
            state = "corrupt"
        else:
            state = "ready"
        _VOICE_CHECK_CACHE[voice_id] = fingerprint, state
        return state

    def available_voices(self) -> list[str]:
        if not VOICES_DIR.exists():
            return []
        return sorted(voice_id for voice_id in _VOICES_BY_ID if self.is_voice_available(voice_id))

    async def synthesize(
        self,
        text: str,
        voice: str,
        lang: str,
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> SynthesisResult:
        # rate/volume accepted only so every TTSProvider can be called the
        # same way (see SynthesisWorker) - Piper has no simple equivalent
        # knob exposed here; AudioPlayer's own gain still applies volume
        # regardless of provider, same as Silero.
        if not self.is_engine_available():
            raise RuntimeError(f"Piper не установлен — {PIPER_MISSING_HINT}")
        if not self.is_voice_available(voice):
            raise RuntimeError(f"Голос Piper '{voice}' не скачан — {PIPER_MISSING_HINT.replace('движок Piper', 'нужный голос')}")
        return await asyncio.to_thread(self._synthesize_sync, text, voice)

    def _synthesize_sync(self, text: str, voice: str) -> SynthesisResult:
        exe = ENGINE_DIR / BINARY_NAME
        model_path = VOICES_DIR / f"{voice}.onnx"
        if sys.platform != "win32":
            # Belt-and-suspenders: the Linux/macOS tarball's own entries
            # already carry the exec bit and tarfile.extractall() preserves
            # it, but this makes synthesize() self-healing regardless (a
            # manually-copied engine folder, an extraction edge case, ...)
            # rather than failing with a bare "Permission denied".
            try:
                exe.chmod(exe.stat().st_mode | 0o111)
            except OSError:
                pass
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            result = subprocess.run(
                [str(exe), "--model", str(model_path), "--output_file", str(out_path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
                # piper.exe is a console-subsystem binary - launched plainly
                # from a windowed (no-console) app, Windows briefly flashes a
                # terminal window for it on every single synthesize() call.
                # CREATE_NO_WINDOW suppresses that window entirely while
                # capture_output still pipes stdin/stdout/stderr normally.
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", "replace")[-500:]
                raise RuntimeError(f"piper.exe завершился с ошибкой: {stderr}")
            audio = out_path.read_bytes()
        finally:
            out_path.unlink(missing_ok=True)
        return SynthesisResult(audio=audio, format="wav")


def download_voice(
    voice: PiperVoice,
    on_progress: Callable[[int, int], None],
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Blocking — call from a background thread, not the Qt main thread.
    Downloads a voice's two files (the .onnx model + its .onnx.json config,
    both required) straight from Hugging Face into VOICES_DIR — see
    vocari/tts/piper_voices.py for where each voice's URLs come from.
    `on_progress` sees combined progress across both files (the .json is
    tiny compared to the .onnx, so this doesn't need to weight them)."""
    onnx_path = VOICES_DIR / f"{voice.voice_id}.onnx"
    config_path = VOICES_DIR / f"{voice.voice_id}.onnx.json"

    # The .onnx is ~60 MB, its .json a few KB — treat the .onnx download as
    # essentially the whole thing for progress purposes rather than trying
    # to divide total_bytes across two separate HTTP responses.
    download_raw_file(
        voice.onnx_url, onnx_path, on_progress, sha256=voice.onnx_sha256,
        is_cancelled=is_cancelled,
    )
    download_raw_file(
        voice.config_url, config_path, lambda _d, _t: None, sha256=voice.config_sha256,
        is_cancelled=is_cancelled,
    )
    _VOICE_CHECK_CACHE.pop(voice.voice_id, None)
