"""Guarded, single-attempt EMR charting after the vaccine-system lookup."""

from __future__ import annotations

from time import monotonic, sleep
from typing import Callable

from KaosEghis.core.clipboard_service import _read_clipboard_text
from KaosEghis.core.eghis_connector import (
    focus_cached_eghis_process_window,
    validate_cached_connection_identity,
)
from KaosEghis.core.kdca_certificate_login import _send_unicode_text
from KaosEghis.core.vaccine_session_keeper import _input_is_idle
from KaosEghis.core.vaccine_system_input import (
    VaccineHandoffResult, _focus_belongs_to_window, _focused_native_handle, _send_keys,
)
from KaosEghis.core.windows_desktop import interactive_desktop_error


def paste_vaccine_charting(
    settings: dict[str, str],
    charting_text: str,
    *,
    order_text: str = "",
    cancelled: Callable[[], bool] = lambda: False,
) -> VaccineHandoffResult:
    """Focus EMR, paste charting, then optionally enter one F3 order.

    The caller has already copied this exact note. Success means key dispatch,
    not verification of the chart contents or of the currently selected patient.
    """
    if not charting_text.strip():
        return VaccineHandoffResult(False, "No charting text is available.")
    order_text = order_text.strip()
    if len(order_text) > 256 or any(
        ord(character) < 32 or 0xD800 <= ord(character) <= 0xDFFF
        for character in order_text
    ):
        return VaccineHandoffResult(
            False,
            "Order text contains unsupported characters. No EMR keys were sent.",
        )

    def allowed() -> bool:
        return (
            not cancelled() and interactive_desktop_error() is None
            and _input_is_idle(0) is True
        )

    try:
        if not allowed():
            return VaccineHandoffResult(False, "EMR charting stopped: Windows is locked or input was interrupted.")
        if _read_clipboard_text() != charting_text:
            return VaccineHandoffResult(False, "Clipboard changed. No EMR keys were sent.")
        state = validate_cached_connection_identity(settings)
        if state.status == "red" or not state.window_handle or not state.pid:
            return VaccineHandoffResult(False, "EMR is not connected. No EMR keys were sent.")
        if not allowed():
            return VaccineHandoffResult(False, "EMR charting stopped before focusing.")
        focused, _reason = focus_cached_eghis_process_window(settings, state.window_handle)
        if not focused:
            return VaccineHandoffResult(False, "EMR could not be focused. No EMR keys were sent.")

        def ready() -> bool:
            return allowed() and _emr_input_ready(state.window_handle, state.pid)

        def settle(seconds: float) -> bool:
            deadline = monotonic() + seconds
            while ready():
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return True
                sleep(min(0.025, remaining))
            return False

        # Do not refocus after F1: an unexpected popup or user focus change
        # must stop the sequence, not redirect Enter/paste into another window.
        for keys in ("{F1}", "{ENTER}", "^v"):
            if not settle(0.2):
                return VaccineHandoffResult(False, "EMR focus/input changed. Charting stopped; review before pasting manually.")
            if keys == "^v" and _read_clipboard_text() != charting_text:
                return VaccineHandoffResult(False, "Clipboard changed. Charting text was not pasted.")
            if not ready():
                return VaccineHandoffResult(False, "EMR charting stopped before the next key.")
            _send_keys(keys)
        if not order_text:
            return VaccineHandoffResult(True, "EMR paste input sent. Review the current chart.")

        if not settle(0.2):
            return VaccineHandoffResult(
                False,
                "Charting was pasted, but EMR focus/input changed before order entry.",
            )
        _send_keys("{F3}")
        if not settle(0.2):
            return VaccineHandoffResult(
                False,
                "Charting was pasted and F3 sent, but order entry was interrupted.",
            )
        if not _send_unicode_text(order_text):
            return VaccineHandoffResult(
                False,
                "Charting was pasted, but order text entry could not be confirmed. Review the order field.",
            )
        if not settle(0.2):
            return VaccineHandoffResult(
                False,
                "Charting was pasted and order text entered, but submission was interrupted.",
            )
        _send_keys("{ENTER}")
        return VaccineHandoffResult(
            True,
            "EMR paste and order input sent. Review the current chart and order.",
        )
    except Exception:
        # Never retry an uncertain paste or expose text from provider errors.
        return VaccineHandoffResult(False, "EMR charting could not be confirmed. Review before pasting manually.")


def _emr_input_ready(handle: int, pid: int) -> bool:
    import win32gui
    import win32process

    return (
        win32gui.IsWindow(handle) and win32gui.IsWindowEnabled(handle)
        and win32gui.IsWindowVisible(handle)
        and win32process.GetWindowThreadProcessId(handle)[1] == pid
        and int(win32gui.GetForegroundWindow()) == handle
        and bool(focused := _focused_native_handle())
        and _focus_belongs_to_window(focused, handle)
    )
