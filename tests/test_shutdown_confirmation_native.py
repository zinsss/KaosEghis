from dataclasses import replace
from types import SimpleNamespace
import sys
from unittest.mock import Mock

import pytest

from KaosEghis.core.eghis_shutdown import resolve_native_confirmation_target
from KaosEghis.db.repositories import UiTargetRecord


@pytest.fixture
def native_dialog(monkeypatch):
    nodes = {
        10: dict(name="확인", pid=721, parent=None, visible=True, enabled=True, cls="WindowsForms10.Window.8", tabstop=False),
        20: dict(name="예(&Y)", pid=721, parent=10, visible=True, enabled=True, cls="WindowsForms10.Window.b", tabstop=True),
        21: dict(name="아니요(&N)", pid=721, parent=10, visible=True, enabled=True, cls="WindowsForms10.Window.b", tabstop=True),
    }

    def enumerate_windows(callback, extra):
        for handle, node in nodes.items():
            if node["parent"] is None:
                callback(handle, extra)

    def enumerate_children(parent, callback, extra):
        for handle, node in nodes.items():
            if node["parent"] == parent:
                callback(handle, extra)

    gui = SimpleNamespace(
        EnumWindows=enumerate_windows,
        EnumChildWindows=enumerate_children,
        IsWindowVisible=lambda h: nodes[h]["visible"],
        IsWindowEnabled=lambda h: nodes[h]["enabled"],
        GetWindowText=lambda h: nodes[h]["name"],
        GetClassName=lambda h: nodes[h]["cls"],
        GetWindowLong=lambda h, _index: 0x10000 if nodes[h]["tabstop"] else 0,
    )
    monkeypatch.setitem(sys.modules, "win32gui", gui)
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(GWL_STYLE=-16, WS_TABSTOP=0x10000))
    monkeypatch.setitem(sys.modules, "win32process", SimpleNamespace(GetWindowThreadProcessId=lambda h: (1, nodes[h]["pid"])))
    element = SimpleNamespace(handle=20)
    desktop = Mock()
    desktop.return_value.window.return_value.wrapper_object.return_value = element
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(Desktop=desktop))
    return nodes, desktop, element


def target(**changes):
    record = UiTargetRecord(
        id=1, target_id="shutdown.close_yes", parent_target_id=None,
        parent_automation_id=None, automation_id=None, name="예(Y)",
        control_type="Button", class_name=None, created_at="",
        ancestor_path='[{"name":"확인","control_type":"Window"}]',
    )
    return replace(record, **changes)


@pytest.mark.parametrize("key", ["shutdown.close_yes", "shutdown.backup_yes"])
def test_native_caption_mnemonic_matches_without_activation(native_dialog, key):
    nodes, desktop, element = native_dialog
    nodes[30] = dict(nodes[10], name="Unrelated dialog")
    nodes[31] = dict(nodes[20], parent=30)
    nodes[40] = dict(nodes[10], pid=999)
    nodes[41] = dict(nodes[20], parent=40, pid=999)
    found, _message = resolve_native_confirmation_target(target(target_id=key), "확인", 721)
    assert found is element
    desktop.assert_called_once_with(backend="win32")
    desktop.return_value.window.assert_called_once_with(handle=20)


@pytest.mark.parametrize("field,value", [
    ("name", "아니요(&N)"), ("pid", 999), ("visible", False),
    ("enabled", False), ("tabstop", False), ("cls", "Static"),
    ("cls", "ButtonLikePanel"),
])
def test_native_confirmation_rejects_wrong_or_inactive_control(native_dialog, field, value):
    nodes, desktop, _element = native_dialog
    nodes[20][field] = value
    found, message = resolve_native_confirmation_target(target(), "확인", 721)
    assert found is None
    assert message == "target not found"
    desktop.assert_not_called()


@pytest.mark.parametrize("duplicate_dialog", [True, False])
def test_native_confirmation_ambiguity_is_blocked(native_dialog, duplicate_dialog):
    nodes, desktop, _element = native_dialog
    nodes[30] = dict(nodes[10] if duplicate_dialog else nodes[20])
    found, message = resolve_native_confirmation_target(target(), "확인", 721)
    assert found is None
    assert message == "confirmation target ambiguous"
    desktop.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"automation_id": "configured-id"}, {"parent_automation_id": "scope"},
    {"name": "prefix:예"}, {"name": "예*"}, {"control_type": "Edit"},
    {"class_name": "AnotherClass"}, {"target_id": "unrelated.target"},
    {"ancestor_path": '[{"name":"panel","control_type":"Pane"},{"name":"확인","control_type":"Window"}]'},
])
def test_native_confirmation_does_not_relax_other_configured_constraints(native_dialog, changes):
    _nodes, desktop, _element = native_dialog
    found, _message = resolve_native_confirmation_target(target(**changes), "확인", 721)
    assert found is None
    desktop.assert_not_called()


def test_confirmation_uses_native_match_before_uia(monkeypatch):
    from KaosEghis.core import macro_runner

    button = object()
    native = Mock(return_value=(button, "found"))
    uia = Mock(side_effect=AssertionError("Native match must not scan UIA"))
    monkeypatch.setattr(macro_runner, "get_cached_eghis_state", lambda: SimpleNamespace(pid=721))
    monkeypatch.setattr(macro_runner, "resolve_native_confirmation_target", native)
    monkeypatch.setattr(macro_runner, "resolve_target_element_in_named_top_level_window", uia)
    found, _message = macro_runner.MacroRunner._resolve_confirmation_modal_target("shutdown.close_yes", target())
    assert found is button
    native.assert_called_once_with(target(), "확인", 721)
    uia.assert_not_called()


def test_ambiguous_confirmation_stops_wait_immediately(monkeypatch):
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    runner = MacroRunner()
    resolve = Mock(return_value=(None, "confirmation target ambiguous"))
    monkeypatch.setattr(runner, "_resolve_process_target", resolve)
    found, message = runner._wait_for_process_target(MacroStep("confirm_eghis_backup", "shutdown.close_yes"))
    assert found is None
    assert message == "confirmation target ambiguous"
    resolve.assert_called_once()
