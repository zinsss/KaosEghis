from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

from KaosEghis.core.credential_vault import (
    CredentialVault,
    CredentialVaultSession,
    InvalidMasterPasswordError,
)


_ACTIVE_VAULT_SESSION: CredentialVaultSession | None = None


def get_unlocked_credential_password(service_name: str) -> str | None:
    session = _ACTIVE_VAULT_SESSION
    if session is None:
        return None
    entry = session.get_entry(service_name.strip())
    if entry is None or not entry.password:
        return None
    return entry.password


def has_unlocked_credential(service_name: str) -> bool:
    """Report credential availability without returning the secret."""

    session = _ACTIVE_VAULT_SESSION
    if session is None:
        return False
    entry = session.get_entry(service_name.strip())
    return bool(entry is not None and entry.password)


@dataclass(frozen=True)
class ForegroundWindowContext:
    hwnd: int | None
    title: str


class PwRuntime(QObject):
    state_changed = Signal(bool)
    action_requested = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.vault = CredentialVault()
        self.session: CredentialVaultSession | None = None
        self._hotkey_listener: _WindowsPwHotkeyListener | None = None
        self._last_context = ForegroundWindowContext(None, "")
        self.action_requested.connect(self._emit_noop)

    def start(self) -> None:
        if not _is_windows_platform():
            return
        if self._hotkey_listener is not None:
            return
        listener = _WindowsPwHotkeyListener(self._on_hotkey)
        if listener.start():
            self._hotkey_listener = listener

    def stop(self) -> None:
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

    @property
    def is_unlocked(self) -> bool:
        return self.session is not None

    def initialize_or_unlock(self, master_password: str) -> tuple[bool, str]:
        global _ACTIVE_VAULT_SESSION
        try:
            if self.vault.exists():
                self.session = self.vault.unlock(master_password)
                _ACTIVE_VAULT_SESSION = self.session
                self.state_changed.emit(True)
                return True, "Credential vault unlocked."
            self.session = self.vault.create(master_password)
            _ACTIVE_VAULT_SESSION = self.session
            self.state_changed.emit(True)
            return True, "Credential vault created and unlocked."
        except InvalidMasterPasswordError:
            self.session = None
            _ACTIVE_VAULT_SESSION = None
            self.state_changed.emit(False)
            return False, "Master password is invalid."
        except Exception as error:
            self.session = None
            _ACTIVE_VAULT_SESSION = None
            self.state_changed.emit(False)
            return False, f"Credential vault error: {error}"

    def lock(self) -> None:
        global _ACTIVE_VAULT_SESSION
        active_session = self.session
        self.session = None
        if _ACTIVE_VAULT_SESSION is active_session:
            _ACTIVE_VAULT_SESSION = None
        self.state_changed.emit(False)

    def current_context(self) -> ForegroundWindowContext:
        return self._last_context

    def _on_hotkey(self) -> None:
        self._last_context = capture_foreground_window_context()
        self.action_requested.emit(self._last_context)

    @staticmethod
    def _emit_noop(_context) -> None:
        return None


class _WindowsPwHotkeyListener(QAbstractNativeEventFilter):
    HOTKEY_ID = 0x5057
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    VK_F12 = 0x7B
    WM_HOTKEY = 0x0312

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
                self.MOD_CONTROL | self.MOD_ALT | self.MOD_SHIFT | self.MOD_NOREPEAT,
                self.VK_F12,
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


def capture_foreground_window_context() -> ForegroundWindowContext:
    if not _is_windows_platform():
        return ForegroundWindowContext(None, "")
    user32 = ctypes.windll.user32
    hwnd = int(user32.GetForegroundWindow() or 0)
    if hwnd == 0:
        return ForegroundWindowContext(None, "")
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return ForegroundWindowContext(hwnd, buffer.value or "")


def _is_windows_platform() -> bool:
    try:
        return hasattr(ctypes, "windll")
    except Exception:
        return False
