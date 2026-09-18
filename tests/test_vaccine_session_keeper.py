from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_session_keeper


class FakeWindowApi:
    def __init__(self, windows: dict[int, dict[str, object]], point_handle: int = 0) -> None:
        self.windows = windows
        self.point_handle = point_handle

    def EnumWindows(self, callback, value) -> None:
        for handle in self.windows:
            callback(handle, value)

    def IsWindowVisible(self, handle: int) -> bool:
        return bool(self.windows[handle].get("visible", True))

    def GetWindowText(self, handle: int) -> str:
        return str(self.windows[handle]["title"])

    def GetClassName(self, handle: int) -> str:
        return str(self.windows[handle]["class_name"])

    def IsIconic(self, handle: int) -> bool:
        return bool(self.windows[handle].get("minimized", False))

    def IsWindowEnabled(self, handle: int) -> bool:
        return bool(self.windows[handle].get("enabled", True))

    def GetWindowRect(self, handle: int) -> tuple[int, int, int, int]:
        return self.windows[handle].get("rect", (0, 0, 3000, 3000))

    def WindowFromPoint(self, _point: tuple[int, int]) -> int:
        return self.point_handle


def _target() -> vaccine_session_keeper.VaccineSessionResetTarget:
    return vaccine_session_keeper.VaccineSessionResetTarget(
        key="general",
        label="General vaccine system",
        window_title="General vaccine",
        window_class="CyWindowClass",
        reset_x=1154,
        reset_y=1968,
    )


def _install_windows(monkeypatch, fake_windows: FakeWindowApi) -> None:
    monkeypatch.setitem(sys.modules, "win32gui", fake_windows)
    monkeypatch.delitem(sys.modules, "win32con", raising=False)


@pytest.fixture(autouse=True)
def simulated_input(monkeypatch):
    monkeypatch.setattr(vaccine_session_keeper, "interactive_desktop_error", lambda: None)
    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle", lambda _minimum: True)
    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop",
                        lambda: SimpleNamespace(success=True))
    monkeypatch.setattr(vaccine_session_keeper, "first_virtual_desktop_is_active", lambda: True)


@pytest.fixture
def verified_window(monkeypatch):
    api = FakeWindowApi({101: {
        "title": "General vaccine", "class_name": "CyWindowClass",
    }}, point_handle=101)
    _install_windows(monkeypatch, api)
    clicks = []
    monkeypatch.setattr(vaccine_session_keeper, "_click_screen_coordinate",
                        lambda x, y: clicks.append((x, y)) or True)
    return api, clicks


def test_configured_session_targets_include_general_and_covid_only() -> None:
    targets = vaccine_session_keeper.configured_session_reset_targets(
        {
            "vaccine_general_system_window_title": "General",
            "vaccine_general_system_window_class": "GeneralClass",
            "vaccine_general_system_keepalive_x": "1",
            "vaccine_general_system_keepalive_y": "2",
            "vaccine_covid_system_window_title": "COVID",
            "vaccine_covid_system_window_class": "CovidClass",
            "vaccine_covid_system_keepalive_x": "3",
            "vaccine_covid_system_keepalive_y": "4",
        }
    )

    assert [target.key for target in targets] == ["general", "covid"]
    assert all(target.is_configured for target in targets)


def test_session_reset_clicks_only_verified_native_window(monkeypatch) -> None:
    fake_windows = FakeWindowApi(
        {
            101: {
                "title": "General vaccine",
                "class_name": "CyWindowClass",
                "rect": (100, 100, 2000, 2100),
            }
        },
        point_handle=101,
    )
    _install_windows(monkeypatch, fake_windows)
    clicks: list[tuple[int, int]] = []
    monkeypatch.setattr(
        vaccine_session_keeper,
        "_click_screen_coordinate",
        lambda x, y: clicks.append((x, y)) or True,
    )

    result = vaccine_session_keeper.reset_vaccine_session(_target())

    assert result.status == "reset_sent"
    assert result.clicked is True
    assert clicks == [(1154, 1968)]


def test_session_reset_skips_closed_or_covered_system_without_click(monkeypatch) -> None:
    fake_windows = FakeWindowApi(
        {
            101: {
                "title": "General vaccine",
                "class_name": "CyWindowClass",
                "rect": (100, 100, 2000, 2100),
            },
            202: {
                "title": "Other application",
                "class_name": "OtherClass",
                "rect": (100, 100, 2000, 2100),
            },
        },
        point_handle=202,
    )
    _install_windows(monkeypatch, fake_windows)
    clicks: list[tuple[int, int]] = []
    monkeypatch.setattr(
        vaccine_session_keeper,
        "_click_screen_coordinate",
        lambda x, y: clicks.append((x, y)) or True,
    )

    covered = vaccine_session_keeper.reset_vaccine_session(_target())
    fake_windows.windows.clear()
    closed = vaccine_session_keeper.reset_vaccine_session(_target())

    assert covered.status == "point_not_ready"
    assert closed.status == "not_open"
    assert clicks == []


def test_session_reset_requires_complete_configuration(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace())
    target = vaccine_session_keeper.VaccineSessionResetTarget(
        key="covid",
        label="COVID system",
        window_title="COVID",
        window_class="",
        reset_x=2456,
        reset_y=1982,
    )

    result = vaccine_session_keeper.reset_vaccine_session(target)

    assert result.status == "configuration_required"
    assert result.clicked is False


@pytest.mark.parametrize("idle,expected", [(False, "input_busy"), (None, "unavailable")])
def test_automatic_reset_defers_active_or_unreadable_input(monkeypatch, verified_window, idle, expected):
    _api, clicks = verified_window
    thresholds = []
    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle",
                        lambda minimum: thresholds.append(minimum) or idle)
    result = vaccine_session_keeper.reset_vaccine_session(_target(), require_idle=True)
    assert result.status == expected
    assert thresholds == [5000]
    assert not result.clicked
    assert clicks == []


def test_manual_reset_does_not_require_five_seconds_since_button_click(monkeypatch, verified_window):
    _api, clicks = verified_window
    thresholds = []
    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle",
                        lambda minimum: thresholds.append(minimum) or True)
    assert vaccine_session_keeper.reset_vaccine_session(_target()).clicked
    assert thresholds == [0, 0]
    assert len(clicks) == 1


def test_reset_rechecks_point_after_input_check(monkeypatch, verified_window):
    api, clicks = verified_window

    def idle(_minimum):
        api.point_handle = 0
        return True

    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle", idle)
    result = vaccine_session_keeper.reset_vaccine_session(_target(), require_idle=True)
    assert result.status == "point_not_ready"
    assert clicks == []


def test_reset_blocks_locked_desktop(monkeypatch, verified_window):
    _api, clicks = verified_window
    monkeypatch.setattr(vaccine_session_keeper, "interactive_desktop_error", lambda: "locked")
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "desktop_unavailable"
    assert clicks == []


def test_reset_blocks_disabled_system(verified_window):
    api, clicks = verified_window
    api.windows[101]["enabled"] = False
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "point_not_ready"
    assert clicks == []


def test_reset_switches_before_testing_coordinate_on_other_desktop(monkeypatch, verified_window):
    api, clicks = verified_window
    api.point_handle = 0
    events = []

    def switch():
        events.append("switch")
        api.point_handle = 101
        return SimpleNamespace(success=True)

    original = api.WindowFromPoint

    def point(coords):
        events.append("point")
        return original(coords)

    monkeypatch.setattr(api, "WindowFromPoint", point)
    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop", switch)
    assert vaccine_session_keeper.reset_vaccine_session(_target(), require_idle=True).clicked
    assert events == ["switch", "point", "point"]
    assert len(clicks) == 1


@pytest.mark.parametrize("automatic", [False, True])
def test_busy_input_blocks_desktop_switch(monkeypatch, verified_window, automatic):
    _api, clicks = verified_window
    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle", lambda _minimum: False)

    def forbidden():
        raise AssertionError("Must not switch while operator is using input")

    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop", forbidden)
    assert vaccine_session_keeper.reset_vaccine_session(_target(), require_idle=automatic).status == "input_busy"
    assert clicks == []


def test_failed_desktop_switch_never_clicks(monkeypatch, verified_window):
    _api, clicks = verified_window
    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop", lambda: SimpleNamespace(
        success=False, status="desktop_switch_failed", message="Switch failed.",
    ))
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "desktop_switch_failed"
    assert clicks == []


def test_operator_leaving_desktop_one_prevents_click(monkeypatch, verified_window):
    _api, clicks = verified_window
    monkeypatch.setattr(vaccine_session_keeper, "first_virtual_desktop_is_active", lambda: False)
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "desktop_switch_failed"
    assert clicks == []


def test_input_resuming_after_switch_prevents_click(monkeypatch, verified_window):
    _api, clicks = verified_window
    idle = iter([True, False])
    monkeypatch.setattr(vaccine_session_keeper, "_input_is_idle", lambda _minimum: next(idle))
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "input_busy"
    assert clicks == []


def test_changed_window_after_switch_prevents_click(monkeypatch, verified_window):
    api, clicks = verified_window

    def switch():
        api.windows[202] = api.windows.pop(101)
        api.point_handle = 202
        return SimpleNamespace(success=True)

    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop", switch)
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "point_not_ready"
    assert clicks == []


def test_closed_system_does_not_switch_desktops(monkeypatch, verified_window):
    api, clicks = verified_window
    api.windows.clear()

    def forbidden():
        raise AssertionError("Must not switch for a closed system")

    monkeypatch.setattr(vaccine_session_keeper, "ensure_first_virtual_desktop", forbidden)
    assert vaccine_session_keeper.reset_vaccine_session(_target()).status == "not_open"
    assert clicks == []
