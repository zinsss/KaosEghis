from __future__ import annotations

import ctypes
import ctypes.wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal


class LauncherHotkeyRuntime(QObject):
    """Expose the Launcher through one explicit Windows global shortcut."""

    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener: _WindowsLauncherHotkeyListener | None = None

    def start(self) -> bool:
        if not _is_windows_platform():
            return False
        if self._listener is not None:
            return True
        listener = _WindowsLauncherHotkeyListener(self.activated.emit)
        if not listener.start():
            return False
        self._listener = listener
        return True

    def stop(self) -> None:
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None


class SoclHotkeyRuntime(QObject):
    """Expose the separate SOCL window through a Windows global shortcut."""

    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener: _WindowsSoclHotkeyListener | None = None

    def start(self) -> bool:
        if not _is_windows_platform():
            return False
        if self._listener is not None:
            return True
        listener = _WindowsSoclHotkeyListener(self.activated.emit)
        if not listener.start():
            return False
        self._listener = listener
        return True

    def stop(self) -> None:
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None


class _WindowsAppHotkeyListener(QAbstractNativeEventFilter):
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY = 0x0312
    HOTKEY_ID = 0
    VIRTUAL_KEY = 0

    def __init__(self, callback, *, application=None, user32=None) -> None:
        super().__init__()
        self._callback = callback
        self._application = application
        self._user32 = user32
        self._filter_installed = False
        self._registered = False

    def start(self) -> bool:
        if self._registered:
            return True
        application = self._application or QCoreApplication.instance()
        user32 = self._user32
        if user32 is None and _is_windows_platform():
            user32 = ctypes.windll.user32
        if application is None or user32 is None:
            return False

        application.installNativeEventFilter(self)
        self._filter_installed = True
        registered = bool(
            user32.RegisterHotKey(
                None,
                self.HOTKEY_ID,
                self.MOD_CONTROL
                | self.MOD_ALT
                | self.MOD_SHIFT
                | self.MOD_NOREPEAT,
                self.VIRTUAL_KEY,
            )
        )
        if not registered:
            application.removeNativeEventFilter(self)
            self._filter_installed = False
            return False

        self._application = application
        self._user32 = user32
        self._registered = True
        return True

    def stop(self) -> None:
        if self._registered and self._user32 is not None:
            try:
                self._user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:
                pass
        self._registered = False
        if self._filter_installed and self._application is not None:
            try:
                self._application.removeNativeEventFilter(self)
            except Exception:
                pass
        self._filter_installed = False

    def nativeEventFilter(self, _event_type, message):
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0
        if msg.message != self.WM_HOTKEY or int(msg.wParam) != self.HOTKEY_ID:
            return False, 0
        self._callback()
        return True, 0


class _WindowsLauncherHotkeyListener(_WindowsAppHotkeyListener):
    HOTKEY_ID = 0x4B4C
    VK_F11 = 0x7A
    VIRTUAL_KEY = VK_F11


class _WindowsSoclHotkeyListener(_WindowsAppHotkeyListener):
    HOTKEY_ID = 0x4B53
    VK_F10 = 0x79
    VIRTUAL_KEY = VK_F10


def _is_windows_platform() -> bool:
    try:
        return hasattr(ctypes, "windll")
    except Exception:
        return False
