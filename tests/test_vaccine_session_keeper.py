from __future__ import annotations

import sys
from types import SimpleNamespace

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
