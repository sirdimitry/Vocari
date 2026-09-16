"""config.json is stored at rest, not as plain human-readable JSON on disk —
see settings.py's save()/load(). On Windows this uses CryptProtectData/
CryptUnprotectData (crypt32 + kernel32, present on every Windows install, no
extra dependency needed). On every other platform it uses the `cryptography`
package instead (see requirements.txt's platform marker), with its key kept
in a small file next to config.json (see _KEY_PATH below) rather than typed
in by the user - same trust boundary as the Windows path: whoever can read
files under this app's own data folder could read either.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from vocari.logging_setup import get_logger
from vocari.paths import app_root

logger = get_logger("config.dpapi")

_IS_WINDOWS = sys.platform == "win32"
_KEY_PATH = app_root() / ".config.key"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _to_blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _extract_and_free(blob: _DATA_BLOB) -> bytes:
    result = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return result


def _get_or_create_key():
    from cryptography.fernet import Fernet

    if _KEY_PATH.exists():
        return _KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    _KEY_PATH.write_bytes(key)
    try:
        _KEY_PATH.chmod(0o600)  # readable/writable by this user only, like the rest of this app's own data folder
    except OSError:
        pass
    return key


def protect(data: bytes) -> bytes:
    if not _IS_WINDOWS:
        try:
            from cryptography.fernet import Fernet

            return Fernet(_get_or_create_key()).encrypt(data)
        except ImportError:
            logger.warning("Модуль 'cryptography' не установлен — config.json будет сохранён как обычный JSON")
            return data
    blob_in = _to_blob(data)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return _extract_and_free(blob_out)


def unprotect(data: bytes) -> bytes:
    if not _IS_WINDOWS:
        try:
            from cryptography.fernet import Fernet, InvalidToken

            try:
                return Fernet(_get_or_create_key()).decrypt(data)
            except InvalidToken as exc:
                # Same contract as the Windows path below (which raises
                # OSError on bad ciphertext) - settings.py's load() already
                # catches OSError and falls back to reading `data` as plain
                # JSON, e.g. a config.json from before this existed.
                raise OSError("not a valid token for the local key") from exc
        except ImportError:
            return data
    blob_in = _to_blob(data)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return _extract_and_free(blob_out)
