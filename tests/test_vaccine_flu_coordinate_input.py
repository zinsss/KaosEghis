from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_system_input as handoff


def test_library_digit_key_path_uses_virtual_keys_without_running_them():
    from pywinauto import keyboard

    actions = keyboard.parse_keys("0123456789", vk_packet=False)
    assert len(actions) == 10
    assert all(isinstance(action, keyboard.VirtualKeyAction) for action in actions)


@pytest.fixture
def browser(monkeypatch):
    import pyautogui
    import pywinauto

    state = {
        "url": "https://ois.kdca.go.kr/iroi/patient", "foreground": 10,
        "focus": 20, "owned": True, "enabled": True, "visible": True,
        "focus_works": True, "clock": 0.0, "events": [], "title": "Influenza",
        "rectangle": SimpleNamespace(left=0, top=0, right=100, bottom=100),
    }
    document = SimpleNamespace(
        element_info=SimpleNamespace(control_type="Document", runtime_id=(42, 1)),
        get_value=lambda: state["url"], is_visible=lambda: state["visible"],
        rectangle=lambda: state["rectangle"],
    )
    hit = SimpleNamespace(element_info=SimpleNamespace(control_type="Custom"), parent=lambda: document)
    state["hit"] = hit
    documents = [document]

    def focus_window():
        if state["focus_works"]:
            state["foreground"] = 10

    window = SimpleNamespace(
        handle=10, element_info=SimpleNamespace(class_name="Chrome_WidgetWin_1"),
        window_text=lambda: state["title"], set_focus=focus_window,
        is_enabled=lambda: state["enabled"], descendants=lambda **_kw: documents,
    )
    windows = [window]
    monkeypatch.setattr(pywinauto, "Desktop", lambda **_kw: SimpleNamespace(
        windows=lambda: windows, from_point=lambda x, y: state["hit"],
    ))
    monkeypatch.setattr(pyautogui, "click", lambda **kw: state["events"].append(("click", kw)))
    monkeypatch.setattr(handoff, "foreground_handle", lambda: state["foreground"])
    monkeypatch.setattr(handoff, "_focused_native_handle", lambda: state["focus"])
    monkeypatch.setattr(handoff, "_focus_belongs_to_window", lambda focus, handle: focus > 0 and handle == 10)
    monkeypatch.setattr(handoff, "_screen_point_belongs_to_window", lambda *_a: state["owned"])
    monkeypatch.setattr(handoff, "monotonic", lambda: state["clock"])
    monkeypatch.setattr(handoff, "sleep", lambda seconds: state.__setitem__("clock", state["clock"] + seconds))
    settings = {
        "vaccine_influenza_system_launch_url": "https://ois.kdca.go.kr/iroi/indexWSP.jsp",
        "vaccine_influenza_system_resident_x": "40",
        "vaccine_influenza_system_resident_y": "50",
    }
    return SimpleNamespace(state=state, settings=settings, document=document, documents=documents,
                           window=window, windows=windows)


def test_flu_clicks_saved_coordinate_without_edit_focus_or_value_readback(browser):
    target = handoff._resolve_input_target(browser.settings, "influenza")
    assert target is not None
    assert not target.ready()
    assert target.activate(lambda: True)
    assert browser.state["events"] == [("click", {"x": 40, "y": 50, "duration": 0})]
    assert target.ready()
    assert target.read_value is None


@pytest.mark.parametrize("key,value", [
    ("launch_url", ""), ("launch_url", "https://example.test/iroi/main"),
    ("launch_url", "http://ois.kdca.go.kr/iroi/main"),
    ("launch_url", "https://ois.kdca.go.kr/iris/index_run.jsp"),
    ("resident_x", "invalid"), ("resident_x", "200"), ("resident_y", "200"),
    ("window_title", "Other app"),
])
def test_invalid_target_configuration_does_not_click(browser, key, value):
    browser.settings[f"vaccine_influenza_system_{key}"] = value
    assert handoff._browser_input_target(browser.settings) is None
    assert browser.state["events"] == []


def test_unset_coordinates_do_not_fall_back_to_uia_field(browser):
    del browser.settings["vaccine_influenza_system_resident_x"]
    del browser.settings["vaccine_influenza_system_resident_y"]
    browser.settings["vaccine_influenza_system_resident_automation_id"] = "edtPtntRrn1"
    assert handoff._browser_input_target(browser.settings) is None


def test_multiple_matching_windows_are_rejected_but_repeated_frames_are_not(browser):
    browser.documents.append(browser.document)
    assert handoff._browser_input_target(browser.settings) is not None
    browser.windows.append(SimpleNamespace(**{**vars(browser.window), "handle": 11}))
    assert handoff._browser_input_target(browser.settings) is None


def test_later_matching_document_is_used(browser):
    other = SimpleNamespace(**{**vars(browser.document), "get_value": lambda: "https://ois.kdca.go.kr/iris/main"})
    browser.documents.insert(0, other)
    assert handoff._browser_input_target(browser.settings).activate(lambda: True)


def test_clicked_frame_navigation_stops_even_when_outer_page_remains_trusted(browser):
    browser.state["frame_url"] = "https://ois.kdca.go.kr/iroi/frame"
    frame = SimpleNamespace(**{
        **vars(browser.document),
        "element_info": SimpleNamespace(control_type="Document", runtime_id=(42, 2)),
        "get_value": lambda: browser.state["frame_url"],
    })
    browser.documents.append(frame)
    browser.state["hit"].parent = lambda: frame
    target = handoff._browser_input_target(browser.settings)
    assert target.activate(lambda: True)
    browser.state["frame_url"] = "https://example.test/other"
    assert not target.ready()


@pytest.mark.parametrize("failure", [
    "navigation", "covered", "moved", "disabled", "hidden", "replaced_document",
    "wrong_frame", "browser_chrome", "foreground", "stopped",
])
def test_coordinate_activation_stops_before_click_when_context_is_wrong(browser, failure):
    target = handoff._browser_input_target(browser.settings)
    state = browser.state
    if failure == "navigation":
        state["url"] = "https://example.test/iroi/patient"
    elif failure == "covered":
        state["owned"] = False
    elif failure == "moved":
        state["rectangle"].left = 60
    elif failure == "disabled":
        state["enabled"] = False
    elif failure == "hidden":
        state["visible"] = False
    elif failure == "replaced_document":
        browser.document.element_info.runtime_id = (42, 2)
    elif failure == "wrong_frame":
        state["hit"] = SimpleNamespace(
            element_info=SimpleNamespace(control_type="Document", runtime_id=(42, 9)),
            get_value=lambda: "https://example.test/iframe",
        )
    elif failure == "browser_chrome":
        state["hit"] = SimpleNamespace(element_info=SimpleNamespace(control_type="Edit"), parent=lambda: None)
    elif failure == "foreground":
        state["foreground"], state["focus_works"] = 11, False
    assert not target.activate(lambda: failure != "stopped")
    assert state["events"] == []


def test_no_native_keyboard_focus_after_click_stops_input(browser):
    target = handoff._browser_input_target(browser.settings)
    browser.state["focus"] = 0
    assert not target.activate(lambda: True)
    assert not target.ready()
    assert "after clicking" in target.activation_error()
    assert len(browser.state["events"]) == 1


@pytest.mark.parametrize("change", ["focus", "foreground", "url", "covered"])
def test_coordinate_ready_guard_detects_changes_after_click(browser, change):
    target = handoff._browser_input_target(browser.settings)
    assert target.activate(lambda: True)
    if change == "focus":
        browser.state["focus"] = 21
    elif change == "foreground":
        browser.state["foreground"] = 11
    elif change == "url":
        browser.state["url"] = "https://ois.kdca.go.kr/iris/main"
    else:
        browser.state["owned"] = False
    assert not target.ready()


@pytest.mark.parametrize("interrupt", [False, True])
def test_complete_flu_handoff_uses_thirteen_digit_keys_not_unicode_or_paste(browser, monkeypatch, interrupt):
    from pywinauto import keyboard

    events = browser.state["events"]
    monkeypatch.setattr(handoff, "interactive_desktop_error", lambda: None)
    monkeypatch.setattr(handoff, "_input_is_idle", lambda _ms: True)
    monkeypatch.setattr(handoff, "ensure_first_virtual_desktop", lambda: SimpleNamespace(success=True))
    monkeypatch.setattr(handoff, "first_virtual_desktop_is_active", lambda: True)
    monkeypatch.setattr(handoff, "_send_unicode_text", lambda text: pytest.fail("Flu must use digit keys"))

    def send_keys(keys, **kwargs):
        events.append(("keys", keys, kwargs))
        if interrupt and keys == "7":
            browser.state["foreground"] = 11

    monkeypatch.setattr(keyboard, "send_keys", send_keys)
    result = handoff.enter_vaccine_resident(
        browser.settings, handoff.VaccineHandoffRequest("influenza", "700101-1000000"),
    )
    assert events[0] == ("click", {"x": 40, "y": 50, "duration": 0})
    assert events[1] == ("keys", "^a", {"pause": 0.05})
    if interrupt:
        assert not result.success
        assert events[2:] == [("keys", "7", {"pause": 0.05, "vk_packet": False})]
    else:
        assert result.success
        assert events[2:-1] == [
            ("keys", digit, {"pause": 0.05, "vk_packet": False}) for digit in "7001011000000"
        ]
        assert events[-1] == ("keys", "{ENTER}", {"pause": 0.05})
    assert "700101" not in result.message
