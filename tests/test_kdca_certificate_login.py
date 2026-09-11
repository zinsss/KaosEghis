from __future__ import annotations

from types import SimpleNamespace

from KaosEghis.core import kdca_certificate_login


class _Element:
    def __init__(
        self,
        *,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        handle: int | None = None,
        children: list["_Element"] | None = None,
        on_activate=None,
    ) -> None:
        self.element_info = SimpleNamespace(
            name=name,
            automation_id=automation_id,
            control_type=control_type,
        )
        self.handle = handle
        self._children = children or []
        self._on_activate = on_activate
        self.focused = False
        self.activated = False

    def descendants(self) -> list["_Element"]:
        return list(self._children)

    def window_text(self) -> str:
        return self.element_info.name

    def is_visible(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def set_focus(self) -> None:
        self.focused = True

    def invoke(self) -> None:
        self.activated = True
        if self._on_activate is not None:
            self._on_activate()


def _settings() -> dict[str, str]:
    return {
        "vaccine_kdca_portal_url": "https://is.kdca.go.kr/",
        "vaccine_kdca_browser_window_title_contains": "질병관리청",
        "vaccine_kdca_login_control_name": "공동인증서 로그인",
        "vaccine_kdca_certificate_window_title_contains": "인증서",
        "vaccine_kdca_certificate_name": "이진성34",
        "vaccine_kdca_password_window_title_contains": "인증서",
        "vaccine_kdca_password_automation_id": "",
        "vaccine_kdca_password_control_type": "Edit",
        "vaccine_kdca_confirm_control_name": "확인",
        "vaccine_kdca_credential_reference": "공인인증서 - 이진성",
    }


def test_kdca_login_requires_unlocked_vault_before_opening_portal(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        kdca_certificate_login,
        "_open_portal",
        lambda url: opened.append(url) or True,
    )

    result = kdca_certificate_login.start_kdca_certificate_login(
        _settings(),
        password_provider=lambda _reference: None,
    )

    assert result.success is False
    assert result.status == "credential_unavailable"
    assert opened == []


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
    confirm = _Element(
        name="확인",
        control_type="Button",
        on_activate=lambda: confirmed.append(True),
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
        control_type="Button",
        on_activate=lambda: phase.update(value="certificate"),
    )
    browser = _Element(
        name="질병관리청 질병보건통합관리시스템 - Browser",
        handle=101,
        children=[login],
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
    assert result.status == "submitted"
    assert opened == ["https://is.kdca.go.kr/"]
    assert login.activated is True
    assert certificate.activated is True
    assert typed == [(password, "test-certificate-password")]
    assert confirmed == [True]
    assert "test-certificate-password" not in result.message


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
    assert config.credential_reference == "공인인증서 - 이진성"
    assert "password" not in config.credential_reference.casefold()
