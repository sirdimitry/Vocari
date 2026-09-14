"""The app's actual icon/logo (assets/branding/) — used for the tray icon,
every top-level window's title-bar/taskbar icon, and the About dialog, so
there's exactly one place that knows where that file lives."""
from __future__ import annotations

from PySide6.QtGui import QIcon

from vocari.paths import app_root

ICON_PNG = app_root() / "assets" / "branding" / "icon.png"

_cached_icon: QIcon | None = None


def app_icon() -> QIcon:
    global _cached_icon
    if _cached_icon is None:
        _cached_icon = QIcon(str(ICON_PNG))
    return _cached_icon
