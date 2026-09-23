import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_emr_charting as charting


@pytest.fixture
def desktop(monkeypatch):
    events = []
    now = [0.0]
    monkeypatch.setattr(charting, "monotonic", lambda: now[0])
    monkeypatch.setattr(charting, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(charting, "interactive_desktop_error", lambda: None)
    monkeypatch.setattr(charting, "_input_is_idle", lambda _ms: True)
    monkeypatch.setattr(charting, "_read_clipboard_text", lambda: "Test charting note")
    monkeypatch.setattr(charting, "validate_cached_connection_identity", lambda _settings: SimpleNamespace(
        status="yellow", window_handle=123, pid=456,
    ))
    monkeypatch.setattr(charting, "focus_cached_eghis_process_window", lambda _settings, handle: (
        events.append(("focus", handle)) or (True, "Focused.")
    ))
    monkeypatch.setattr(charting, "_emr_input_ready", lambda _handle, _pid: True)
    monkeypatch.setattr(charting, "_send_keys", lambda keys: events.append(keys))
    return events


def test_exact_sequence_no_final_enter_and_no_clipboard_rewrite(desktop):
    result = charting.paste_vaccine_charting({}, "Test charting note")
    assert result.success
    assert desktop == [("focus", 123), "{F1}", "{ENTER}", "^v"]
    assert "paste input sent" in result.message


@pytest.mark.parametrize("block", ["empty", "cancel", "locked", "held_key", "clipboard", "disconnected"])
def test_no_focus_or_keys_if_preflight_fails(desktop, monkeypatch, block):
    text = "Test charting note"
    if block == "empty":
        text = " "
    elif block == "locked":
        monkeypatch.setattr(charting, "interactive_desktop_error", lambda: "locked")
    elif block == "held_key":
        monkeypatch.setattr(charting, "_input_is_idle", lambda _ms: False)
    elif block == "clipboard":
        monkeypatch.setattr(charting, "_read_clipboard_text", lambda: "different text")
    elif block == "disconnected":
        monkeypatch.setattr(charting, "validate_cached_connection_identity", lambda _s: SimpleNamespace(status="red"))
    result = charting.paste_vaccine_charting({}, text, cancelled=lambda: block == "cancel")
    assert not result.success
    assert desktop == []


def test_focus_failure_does_not_send_keys(desktop, monkeypatch):
    monkeypatch.setattr(charting, "focus_cached_eghis_process_window", lambda *_a: (False, "failed"))
    assert not charting.paste_vaccine_charting({}, "Test charting note").success
    assert desktop == []


@pytest.mark.parametrize("last_key", ["{F1}", "{ENTER}"])
@pytest.mark.parametrize("block", ["focus", "cancel", "lock", "held_key"])
def test_interruption_stops_without_refocusing_or_pasting(desktop, monkeypatch, last_key, block):
    if block == "focus":
        monkeypatch.setattr(charting, "_emr_input_ready", lambda *_a: last_key not in desktop)
    elif block == "lock":
        monkeypatch.setattr(charting, "interactive_desktop_error", lambda: "locked" if last_key in desktop else None)
    elif block == "held_key":
        monkeypatch.setattr(charting, "_input_is_idle", lambda _ms: last_key not in desktop)
    result = charting.paste_vaccine_charting(
        {}, "Test charting note", cancelled=lambda: block == "cancel" and last_key in desktop,
    )
    assert not result.success
    assert desktop == [("focus", 123), "{F1}"] + (["{ENTER}"] if last_key == "{ENTER}" else [])


def test_changed_clipboard_after_enter_is_not_pasted(desktop, monkeypatch):
    monkeypatch.setattr(charting, "_read_clipboard_text", lambda: "changed" if "{ENTER}" in desktop else "Test charting note")
    result = charting.paste_vaccine_charting({}, "Test charting note")
    assert not result.success
    assert desktop == [("focus", 123), "{F1}", "{ENTER}"]


def test_uncertain_paste_is_not_retried_and_error_is_sanitized(desktop, monkeypatch):
    def send(keys):
        desktop.append(keys)
        if keys == "^v":
            raise RuntimeError("sensitive provider text")
    monkeypatch.setattr(charting, "_send_keys", send)
    result = charting.paste_vaccine_charting({}, "Test charting note")
    assert not result.success
    assert desktop == [("focus", 123), "{F1}", "{ENTER}", "^v"]
    assert "sensitive" not in result.message


@pytest.mark.parametrize("block", [None, "closed", "disabled", "hidden", "pid", "foreground", "no_focus", "other_focus"])
def test_native_guard_rejects_wrong_process_popup_and_focus(monkeypatch, block):
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        IsWindow=lambda _h: block != "closed",
        IsWindowEnabled=lambda _h: block != "disabled",
        IsWindowVisible=lambda _h: block != "hidden",
        GetForegroundWindow=lambda: 999 if block == "foreground" else 123,
    ))
    monkeypatch.setitem(sys.modules, "win32process", SimpleNamespace(
        GetWindowThreadProcessId=lambda _h: (1, 999 if block == "pid" else 456),
    ))
    monkeypatch.setattr(charting, "_focused_native_handle", lambda: 0 if block == "no_focus" else 124)
    monkeypatch.setattr(charting, "_focus_belongs_to_window", lambda focused, handle: (
        focused == 124 and handle == 123 and block != "other_focus"
    ))
    assert bool(charting._emr_input_ready(123, 456)) is (block is None)
