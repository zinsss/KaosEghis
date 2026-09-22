from types import SimpleNamespace

import pytest

from KaosEghis.core import kdca_browser as browser
from KaosEghis.core import vaccine_system_launch as launch


class Element:
    def __init__(self, *, url="", kind="Document", visible=True, handle=0, parent=None):
        self.url = url
        self.element_info = SimpleNamespace(control_type=kind)
        self.visible = visible
        self.handle = handle
        self._parent = parent

    def get_value(self):
        return self.url

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return True

    def set_focus(self):
        pass

    def parent(self):
        return self._parent


@pytest.mark.parametrize("actual,visible,match", [
    ("https://is.kdca.go.kr/isc/main", True, True),
    ("https://is.kdca.go.kr/", False, False),
    ("https://unrelated.test/", True, False),
    ("https://is.kdca.go.kr.unrelated.test/", True, False),
    ("http://is.kdca.go.kr/", True, False),
    ("", True, False),
])
def test_document_binding_requires_visible_exact_origin(actual, visible, match):
    document = Element(url=actual, visible=visible)
    window = SimpleNamespace(descendants=lambda **_kwargs: [document])
    result = browser.document_for_url(window, "https://is.kdca.go.kr/")
    assert result is (document if match else None)


@pytest.mark.parametrize("failure", ["", "modal", "page_edit", "lost_focus", "partial_input", "cancelled"])
def test_navigation_is_bound_to_browser_address_field(monkeypatch, failure):
    import pywinauto
    import pywinauto.keyboard
    from KaosEghis.core import kdca_certificate_login

    events = []
    window = Element(kind="Window", handle=101)
    parent = Element(kind="Document", parent=window) if failure == "page_edit" else window
    address = Element(kind="Edit", parent=parent)
    monkeypatch.setattr(pywinauto, "Desktop", lambda **_kwargs: SimpleNamespace(
        window=lambda **_kwargs: SimpleNamespace(wrapper_object=lambda: window),
    ))
    monkeypatch.setattr(browser, "focused_element", lambda: address)
    monkeypatch.setattr(browser, "foreground_handle", lambda: 202 if failure == "modal" else 101)
    monkeypatch.setattr(browser, "has_keyboard_focus", lambda _field: failure != "lost_focus" or not events)
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda value, **_kwargs: events.append(value))
    monkeypatch.setattr(kdca_certificate_login, "_send_unicode_text", lambda value: events.append(value) or failure != "partial_input")

    assert browser.navigate_browser(101, "https://ois.kdca.go.kr/iris/index_run.jsp", cancelled=lambda: failure == "cancelled") is (not failure)
    if failure:
        assert "{ENTER}" not in events
    else:
        assert events == ["^l", "https://ois.kdca.go.kr/iris/index_run.jsp", "{ENTER}"]


@pytest.fixture
def fake_clock(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(launch.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(launch.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    return clock


@pytest.mark.parametrize("system", ["general", "covid", "influenza"])
def test_launch_uses_authenticated_browser_and_waits_for_real_system(monkeypatch, fake_clock, system):
    activated = []
    class Portal:
        phase = "portal_menu"
        waiting_message = "waiting for portal menu"

        def __init__(self, settings, key, hwnd, **_kwargs):
            assert key == system and hwnd == 101

        def advance(self):
            if self.phase == "portal_menu":
                activated.append(system)
                self.phase = "system_window"

    monkeypatch.setattr(launch, "KdcaPortalLaunch", Portal)
    url = "https://ois.kdca.go.kr/fixture"
    result = launch.open_vaccine_system(
        {f"vaccine_{system}_system_launch_url": url}, system, browser_handle=101,
        opener=lambda *_args, **_kwargs: pytest.fail("must not open another browser"),
        ready=lambda *_args: fake_clock[0] >= 2,
        timeout_seconds=3,
    )
    assert result.success
    assert fake_clock[0] == 2
    assert activated == [system]


def test_browser_accepting_url_is_not_system_launch_success(fake_clock):
    requests = []
    result = launch.open_vaccine_system(
        {"vaccine_general_system_launch_url": "https://ois.kdca.go.kr/iris/index_run.jsp"}, "general",
        opener=lambda *_args, **_kwargs: requests.append(True) or True,
        ready=lambda *_args: False, timeout_seconds=1,
    )
    assert not result.success
    assert "not detected" in result.message
    assert len(requests) == 1


def test_failed_portal_menu_does_not_fall_back_to_default_browser(monkeypatch):
    monkeypatch.setattr(launch, "KdcaPortalLaunch", lambda *_args, **_kwargs: SimpleNamespace(
        phase="portal_menu", waiting_message="waiting for portal menu",
        advance=lambda: "Could not activate menu. Check browser focus.",
    ))
    result = launch.open_vaccine_system(
        {"vaccine_general_system_launch_url": "https://ois.kdca.go.kr/iris/index_run.jsp"}, "general",
        browser_handle=101, ready=lambda *_args: False,
        opener=lambda *_args, **_kwargs: pytest.fail("wrong browser fallback"),
    )
    assert not result.success
    assert "browser focus" in result.message


def test_menu_activation_without_destination_does_not_report_success(monkeypatch, fake_clock):
    actions = []
    portal = SimpleNamespace(phase="portal_menu", waiting_message="waiting for launch link")
    def advance():
        if portal.phase == "portal_menu":
            actions.append("menu")
            portal.phase = "system_link"
    portal.advance = advance
    monkeypatch.setattr(launch, "KdcaPortalLaunch", lambda *_args, **_kwargs: portal)
    result = launch.open_vaccine_system(
        {"vaccine_general_system_launch_url": "https://ois.kdca.go.kr/iris/index_run.jsp"}, "general",
        browser_handle=101, ready=lambda *_args: False, timeout_seconds=2,
        opener=lambda *_args, **_kwargs: pytest.fail("direct URL fallback"),
    )
    assert not result.success
    assert "launch-control text" in result.message
    assert actions == ["menu"]


def test_portal_cancellation_stops_before_launch(monkeypatch, fake_clock):
    portal = SimpleNamespace(phase="portal_menu", waiting_message="waiting for menu",
                             advance=lambda: pytest.fail("cancelled click"))
    monkeypatch.setattr(launch, "KdcaPortalLaunch", lambda *_args, **_kwargs: portal)
    result = launch.open_vaccine_system(
        {"vaccine_general_system_launch_url": "https://ois.kdca.go.kr/iris/index_run.jsp"}, "general",
        browser_handle=101, ready=lambda *_args: False, cancelled=lambda: True,
    )
    assert not result.success
    assert "cancelled" in result.message


def test_existing_native_system_is_not_relaunched(fake_clock):
    result = launch.open_vaccine_system(
        {"vaccine_covid_system_launch_url": "https://ois.kdca.go.kr/covr/index_run.jsp"}, "covid",
        opener=lambda *_args, **_kwargs: pytest.fail("duplicate launch"),
        ready=lambda *_args: True,
    )
    assert result.success and "already open" in result.message


@pytest.mark.parametrize("handles,focus_ok,success", [([202], True, True), ([202], False, False), ([202, 203], True, False)])
def test_native_existing_window_is_focused_without_duplicate_launch(monkeypatch, handles, focus_ok, success):
    focused = []
    monkeypatch.setattr(launch, "_native_handles", lambda *_args: handles)
    monkeypatch.setattr(launch, "_focus_native_window", lambda hwnd: focused.append(hwnd) or focus_ok)
    result = launch.open_vaccine_system(
        {"vaccine_covid_system_launch_url": "https://ois.kdca.go.kr/covr/index_run.jsp"}, "covid",
        opener=lambda *_args, **_kwargs: pytest.fail("duplicate launch"),
    )
    assert result.success is success
    assert focused == ([202] if len(handles) == 1 else [])
