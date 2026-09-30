"""Manual, guarded vaccination-system session maintenance.

The General and COVID applications time out independently.  This module is
limited to their configured session-reset points. Flu refresh requires operator
approval from its caller (the manual Reset Now press). Nothing schedules input or retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import posixpath
from urllib.parse import urlparse

from KaosEghis.core.kdca_browser import (
    _document_url, document_identity, foreground_handle, iter_documents_for_url,
)

from KaosEghis.core.vaccine_system_launch import _focus_native_window, find_native_vaccine_windows
from KaosEghis.core.windows_desktop import interactive_desktop_error
from KaosEghis.core.windows_virtual_desktop import (
    ensure_first_virtual_desktop,
    first_virtual_desktop_is_active,
)


SESSION_KEEPER_IDLE_MS = 5000


@dataclass(frozen=True)
class VaccineSessionResetTarget:
    """A stable native-window selector and its safe session-reset point."""

    key: str
    label: str
    window_title: str
    window_class: str
    reset_x: int
    reset_y: int

    @property
    def is_configured(self) -> bool:
        return bool(
            self.window_title.strip()
            and self.window_class.strip()
            and self.reset_x > 0
            and self.reset_y > 0
        )


@dataclass(frozen=True)
class VaccineSessionResetResult:
    target_key: str
    status: str
    message: str
    clicked: bool = False

    @property
    def sent(self) -> bool:
        return self.clicked or self.status == "refresh_sent"


def configured_session_reset_targets(
    settings: dict[str, str],
) -> tuple[VaccineSessionResetTarget, ...]:
    """Return the two native systems that have a known idle-session reset.

    Influenza uses the manual browser-refresh operation.
    """

    return (
        _target_from_settings(settings, "general", "General vaccine system"),
        _target_from_settings(settings, "covid", "COVID system"),
    )


def reset_vaccine_session(
    target: VaccineSessionResetTarget, *, require_idle: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
) -> VaccineSessionResetResult:
    """Click a reset point only after exact native-window verification.

    Bring the exact target forward before checking point ownership. Closed,
    ambiguous, minimized, moved, or still-covered targets are skipped.
    """

    if cancelled():
        return _result(target, "cancelled", "Reset stopped; no click sent.")
    if not target.is_configured:
        return _result(target, "configuration_required", "Session reset is not configured.")
    if interactive_desktop_error() is not None:
        return _result(target, "desktop_unavailable", "Unlock Windows before resetting sessions.")

    try:
        import win32gui
    except Exception:
        return _result(target, "unavailable", "Native window checking is unavailable.")

    window_handles = _matching_window_handles(win32gui, target)
    if not window_handles:
        return _result(target, "not_open", "System is not open; no session reset was sent.")
    if len(window_handles) > 1:
        return _result(target, "ambiguous", "More than one matching system window is open.")

    idle = _input_is_idle(SESSION_KEEPER_IDLE_MS if require_idle else 0)
    if idle is None:
        return _result(target, "unavailable", "Input activity could not be checked; no reset was sent.")
    if not idle:
        return _result(target, "input_busy", "Keyboard or mouse is in use; no reset sent. Retry when ready.")

    if cancelled():
        return _result(target, "cancelled", "Reset stopped; no click sent.")
    desktop = ensure_first_virtual_desktop()
    if not desktop.success:
        return _result(target, desktop.status, desktop.message)
    # Desktop switching may reveal different windows; do not reuse the old view.
    if _matching_window_handles(win32gui, target) != window_handles:
        return _result(target, "point_not_ready", "System window changed; no reset was sent.")
    window_handle = window_handles[0]
    if not _reset_point_in_window(win32gui, window_handle, target):
        return _result(target, "point_not_ready", "Reset point is outside the available window; check System targets.")
    if cancelled():
        return _result(target, "cancelled", "Reset stopped; no click sent.")
    if not _focus_native_window(window_handle):
        return _result(target, "focus_failed", "Could not bring the system forward; no reset sent.")
    if not _reset_point_is_ready(win32gui, window_handle, target):
        return _result(target, "point_not_ready", "Reset point is still covered or unavailable on Desktop 1; no reset sent.")
    idle = _input_is_idle(SESSION_KEEPER_IDLE_MS if require_idle else 0)
    if idle is not True:
        return _result(target, "input_busy", "Input activity changed; no reset sent. Retry when ready.")
    if not first_virtual_desktop_is_active():
        return _result(target, "desktop_switch_failed", "Desktop 1 is no longer active; no reset was sent.")
    # Recheck point ownership immediately before input, after all other guards.
    if not _reset_point_is_ready(win32gui, window_handle, target):
        return _result(target, "point_not_ready", "Session reset point changed; no reset was sent.")
    if cancelled():
        return _result(target, "cancelled", "Reset stopped; no click sent.")
    if interactive_desktop_error() is not None or foreground_handle() != window_handle:
        return _result(target, "focus_failed", "System focus changed; no reset sent.")
    if cancelled():
        return _result(target, "cancelled", "Reset stopped; no click sent.")
    if not _click_screen_coordinate(target.reset_x, target.reset_y):
        return _result(target, "input_failed", "Session reset click could not be sent.")
    return _result(target, "reset_sent", "Session reset sent.", clicked=True)


def _input_is_idle(minimum_idle_ms: int) -> bool | None:
    """Read input timing/key-down state only; never capture text or suppress input."""

    try:
        import win32api

        if any(win32api.GetAsyncKeyState(key) & 0x8000 for key in range(1, 256)):
            return False
        elapsed = (win32api.GetTickCount() - win32api.GetLastInputInfo()) & 0xFFFFFFFF
        # An input timestamp can be ahead of the sampled tick count. Fail closed.
        return minimum_idle_ms <= elapsed < 0x80000000
    except Exception:
        return None


def refresh_influenza_session(
    settings: dict[str, str], *, confirm: Callable[[], bool],
    cancelled: Callable[[], bool] = lambda: False,
) -> VaccineSessionResetResult:
    """Send F5 once to a verified Flu tab after caller-supplied operator approval."""
    def result(status: str, message: str) -> VaccineSessionResetResult:
        return VaccineSessionResetResult("influenza", status, message)

    if cancelled():
        return result("cancelled", "Flu refresh stopped; no F5 sent.")
    if interactive_desktop_error() is not None:
        return result("desktop_unavailable", "Unlock Windows before refreshing Flu.")
    url = settings.get("vaccine_influenza_system_launch_url", "").strip()
    expected = urlparse(url)
    prefix = posixpath.dirname(expected.path).rstrip("/") + "/"
    if expected.scheme != "https" or not expected.netloc or prefix == "/":
        return result("configuration_required", "Flu launch URL is not configured safely.")
    title = settings.get("vaccine_influenza_system_window_title", "").strip().casefold()

    def trusted_document(document, handle: int) -> bool:
        actual = urlparse(_document_url(document))
        if (
            not document.is_visible() or document_identity(document) is None
            or (actual.scheme, actual.netloc.casefold()) != (expected.scheme, expected.netloc.casefold())
            or not actual.path.startswith(prefix)
        ):
            return False
        # A Flu iframe inside a portal is not permission to reload the whole portal.
        parent = document.parent()
        for _ in range(32):
            if parent is None or parent.element_info.control_type == "Document":
                return False
            if parent.element_info.control_type == "Window":
                return int(getattr(parent, "handle", 0) or 0) == handle
            parent = parent.parent()
        return False

    try:
        from pywinauto import Desktop
        import pyautogui

        matches = []
        for window in Desktop(backend="uia").windows():
            if cancelled():
                return result("cancelled", "Flu refresh stopped; no F5 sent.")
            if window.element_info.class_name not in {"Chrome_WidgetWin_1", "MozillaWindowClass"}:
                continue
            if not window.is_visible() or not window.is_enabled():
                continue
            if title and title not in window.window_text().casefold():
                continue
            for document in iter_documents_for_url(window, url):
                if cancelled():
                    return result("cancelled", "Flu refresh stopped; no F5 sent.")
                if trusted_document(document, int(window.handle)):
                    matches.append((window, document))
        if cancelled():
            return result("cancelled", "Flu refresh stopped; no F5 sent.")
        if not matches:
            return result("not_open", "No visible verified Flu tab; no refresh sent.")
        if len(matches) != 1:
            return result("ambiguous", "Multiple Flu pages match; no refresh sent.")
        window, document = matches[0]
        identity = document_identity(document)
        handle = int(window.handle)
        if not confirm():
            return result("declined", "Flu refresh declined; no input sent.")
        if cancelled():
            return result("cancelled", "Flu refresh stopped; no F5 sent.")
        if interactive_desktop_error() is not None or _input_is_idle(0) is not True:
            return result("input_busy", "Desktop or input changed; no refresh sent.")
        desktop = ensure_first_virtual_desktop()
        if not desktop.success:
            return result(desktop.status, desktop.message)
        if cancelled():
            return result("cancelled", "Flu refresh stopped; no F5 sent.")
        window.set_focus()
        if (
            interactive_desktop_error() is not None
            or not first_virtual_desktop_is_active() or _input_is_idle(0) is not True
            or foreground_handle() != handle or not window.is_enabled()
            or (title and title not in window.window_text().casefold())
            or document_identity(document) != identity or not trusted_document(document, handle)
        ):
            return result("page_changed", "Flu page/focus changed; no refresh sent.")
        if (
            cancelled() or foreground_handle() != handle or _input_is_idle(0) is not True
            or not first_virtual_desktop_is_active() or interactive_desktop_error() is not None
        ):
            return result("page_changed", "Focus/input changed before F5; no refresh sent.")
        if cancelled():
            return result("cancelled", "Flu refresh stopped; no F5 sent.")
        pyautogui.press("f5")
        return result("refresh_sent", "F5 sent; session renewal is not verified.")
    except Exception:
        return result("unavailable", "Flu refresh could not be verified; no automatic retry.")


def _target_from_settings(
    settings: dict[str, str], key: str, label: str
) -> VaccineSessionResetTarget:
    prefix = f"vaccine_{key}_system"
    return VaccineSessionResetTarget(
        key=key,
        label=label,
        window_title=str(settings.get(f"{prefix}_window_title", "")).strip(),
        window_class=str(settings.get(f"{prefix}_window_class", "")).strip(),
        reset_x=_coordinate(settings.get(f"{prefix}_keepalive_x")),
        reset_y=_coordinate(settings.get(f"{prefix}_keepalive_y")),
    )


def _coordinate(value: object) -> int:
    try:
        return max(0, int(str(value or "0")))
    except (TypeError, ValueError):
        return 0


def _matching_window_handles(win32gui, target: VaccineSessionResetTarget) -> list[int]:
    return find_native_vaccine_windows(win32gui, target.window_title, target.window_class)


def _reset_point_is_ready(
    win32gui, window_handle: int, target: VaccineSessionResetTarget
) -> bool:
    try:
        if not _reset_point_in_window(win32gui, window_handle, target):
            return False
        point_handle = win32gui.WindowFromPoint((target.reset_x, target.reset_y))
        if not point_handle:
            return False
        if not win32gui.IsWindowEnabled(point_handle):
            return False
        return _root_window_handle(win32gui, int(point_handle)) == window_handle
    except Exception:
        return False


def _reset_point_in_window(win32gui, window_handle: int, target: VaccineSessionResetTarget) -> bool:
    try:
        if win32gui.IsIconic(window_handle) or not win32gui.IsWindowEnabled(window_handle):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(window_handle)
        return left <= target.reset_x < right and top <= target.reset_y < bottom
    except Exception:
        return False


def _root_window_handle(win32gui, window_handle: int) -> int:
    try:
        import win32con

        return int(win32gui.GetAncestor(window_handle, win32con.GA_ROOT))
    except Exception:
        return window_handle


def _click_screen_coordinate(x: int, y: int) -> bool:
    try:
        import pyautogui

        pyautogui.click(x=x, y=y, duration=0)
        return True
    except Exception:
        return False


def _result(
    target: VaccineSessionResetTarget,
    status: str,
    message: str,
    *,
    clicked: bool = False,
) -> VaccineSessionResetResult:
    return VaccineSessionResetResult(
        target_key=target.key,
        status=status,
        message=message,
        clicked=clicked,
    )
