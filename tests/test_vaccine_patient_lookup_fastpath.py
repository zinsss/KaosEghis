import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_patient_context as patient


@pytest.mark.parametrize("handle,pid,visible,minimized,expected", [
    (2, 100, True, False, 2),
    (2, 200, True, False, 2),
    (1, 100, True, False, None),
    (3, 100, True, False, None),
    (2, 999, True, False, None),
    (2, 100, False, False, None),
    (2, 100, True, True, None),
    (0, 100, True, False, None),
])
def test_foreground_fast_path_accepts_only_visible_trusted_popup(
    monkeypatch, handle, pid, visible, minimized, expected,
):
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        GetForegroundWindow=lambda: handle,
        GetAncestor=lambda h, _kind: h,
        IsWindowVisible=lambda _h: visible,
        IsIconic=lambda _h: minimized,
    ))
    monkeypatch.setitem(sys.modules, "win32process", SimpleNamespace(
        GetWindowThreadProcessId=lambda _h: (10, pid),
    ))
    state = SimpleNamespace(window_handle=1, main_window_handle=3)
    assert patient._foreground_patient_window_handle(state, (100, 200)) == expected


@pytest.fixture
def popup(monkeypatch):
    state = SimpleNamespace(
        handle=2, foreground_calls=0, reads=0, window_calls=[],
        chart_visible=True, scope_visible=True, chart_pid=100, value="1234",
    )

    def read():
        state.reads += 1
        return state.value

    state.chart = SimpleNamespace(
        is_visible=lambda: state.chart_visible,
        element_info=SimpleNamespace(process_id=100), get_value=read,
    )
    state.scope = SimpleNamespace(is_visible=lambda: state.scope_visible)

    def window(*, handle):
        state.window_calls.append(handle)
        return SimpleNamespace(wrapper_object=lambda: object())

    def foreground(*_args):
        state.foreground_calls += 1
        return state.handle

    state.desktop = SimpleNamespace(window=window)
    monkeypatch.setattr(patient, "_foreground_patient_window_handle", foreground)
    monkeypatch.setattr(patient, "_find_element", lambda _root, _id: state.chart)
    monkeypatch.setattr(patient, "_nearest_patient_information_scope", lambda _c: state.scope)
    return state


def test_fast_path_resolves_only_active_patient_popup(popup):
    result = patient._find_foreground_patient_information_scope(
        popup.desktop, object(), "chart", (100,),
    )
    assert result.chart_element is popup.chart
    assert result.scope is popup.scope
    assert result.chart_value == "1234"
    assert not result.pending
    assert popup.window_calls == [2]
    assert popup.foreground_calls == 2
    assert popup.reads == 1


@pytest.mark.parametrize("problem", ["chart_missing", "chart_hidden", "scope_missing", "scope_hidden", "foreign_chart"])
def test_fast_path_does_not_read_unverified_patient_field(popup, problem):
    if problem == "chart_missing":
        popup.chart = None
    elif problem == "chart_hidden":
        popup.chart_visible = False
    elif problem == "scope_missing":
        popup.scope = None
    elif problem == "scope_hidden":
        popup.scope_visible = False
    else:
        popup.chart.element_info.process_id = 999
    result = patient._find_foreground_patient_information_scope(
        popup.desktop, object(), "chart", (100,),
    )
    assert result is None
    assert popup.reads == 0


def test_fast_path_rejects_foreground_change_during_lookup(popup, monkeypatch):
    handles = iter((2, 3))
    monkeypatch.setattr(patient, "_foreground_patient_window_handle", lambda *_a: next(handles))
    assert patient._find_foreground_patient_information_scope(
        popup.desktop, object(), "chart", (100,),
    ) is None


def test_fast_path_treats_empty_chart_as_pending_not_ready(popup):
    popup.value = ""
    result = patient._find_foreground_patient_information_scope(
        popup.desktop, object(), "chart", (100,),
    )
    assert result.pending
    assert result.chart_value == ""


def test_fast_path_does_not_enumerate_main_window_when_no_popup_is_active(popup):
    popup.handle = None
    assert patient._find_foreground_patient_information_scope(
        popup.desktop, object(), "chart", (100,),
    ) is None
    assert popup.window_calls == []
    assert popup.reads == 0
