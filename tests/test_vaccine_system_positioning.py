from types import SimpleNamespace
import sys

import pytest

from KaosEghis.core.vaccine_system_launch import (
    VaccineSystemPositioner,
    _send_positioning_key,
)


class FakeWindows:
    def __init__(self):
        self.handles = [101]
        self.foreground = 999
        self.focus_allowed = True
        self.minimized = False
        self.restored = []
        self.title = "Vaccine system"
        self.class_name = "CyWindowClass"

    def EnumWindows(self, callback, _):
        for handle in self.handles:
            callback(handle, None)

    def IsWindowVisible(self, _):
        return True

    def GetWindowText(self, _):
        return self.title

    def GetClassName(self, _):
        return self.class_name

    def IsIconic(self, _):
        return self.minimized

    def ShowWindow(self, handle, state):
        self.restored.append((handle, state))
        self.minimized = False

    def BringWindowToTop(self, _):
        pass

    def SetForegroundWindow(self, handle):
        if self.focus_allowed:
            self.foreground = handle

    def GetForegroundWindow(self):
        return self.foreground


def _positioner(system="general", **kwargs):
    now = [0.0]
    sent = []
    windows = FakeWindows()
    positioner = VaccineSystemPositioner(
        {
            f"vaccine_{system}_system_window_title": "Vaccine system",
            f"vaccine_{system}_system_window_class": "CyWindowClass",
        },
        system,
        window_api=windows,
        key_sender=lambda direction: sent.append(direction) or True,
        clock=lambda: now[0],
        **kwargs,
    )
    return positioner, now, windows, sent


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("general", ["left", "left", "left", "down"]),
        ("covid", ["left", "left", "left", "down", "right"]),
    ],
)
def test_positions_only_after_window_appears_and_one_second_passes(system, expected):
    positioner, now, windows, sent = _positioner(system)
    windows.handles = []
    assert positioner.advance() is None
    now[0] = 5.0
    windows.handles = [101]
    assert positioner.advance() is None
    now[0] = 5.99
    assert positioner.advance() is None
    assert sent == []
    assert windows.foreground == 999

    now[0] = 6.0
    result = positioner.advance()
    assert sent == ["left"]
    assert windows.foreground == 101
    for _ in expected[1:]:
        now[0] += 0.21
        result = positioner.advance()
    assert result.success is True
    assert sent == expected
    assert positioner.advance() is result
    assert sent == expected


def test_positioning_times_out_without_window_or_keys():
    positioner, now, windows, sent = _positioner(timeout_seconds=2)
    windows.handles = []
    assert positioner.advance() is None
    now[0] = 2.0
    assert positioner.advance().success is False
    assert sent == []


@pytest.mark.parametrize("replacement", [[], [202], [101, 202]])
def test_positioning_stops_if_window_closes_changes_or_becomes_ambiguous(replacement):
    positioner, now, windows, sent = _positioner()
    assert positioner.advance() is None
    windows.handles = replacement
    now[0] = 1.0
    assert positioner.advance().success is False
    assert sent == []


def test_positioning_never_sends_keys_when_focus_fails():
    positioner, now, windows, sent = _positioner()
    windows.focus_allowed = False
    assert positioner.advance() is None
    now[0] = 1.0
    assert positioner.advance().success is False
    assert sent == []


def test_positioning_stops_without_stealing_focus_back():
    positioner, now, windows, sent = _positioner()
    assert positioner.advance() is None
    now[0] = 1.0
    assert positioner.advance() is None
    windows.foreground = 999
    now[0] = 1.21
    assert positioner.advance().success is False
    assert sent == ["left"]
    assert windows.foreground == 999


def test_positioning_restores_a_minimized_target_once():
    positioner, now, windows, sent = _positioner()
    windows.minimized = True
    assert positioner.advance() is None
    now[0] = 1.0
    assert positioner.advance() is None
    assert windows.restored == [(101, 9)]
    assert sent == ["left"]


def test_influenza_has_no_native_positioning_sequence():
    positioner, _now, _windows, sent = _positioner("influenza")
    assert positioner.advance().success is False
    assert sent == []


def test_native_positioning_requires_exact_title_and_class():
    for settings in (
        {"vaccine_general_system_window_title": "Vaccine system"},
        {"vaccine_general_system_window_class": "CyWindowClass"},
    ):
        positioner = VaccineSystemPositioner(settings, "general")
        assert positioner.advance().success is False


@pytest.mark.parametrize("attribute", ["title", "class_name"])
def test_native_positioning_ignores_nonmatching_window(attribute):
    positioner, now, windows, sent = _positioner(timeout_seconds=2)
    setattr(windows, attribute, "Other application")
    assert positioner.advance() is None
    now[0] = 2.0
    assert positioner.advance().success is False
    assert sent == []


@pytest.mark.parametrize("raises", [False, True])
def test_positioning_hotkey_releases_windows_key(monkeypatch, raises):
    events = []

    def hotkey(*keys, interval, _pause):
        events.append(keys)
        if raises:
            raise RuntimeError("input failed")

    monkeypatch.setitem(sys.modules, "pyautogui", SimpleNamespace(
        hotkey=hotkey, keyUp=lambda key, **_kwargs: events.append(("release", key))
    ))
    assert _send_positioning_key("left") is not raises
    assert events == [("win", "left"), ("release", "left"), ("release", "win")]
