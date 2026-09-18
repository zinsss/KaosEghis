import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from KaosEghis.core import windows_virtual_desktop as desktop


@pytest.fixture
def desktops(monkeypatch):
    state = {"current": "desktop-three", "first": "desktop-one"}
    first = SimpleNamespace(id="desktop-one")

    def switch(**_kwargs):
        state["current"] = state["first"]

    first.go = Mock(side_effect=switch)
    api = Mock(return_value=first)
    api.current.side_effect = lambda: SimpleNamespace(id=state["current"])
    monkeypatch.setitem(sys.modules, "pyvda", SimpleNamespace(VirtualDesktop=api))
    monkeypatch.setattr(desktop, "interactive_desktop_error", lambda: None)
    return state, first, api


def test_switches_to_first_desktop_by_identity_and_verifies(desktops):
    state, first, api = desktops
    result = desktop.ensure_first_virtual_desktop()
    assert result.success
    assert state["current"] == first.id
    first.go.assert_called_once_with(allow_set_foreground=False)
    assert all(call.args == (1,) for call in api.call_args_list)


def test_already_on_first_desktop_does_not_switch(desktops):
    state, first, _api = desktops
    state["current"] = first.id
    assert desktop.ensure_first_virtual_desktop().success
    first.go.assert_not_called()


def test_switch_not_confirmed_is_failure(desktops):
    _state, first, _api = desktops
    first.go.side_effect = None
    result = desktop.ensure_first_virtual_desktop()
    assert not result.success
    assert result.status == "desktop_switch_failed"


def test_desktop_reordered_during_switch_is_failure(desktops):
    state, first, api = desktops

    def switch(**_kwargs):
        state["current"] = first.id
        api.return_value = SimpleNamespace(id="new-first")

    first.go.side_effect = switch
    assert not desktop.ensure_first_virtual_desktop().success


def test_unsupported_desktop_api_blocks_and_does_not_expose_raw_error(desktops):
    _state, first, _api = desktops
    first.go.side_effect = RuntimeError("private native details")
    result = desktop.ensure_first_virtual_desktop()
    assert result.status == "desktop_switch_failed"
    assert "private" not in result.message


def test_locked_desktop_never_switches(monkeypatch, desktops):
    _state, first, api = desktops
    monkeypatch.setattr(desktop, "interactive_desktop_error", lambda: "locked")
    assert desktop.ensure_first_virtual_desktop().status == "desktop_unavailable"
    assert not desktop.first_virtual_desktop_is_active()
    api.assert_not_called()
    first.go.assert_not_called()


def test_missing_dependency_blocks(monkeypatch, desktops):
    monkeypatch.setitem(sys.modules, "pyvda", None)
    assert desktop.ensure_first_virtual_desktop().status == "unavailable"
    assert not desktop.first_virtual_desktop_is_active()


def test_final_guard_is_read_only(desktops):
    state, first, _api = desktops
    assert not desktop.first_virtual_desktop_is_active()
    state["current"] = first.id
    assert desktop.first_virtual_desktop_is_active()
    first.go.assert_not_called()
