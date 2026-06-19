from dataclasses import dataclass
import time

from KaosEghis.core.clipboard_service import copy_text, restore_clipboard
from KaosEghis.core.emr_detector import is_target_window_active

ALLOWED_FUNCTION_KEYS = {"F1", "F2", "F3", "F4"}
ALLOWED_DESTINATIONS = {
    "Symptom": "F1",
    "Diagnosis": "F2",
    "Orders": "F3",
    "Patient Notes": "F4",
}


@dataclass(frozen=True)
class FunctionKeyPasteResult:
    success: bool
    message: str
    destination: str
    function_key: str
    text_length: int
    eghis_active: bool
    popup_check_passed: bool | None
    key_sent: bool
    paste_sent: bool
    clipboard_restored: bool


def paste_to_eghis_field_by_function_key_for_test(
    settings: dict[str, str],
    destination: str,
    function_key: str,
    text: str,
) -> FunctionKeyPasteResult:
    if not text.strip():
        return _result(
            success=False,
            message="Paste test text is empty.",
            destination=destination,
            function_key=function_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    normalized_key = function_key.strip().upper()
    if normalized_key not in ALLOWED_FUNCTION_KEYS:
        return _result(
            success=False,
            message=f"Function key '{function_key}' is not supported.",
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    expected_key = ALLOWED_DESTINATIONS.get(destination)
    if expected_key is None:
        return _result(
            success=False,
            message=f"Destination '{destination}' is not supported.",
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )
    if expected_key != normalized_key:
        return _result(
            success=False,
            message=(
                f"Destination '{destination}' must use {expected_key}, not {normalized_key}."
            ),
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    title_fragment = settings.get("eghis_window_title_contains", "").strip()
    if not title_fragment:
        return _result(
            success=False,
            message="Eghis window title setting is empty.",
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    eghis_active = is_target_window_active(title_fragment)
    if not eghis_active:
        return _result(
            success=False,
            message="Eghis window is not active. Click Eghis and retry.",
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=False,
            popup_check_passed=None,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    popup_check_passed = _check_for_possible_popup(title_fragment)
    if popup_check_passed is False:
        return _result(
            success=False,
            message="Possible Eghis popup/modal detected. Close it and retry.",
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=True,
            popup_check_passed=False,
            key_sent=False,
            paste_sent=False,
            clipboard_restored=False,
        )

    snapshot = None
    key_sent = False
    paste_sent = False
    clipboard_restored = False
    try:
        snapshot = copy_text(text)
        from pywinauto.keyboard import send_keys

        send_keys(f"{{{normalized_key}}}")
        key_sent = True
        time.sleep(0.3)
        send_keys("^v")
        paste_sent = True
        time.sleep(0.15)
    except Exception as error:
        if snapshot is not None:
            clipboard_restored = _try_restore_clipboard(snapshot)
        return _result(
            success=False,
            message=(
                f"Function-key paste test failed for {destination} via {normalized_key}:"
                f" {error}"
            ),
            destination=destination,
            function_key=normalized_key,
            text=text,
            eghis_active=True,
            popup_check_passed=popup_check_passed,
            key_sent=key_sent,
            paste_sent=paste_sent,
            clipboard_restored=clipboard_restored,
        )

    if snapshot is not None:
        clipboard_restored = _try_restore_clipboard(snapshot)

    restore_message = (
        "Clipboard restored."
        if clipboard_restored
        else "Clipboard restore was not available."
    )
    return _result(
        success=True,
        message=(
            f"Function-key paste test sent {normalized_key} then Ctrl+V to"
            f" {destination}. {restore_message}"
        ),
        destination=destination,
        function_key=normalized_key,
        text=text,
        eghis_active=True,
        popup_check_passed=popup_check_passed,
        key_sent=key_sent,
        paste_sent=paste_sent,
        clipboard_restored=clipboard_restored,
    )


def _check_for_possible_popup(_title_fragment: str) -> bool | None:
    return None


def _try_restore_clipboard(snapshot: object) -> bool:
    try:
        restore_clipboard(snapshot)
    except Exception:
        return False
    return True


def _result(
    *,
    success: bool,
    message: str,
    destination: str,
    function_key: str,
    text: str,
    eghis_active: bool,
    popup_check_passed: bool | None,
    key_sent: bool,
    paste_sent: bool,
    clipboard_restored: bool,
) -> FunctionKeyPasteResult:
    return FunctionKeyPasteResult(
        success=success,
        message=message,
        destination=destination,
        function_key=function_key,
        text_length=len(text),
        eghis_active=eghis_active,
        popup_check_passed=popup_check_passed,
        key_sent=key_sent,
        paste_sent=paste_sent,
        clipboard_restored=clipboard_restored,
    )
