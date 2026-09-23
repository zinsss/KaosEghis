from datetime import date
import sys
import time
from types import SimpleNamespace

import pytest

from KaosEghis.core import claim_screen_reader as module
from KaosEghis.core.claim_preparation import ClaimPreviewError


class Node:
    def __init__(self, name, kind, value=None, *, auto_id="", children=()):
        self.element_info = SimpleNamespace(name=name, control_type=kind, automation_id=auto_id)
        self.nodes = list(children)
        self.iface_value = SimpleNamespace(CurrentValue=value)
        self.enabled = self.visible = True

    def is_enabled(self):
        return self.enabled

    def is_visible(self):
        return self.visible


def make_reader(weeks=(2, 1, 2, 1), month_value="2026년 9월 18일 금요일"):
    reader = module._ClaimReader.__new__(module._ClaimReader)
    reader.deadline = time.monotonic() + 60
    queries = []
    month = Node("", "ComboBox", month_value, auto_id="mpDemandYm")
    mode = Node("rdoWeek", "RadioButton")
    mode.iface_selection_item = SimpleNamespace(CurrentIsSelected=True)
    build = Node("청구 집계 (F7) [집계 대기]", "Button", auto_id="btnBuild")
    filters = Node("조회구분", "Pane", children=[month, mode, build] + [
        Node(f"{i}주", "RadioButton") for i in range(1, 7)
    ])
    rows = [Node(f"Row {i}", "ListItem", children=[
        Node(f"진료년월 row {i}", "DataItem", "2026/09"),
        Node(f"청구단위 row {i}", "DataItem", f"{week}주"),
        Node(f"청구번호 row {i}", "DataItem", "MUST NOT READ"),
    ]) for i, week in enumerate(weeks, 1)]
    panel = Node("Data Panel", "Custom", children=rows)
    table = Node("MainView", "Table", children=[panel])
    table.iface_grid = SimpleNamespace(CurrentRowCount=len(rows))
    pane = Node("청구리스트", "Pane", children=[table])
    scope = Node(module.CLAIM_WINDOW, "Window", children=[filters, pane])

    def descendants(node):
        for child in node.nodes:
            yield child
            yield from descendants(child)

    def find(root, control_type, *, name="", automation_id="", children=False):
        queries.append((control_type, name, automation_id))
        return [node for node in (root.nodes if children else descendants(root)) if
                node.element_info.control_type == control_type
                and (not name or node.element_info.name == name)
                and (not automation_id or node.element_info.automation_id == automation_id)]

    reader.find = find
    return SimpleNamespace(
        reader=reader, scope=scope, filters=filters, mode=mode, month=month,
        build=build, table=table, panel=panel, queries=queries,
    )


def test_reads_only_month_and_week_values():
    setup = make_reader()
    month, weeks, available = setup.reader.snapshot(setup.scope)
    assert month == date(2026, 9, 1)
    assert weeks == (1, 1, 2, 2)
    assert available == (1, 2, 3, 4, 5, 6)
    assert all(name.startswith(("진료년월", "청구단위")) for kind, name, _ in setup.queries if kind == "DataItem")


def test_confirmed_zero_rows_distinct_from_missing_table():
    setup = make_reader(())
    assert setup.reader.snapshot(setup.scope)[1] == ()
    setup.scope.nodes.pop()
    with pytest.raises(ClaimPreviewError, match="missing or ambiguous"):
        setup.reader.snapshot(setup.scope)


def test_virtualized_partial_grid_not_treated_as_full_history():
    setup = make_reader()
    setup.table.iface_grid.CurrentRowCount = 12
    with pytest.raises(ClaimPreviewError, match="part of"):
        setup.reader.snapshot(setup.scope)


def test_unknown_grid_row_count_is_not_empty():
    setup = make_reader(())
    del setup.table.iface_grid
    with pytest.raises(ClaimPreviewError, match="completeness"):
        setup.reader.snapshot(setup.scope)


@pytest.mark.parametrize("problem", ["wrong_month", "missing_value", "duplicate", "not_weekly", "busy", "out_of_order_rows"])
def test_unsafe_screen_states_fail_closed(problem):
    setup = make_reader()
    if problem == "wrong_month":
        setup.panel.nodes[0].nodes[0].iface_value.CurrentValue = "2026/08"
    elif problem == "missing_value":
        setup.panel.nodes[0].nodes[1].iface_value.CurrentValue = ""
    elif problem == "duplicate":
        setup.filters.nodes.append(setup.month)
    elif problem == "not_weekly":
        setup.mode.iface_selection_item.CurrentIsSelected = False
    elif problem == "busy":
        setup.build.enabled = False
    else:
        setup.panel.nodes[0].element_info.name = "Row 2"
    with pytest.raises(ClaimPreviewError):
        setup.reader.snapshot(setup.scope)


def test_legacy_value_fallback_does_not_use_name():
    node = Node("청구단위 row 1", "DataItem")
    legacy = {"Value": "2주", "Name": "청구단위 row 1"}
    node.legacy_properties = lambda: legacy
    assert module._ClaimReader.value(node) == "2주"
    legacy["Value"] = ""
    with pytest.raises(ClaimPreviewError):
        module._ClaimReader.value(node)


def test_deadline_is_checked_between_native_calls():
    setup = make_reader()
    setup.reader.deadline = 0
    with pytest.raises(ClaimPreviewError, match="timed out"):
        setup.reader.snapshot(setup.scope)


def test_reader_requires_connected_emr_before_touching_uia(monkeypatch):
    monkeypatch.setattr(module, "connected_claim_identity", lambda: None)
    with pytest.raises(ClaimPreviewError, match="Connect EMR"):
        module.read_claim_history()


@pytest.mark.parametrize("change", ["none", "screen", "connection", "exception"])
def test_reader_checks_stability_and_com_cleanup(monkeypatch, change):
    com_calls = []
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: com_calls.append("init"),
        CoUninitialize=lambda: com_calls.append("close"),
    ))
    calls = []
    snapshot = (date(2026, 9, 1), (1, 2), (1, 2, 3, 4, 5, 6))

    def read(_scope):
        calls.append(1)
        if change == "exception":
            raise RuntimeError("PRIVATE SCREEN CONTENT")
        if change == "screen" and len(calls) == 2:
            return (snapshot[0], (), snapshot[2])
        return snapshot

    fake = SimpleNamespace(claim_scope=lambda: object(), snapshot=read, check_time=lambda: None)
    monkeypatch.setattr(module, "_ClaimReader", lambda _identity: fake)
    identities = iter([(1, 2), (2, 3) if change == "connection" else (1, 2)])
    monkeypatch.setattr(module, "connected_claim_identity", lambda: next(identities))
    if change == "none":
        result = module.read_claim_history()
        assert result.weeks == (1, 2)
        assert result.connection == (1, 2)
    else:
        with pytest.raises(ClaimPreviewError) as error:
            module.read_claim_history()
        assert "PRIVATE" not in str(error.value)
    assert com_calls == ["init", "close"]


@pytest.mark.parametrize("kind", ["child", "top_level", "ambiguous", "wrong_process", "stale_main"])
def test_claim_window_scope_is_bound_to_connected_process(monkeypatch, kind):
    reader = module._ClaimReader.__new__(module._ClaimReader)
    reader.pid, reader.handle = 100, 200
    reader.deadline = time.monotonic() + 60
    wrapped = []
    child_queries = []

    def wrap(handle):
        wrapped.append(handle)
        return Node(module.CLAIM_WINDOW, "Window")

    def one(root, control_type, **criteria):
        child_queries.append((control_type, criteria))
        return Node(module.CLAIM_WINDOW, "Window")

    reader.one = one
    handles = [300, 400] if kind == "ambiguous" else [300]
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        IsWindow=lambda h: kind != "stale_main",
        IsWindowVisible=lambda h: True,
        GetWindowText=lambda h: "Main" if kind == "child" else module.CLAIM_WINDOW,
        EnumWindows=lambda callback, extra: [callback(h, extra) for h in handles],
    ))
    monkeypatch.setitem(sys.modules, "win32process", SimpleNamespace(
        GetWindowThreadProcessId=lambda h: (1, 999 if kind == "wrong_process" and h == 300 else 100),
    ))
    monkeypatch.setitem(sys.modules, "pywinauto.controls.uiawrapper", SimpleNamespace(UIAWrapper=wrap))
    monkeypatch.setitem(sys.modules, "pywinauto.uia_element_info", SimpleNamespace(UIAElementInfo=lambda h: h))
    if kind in {"ambiguous", "stale_main"}:
        with pytest.raises(ClaimPreviewError):
            reader.claim_scope()
        assert wrapped == []
    else:
        reader.claim_scope()
        if kind == "top_level":
            assert wrapped == [300]
            assert child_queries == []
        else:
            assert wrapped == [200]
            assert child_queries == [("Window", {"name": module.CLAIM_WINDOW})]
