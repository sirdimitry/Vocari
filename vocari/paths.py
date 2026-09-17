"""Locations for Vocari's installed files and writable user data.

Source runs and Windows onedir builds keep their established portable
layout. Frozen Linux builds use ``$XDG_DATA_HOME/vocari`` (normally
``~/.local/share/vocari``), because /opt and AppImage mounts are read-only.
Bundled assets are copied there on first launch/update, preserving imported
models. ``VOCARI_HOME`` is an explicit override for portable deployments.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_cached_root: Path | None = None


def install_root() -> Path:
    """Read-only application files shipped by the source tree or package."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _prepare_linux_data(root: Path) -> None:
    """Seed/update bundled assets in the user's writable XDG data folder."""
    root.mkdir(parents=True, exist_ok=True)
    source = install_root() / "assets"
    if not source.is_dir():
        return

    from vocari.__version__ import __version__

    marker = root / ".bundled-assets-version"
    try:
        current = marker.read_text(encoding="utf-8").strip()
    except OSError:
        current = ""
    if current == __version__:
        return
    # dirs_exist_ok preserves imported model folders while refreshing the
    # built-in models and branding shipped by a newer application version.
    shutil.copytree(source, root / "assets", dirs_exist_ok=True)
    marker.write_text(__version__, encoding="utf-8")


def app_root() -> Path:
    global _cached_root
    if _cached_root is not None:
        return _cached_root

    override = os.environ.get("VOCARI_HOME")
    if override:
        root = Path(override).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
    elif getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        root = data_home / "vocari"
        _prepare_linux_data(root)
    else:
        root = install_root()
    _cached_root = root
    return root
