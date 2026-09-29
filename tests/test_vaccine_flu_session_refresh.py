import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_session_keeper as keeper


@pytest.fixture
def browser(monkeypatch):
    state = {"foreground": 0, "keys": [], "switches": 0, "focuses": 0, "url": "https://ois.kdca.go.kr/iroi/patient.html"}
    window = SimpleNamespace(
        handle=10,
        element_info=SimpleNamespace(class_name="Chrome_WidgetWin_1", control_type="Window"),
        is_visible=lambda: True, is_enabled=lambda: True, window_text=lambda: "Flu - Chrome",
    )
    document = SimpleNamespace(
        element_info=SimpleNamespace(runtime_id=(1, 2), control_type="Document"),
        is_visible=lambda: True, parent=lambda: window, get_value=lambda: state["url"],
    )
    window.descendants = lambda **_kwargs: [document]

    def focus():
        state["foreground"] = 10
        state["focuses"] += 1

    def switch():
        state["switches"] += 1
        return SimpleNamespace(success=True)

    window.set_focus = focus
    windows = [window]
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(Desktop=lambda **_kw: SimpleNamespace(windows=lambda: windows)))
    monkeypatch.setitem(sys.modules, "pyautogui", SimpleNamespace(press=state["keys"].append))
    monkeypatch.setattr(keeper, "foreground_handle", lambda: state["foreground"])
    monkeypatch.setattr(keeper, "interactive_desktop_error", lambda: None)
    monkeypatch.setattr(keeper, "_input_is_idle", lambda _ms: True)
    monkeypatch.setattr(keeper, "ensure_first_virtual_desktop", switch)
    monkeypatch.setattr(keeper, "first_virtual_desktop_is_active", lambda: True)
    settings = {"vaccine_influenza_system_launch_url": "https://ois.kdca.go.kr/iroi/indexWSP.jsp"}
    return state, window, document, windows, settings


def test_manual_confirmed_refresh_sends_only_f5(browser):
    state, _window, _document, _windows, settings = browser
    confirmations = []
    result = keeper.refresh_influenza_session(settings, confirm=lambda: confirmations.append(True) or True)
    assert confirmations == [True]
    assert result.sent and result.status == "refresh_sent"
    assert "not verified" in result.message
    assert state["keys"] == ["f5"]


def test_declined_refresh_never_focuses_or_switches(browser):
    state, _window, _document, _windows, settings = browser
    result = keeper.refresh_influenza_session(settings, confirm=lambda: False)
    assert result.status == "declined" and not result.sent
    assert state["keys"] == [] and state["focuses"] == 0 and state["switches"] == 0


@pytest.mark.parametrize("url", ["https://is.kdca.go.kr/isc/index.do", "https://ois.kdca.go.kr/iris/index_run.jsp", "https://example.com/iroi/patient.html"])
def test_wrong_origin_or_system_never_refreshes(browser, url):
    state, _window, _document, _windows, settings = browser
    state["url"] = url
    result = keeper.refresh_influenza_session(settings, confirm=lambda: pytest.fail("No matching Flu page"))
    assert not result.sent
    assert state["keys"] == []


def test_embedded_flu_frame_cannot_reload_the_portal(browser):
    state, window, document, _windows, settings = browser
    document.parent = lambda: SimpleNamespace(element_info=SimpleNamespace(control_type="Document"), handle=10)
    result = keeper.refresh_influenza_session(settings, confirm=lambda: pytest.fail("Not a top-level Flu page"))
    assert not result.sent and state["keys"] == []


def test_ambiguous_pages_never_focus_or_refresh(browser):
    state, window, _document, windows, settings = browser
    windows.append(window)
    result = keeper.refresh_influenza_session(settings, confirm=lambda: pytest.fail("Ambiguous"))
    assert result.status == "ambiguous"
    assert state["keys"] == [] and state["focuses"] == 0


@pytest.mark.parametrize("change", ["url", "focus", "input", "desktop", "locked", "identity"])
def test_changes_after_confirmation_block_f5(browser, monkeypatch, change):
    state, window, document, _windows, settings = browser

    def focus():
        state["foreground"] = 10
        if change == "url":
            state["url"] = "https://ois.kdca.go.kr/iris/index_run.jsp"
        elif change == "focus":
            # Change foreground during the last UIA read, after the first focus check.
            def read_url():
                state["foreground"] = 99
                return state["url"]
            document.get_value = read_url
        elif change == "input":
            monkeypatch.setattr(keeper, "_input_is_idle", lambda _ms: False)
        elif change == "desktop":
            monkeypatch.setattr(keeper, "first_virtual_desktop_is_active", lambda: False)
        elif change == "locked":
            monkeypatch.setattr(keeper, "interactive_desktop_error", lambda: "locked")
        else:
            document.element_info.runtime_id = (4, 5)

    window.set_focus = focus
    result = keeper.refresh_influenza_session(settings, confirm=lambda: True)
    assert not result.sent and state["keys"] == []


def test_no_tab_does_not_prompt_or_focus(browser):
    state, _window, _document, windows, settings = browser
    windows.clear()
    result = keeper.refresh_influenza_session(settings, confirm=lambda: pytest.fail("No tab"))
    assert result.status == "not_open"
    assert state["keys"] == [] and state["switches"] == 0
