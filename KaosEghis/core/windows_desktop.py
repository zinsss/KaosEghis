from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys


DESKTOP_UNAVAILABLE_MESSAGE = (
    "Windows desktop is locked or unavailable. Unlock Windows and retry manually."
)


def interactive_desktop_error() -> str | None:
    """Check the input desktop without switching desktops or sending input."""

    if sys.platform != "win32":
        return None
    try:
        if _input_desktop_name().casefold() == "default":
            return None
        return DESKTOP_UNAVAILABLE_MESSAGE
    except Exception:
        return DESKTOP_UNAVAILABLE_MESSAGE


def _input_desktop_name() -> str:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL

    desktop = user32.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        if not user32.GetUserObjectInformationW(
            desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed),  # UOI_NAME
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return name.value
    finally:
        user32.CloseDesktop(desktop)
