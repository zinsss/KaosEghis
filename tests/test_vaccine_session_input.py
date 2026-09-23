import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core.vaccine_session_keeper import _input_is_idle


def install_input(monkeypatch, *, now=10000, last=4000, held=0):
    api = SimpleNamespace(
        GetTickCount=lambda: now,
        GetLastInputInfo=lambda: last,
        GetAsyncKeyState=lambda key: 0x8000 if key == held else 1,
    )
    monkeypatch.setitem(sys.modules, "win32api", api)
    return api


@pytest.mark.parametrize("elapsed,expected", [(4999, False), (5000, True), (10000, True)])
def test_idle_threshold_ignores_unreliable_recent_key_bit(monkeypatch, elapsed, expected):
    install_input(monkeypatch, now=10000, last=10000 - elapsed)
    assert _input_is_idle(5000) is expected


@pytest.mark.parametrize("key", [1, 2, 4, 16, 17, 18, 65, 91])
def test_held_mouse_or_keyboard_prevents_click_even_when_last_input_is_old(monkeypatch, key):
    install_input(monkeypatch, held=key)
    assert _input_is_idle(5000) is False
    assert _input_is_idle(0) is False


def test_idle_tick_wraparound(monkeypatch):
    install_input(monkeypatch, now=1000, last=0x100000000 - 4000)
    assert _input_is_idle(5000) is True


def test_future_input_tick_fails_closed(monkeypatch):
    install_input(monkeypatch, now=1000, last=1010)
    assert _input_is_idle(5000) is False


def test_unavailable_input_check_fails_closed(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace())
    assert _input_is_idle(5000) is None
