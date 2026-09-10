"""Guarded session-reset clicks for the native vaccination systems.

The General and COVID applications time out independently.  This module is
deliberately limited to their configured non-clinical session-reset points; it
never reads or writes patient data, enters credentials, or submits a record.
"""

from __future__ import annotations

from dataclasses import dataclass


SESSION_KEEPER_INTERVAL_MS = 90 * 60 * 1000


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


def configured_session_reset_targets(
    settings: dict[str, str],
) -> tuple[VaccineSessionResetTarget, ...]:
    """Return the two native systems that have a known idle-session reset.

    Influenza is browser-based and has no captured idle-reset operation, so it
    is intentionally not represented here.
    """

    return (
        _target_from_settings(settings, "general", "General vaccine system"),
        _target_from_settings(settings, "covid", "COVID system"),
    )


def reset_vaccine_session(target: VaccineSessionResetTarget) -> VaccineSessionResetResult:
    """Click a reset point only after exact native-window verification.

    The reset is skipped when the app is closed, ambiguous, minimized, moved,
    or covered at the configured point.  This keeps a saved absolute coordinate
    from becoming an unqualified global click.
    """

    if not target.is_configured:
        return _result(target, "configuration_required", "Session reset is not configured.")

    try:
        import win32gui
    except Exception:
        return _result(target, "unavailable", "Native window checking is unavailable.")

    window_handles = _matching_window_handles(win32gui, target)
    if not window_handles:
        return _result(target, "not_open", "System is not open; no session reset was sent.")
    if len(window_handles) > 1:
        return _result(target, "ambiguous", "More than one matching system window is open.")

    window_handle = window_handles[0]
    if not _reset_point_is_ready(win32gui, window_handle, target):
        return _result(
            target,
            "point_not_ready",
            "Session reset point is not available in the configured system window.",
        )

    if not _click_screen_coordinate(target.reset_x, target.reset_y):
        return _result(target, "input_failed", "Session reset click could not be sent.")
    return _result(target, "reset_sent", "Session reset sent.", clicked=True)


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
    handles: list[int] = []

    def inspect(window_handle: int, _unused: object) -> bool:
        try:
            is_visible = bool(win32gui.IsWindowVisible(window_handle))
            title = str(win32gui.GetWindowText(window_handle) or "").strip()
            class_name = str(win32gui.GetClassName(window_handle) or "").strip()
        except Exception:
            return True
        if (
            is_visible
            and title == target.window_title
            and class_name == target.window_class
        ):
            handles.append(int(window_handle))
        return True

    try:
        win32gui.EnumWindows(inspect, None)
    except Exception:
        return []
    return handles


def _reset_point_is_ready(
    win32gui, window_handle: int, target: VaccineSessionResetTarget
) -> bool:
    try:
        if bool(win32gui.IsIconic(window_handle)):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(window_handle)
        if not (left <= target.reset_x < right and top <= target.reset_y < bottom):
            return False
        point_handle = win32gui.WindowFromPoint((target.reset_x, target.reset_y))
        if not point_handle:
            return False
        return _root_window_handle(win32gui, int(point_handle)) == window_handle
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
