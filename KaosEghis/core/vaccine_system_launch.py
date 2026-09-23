"""Explicit browser launch helpers for the external vaccine systems."""

from __future__ import annotations

from dataclasses import dataclass
import posixpath
from typing import Callable
from urllib.parse import urlparse
import time
import webbrowser

from KaosEghis.core.kdca_browser import _document_url, foreground_handle
from KaosEghis.core.kdca_portal_launch import KdcaPortalLaunch

@dataclass(frozen=True)
class VaccineSystemLaunchResult:
    success: bool
    message: str


_SYSTEMS = {
    "general": ("General vaccine system", "vaccine_general_system_launch_url"),
    "influenza": ("Influenza vaccine system", "vaccine_influenza_system_launch_url"),
    "covid": ("COVID vaccine system", "vaccine_covid_system_launch_url"),
}


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


def open_vaccine_system(
    settings: dict[str, str],
    system: str,
    *,
    opener: Callable[..., bool] = webbrowser.open,
    browser_handle: int | None = None,
    ready: Callable[[dict[str, str], str], bool] | None = None,
    timeout_seconds: float = 30.0,
    progress: Callable[[str], None] = lambda _message: None,
    cancelled: Callable[[], bool] = lambda: False,
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
    if cancelled():
        return VaccineSystemLaunchResult(False, "Vaccine system launch cancelled.")
    if ready is None and system in {"general", "covid"}:
        handles = _native_handles(settings, system)
        if len(handles) > 1:
            return VaccineSystemLaunchResult(False, f"Multiple {label} windows are open. Close duplicates and retry.")
        if len(handles) == 1:
            focused = not cancelled() and _focus_native_window(handles[0])
            return VaccineSystemLaunchResult(focused, (
                f"{label} is already open and focused." if focused else
                f"{label} is already open, but focus could not be confirmed. No duplicate launch was sent."
            ))
    if browser_handle:
        return _open_from_portal(
            settings, system, label, browser_handle, ready=ready,
            timeout_seconds=timeout_seconds, progress=progress, cancelled=cancelled,
        )
    ready = ready or vaccine_system_is_ready
    # Native systems need not be launched twice. No resident number is entered.
    if system in {"general", "covid"} and ready(settings, system):
        return VaccineSystemLaunchResult(True, f"{label} is already open.")
    progress(f"{label}: opening saved deep link...")
    try:
        opened = bool(opener(url, new=2, autoraise=True))
    except Exception:
        opened = False
    if not opened:
        return VaccineSystemLaunchResult(False, f"Could not open {label}. Check browser focus or a blocking popup, then retry.")
    progress(f"{label}: waiting for system window...")
    deadline = time.monotonic() + max(timeout_seconds, 0.1)
    while time.monotonic() < deadline and not cancelled():
        if ready(settings, system):
            return VaccineSystemLaunchResult(True, f"{label} opened and detected.")
        time.sleep(0.5)
    return VaccineSystemLaunchResult(False, (
        "Vaccine system launch cancelled." if cancelled() else
        f"{label} was not detected after opening its deep link. Check the browser for "
        "a launch permission, notice, or expired session. No duplicate launch was sent."
    ))


def _open_from_portal(settings, system, label, browser_handle, *, ready,
                      timeout_seconds, progress, cancelled):
    try:
        portal = KdcaPortalLaunch(settings, system, browser_handle, cancelled=cancelled)
        progress(f"{label}: {portal.waiting_message}...")
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        while time.monotonic() < deadline and not cancelled():
            if system != "influenza" or portal.phase != "portal_menu":
                detected = ready(settings, system) if ready else vaccine_system_is_ready(
                    settings, system,
                    windows=portal.windows() if system == "influenza" else None,
                )
                if detected and not cancelled():
                    return VaccineSystemLaunchResult(True, f"{label} opened and detected.")
            previous_phase = portal.phase
            error = portal.advance()
            if error:
                return VaccineSystemLaunchResult(False, error)
            if previous_phase != portal.phase:
                progress(f"{label}: {portal.waiting_message}...")
            time.sleep(0.5)
        message = (
            "Vaccine system launch cancelled." if cancelled() else
            f"{label}: {portal.waiting_message}, but it was not detected in time. "
            "Check for a notice or launch permission. If a system-selection page is open, "
            "check its launch-control text in Vaccine > Settings > System targets. "
            "No direct URL or duplicate launch was sent."
        )
    except Exception:
        message = "KDCA launch could not be verified. Check the portal window and retry. No direct URL fallback was sent."
    return VaccineSystemLaunchResult(False, message)


def vaccine_system_is_ready(settings: dict[str, str], system: str, *, browser_handle=None, windows=None) -> bool:
    if system in {"general", "covid"}:
        return len(_native_handles(settings, system)) == 1
    if system != "influenza":
        return False
    try:
        from pywinauto import Desktop

        url = settings.get("vaccine_influenza_system_launch_url", "")
        target_id = settings.get("vaccine_influenza_system_resident_automation_id", "edtPtntRrn1")
        if not url or not target_id:
            return False
        expected = urlparse(url)
        application_path = posixpath.dirname(expected.path).rstrip("/") + "/"
        for window in windows if windows is not None else Desktop(backend="uia").windows():
            if str(window.element_info.class_name) not in {"Chrome_WidgetWin_1", "MozillaWindowClass"}:
                continue
            if browser_handle and int(window.handle or 0) != browser_handle:
                continue
            for document in window.descendants(control_type="Document"):
                actual = urlparse(_document_url(document))
                if (not document.is_visible()
                        or (actual.scheme, actual.netloc.casefold()) != (expected.scheme, expected.netloc.casefold())
                        or not actual.path.startswith(application_path)):
                    continue
                matches = document.descendants(auto_id=target_id, control_type="Edit")
                if len(matches) == 1 and matches[0].is_visible() and matches[0].is_enabled():
                    return True
    except Exception:
        pass
    return False


def _native_handles(settings: dict[str, str], system: str) -> list[int]:
    title = settings.get(f"vaccine_{system}_system_window_title", "").strip()
    class_name = settings.get(f"vaccine_{system}_system_window_class", "").strip()
    if not title or not class_name:
        return []
    try:
        import win32gui

        return find_native_vaccine_windows(win32gui, title, class_name)
    except Exception:
        return []


def _focus_native_window(handle: int) -> bool:
    try:
        from pywinauto import Desktop

        Desktop(backend="win32").window(handle=handle).wrapper_object().set_focus()
        return foreground_handle() == handle
    except Exception:
        return False
