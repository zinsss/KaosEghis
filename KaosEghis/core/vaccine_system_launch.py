"""Explicit browser launch helpers for the external vaccine systems."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
from urllib.parse import urlparse
import webbrowser


@dataclass(frozen=True)
class VaccineSystemLaunchResult:
    success: bool
    message: str


_SYSTEMS = {
    "general": ("General vaccine system", "vaccine_general_system_launch_url"),
    "influenza": ("Influenza vaccine system", "vaccine_influenza_system_launch_url"),
    "covid": ("COVID vaccine system", "vaccine_covid_system_launch_url"),
}

_POSITIONING_KEYS = {
    "general": ("left", "left", "left", "down"),
    "covid": ("left", "left", "left", "down", "right"),
}


class VaccineSystemPositioner:
    """Advance an explicit launch's positioning without blocking the Qt event loop."""

    def __init__(
        self,
        settings: dict[str, str],
        system: str,
        *,
        window_api: Any | None = None,
        key_sender: Callable[[str], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._label = _SYSTEMS.get(system, ("Vaccine system", ""))[0]
        self._title = str(settings.get(f"vaccine_{system}_system_window_title", "")).strip()
        self._class = str(settings.get(f"vaccine_{system}_system_window_class", "")).strip()
        self._keys = _POSITIONING_KEYS.get(system, ())
        self._api = window_api
        self._send_key = key_sender or _send_positioning_key
        self._clock = clock
        self._deadline = clock() + timeout_seconds
        self._handle: int | None = None
        self._next_action_at = 0.0
        self._focused = False
        self._key_index = 0
        self._result: VaccineSystemLaunchResult | None = None

    def advance(self) -> VaccineSystemLaunchResult | None:
        """Return None while waiting, or a terminal result; never send a blind hotkey."""

        if self._result is not None:
            return self._result
        if not self._keys or not self._title or not self._class:
            return self._finish(False, "Window positioning is not configured.")
        now = self._clock()
        if now >= self._deadline:
            return self._finish(False, "Window positioning timed out; no further keys were sent.")
        if self._api is None:
            try:
                import win32gui

                self._api = win32gui
            except ImportError:
                return self._finish(False, "Native window positioning is unavailable.")

        handles = find_native_vaccine_windows(self._api, self._title, self._class)
        if len(handles) > 1:
            return self._finish(False, "Multiple matching windows; positioning stopped.")
        if self._handle is None:
            if not handles:
                return None
            self._handle = handles[0]
            self._next_action_at = now + 1.0
            return None
        if handles != [self._handle]:
            return self._finish(False, "System window changed or closed; positioning stopped.")
        if now < self._next_action_at:
            return None

        try:
            if not self._focused:
                if self._api.IsIconic(self._handle):
                    self._api.ShowWindow(self._handle, 9)  # SW_RESTORE
                if self._api.GetForegroundWindow() != self._handle:
                    self._api.BringWindowToTop(self._handle)
                    self._api.SetForegroundWindow(self._handle)
                self._focused = True
            # Never reacquire focus partway through the sequence: the operator
            # may have moved to another application or opened a modal dialog.
            if self._api.GetForegroundWindow() != self._handle:
                return self._finish(False, "System is not focused; positioning stopped.")
            if not self._send_key(self._keys[self._key_index]):
                return self._finish(False, "Positioning shortcut could not be sent.")
        except Exception:
            return self._finish(False, "Window positioning failed; no further keys were sent.")

        self._key_index += 1
        if self._key_index == len(self._keys):
            return self._finish(True, "Workflow positioning shortcuts sent.")
        self._next_action_at = self._clock() + 0.2
        return None

    def _finish(self, success: bool, message: str) -> VaccineSystemLaunchResult:
        self._result = VaccineSystemLaunchResult(success, f"{self._label}: {message}")
        return self._result


def find_native_vaccine_windows(window_api, title: str, class_name: str) -> list[int]:
    """Find visible top-level windows with both configured native identifiers."""

    handles: list[int] = []

    def inspect(handle: int, _unused: object) -> bool:
        try:
            if (
                window_api.IsWindowVisible(handle)
                and str(window_api.GetWindowText(handle) or "").strip() == title
                and str(window_api.GetClassName(handle) or "").strip() == class_name
            ):
                handles.append(int(handle))
        except Exception:
            pass
        return True

    try:
        window_api.EnumWindows(inspect, None)
    except Exception:
        return []
    return handles


def _send_positioning_key(direction: str) -> bool:
    try:
        import pyautogui

        try:
            pyautogui.hotkey("win", direction, interval=0.01, _pause=False)
        finally:
            try:
                pyautogui.keyUp(direction, _pause=False)
            finally:
                pyautogui.keyUp("win", _pause=False)
        return True
    except Exception:
        return False


def open_vaccine_system(
    settings: dict[str, str],
    system: str,
    *,
    opener: Callable[..., bool] = webbrowser.open,
) -> VaccineSystemLaunchResult:
    """Open one configured external system without passing patient data or credentials."""

    target = _SYSTEMS.get(system)
    if target is None:
        return VaccineSystemLaunchResult(False, "Vaccine system is not configured.")
    label, setting_key = target
    url = str(settings.get(setting_key, "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return VaccineSystemLaunchResult(
            False,
            f"{label} launch URL is not configured.",
        )
    try:
        opened = bool(opener(url, new=2, autoraise=True))
    except Exception:
        opened = False
    if not opened:
        return VaccineSystemLaunchResult(False, f"Could not open {label}.")
    return VaccineSystemLaunchResult(
        True,
        f"{label} opened. Complete sign-in and the remaining workflow manually.",
    )
