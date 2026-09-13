"""Optional heavy runtime dependencies that are downloaded on demand instead
of bundled into the installer — right now, that's just the PyTorch CPU
wheel closure Silero needs. Every Vocari user would otherwise pay ~600 MB
extra just for the app itself, even the ones who never touch the offline
voices, so torch stays out of vocari.spec's build (see its own comment on
that) and gets fetched here instead, the first time someone actually wants
offline voices.

Downloaded once into runtime_deps/<dir_name>/ next to Vocari.exe (gitignored,
same convention as silero_cache/config.json/logs) and added to sys.path on
every later startup via ensure_all_on_path() — called at the very top of
main.py, before anything could try to import torch, so a plain `import
torch` anywhere else in the app (see silero_provider.py) just works once
it's been downloaded, with no special-casing needed at each call site.

The download is one pre-built zip (torch + its exact runtime dependency
closure — torchgen, filelock, fsspec, jinja2, markupsafe, mpmath, networkx,
sympy, typing_extensions — pinned to the versions this app was tested
against) hosted as a GitHub release asset, not a live pip/PyPI resolve:
reimplementing dependency resolution here would be its own source of
breakage, and a fixed asset is exactly reproducible.
"""
from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vocari.paths import app_root

RUNTIME_DEPS_DIR = app_root() / "runtime_deps"


@dataclass(frozen=True)
class RuntimeDep:
    label: str  # shown in the UI
    dir_name: str  # subfolder under runtime_deps/
    url: str
    approx_size_mb: int


TORCH_CPU = RuntimeDep(
    label="PyTorch (офлайн-голоса Silero)",
    dir_name="torch_cpu",
    url="https://github.com/sirdimitry/Vocari/releases/download/runtime-deps-torch-cpu-v1/torch_cpu_win_amd64_py312.zip",
    approx_size_mb=175,
)


def _dep_path(dep: RuntimeDep) -> Path:
    return RUNTIME_DEPS_DIR / dep.dir_name


def _marker(dep: RuntimeDep) -> Path:
    return _dep_path(dep) / ".complete"


def is_downloaded(dep: RuntimeDep) -> bool:
    return _marker(dep).exists()


def ensure_on_path(dep: RuntimeDep) -> None:
    """Makes an already-downloaded dependency importable. Cheap and safe to
    call unconditionally on every startup, whether or not it was ever
    downloaded — this is also what makes "already installed" checks work
    for free: a plain `import torch` after this succeeds exactly when it's
    genuinely available, in a dev venv (already on sys.path the normal way)
    or a packaged build (downloaded previously, picked up here) alike."""
    if not is_downloaded(dep):
        return
    path = str(_dep_path(dep))
    if path not in sys.path:
        sys.path.insert(0, path)


def ensure_all_on_path() -> None:
    for dep in (TORCH_CPU,):
        ensure_on_path(dep)


def download(dep: RuntimeDep, on_progress: Callable[[int, int], None]) -> None:
    """Blocking (network + disk I/O) — call from a background thread, not
    the Qt main thread. Downloads the zip and extracts it into place;
    `on_progress(downloaded_bytes, total_bytes)` is invoked periodically —
    total_bytes is 0 if the server doesn't send a Content-Length, so callers
    should treat that as "unknown" rather than divide by it."""
    target = _dep_path(dep)
    if target.exists():
        shutil.rmtree(target)
    RUNTIME_DEPS_DIR.mkdir(parents=True, exist_ok=True)

    tmp_zip = RUNTIME_DEPS_DIR / f"{dep.dir_name}.download.zip"
    try:
        with urllib.request.urlopen(dep.url) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    on_progress(downloaded, total)

        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(target)
        _marker(dep).touch()
    finally:
        tmp_zip.unlink(missing_ok=True)

    ensure_on_path(dep)
