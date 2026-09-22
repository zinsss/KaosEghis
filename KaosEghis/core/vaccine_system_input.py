"""Explicit, guarded patient lookup after vaccine-label printing."""

from __future__ import annotations

from dataclasses import dataclass, field
import posixpath
from time import monotonic, sleep
from typing import Callable
from urllib.parse import urlparse

from KaosEghis.core.kdca_browser import (
    _document_url, document_identity, focused_element, foreground_handle, has_keyboard_focus,
    iter_documents_for_url,
)
from KaosEghis.core.kdca_certificate_login import (
    _screen_point_belongs_to_window,
    _send_unicode_text,
)
from KaosEghis.core.vaccine_patient_context import resident_id_for_vaccine_system
from KaosEghis.core.uia_fast_lookup import find_uia_elements_by_automation_ids
from KaosEghis.core.vaccine_session_keeper import _input_is_idle
from KaosEghis.core.vaccine_system_launch import _focus_native_window, find_native_vaccine_windows
from KaosEghis.core.windows_desktop import interactive_desktop_error
from KaosEghis.core.windows_virtual_desktop import (
    ensure_first_virtual_desktop,
    first_virtual_desktop_is_active,
)


SYSTEM_LABELS = {
    "general": "General vaccine system",
    "influenza": "Influenza system",
    "covid": "COVID system",
}


@dataclass(frozen=True)
class VaccineHandoffRequest:
    system: str
    resident_id: str = field(repr=False)


@dataclass(frozen=True)
class VaccineHandoffResult:
    success: bool
    message: str


@dataclass(frozen=True)
class _InputTarget:
    activate: Callable[[Callable[[], bool]], bool]
    ready: Callable[[], bool]
    read_value: Callable[[], str] | None = None
    activation_error: Callable[[], str] | None = None


def handoff_request_for_record(record) -> VaccineHandoffRequest:
    systems = {
        "national_influenza": "influenza",
        "national_covid": "covid",
        "general_influenza": "general",
        "general": "general",
    }
    return VaccineHandoffRequest(
        systems.get(record.program_type, ""), record.patient_resident_id or ""
    )


def enter_vaccine_resident(
    settings: dict[str, str],
    request: VaccineHandoffRequest,
    *,
    cancelled: Callable[[], bool] = lambda: False,
    timeout_seconds: float = 15.0,
) -> VaccineHandoffResult:
    """Enter digits and one Enter only into an explicitly verified lookup target.

    A successful result means input was sent, not that the national system has
    accepted a patient or registered a vaccination. No input is retried here.
    """
    digits = resident_id_for_vaccine_system(request.resident_id)
    if request.system not in SYSTEM_LABELS:
        return VaccineHandoffResult(False, "Vaccine system mapping is not configured.")
    if len(digits) != 13 or not digits.isascii() or not digits.isdigit():
        return VaccineHandoffResult(False, "A complete 13-digit resident number is required.")
    deadline = monotonic() + max(timeout_seconds, 0.1)

    def allowed() -> bool:
        return not cancelled() and monotonic() < deadline

    try:
        if not allowed() or interactive_desktop_error() is not None:
            return VaccineHandoffResult(False, "Input stopped or Windows is locked.")
        if _input_is_idle(0) is not True:
            return VaccineHandoffResult(False, "Release the keyboard and mouse, then retry entry.")
        desktop = ensure_first_virtual_desktop()
        if not desktop.success or not allowed():
            return VaccineHandoffResult(False, "Virtual Desktop 1 could not be confirmed.")
        target = _resolve_input_target(settings, request.system)
        if not allowed():
            return VaccineHandoffResult(False, "Input target search timed out or was stopped. No number was typed.")
        if target is None:
            if request.system == "influenza":
                return VaccineHandoffResult(False, (
                    "The influenza resident-number field could not be uniquely identified. "
                    "Keep one influenza patient-lookup tab visible and check its input Automation ID."
                ))
            return VaccineHandoffResult(False, "Open the correct system and check its configured input target.")
        activation_block = ""

        def can_activate() -> bool:
            nonlocal activation_block
            if cancelled():
                activation_block = "Entry stopped before typing."
            elif monotonic() >= deadline:
                activation_block = "Entry timed out while focusing the system. No number was typed."
            elif not first_virtual_desktop_is_active():
                activation_block = "Virtual Desktop 1 is no longer active. No number was typed."
            elif _input_is_idle(0) is not True:
                activation_block = "Keyboard or mouse input interrupted focusing. No number was typed."
            else:
                return True
            return False

        if not can_activate() or not target.activate(can_activate):
            detail = activation_block or (target.activation_error() if target.activation_error else "")
            return VaccineHandoffResult(
                False, detail or "The system input could not be focused. No number was typed.",
            )

        def ready() -> bool:
            return (
                allowed() and first_virtual_desktop_is_active()
                and _input_is_idle(0) is True and target.ready()
            )

        if not ready():
            return VaccineHandoffResult(False, "Input focus was not confirmed. No number was typed.")
        _send_keys("^a")
        for digit in digits:
            if not ready() or not _send_unicode_text(digit):
                return VaccineHandoffResult(False, "Entry interrupted. Check the system before retrying; Enter was not sent.")
        if not ready():
            return VaccineHandoffResult(False, "Entry focus changed. Check the system; Enter was not sent.")
        if target.read_value is not None:
            if not _wait_for(
                lambda: resident_id_for_vaccine_system(target.read_value()) == digits,
                allowed=ready,
            ):
                return VaccineHandoffResult(False, "The input value could not be verified; Enter was not sent.")
        if not ready():
            return VaccineHandoffResult(False, "Entry stopped before patient lookup.")
        _send_keys("{ENTER}")
        return VaccineHandoffResult(True, "Patient lookup input sent. Review the system manually.")
    except Exception:
        # External providers can include patient data in exception messages.
        return VaccineHandoffResult(False, "Entry could not be confirmed. Check the system before retrying.")


def _send_keys(keys: str) -> None:
    from pywinauto.keyboard import send_keys

    send_keys(keys, pause=0.05)


def _wait_for(
    predicate: Callable[[], bool], *, allowed: Callable[[], bool], timeout_seconds: float = 0.75,
) -> bool:
    deadline = monotonic() + timeout_seconds
    while allowed():
        if predicate():
            return allowed()
        if monotonic() >= deadline:
            break
        sleep(0.025)
    return False


def _resolve_input_target(settings: dict[str, str], system: str) -> _InputTarget | None:
    if system == "influenza":
        return _browser_input_target(settings)
    return _native_input_target(settings, system)


def _native_input_target(settings: dict[str, str], system: str) -> _InputTarget | None:
    import win32gui

    prefix = f"vaccine_{system}_system"
    title = settings.get(f"{prefix}_window_title", "").strip()
    class_name = settings.get(f"{prefix}_window_class", "").strip()
    x = int(settings.get(f"{prefix}_resident_x", "0"))
    y = int(settings.get(f"{prefix}_resident_y", "0"))
    if not title or not class_name or (x, y) == (0, 0):
        return None
    handles = find_native_vaccine_windows(win32gui, title, class_name)
    if len(handles) != 1:
        return None
    handle = handles[0]
    focused = 0

    def window_ready() -> bool:
        return (
            foreground_handle() == handle
            and win32gui.GetWindowText(handle).strip() == title
            and win32gui.GetClassName(handle).strip() == class_name
            and win32gui.IsWindowEnabled(handle)
            and _screen_point_belongs_to_window(handle, x, y)
            and win32gui.IsWindowEnabled(win32gui.WindowFromPoint((x, y)))
        )

    def activate(guard: Callable[[], bool]) -> bool:
        nonlocal focused
        import pyautogui

        if not guard() or not _focus_native_window(handle) or not guard() or not window_ready():
            return False
        pyautogui.click(x=x, y=y, duration=0)
        focused = _focused_native_handle()
        return bool(focused) and window_ready() and _focus_belongs_to_window(focused, handle)

    return _InputTarget(
        activate=activate,
        ready=lambda: (
            window_ready() and bool(focused) and _focused_native_handle() == focused
            and _focus_belongs_to_window(focused, handle)
        ),
    )


def _focused_native_handle() -> int:
    import ctypes
    from ctypes import wintypes

    class GuiThreadInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]

    info = GuiThreadInfo(cbSize=ctypes.sizeof(GuiThreadInfo))
    if not ctypes.windll.user32.GetGUIThreadInfo(0, ctypes.byref(info)):
        return 0
    return int(info.hwndFocus or 0)


def _focus_belongs_to_window(focused: int, handle: int) -> bool:
    import win32con
    import win32gui

    return (
        win32gui.IsWindowEnabled(focused)
        and int(win32gui.GetAncestor(focused, win32con.GA_ROOT)) == handle
    )


def _same_browser_input(control, candidate) -> bool:
    identity = document_identity(control)
    return (
        identity is not None and document_identity(candidate) == identity
        and candidate.element_info.control_type == "Edit"
        and candidate.element_info.automation_id == control.element_info.automation_id
    )


def _browser_input_has_focus(control) -> bool:
    if has_keyboard_focus(control):
        return True
    try:
        # A field flag alone can lag behind UIA's current focused element.
        return _same_browser_input(control, focused_element())
    except Exception:
        return False


def _click_verified_browser_input(window, control, guard: Callable[[], bool]) -> bool:
    """One click at the live field, never at an unverified stored coordinate."""
    try:
        from pywinauto import Desktop
        import pyautogui

        handle = int(window.handle)
        if not guard() or foreground_handle() != handle:
            return False
        rectangle = control.rectangle()
        if rectangle.right <= rectangle.left or rectangle.bottom <= rectangle.top:
            return False
        x = (rectangle.left + rectangle.right) // 2
        y = (rectangle.top + rectangle.bottom) // 2
        if not guard() or not _screen_point_belongs_to_window(handle, x, y):
            return False
        hit = Desktop(backend="uia").from_point(x, y)
        if not _same_browser_input(control, hit) or foreground_handle() != handle:
            return False
        if not guard():
            return False
        current = control.rectangle()
        if not (current.left <= x < current.right and current.top <= y < current.bottom):
            return False
        if foreground_handle() != handle or not _screen_point_belongs_to_window(handle, x, y):
            return False
        pyautogui.click(x=x, y=y, duration=0)
        return True
    except Exception:
        return False


def _browser_input_target(settings: dict[str, str]) -> _InputTarget | None:
    from pywinauto import Desktop

    url = settings.get("vaccine_influenza_system_launch_url", "")
    target_id = settings.get("vaccine_influenza_system_resident_automation_id", "")
    if not url or not target_id:
        return None
    expected = urlparse(url)
    path_prefix = posixpath.dirname(expected.path).rstrip("/") + "/"

    def matches_document(document) -> bool:
        actual = urlparse(_document_url(document))
        return (
            (actual.scheme, actual.netloc.casefold()) == (expected.scheme, expected.netloc.casefold())
            and actual.path.startswith(path_prefix)
        )

    def input_document(control):
        # A trusted outer page must not authorize input into an unrelated iframe.
        parent = control.parent()
        for _ in range(32):
            if parent.element_info.control_type == "Document":
                return parent if parent.is_visible() and matches_document(parent) else None
            parent = parent.parent()
        return None

    matches = {}
    for window in Desktop(backend="uia").windows():
        if window.element_info.class_name not in {"Chrome_WidgetWin_1", "MozillaWindowClass"}:
            continue
        for document in iter_documents_for_url(window, url):
            if not matches_document(document):
                continue
            controls = find_uia_elements_by_automation_ids(
                (target_id,), root_element=document, control_type="Edit",
            ).get(target_id, [])
            for control in controls:
                identity = document_identity(control)
                if identity is None or not control.is_visible() or not control.is_enabled():
                    continue
                owner = input_document(control)
                if owner is not None:
                    # The same field can occur in both outer and nested document searches.
                    matches[(int(window.handle), identity)] = (window, owner, control)
    if len(matches) != 1:
        return None
    window, document, control = next(iter(matches.values()))
    owner_identity = document_identity(document)
    activation_message = ""

    def document_ready() -> bool:
        owner = input_document(control)
        return (
            owner_identity is not None and owner is not None
            and document_identity(owner) == owner_identity
            and matches_document(document) and document.is_visible()
            and window.is_enabled() and control.is_visible() and control.is_enabled()
            and control.element_info.automation_id == target_id
        )

    def activate(guard: Callable[[], bool]) -> bool:
        nonlocal activation_message
        activation_message = "Influenza browser did not become the foreground window. No number was typed."
        if not guard():
            return False
        if foreground_handle() != int(window.handle):
            window.set_focus()
        if not _wait_for(lambda: foreground_handle() == int(window.handle), allowed=guard):
            return False
        activation_message = "Influenza page or input changed before entry. No number was typed."
        if not guard() or not document_ready():
            return False
        if _browser_input_has_focus(control):
            return True
        control.set_focus()
        def guarded() -> bool:
            nonlocal activation_message
            if not guard():
                return False
            if foreground_handle() != int(window.handle):
                activation_message = "Influenza browser lost foreground focus. No number was typed."
                return False
            if not document_ready():
                activation_message = "Influenza page or input changed while focusing. No number was typed."
                return False
            return True

        activation_message = "Influenza input keyboard focus was not confirmed. No number was typed."
        if _wait_for(lambda: _browser_input_has_focus(control), allowed=guarded):
            return True
        if not guarded():
            return False
        activation_message = "Influenza input could not be safely clicked. Check for a covering popup. No number was typed."
        if not _click_verified_browser_input(window, control, guarded):
            return False
        activation_message = "Influenza input keyboard focus was not confirmed after clicking. No number was typed."
        return _wait_for(
            lambda: _browser_input_has_focus(control), allowed=guarded,
        )

    def ready() -> bool:
        return (
            foreground_handle() == int(window.handle) and _browser_input_has_focus(control)
            and document_ready()
        )

    return _InputTarget(
        activate, ready, lambda: str(control.get_value() or ""), lambda: activation_message,
    )
