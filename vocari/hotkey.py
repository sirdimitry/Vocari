"""System-wide "skip current line" hotkey — works even while a game or OBS
has keyboard focus, not just when Vocari's own window is focused, since the
whole point is skipping an unwanted TTS line mid-stream without alt-tabbing.

Uses RegisterHotKey via ctypes on Windows — the standard OS-level API for
exactly this ("bind one specific combo"), deliberately not a third-party
global-hotkey library (e.g. `keyboard`/`pynput`) that hooks every keystroke
system-wide like a keylogger would. On any other platform this degrades to a
harmless no-op (see _IS_WINDOWS below): binding a hotkey just fails/logs
instead of the app refusing to start, since ctypes.windll doesn't exist
outside Windows at all - a real Linux backend (X11/evdev, or a portal-based
one for Wayland) is still a separate piece of work, not yet built.
"""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from vocari.logging_setup import get_logger

logger = get_logger("hotkey")

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1  # only one global hotkey exists right now, so a constant id is fine

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
else:
    _user32 = None

# Qt.Key values line up numerically with Win32 virtual-key codes for these —
# both ultimately trace back to the same US-keyboard/ASCII assumptions —
# which covers every realistic choice for a "skip" hotkey without needing a
# large lookup table for keys nobody would bind this to.
_SPECIAL_VK: dict[Qt.Key, int] = {
    Qt.Key.Key_Escape: 0x1B,
    Qt.Key.Key_Tab: 0x09,
    Qt.Key.Key_Backspace: 0x08,
    Qt.Key.Key_Return: 0x0D,
    Qt.Key.Key_Enter: 0x0D,
    Qt.Key.Key_Space: 0x20,
    Qt.Key.Key_Insert: 0x2D,
    Qt.Key.Key_Delete: 0x2E,
    Qt.Key.Key_Home: 0x24,
    Qt.Key.Key_End: 0x23,
    Qt.Key.Key_PageUp: 0x21,
    Qt.Key.Key_PageDown: 0x22,
    Qt.Key.Key_Left: 0x25,
    Qt.Key.Key_Up: 0x26,
    Qt.Key.Key_Right: 0x27,
    Qt.Key.Key_Down: 0x28,
    Qt.Key.Key_CapsLock: 0x14,
    Qt.Key.Key_Pause: 0x13,
}


def qt_key_to_vk(key: int) -> int | None:
    """Maps a Qt.Key value to a Win32 virtual-key code, or None if this
    particular key isn't one of the mapped/derivable ones (RegisterHotKey
    can't be used for it)."""
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        return 0x70 + (key - Qt.Key.Key_F1)
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return key  # Qt.Key_A..Key_Z == ord('A')..ord('Z') == VK_A..VK_Z
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return key  # same story for the top-row digit keys
    return _SPECIAL_VK.get(Qt.Key(key))


def qt_sequence_to_win32(sequence_text: str) -> tuple[int, int] | None:
    """Parses a QKeySequence string (e.g. "Ctrl+Alt+F9") into a
    (modifiers, virtual_key) pair for RegisterHotKey, or None if the string
    is empty or its key can't be mapped."""
    if not sequence_text:
        return None
    sequence = QKeySequence(sequence_text)
    if sequence.count() == 0:
        return None
    combination = sequence[0]
    vk = qt_key_to_vk(int(combination.key()))
    if vk is None:
        return None

    qt_mods = combination.keyboardModifiers()
    mods = MOD_NOREPEAT
    if qt_mods & Qt.KeyboardModifier.ControlModifier:
        mods |= MOD_CONTROL
    if qt_mods & Qt.KeyboardModifier.AltModifier:
        mods |= MOD_ALT
    if qt_mods & Qt.KeyboardModifier.ShiftModifier:
        mods |= MOD_SHIFT
    if qt_mods & Qt.KeyboardModifier.MetaModifier:
        mods |= MOD_WIN
    return mods, vk


class _HotkeyNativeFilter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt override)
        # Qt only ever reports this exact event_type string on Windows, so
        # this branch is naturally inert everywhere else - the _IS_WINDOWS
        # check is just belt-and-suspenders against relying on that alone.
        if _IS_WINDOWS and event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._on_hotkey()
        return False, 0


class GlobalHotkeyManager(QObject):
    """Wraps RegisterHotKey/UnregisterHotKey + a native event filter that
    catches the resulting WM_HOTKEY message regardless of which window (if
    any) currently has focus."""

    triggered = Signal()

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._registered = False
        self._filter = _HotkeyNativeFilter(self.triggered.emit)
        app.installNativeEventFilter(self._filter)

    def set_binding(self, sequence_text: str) -> bool:
        """Registers `sequence_text` (a QKeySequence string, e.g. "F9") as
        the global hotkey, replacing any previous binding; an empty string
        just clears it. Returns False if the string can't be mapped to a key
        Windows understands, or the combo is already claimed by another
        running application — the caller should surface that to the user
        rather than fail silently."""
        self._unregister()
        parsed = qt_sequence_to_win32(sequence_text)
        if parsed is None:
            return sequence_text == ""
        mods, vk = parsed
        ok = bool(_user32.RegisterHotKey(None, HOTKEY_ID, mods, vk))
        self._registered = ok
        if not ok:
            logger.warning(
                "Не удалось зарегистрировать хоткей '%s' — возможно, занят другим приложением",
                sequence_text,
            )
        return ok

    def _unregister(self) -> None:
        if self._registered:
            _user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False

    def shutdown(self) -> None:
        self._unregister()
        self._app.removeNativeEventFilter(self._filter)
