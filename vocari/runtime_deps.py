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
sympy, typing_extensions, PLUS the full CPython 3.12 standard library, minus
test/tkinter/idlelib/lib2to3 — see below for why) hosted as a GitHub release
asset, not a live pip/PyPI resolve: reimplementing dependency resolution
here would be its own source of breakage, and a fixed asset is exactly
reproducible.

Why the stdlib is in there too: torch itself, and the actual Silero model
code it loads via torch.hub, both reach for stdlib modules (timeit,
xml.etree, ...) that nothing in Vocari's own code ever imports — since
torch is excluded from this build (see vocari.spec), PyInstaller's static
analysis never sees that need and silently drops those modules, which
surfaced as ModuleNotFoundError deep inside torch.hub.load() the first time
this shipped (RuntimeDep.version 1 -> 2). vocari.spec also force-bundles
the same list directly (via collect_submodules(), not bare names — a bare
package name in hiddenimports doesn't pull in its submodules, and a
same-named package that's already partially bundled from something else
takes priority via its own __path__ regardless of what's on sys.path), so
this stdlib copy here is a second line of defense for anything that isn't.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vocari.logging_setup import get_logger
from vocari.paths import app_root

logger = get_logger("runtime_deps")

RUNTIME_DEPS_DIR = app_root() / "runtime_deps"


class DownloadCancelled(RuntimeError):
    """A background download was cancelled during application shutdown."""


def _check_cancelled(is_cancelled: Callable[[], bool] | None) -> None:
    if is_cancelled is not None and is_cancelled():
        raise DownloadCancelled("Загрузка отменена при завершении приложения")


@dataclass(frozen=True)
class RuntimeDep:
    label: str  # shown in the UI
    dir_name: str  # subfolder under runtime_deps/
    url: str
    approx_size_mb: int
    sha256: str  # pinned in the app, never fetched alongside a download at runtime
    # Bumped whenever the hosted zip's *contents* change (not just its
    # bytes/URL) — e.g. adding a missing stdlib module the first cut of this
    # bundle turned out not to include. The marker file records which
    # version produced it, so a machine that already downloaded an older,
    # broken bundle re-downloads automatically instead of is_downloaded()
    # trusting stale content forever just because a folder with that name
    # exists.
    version: int = 1


TORCH_CPU = RuntimeDep(
    label="PyTorch (офлайн-голоса Silero)",
    dir_name="torch_cpu",
    url="https://github.com/sirdimitry/Vocari/releases/download/runtime-deps-torch-cpu-v1/torch_cpu_win_amd64_py312.zip",
    approx_size_mb=160,
    sha256="63ba526ca47744cb51891e180f15dce77d77017b4710e5724a9c9353bb0c1d0f",
    version=2,  # v2: bundles the full stdlib + omegaconf's deps too - v1 was missing timeit/xml.etree/omegaconf etc.
)
TORCH_RUNTIME_DOWNLOAD_SUPPORTED = sys.platform == "win32"

# Piper's own official release, used as-is (not re-hosted) - it's a public
# GitHub repo, no auth needed, same as any other direct download. Every
# platform's archive extracts to the same top-level "piper/" folder (verified
# for both the Windows .zip and the Linux .tar.gz), hence
# PiperTTSProvider.ENGINE_DIR pointing at runtime_deps/piper_engine/piper -
# only the archive format and the binary's own filename differ (piper.exe vs
# a plain "piper", see PiperTTSProvider.BINARY_NAME).
if sys.platform == "win32":
    _PIPER_ASSET = "piper_windows_amd64.zip"
    _PIPER_SHA256 = "f3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea"
elif sys.platform == "darwin":
    _PIPER_ASSET = "piper_macos_x64.tar.gz"
    _PIPER_SHA256 = "ced85c0a3df13945b1e623b878a48fdc2854d5c485b4b67f62857cf551deaf8b"
else:
    _PIPER_ASSET = "piper_linux_x86_64.tar.gz"
    _PIPER_SHA256 = "a50cb45f355b7af1f6d758c1b360717877ba0a398cc8cbe6d2a7a3a26e225992"

PIPER_ENGINE = RuntimeDep(
    label="Piper (офлайн-голоса)",
    dir_name="piper_engine",
    url=f"https://github.com/rhasspy/piper/releases/download/2023.11.14-2/{_PIPER_ASSET}",
    approx_size_mb=25,
    sha256=_PIPER_SHA256,
    version=1,
)


def _dep_path(dep: RuntimeDep) -> Path:
    return RUNTIME_DEPS_DIR / dep.dir_name


def _marker(dep: RuntimeDep) -> Path:
    return _dep_path(dep) / ".complete"


_PROGRESS_MIN_INTERVAL_S = 0.1  # ~10 UI updates/sec - plenty smooth, far less repaint pressure than one per 256 KB chunk


def _throttled(on_progress: Callable[[int, int], None]) -> Callable[[int, int], None]:
    """Wraps `on_progress` so it's actually called at most a few times a
    second instead of once per 256 KB chunk - on a fast connection that's
    hundreds of QProgressBar repaints/sec, which on at least one real setup
    (Linux, software-rendered Qt inside a VM) produced a stack-overflow
    segfault deep in Qt's own repaint recursion. Always lets the very last
    call through regardless of timing, so 100% still reliably lands."""
    last_call = 0.0

    def wrapped(downloaded: int, total: int) -> None:
        nonlocal last_call
        now = time.monotonic()
        if (total > 0 and downloaded >= total) or now - last_call >= _PROGRESS_MIN_INTERVAL_S:
            last_call = now
            on_progress(downloaded, total)

    return wrapped


def is_downloaded(dep: RuntimeDep) -> bool:
    marker = _marker(dep)
    if not marker.exists():
        return False
    try:
        recorded_version = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return False  # unreadable/corrupted marker — treat as stale
    return recorded_version == f"{dep.version}:{dep.sha256}"


def ensure_on_path(dep: RuntimeDep) -> None:
    """Makes an already-downloaded dependency importable. Cheap and safe to
    call unconditionally on every startup, whether or not it was ever
    downloaded — this is also what makes "already installed" checks work
    for free: a plain `import torch` after this succeeds exactly when it's
    genuinely available, in a dev venv (already on sys.path the normal way)
    or a packaged build (downloaded previously, picked up here) alike."""
    if dep is TORCH_CPU and not TORCH_RUNTIME_DOWNLOAD_SUPPORTED:
        return
    if not is_downloaded(dep):
        return
    path = str(_dep_path(dep))
    if path not in sys.path:
        sys.path.insert(0, path)


def ensure_all_on_path() -> None:
    for dep in (TORCH_CPU,):
        ensure_on_path(dep)


def download(
    dep: RuntimeDep,
    on_progress: Callable[[int, int], None],
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Blocking (network + disk I/O) — call from a background thread, not
    the Qt main thread. Downloads the archive and extracts it into place
    (.zip or .tar.gz, by `dep.url`'s extension - see PIPER_ENGINE for why
    that varies by platform); `on_progress(downloaded_bytes, total_bytes)`
    is invoked periodically — total_bytes is 0 if the server doesn't send a
    Content-Length, so callers should treat that as "unknown" rather than
    divide by it."""
    if dep is TORCH_CPU and not TORCH_RUNTIME_DOWNLOAD_SUPPORTED:
        raise RuntimeError("Автоматическая загрузка PyTorch не поддерживается на этой платформе")
    target = _dep_path(dep)
    # Only an immediate child of our dependency directory can be replaced.
    if target.is_symlink() or target.resolve().parent != RUNTIME_DEPS_DIR.resolve():
        raise ValueError("Недопустимый путь установки зависимости")
    RUNTIME_DEPS_DIR.mkdir(parents=True, exist_ok=True)

    is_tar = dep.url.endswith(".tar.gz")
    logger.info("Скачивание %s: %s -> %s", dep.label, dep.url, target)
    tmp_archive = RUNTIME_DEPS_DIR / f"{dep.dir_name}.download{'.tar.gz' if is_tar else '.zip'}"
    try:
        try:
            download_raw_file(
                dep.url, tmp_archive, on_progress, sha256=dep.sha256,
                is_cancelled=is_cancelled,
            )

            # A rejected/corrupt download must leave the previous install intact.
            _check_cancelled(is_cancelled)
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
            if is_tar:
                with tarfile.open(tmp_archive) as tf:
                    tf.extractall(target, filter="data")
            else:
                with zipfile.ZipFile(tmp_archive) as zf:
                    for entry in zf.infolist():
                        destination = (target / entry.filename).resolve()
                        if not destination.is_relative_to(target.resolve()):
                            raise ValueError("Архив содержит путь вне папки установки")
                    zf.extractall(target)
            _marker(dep).write_text(f"{dep.version}:{dep.sha256}", encoding="utf-8")
            logger.info("Распаковано и готово: %s", dep.label)
        except DownloadCancelled:
            raise
        except Exception:
            logger.exception("Не удалось скачать/распаковать %s (%s)", dep.label, dep.url)
            raise
    finally:
        tmp_archive.unlink(missing_ok=True)

    ensure_on_path(dep)


def verify_file(path: Path, sha256: str) -> None:
    """Check cached executable/model content before loading it."""
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != sha256:
        raise ValueError(f"Проверка SHA-256 не пройдена: {path.name}")


def download_raw_file(
    url: str,
    dest: Path,
    on_progress: Callable[[int, int], None],
    *,
    sha256: str,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Blocking (network + disk I/O) — call from a background thread. Plain
    single-file download, not a RuntimeDep zip — used for individual Piper
    voice model files (a .onnx + its .onnx.json, downloaded one at a time
    rather than as one big bundle, since there can be many voices and a user
    only wants a few). Downloads to a temp name first and renames on
    success, so a failed/interrupted download can never look like a
    complete file to a later is_voice_available()-style check. The expected
    SHA-256 must be pinned by the caller; no unverified downloads are allowed."""
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError("Не задана корректная контрольная сумма SHA-256")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".part")
    logger.info("Скачивание файла: %s -> %s", url, dest)
    progress = _throttled(on_progress)
    try:
        try:
            _check_cancelled(is_cancelled)
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=30) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        _check_cancelled(is_cancelled)
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        progress(downloaded, total)
            _check_cancelled(is_cancelled)
            if total and downloaded != total:
                raise ValueError(f"Файл скачан не полностью: {dest.name}")
            if digest.hexdigest() != sha256:
                raise ValueError(f"Проверка SHA-256 не пройдена: {dest.name}")
            logger.info("Скачан и проверен файл %s: %d байт", dest.name, downloaded)
        except DownloadCancelled:
            raise
        except Exception:
            logger.exception("Не удалось скачать файл %s (%s)", dest.name, url)
            raise
        tmp_path.replace(dest)
    finally:
        tmp_path.unlink(missing_ok=True)
