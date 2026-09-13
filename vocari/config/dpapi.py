"""Windows DPAPI (Data Protection API) — encrypts config.json at rest so it
isn't plain, human-readable JSON sitting on disk (the OAuth token especially
has no business being hand-editable/readable in a text editor).

DPAPI ties the ciphertext to the current Windows user profile on this
machine: CryptProtectData/CryptUnprotectData are core Windows APIs (crypt32
+ kernel32, present on every Windows install — no extra dependency needed,
unlike pulling in pywin32 just for this), so anyone logged into that same
Windows account can still decrypt it (that's what lets the app itself keep
working) — but a config.json copied to another machine, opened by another
Windows account, or opened in Notepad is just unreadable ciphertext. That
covers the actual goal (nobody casually hand-edits settings in a text
editor) without pretending to be real DRM: a technically determined person
logged into the same account could still call these same OS APIs directly.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _to_blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _extract_and_free(blob: _DATA_BLOB) -> bytes:
    result = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return result


def protect(data: bytes) -> bytes:
    blob_in = _to_blob(data)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return _extract_and_free(blob_out)


def unprotect(data: bytes) -> bytes:
    blob_in = _to_blob(data)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return _extract_and_free(blob_out)
