from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_system_input as handoff


@pytest.fixture
def input_target(monkeypatch):
    state = {"focused": True, "typed": "", "keys": [], "activated": 0}

    def activate(guard):
        state["activated"] += 1
        return guard() and state["focused"]

    target = handoff._InputTarget(
        activate, lambda: state["focused"], lambda: state["typed"]
    )
    monkeypatch.setattr(handoff, "interactive_desktop_error", lambda: None)
    monkeypatch.setattr(handoff, "_input_is_idle", lambda _ms: True)
    monkeypatch.setattr(handoff, "ensure_first_virtual_desktop", lambda: SimpleNamespace(success=True))
    monkeypatch.setattr(handoff, "first_virtual_desktop_is_active", lambda: True)
    monkeypatch.setattr(handoff, "_resolve_input_target", lambda *_args: target)
    monkeypatch.setattr(handoff, "_send_keys", state["keys"].append)

    def type_digit(digit):
        state["typed"] += digit
        return True

    monkeypatch.setattr(handoff, "_send_unicode_text", type_digit)
    return state


@pytest.mark.parametrize("program,system", [
    ("national_influenza", "influenza"), ("national_covid", "covid"),
    ("general", "general"), ("general_influenza", "general"), ("unknown", ""),
])
def test_handoff_routing_uses_program_not_product_name(program, system):
    request = handoff.handoff_request_for_record(SimpleNamespace(
        program_type=program, patient_resident_id="700101-1000000"
    ))
    assert request.system == system
    assert "700101" not in repr(request)


@pytest.mark.parametrize("system", ["general", "covid", "influenza"])
def test_handoff_sends_digits_and_exactly_one_enter(input_target, system):
    result = handoff.enter_vaccine_resident({}, handoff.VaccineHandoffRequest(system, "700101-1000000"))
    assert result.success
    assert input_target["typed"] == "7001011000000"
    assert input_target["keys"] == ["^a", "{ENTER}"]
    assert "700101" not in result.message


@pytest.mark.parametrize("resident", ["", "700101-1", "700101-123456X", "7" * 14, "７" * 13])
def test_invalid_resident_never_activates_or_types(input_target, resident):
    result = handoff.enter_vaccine_resident({}, handoff.VaccineHandoffRequest("covid", resident))
    assert not result.success
    assert input_target["activated"] == 0
    assert input_target["keys"] == []


@pytest.mark.parametrize("guard", ["locked", "busy", "desktop", "missing", "focus", "cancelled"])
def test_handoff_fails_closed_before_input(input_target, monkeypatch, guard):
    if guard == "locked":
        monkeypatch.setattr(handoff, "interactive_desktop_error", lambda: "locked")
    elif guard == "busy":
        monkeypatch.setattr(handoff, "_input_is_idle", lambda _ms: False)
    elif guard == "desktop":
        monkeypatch.setattr(handoff, "ensure_first_virtual_desktop", lambda: SimpleNamespace(success=False))
    elif guard == "missing":
        monkeypatch.setattr(handoff, "_resolve_input_target", lambda *_args: None)
    elif guard == "focus":
        input_target["focused"] = False
    result = handoff.enter_vaccine_resident(
        {}, handoff.VaccineHandoffRequest("general", "700101-1000000"),
        cancelled=lambda: guard == "cancelled",
    )
    assert not result.success
    assert input_target["typed"] == ""
    assert input_target["keys"] == []


@pytest.mark.parametrize("change", ["focus", "desktop", "cancelled", "timeout"])
def test_interrupted_typing_never_sends_enter(input_target, monkeypatch, change):
    def write(digit):
        input_target["typed"] += digit
        if change == "focus":
            input_target["focused"] = False
        elif change == "desktop":
            monkeypatch.setattr(handoff, "first_virtual_desktop_is_active", lambda: False)
        elif change == "timeout":
            monkeypatch.setattr(handoff, "monotonic", lambda: float("inf"))
        return True

    monkeypatch.setattr(handoff, "_send_unicode_text", write)
    result = handoff.enter_vaccine_resident(
        {}, handoff.VaccineHandoffRequest("general", "700101-1000000"),
        cancelled=lambda: change == "cancelled" and bool(input_target["typed"]),
    )
    assert not result.success
    assert len(input_target["typed"]) == 1
    assert input_target["keys"] == ["^a"]


def test_readback_mismatch_does_not_submit(input_target, monkeypatch):
    target = handoff._InputTarget(lambda guard: guard(), lambda: True, lambda: "incorrect")
    monkeypatch.setattr(handoff, "_resolve_input_target", lambda *_args: target)
    result = handoff.enter_vaccine_resident({}, handoff.VaccineHandoffRequest("influenza", "700101-1000000"))
    assert not result.success
    assert input_target["keys"] == ["^a"]


def test_provider_exception_does_not_expose_resident(input_target, monkeypatch):
    def explode(_digit):
        raise RuntimeError("patient 700101-1000000")

    monkeypatch.setattr(handoff, "_send_unicode_text", explode)
    result = handoff.enter_vaccine_resident({}, handoff.VaccineHandoffRequest("general", "700101-1000000"))
    assert not result.success
    assert "700101" not in result.message
    assert "{ENTER}" not in input_target["keys"]


def test_native_target_rechecks_point_focus_and_window(input_target, monkeypatch):
    import sys

    state = {"title": "Test System", "focus": 20, "point": True, "clicks": []}
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        GetWindowText=lambda _h: state["title"], GetClassName=lambda _h: "TestClass",
        IsWindowEnabled=lambda _h: True,
        WindowFromPoint=lambda _point: 20,
    ))
    monkeypatch.setitem(sys.modules, "pyautogui", SimpleNamespace(
        click=lambda **kwargs: state["clicks"].append(kwargs)
    ))
    monkeypatch.setattr(handoff, "find_native_vaccine_windows", lambda *_args: [10])
    monkeypatch.setattr(handoff, "foreground_handle", lambda: 10)
    monkeypatch.setattr(handoff, "_focus_native_window", lambda _h: True)
    monkeypatch.setattr(handoff, "_screen_point_belongs_to_window", lambda *_args: state["point"])
    monkeypatch.setattr(handoff, "_focused_native_handle", lambda: state["focus"])
    monkeypatch.setattr(handoff, "_focus_belongs_to_window", lambda *_args: True)
    settings = {
        "vaccine_general_system_window_title": "Test System",
        "vaccine_general_system_window_class": "TestClass",
        "vaccine_general_system_resident_x": "40",
        "vaccine_general_system_resident_y": "50",
    }
    target = handoff._native_input_target(settings, "general")
    assert target.activate(lambda: True)
    assert state["clicks"] == [{"x": 40, "y": 50, "duration": 0}]
    assert target.ready()
    state["focus"] = 21
    assert not target.ready()
    state["focus"] = 20
    state["point"] = False
    assert not target.ready()
    assert not target.activate(lambda: True)
    state["point"] = True
    state["title"] = "Wrong window"
    assert not target.ready()
    assert not target.activate(lambda: False)
    assert len(state["clicks"]) == 1
    monkeypatch.setattr(handoff, "find_native_vaccine_windows", lambda *_args: [10, 11])
    assert handoff._native_input_target(settings, "general") is None


def test_browser_target_is_scoped_and_rechecks_origin(monkeypatch):
    import sys

    state = {"url": "https://ois.kdca.go.kr/iroi/main", "focus": True}
    control = SimpleNamespace(
        element_info=SimpleNamespace(automation_id="edtPtntRrn1"),
        is_visible=lambda: True, is_enabled=lambda: True, set_focus=lambda: None,
        get_value=lambda: "7001011000000",
    )
    document = SimpleNamespace(
        descendants=lambda **_kwargs: [control], is_visible=lambda: True,
        get_value=lambda: state["url"],
    )
    window = SimpleNamespace(
        handle=10, element_info=SimpleNamespace(class_name="Chrome_WidgetWin_1"),
        set_focus=lambda: None, is_enabled=lambda: True,
    )
    windows = [window]
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(
        Desktop=lambda **_kw: SimpleNamespace(windows=lambda: windows)
    ))
    monkeypatch.setattr(handoff, "document_for_url", lambda *_args: document)
    monkeypatch.setattr(handoff, "foreground_handle", lambda: 10)
    monkeypatch.setattr(handoff, "has_keyboard_focus", lambda _c: state["focus"])
    settings = {
        "vaccine_influenza_system_launch_url": "https://ois.kdca.go.kr/iroi/indexWSP.jsp",
        "vaccine_influenza_system_resident_automation_id": "edtPtntRrn1",
    }
    target = handoff._browser_input_target(settings)
    assert target.activate(lambda: True)
    assert target.ready()
    state["url"] = "https://example.test/"
    assert not target.ready()
    assert handoff._browser_input_target(settings) is None
    state["url"] = "https://ois.kdca.go.kr/covr/main"
    assert not target.ready()
    assert handoff._browser_input_target(settings) is None
    state["url"] = "https://ois.kdca.go.kr/iroi/main"
    windows.append(window)
    assert handoff._browser_input_target(settings) is None
