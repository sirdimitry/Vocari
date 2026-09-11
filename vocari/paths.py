"""Where Vocari's writable/user-facing files live: config.json, logs/,
silero_cache/, and assets/models/ (including custom imports via the Model
tab).

In a normal (non-frozen) run this is the repo root. Once packaged with
PyInstaller, `__file__`-based paths point inside the bundle instead (a temp
extraction dir for --onefile, or the bundled _internal folder for --onedir)
— neither is writable or where a user would expect config.json/logs/ to
show up, so this falls back to the directory containing the actual .exe
(PyInstaller's documented `sys.frozen` / `sys.executable` convention)
instead. Every module that previously computed its own "project root" via
`Path(__file__).resolve().parent...` should use this instead, so there's
exactly one place that needs to know about frozen vs. dev-tree layout.
"""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
