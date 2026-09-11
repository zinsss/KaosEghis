"""Guarded KDCA 공동인증서 sign-in for the external vaccine systems.

This module intentionally performs one operator-requested sign-in attempt.  It
does not run at app startup, keep a government portal alive, retry blind input,
or retain certificate passwords outside the unlocked KaosEghis-pw session.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
import webbrowser

from KaosEghis.core.pw_runtime import get_unlocked_credential_password


@dataclass(frozen=True)
class KdcaCertificateLoginConfig:
    portal_url: str
    browser_window_title_contains: str
    login_control_name: str
    certificate_window_title_contains: str
    certificate_name: str
    password_window_title_contains: str
    password_automation_id: str
    password_control_type: str
    confirm_control_name: str
    credential_reference: str
    timeout_seconds: float = 12.0

    @classmethod
    def from_settings(cls, settings: dict[str, str]) -> "KdcaCertificateLoginConfig":
        return cls(
            portal_url=str(settings.get("vaccine_kdca_portal_url", "")).strip(),
            browser_window_title_contains=str(
                settings.get("vaccine_kdca_browser_window_title_contains", "")
            ).strip(),
            login_control_name=str(
                settings.get("vaccine_kdca_login_control_name", "")
            ).strip(),
            certificate_window_title_contains=str(
                settings.get("vaccine_kdca_certificate_window_title_contains", "")
            ).strip(),
            certificate_name=str(
                settings.get("vaccine_kdca_certificate_name", "")
            ).strip(),
            password_window_title_contains=str(
                settings.get("vaccine_kdca_password_window_title_contains", "")
            ).strip(),
            password_automation_id=str(
                settings.get("vaccine_kdca_password_automation_id", "")
            ).strip(),
            password_control_type=str(
                settings.get("vaccine_kdca_password_control_type", "Edit")
            ).strip(),
            confirm_control_name=str(
                settings.get("vaccine_kdca_confirm_control_name", "")
            ).strip(),
            credential_reference=str(
                settings.get("vaccine_kdca_credential_reference", "")
            ).strip(),
        )

    def configuration_error(self) -> str | None:
        required = {
            "KDCA portal URL": self.portal_url,
            "KDCA browser title": self.browser_window_title_contains,
            "KDCA login control": self.login_control_name,
            "certificate picker title": self.certificate_window_title_contains,
            "certificate label": self.certificate_name,
            "certificate password window title": self.password_window_title_contains,
            "certificate password control type": self.password_control_type,
            "certificate confirm control": self.confirm_control_name,
            "certificate credential reference": self.credential_reference,
        }
        for label, value in required.items():
            if not value:
                return f"KDCA login configuration is missing {label}."
        if not self.portal_url.startswith(("https://", "http://")):
            return "KDCA portal URL must start with http:// or https://."
        return None


@dataclass(frozen=True)
class KdcaCertificateLoginResult:
    success: bool
    status: str
    message: str


def start_kdca_certificate_login(
    settings: dict[str, str],
    *,
    password_provider: Callable[[str], str | None] = get_unlocked_credential_password,
) -> KdcaCertificateLoginResult:
    """Start one explicit KDCA certificate login attempt.

    Every UI action is limited to a single visible matching window/control.  A
    missing or ambiguous selector stops the workflow before a password is typed.
    """

    config = KdcaCertificateLoginConfig.from_settings(settings)
    configuration_error = config.configuration_error()
    if configuration_error:
        return _result(False, "configuration_required", configuration_error)

    password = password_provider(config.credential_reference)
    if not password:
        return _result(
            False,
            "credential_unavailable",
            "KDCA certificate credential is unavailable. Unlock KaosEghis-pw first.",
        )

    if not _open_portal(config.portal_url):
        return _result(False, "portal_unavailable", "KDCA portal could not be opened.")

    browser_window = _wait_for_single_window(
        config.browser_window_title_contains,
        config.timeout_seconds,
    )
    if browser_window is None:
        return _result(
            False,
            "browser_not_ready",
            "KDCA portal window was not ready. No certificate password was typed.",
        )

    login_control = _find_single_descendant(
        browser_window,
        name=config.login_control_name,
    )
    if login_control is None:
        return _result(
            False,
            "login_control_not_found",
            "KDCA certificate login control was not found. No certificate password was typed.",
        )
    if not _activate(login_control):
        return _result(
            False,
            "login_control_failed",
            "KDCA certificate login control could not be activated.",
        )

    certificate_window = _wait_for_single_window(
        config.certificate_window_title_contains,
        config.timeout_seconds,
        exclude_handles={
            handle
            for handle in (_window_handle(browser_window),)
            if handle is not None
        },
    )
    if certificate_window is None:
        return _result(
            False,
            "certificate_picker_not_ready",
            "Certificate picker was not ready. No certificate password was typed.",
        )

    certificate_control = _find_single_descendant(
        certificate_window,
        name=config.certificate_name,
    )
    if certificate_control is None:
        return _result(
            False,
            "certificate_not_found",
            "Configured certificate was not found. No certificate password was typed.",
        )
    if not _activate(certificate_control):
        return _result(
            False,
            "certificate_selection_failed",
            "Configured certificate could not be selected. No certificate password was typed.",
        )

    password_window, password_control = _wait_for_password_target(
        config,
        config.password_window_title_contains,
        config.timeout_seconds,
        exclude_handles={handle for handle in (_window_handle(browser_window),) if handle is not None},
    )
    if password_window is None or password_control is None:
        return _result(
            False,
            "password_window_not_ready",
            "Certificate password window was not ready. No certificate password was typed.",
        )
    if not _type_secret(password_control, password):
        return _result(
            False,
            "password_input_failed",
            "Certificate password could not be entered.",
        )

    confirm_control = _find_single_descendant(
        password_window,
        name=config.confirm_control_name,
    )
    if confirm_control is None or not _activate(confirm_control):
        return _result(
            False,
            "confirmation_failed",
            "Certificate confirmation control was not available.",
        )
    return _result(
        True,
        "submitted",
        "KDCA certificate login was submitted. Verify the portal completed sign-in.",
    )


def _open_portal(url: str) -> bool:
    try:
        return bool(webbrowser.open(url, new=2, autoraise=True))
    except Exception:
        return False


def _wait_for_single_window(
    title_contains: str,
    timeout_seconds: float,
    *,
    exclude_handles: set[int] | None = None,
) -> Any | None:
    deadline = time.monotonic() + max(timeout_seconds, 0.1)
    while time.monotonic() < deadline:
        matches = [
            window
            for window in _desktop_windows()
            if _is_visible(window)
            and _title_contains(_window_title(window), title_contains)
            and _window_handle(window) not in (exclude_handles or set())
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
        time.sleep(0.1)
    return None


def _desktop_windows() -> list[Any]:
    try:
        from pywinauto import Desktop

        return list(Desktop(backend="uia").windows())
    except Exception:
        return []


def _wait_for_password_target(
    config: KdcaCertificateLoginConfig,
    title_contains: str,
    timeout_seconds: float,
    *,
    exclude_handles: set[int] | None = None,
) -> tuple[Any | None, Any | None]:
    """Find one verified password input, whether it shares the picker or is a new dialog."""

    deadline = time.monotonic() + max(timeout_seconds, 0.1)
    while time.monotonic() < deadline:
        matches: list[tuple[Any, Any]] = []
        for window in _desktop_windows():
            if (
                not _is_visible(window)
                or not _title_contains(_window_title(window), title_contains)
                or _window_handle(window) in (exclude_handles or set())
            ):
                continue
            control = _find_single_password_descendant(
                window,
                automation_id=config.password_automation_id,
                control_type=config.password_control_type,
            )
            if control is not None:
                matches.append((window, control))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None, None
        time.sleep(0.1)
    return None, None


def _find_single_descendant(
    window: Any,
    *,
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
) -> Any | None:
    try:
        elements = list(window.descendants())
    except Exception:
        return None
    matches = [
        element
        for element in elements
        if _is_visible(element)
        and _is_enabled(element)
        and (not name or _matches_text(_element_name(element), name))
        and (not automation_id or _element_automation_id(element) == automation_id)
        and (not control_type or _element_control_type(element) == control_type)
    ]
    return matches[0] if len(matches) == 1 else None


def _find_single_password_descendant(
    window: Any,
    *,
    automation_id: str,
    control_type: str,
) -> Any | None:
    try:
        elements = list(window.descendants())
    except Exception:
        return None
    matches = [
        element
        for element in elements
        if _is_visible(element)
        and _is_enabled(element)
        and (not automation_id or _element_automation_id(element) == automation_id)
        and (not control_type or _element_control_type(element) == control_type)
    ]
    password_matches = [element for element in matches if _is_password_field(element)]
    if len(password_matches) == 1:
        return password_matches[0]
    if len(password_matches) > 1:
        return None
    return matches[0] if len(matches) == 1 else None


def _activate(element: Any) -> bool:
    try:
        element.set_focus()
    except Exception:
        pass
    for method_name in ("invoke", "click_input", "click"):
        method = getattr(element, method_name, None)
        if not callable(method):
            continue
        try:
            method()
            return True
        except Exception:
            continue
    return False


def _type_secret(element: Any, password: str) -> bool:
    """Type directly into the verified password control without clipboard use."""

    try:
        element.set_focus()
    except Exception:
        return False
    return _send_unicode_text(password)


def _send_unicode_text(value: str) -> bool:
    """Send Windows Unicode key events, including Hangul, without using clipboard."""

    if not value:
        return False
    try:
        import ctypes

        wintypes = ctypes.wintypes

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("union",)
            _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

        input_keyboard = 1
        keyeventf_unicode = 0x0004
        keyeventf_keyup = 0x0002
        events: list[INPUT] = []
        utf16_bytes = value.encode("utf-16-le")
        for index in range(0, len(utf16_bytes), 2):
            code_unit = int.from_bytes(
                utf16_bytes[index : index + 2],
                byteorder="little",
            )
            events.append(
                INPUT(
                    type=input_keyboard,
                    ki=KEYBDINPUT(0, code_unit, keyeventf_unicode, 0, None),
                )
            )
            events.append(
                INPUT(
                    type=input_keyboard,
                    ki=KEYBDINPUT(
                        0,
                        code_unit,
                        keyeventf_unicode | keyeventf_keyup,
                        0,
                        None,
                    ),
                )
            )
        sent = ctypes.windll.user32.SendInput(
            len(events),
            (INPUT * len(events))(*events),
            ctypes.sizeof(INPUT),
        )
        return int(sent) == len(events)
    except Exception:
        return False


def _window_title(element: Any) -> str:
    for method_name in ("window_text", "texts"):
        method = getattr(element, method_name, None)
        if callable(method):
            try:
                value = method()
                if isinstance(value, (list, tuple)):
                    value = value[0] if value else ""
                return str(value or "")
            except Exception:
                continue
    return _element_name(element)


def _element_name(element: Any) -> str:
    info = getattr(element, "element_info", None)
    return str(getattr(info, "name", "") or "")


def _element_automation_id(element: Any) -> str:
    info = getattr(element, "element_info", None)
    return str(getattr(info, "automation_id", "") or "")


def _element_control_type(element: Any) -> str:
    info = getattr(element, "element_info", None)
    return str(getattr(info, "control_type", "") or "")


def _is_password_field(element: Any) -> bool:
    info = getattr(element, "element_info", None)
    value = getattr(info, "is_password", None)
    if value is not None:
        return bool(value)
    method = getattr(element, "is_password", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    return False


def _window_handle(element: Any) -> int | None:
    handle = getattr(element, "handle", None)
    try:
        return int(handle) if handle else None
    except (TypeError, ValueError):
        return None


def _is_visible(element: Any) -> bool:
    method = getattr(element, "is_visible", None)
    if not callable(method):
        return True
    try:
        return bool(method())
    except Exception:
        return False


def _is_enabled(element: Any) -> bool:
    method = getattr(element, "is_enabled", None)
    if not callable(method):
        return True
    try:
        return bool(method())
    except Exception:
        return False


def _matches_text(actual: str, expected: str) -> bool:
    return actual.strip().casefold() == expected.strip().casefold()


def _title_contains(actual: str, expected: str) -> bool:
    return expected.strip().casefold() in actual.strip().casefold()


def _result(success: bool, status: str, message: str) -> KdcaCertificateLoginResult:
    return KdcaCertificateLoginResult(success, status, message)
