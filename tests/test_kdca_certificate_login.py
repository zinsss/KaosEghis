from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import kdca_certificate_login


class _Element:
    def __init__(
        self,
        *,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        class_name: str = "",
        handle: int | None = None,
        children: list["_Element"] | None = None,
        legacy_value: str = "",
        on_activate=None,
        visible: bool = True,
        enabled: bool = True,
    ) -> None:
        self.element_info = SimpleNamespace(
            name=name,
            automation_id=automation_id,
            control_type=control_type,
            class_name=class_name,
        )
        self.handle = handle
        self._children = children or []
        self._legacy_value = legacy_value
        self._on_activate = on_activate
        self._visible = visible
        self._enabled = enabled
        self.focused = False
        self.activated = False

    def descendants(self, *, control_type: str = "") -> list["_Element"]:
        elements = []
        for child in self._children:
            elements.append(child)
            elements.extend(child.descendants())
        return [item for item in elements if not control_type or item.element_info.control_type == control_type]

    def window_text(self) -> str:
        return self.element_info.name

    def is_visible(self) -> bool:
        return self._visible

    def is_enabled(self) -> bool:
        return self._enabled

    def set_focus(self) -> None:
        self.focused = True

    def invoke(self) -> None:
        self.activated = True
        if self._on_activate is not None:
            self._on_activate()

    def legacy_properties(self) -> dict[str, str]:
        return {"Value": self._legacy_value} if self._legacy_value else {}


def _settings() -> dict[str, str]:
    return {
        "vaccine_kdca_portal_url": "https://is.kdca.go.kr/",
        "vaccine_kdca_browser_window_title_contains": "질병관리청",
        "vaccine_kdca_login_control_name": "공동인증서 로그인",
        "vaccine_kdca_logout_control_name": "로그아웃",
        "vaccine_kdca_certificate_window_title_contains": "인증서",
        "vaccine_kdca_certificate_name": "이진성34",
        "vaccine_kdca_password_window_title_contains": "인증서",
        "vaccine_kdca_password_automation_id": "",
        "vaccine_kdca_password_control_type": "Edit",
        "vaccine_kdca_confirm_control_name": "확인",
        "vaccine_kdca_credential_reference": "공인인증서 - 이진성",
    }


def test_kdca_login_requests_vault_only_after_login_is_confirmed(monkeypatch) -> None:
    opened: list[str] = []
    login = _Element(name="공동인증서 로그인", control_type="Button")
    browser = _Element(name="질병관리청", handle=101, children=[login])
    monkeypatch.setattr(
        kdca_certificate_login,
        "_open_portal",
        lambda url: opened.append(url) or True,
    )
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda _reference: None,
    )

    assert result.success is False
    assert result.status == "credential_unavailable"
    assert opened == ["https://is.kdca.go.kr/"]
    assert login.activated is False


def test_kdca_certificate_login_anchor_confirms_signed_out_state(monkeypatch) -> None:
    """Chrome may expose KDCA's fnPkiCall('pLo') anchor without link text."""

    link = _Element(
        control_type="Hyperlink",
        legacy_value="javascript:fnPkiCall('pLo');",
    )
    browser = _Element(name="질병관리청", handle=101, children=[link])
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    monkeypatch.setattr(kdca_certificate_login, "_open_portal", lambda _url: True)

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda _reference: None,
    )

    assert result.success is False
    assert result.status == "credential_unavailable"
    assert link.activated is False


def test_kdca_logout_anchor_confirms_authenticated_state(monkeypatch) -> None:
    """Chrome may expose KDCA's logout anchor without link text."""

    logout = _Element(control_type="Hyperlink", legacy_value="/isc/logout.do")
    browser = _Element(name="질병관리청", handle=101, children=[logout])
    password_requests: list[str] = []
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    monkeypatch.setattr(kdca_certificate_login, "_open_portal", lambda _url: True)

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda reference: password_requests.append(reference) or "secret",
    )

    assert result.success is True
    assert result.status == "already_authenticated"
    assert password_requests == []


@pytest.mark.parametrize(
    ("control_name", "expected_state"),
    [("공동인증서 로그인", "login_required"), ("로그아웃", "authenticated")],
)
def test_kdca_session_ignores_text_child_of_action_link(control_name, expected_state) -> None:
    link = _Element(name=control_name, control_type="Hyperlink")
    label = _Element(name=control_name, control_type="Text")
    browser = _Element(name="질병관리청", children=[link, label])
    config = kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(_settings())

    assert kdca_certificate_login._wait_for_session_state(browser, config, 0.1) == expected_state
    if expected_state == "login_required":
        assert kdca_certificate_login._find_single_kdca_login_control(browser, config) is link


def test_kdca_session_does_not_trust_unrelated_text_or_duplicate_links() -> None:
    config = kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(_settings())
    label_only = _Element(children=[_Element(name="로그아웃", control_type="Text")])
    duplicate_links = _Element(children=[
        _Element(name="공동인증서 로그인", control_type="Hyperlink"),
        _Element(name="공동인증서 로그인", control_type="Hyperlink"),
    ])
    assert kdca_certificate_login._wait_for_session_state(label_only, config, 0.1) == "unknown"
    assert kdca_certificate_login._wait_for_session_state(duplicate_links, config, 0.1) == "unknown"


def test_kdca_logout_accepts_absolute_kdca_url_but_not_other_origin() -> None:
    valid = _Element(control_type="Hyperlink", legacy_value="https://is.kdca.go.kr/isc/logout.do")
    invalid = _Element(control_type="Hyperlink", legacy_value="https://example.test/isc/logout.do")
    assert kdca_certificate_login._is_kdca_logout_control(valid, "로그아웃") is True
    assert kdca_certificate_login._is_kdca_logout_control(invalid, "로그아웃") is False


def test_kdca_unicode_input_uses_full_windows_input_structure(monkeypatch) -> None:
    import ctypes

    calls = []

    def send_input(count, events, size):
        calls.append((count, size, [(item.type, item.ki.wScan, item.ki.dwFlags) for item in events]))
        return count

    monkeypatch.setattr(
        ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=send_input)), raising=False
    )
    assert kdca_certificate_login._send_unicode_text("A한") is True
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert calls == [(4, expected_size, [
        (1, ord("A"), 0x0004), (1, ord("A"), 0x0006),
        (1, ord("한"), 0x0004), (1, ord("한"), 0x0006),
    ])]


@pytest.mark.parametrize("sent", [0, 1])
def test_kdca_unicode_input_rejects_failed_or_partial_send(monkeypatch, sent) -> None:
    import ctypes

    monkeypatch.setattr(
        ctypes, "windll",
        SimpleNamespace(user32=SimpleNamespace(SendInput=lambda *_args: sent)), raising=False,
    )
    assert kdca_certificate_login._send_unicode_text("A") is False


def test_kdca_login_uses_unique_verified_controls_without_exposing_password(
    monkeypatch,
) -> None:
    phase = {"value": "browser"}
    confirmed: list[bool] = []
    typed: list[tuple[object, str]] = []

    certificate = _Element(
        name="이진성34",
        control_type="ListItem",
        on_activate=lambda: phase.update(value="password"),
    )
    logout = _Element(name="로그아웃", control_type="Button")
    browser: _Element

    def mark_authenticated() -> None:
        confirmed.append(True)
        browser._children = [logout]

    confirm = _Element(
        name="확인",
        control_type="Button",
        on_activate=mark_authenticated,
    )
    password = _Element(control_type="Edit")
    password_window = _Element(
        name="인증서 비밀번호",
        handle=303,
        children=[password, confirm],
    )
    certificate_window = _Element(
        name="인증서 선택",
        handle=202,
        children=[certificate],
    )
    login = _Element(
        name="공동인증서 로그인",
        control_type="Hyperlink",
        on_activate=lambda: phase.update(value="certificate"),
    )
    browser = _Element(
        name="질병관리청 질병보건통합관리시스템 - Browser",
        handle=101,
        children=[login, _Element(name="공동인증서 로그인", control_type="Text")],
    )

    def windows() -> list[_Element]:
        if phase["value"] == "browser":
            return [browser]
        if phase["value"] == "certificate":
            return [browser, certificate_window]
        return [browser, certificate_window, password_window]

    opened: list[str] = []
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", windows)
    monkeypatch.setattr(
        kdca_certificate_login,
        "_open_portal",
        lambda url: opened.append(url) or True,
    )
    monkeypatch.setattr(
        kdca_certificate_login,
        "_type_secret",
        lambda target, value: typed.append((target, value)) or True,
    )

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda _reference: "test-certificate-password",
    )

    assert result.success is True
    assert result.status == "authenticated"
    assert opened == ["https://is.kdca.go.kr/"]
    assert login.activated is True
    assert certificate.activated is True
    assert typed == [(password, "test-certificate-password")]
    assert confirmed == [True]
    assert "test-certificate-password" not in result.message


def test_kdca_login_skips_vault_when_logout_control_confirms_session(monkeypatch) -> None:
    logout = _Element(name="로그아웃", control_type="Button")
    browser = _Element(name="질병관리청", handle=101, children=[logout])
    opened: list[str] = []
    password_requests: list[str] = []
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    monkeypatch.setattr(
        kdca_certificate_login,
        "_open_portal",
        lambda url: opened.append(url) or True,
    )

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda reference: password_requests.append(reference) or "secret",
    )

    assert result.success is True
    assert result.status == "already_authenticated"
    assert opened == ["https://is.kdca.go.kr/"]
    assert password_requests == []


def test_kdca_login_never_guesses_session_state_when_controls_are_missing(monkeypatch) -> None:
    browser = _Element(name="질병관리청", handle=101)
    password_requests: list[str] = []
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    monkeypatch.setattr(kdca_certificate_login, "_open_portal", lambda _url: True)
    monkeypatch.setattr(
        kdca_certificate_login,
        "_wait_for_session_state",
        lambda *_args: "unknown",
    )

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda reference: password_requests.append(reference) or "secret",
    )

    assert result.success is False
    assert result.status == "session_state_unknown"
    assert password_requests == []


def test_kdca_login_stops_when_certificate_is_not_uniquely_resolved(monkeypatch) -> None:
    phase = {"value": "browser"}
    login = _Element(
        name="공동인증서 로그인",
        control_type="Button",
        on_activate=lambda: phase.update(value="certificate"),
    )
    browser = _Element(name="질병관리청", handle=101, children=[login])
    certificate_window = _Element(
        name="인증서 선택",
        handle=202,
        children=[
            _Element(name="이진성34", control_type="ListItem"),
            _Element(name="이진성34", control_type="ListItem"),
        ],
    )

    monkeypatch.setattr(
        kdca_certificate_login,
        "_desktop_windows",
        lambda: [browser]
        if phase["value"] == "browser"
        else [browser, certificate_window],
    )
    monkeypatch.setattr(kdca_certificate_login, "_open_portal", lambda _url: True)
    typed: list[str] = []
    monkeypatch.setattr(
        kdca_certificate_login,
        "_type_secret",
        lambda _target, value: typed.append(value) or True,
    )

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda _reference: "test-certificate-password",
    )

    assert result.success is False
    assert result.status == "certificate_not_found"
    assert typed == []
    assert "test-certificate-password" not in result.message


def test_default_kdca_settings_are_non_secret_selectors() -> None:
    from KaosEghis.db.repositories import DEFAULT_SETTINGS

    config = kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(
        DEFAULT_SETTINGS
    )

    assert config.portal_url == "https://is.kdca.go.kr/"
    assert config.certificate_name == "이진성34"
    assert config.logout_control_name == "로그아웃"
    assert config.credential_reference == "공인인증서 - 이진성"
    assert (config.login_x, config.login_y) == (0, 0)
    assert "password" not in config.credential_reference.casefold()


def _web_picker(*, children=None, heading="인증서 입력 (전자서명)", **kwargs):
    return _Element(
        control_type="Window",
        class_name="xwup_common xwup_cert_pop",
        children=[_Element(control_type="Window", children=[
            _Element(name=heading, control_type="Text"), *(children or []),
        ])],
        **kwargs,
    )


@pytest.mark.parametrize("failure,expected_status", [
    ("", "authenticated"),
    ("certificate_duplicate", "certificate_not_found"),
    ("password_duplicate", "password_window_not_ready"),
    ("confirm_missing", "confirmation_failed"),
    ("confirm_duplicate", "confirmation_failed"),
])
def test_web_picker_login_is_scoped_to_unnamed_browser_dialog(monkeypatch, failure, expected_status):
    from dataclasses import replace

    config = replace(kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(_settings()), timeout_seconds=0.1)
    monkeypatch.setattr(kdca_certificate_login.KdcaCertificateLoginConfig, "from_settings", lambda _settings: config)
    certificate = _Element(name="이진성34", control_type="DataItem")
    password = _Element(control_type="Edit", automation_id="xwup_certselect_tek_input1")
    logout = _Element(name="로그아웃", control_type="Hyperlink")
    confirm = _Element(
        name="확인", control_type="Button", automation_id="xwup_OkButton",
        on_activate=lambda: setattr(browser, "_children", [logout]),
    )
    controls = [
        _Element(control_type="Pane", automation_id="xwup_cert_table", children=[
            _Element(name="certificate row with issuer and expiry", control_type="DataItem", children=[certificate]),
        ]),
        password,
    ]
    if failure != "confirm_missing":
        controls.append(confirm)
    if failure == "certificate_duplicate":
        controls.append(_Element(name="이진성34", control_type="DataItem"))
    if failure == "password_duplicate":
        controls.append(_Element(control_type="Edit"))
    if failure == "confirm_duplicate":
        controls.append(_Element(name="확인", control_type="Button"))
    picker = _web_picker(children=controls)
    login = _Element(
        name="공동인증서 로그인", control_type="Hyperlink",
        on_activate=lambda: browser._children.append(picker),
    )
    browser = _Element(name="질병관리청 - Chrome", handle=101, children=[
        login,
        _Element(control_type="Edit", automation_id="address_bar"),
        _Element(name="이진성34", control_type="Text"),
        _Element(name="확인", control_type="Button"),
    ])
    typed = []
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    monkeypatch.setattr(kdca_certificate_login, "_open_portal", lambda _url: True)
    monkeypatch.setattr(kdca_certificate_login, "_type_secret", lambda target, value: typed.append((target, value)) or True)

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(), password_provider=lambda _reference: "fake-password",
    )

    assert result.status == expected_status
    assert result.success is (not failure)
    assert typed == ([(password, "fake-password")] if not failure else [])
    assert confirm.activated is (not failure)
    assert "fake-password" not in result.message
    assert certificate.activated is (failure != "certificate_duplicate")


@pytest.mark.parametrize("failure", ["hidden", "disabled", "wrong_heading", "unknown_class", "other_browser"])
def test_web_picker_does_not_accept_unverified_dialogs(monkeypatch, failure):
    picker = _web_picker(
        visible=failure != "hidden", enabled=failure != "disabled",
        heading="Other dialog" if failure == "wrong_heading" else "인증서 입력 (전자서명)",
    )
    if failure == "unknown_class":
        picker.element_info.class_name = "unrelated"
    browser = _Element(name="질병관리청", handle=101, children=[] if failure == "other_browser" else [picker])
    other_browser = _Element(name="Other browser", handle=102, children=[picker])
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser, other_browser])
    assert kdca_certificate_login._wait_for_single_window(
        "인증서", 0.1, exclude_handles={101}, browser_window=browser,
    ) is None


def test_web_picker_rejects_multiple_visible_dialogs(monkeypatch):
    browser = _Element(name="질병관리청", handle=101, children=[_web_picker(), _web_picker()])
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    assert kdca_certificate_login._wait_for_single_window(
        "인증서", 0.1, exclude_handles={101}, browser_window=browser,
    ) is None


def test_web_picker_password_respects_configured_automation_id(monkeypatch):
    from dataclasses import replace

    config = replace(
        kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(_settings()),
        password_automation_id="configured-password",
    )
    password = _Element(control_type="Edit", automation_id="xwup_certselect_tek_input1")
    picker = _web_picker(children=[password])
    browser = _Element(name="질병관리청", handle=101, children=[picker])
    monkeypatch.setattr(kdca_certificate_login, "_desktop_windows", lambda: [browser])
    assert kdca_certificate_login._wait_for_password_target(
        config, "인증서", 0.1, exclude_handles={101}, browser_window=browser,
    ) == (None, None)
    password.element_info.automation_id = "configured-password"
    assert kdca_certificate_login._wait_for_password_target(
        config, "인증서", 0.1, exclude_handles={101}, browser_window=browser,
    ) == (picker, password)


def test_kdca_login_coordinate_fallback_requires_the_trusted_browser_point(
    monkeypatch,
) -> None:
    config = kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(
        _settings() | {"vaccine_kdca_login_x": "100", "vaccine_kdca_login_y": "200"}
    )
    browser = _Element(name="질병관리청", handle=101)
    clicks: list[tuple[int, int]] = []
    monkeypatch.setattr(
        kdca_certificate_login,
        "_screen_point_belongs_to_window",
        lambda handle, x, y: (handle, x, y) == (101, 100, 200),
    )
    monkeypatch.setitem(
        sys.modules,
        "pyautogui",
        SimpleNamespace(click=lambda *, x, y, duration: clicks.append((x, y))),
    )

    assert kdca_certificate_login._click_configured_login_point(browser, config) is True
    assert browser.focused is True
    assert clicks == [(100, 200)]


def test_kdca_login_coordinate_fallback_never_clicks_outside_browser(monkeypatch) -> None:
    config = kdca_certificate_login.KdcaCertificateLoginConfig.from_settings(
        _settings() | {"vaccine_kdca_login_x": "100", "vaccine_kdca_login_y": "200"}
    )
    browser = _Element(name="질병관리청", handle=101)
    monkeypatch.setattr(
        kdca_certificate_login,
        "_screen_point_belongs_to_window",
        lambda *_args: False,
    )

    assert kdca_certificate_login._click_configured_login_point(browser, config) is False
