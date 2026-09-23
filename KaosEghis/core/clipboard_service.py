from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import os
import time


@dataclass
class ClipboardSnapshot:
    text: str


def copy_text(text: str) -> ClipboardSnapshot:
    snapshot = ClipboardSnapshot(_best_effort_read_clipboard_text())
    _write_clipboard_text_with_retry(text)
    return snapshot


def restore_clipboard(snapshot: ClipboardSnapshot) -> None:
    _write_clipboard_text_with_retry(snapshot.text)


def _read_clipboard_text() -> str:
    if os.name == "nt":
        return _read_windows_clipboard_text()
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.clipboard().text()


def _best_effort_read_clipboard_text() -> str:
    try:
        return _read_clipboard_text()
    except Exception:
        return ""


def _write_clipboard_text_with_retry(text: str) -> None:
    last_error: Exception | None = None
    for _attempt in range(10):
        try:
            _write_clipboard_text(text)
            if os.name == "nt":
                return
            if _read_clipboard_text() == text:
                return
        except Exception as error:
            last_error = error
        time.sleep(0.05)
    if last_error is not None:
        raise RuntimeError("Clipboard is busy.") from last_error
    raise RuntimeError("Clipboard is busy.")


def _write_clipboard_text(text: str) -> None:
    if os.name == "nt":
        _write_windows_clipboard_text(text)
        return
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText(text)


def _read_windows_clipboard_text() -> str:
    user32, kernel32 = _windows_clipboard_api()
    cf_unicode_text = 13

    _open_windows_clipboard_with_retry(user32)
    try:
        handle = user32.GetClipboardData(cf_unicode_text)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return ""
        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _write_windows_clipboard_text(text: str) -> None:
    user32, kernel32 = _windows_clipboard_api()
    cf_unicode_text = 13
    gmem_moveable = 0x0002

    data = text + "\0"
    size = len(data) * ctypes.sizeof(ctypes.c_wchar)

    _open_windows_clipboard_with_retry(user32)
    handle = None
    try:
        if not user32.EmptyClipboard():
            raise RuntimeError("EmptyClipboard failed.")
        handle = kernel32.GlobalAlloc(gmem_moveable, size)
        if not handle:
            raise RuntimeError("GlobalAlloc failed.")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("GlobalLock failed.")
        try:
            ctypes.memmove(locked, ctypes.create_unicode_buffer(data), size)
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(cf_unicode_text, handle):
            raise RuntimeError("SetClipboardData failed.")
        handle = None
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()


def _open_windows_clipboard_with_retry(user32: ctypes.WinDLL) -> None:
    for _attempt in range(20):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.02)
    raise RuntimeError("OpenClipboard failed.")


def _windows_clipboard_api() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    return user32, kernel32
