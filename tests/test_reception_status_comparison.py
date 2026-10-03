from datetime import date
import json
from types import SimpleNamespace

import pytest

from KaosEghis.tools import compare_reception_status as comparison
from KaosEghis.tools.compare_reception_status import (
    CHART_HEADER, ComparisonStopped, UiSample, build_status_query,
    compare_samples, read_chart_sample, summarize_states,
)


@pytest.mark.parametrize("charts", [(), ("1", "1"), ("1' OR '1'='1",), ("\uff11",), tuple(str(x) for x in range(6))])
def test_query_rejects_unsafe_or_unbounded_sample(charts):
    with pytest.raises(ComparisonStopped):
        build_status_query(date(2026, 10, 1), charts)


def test_query_only_returns_status_aggregates():
    query = build_status_query(date(2026, 10, 1), ("123", "456"))
    assert "clinic_ymd = '20261001'" in query
    assert "SELECT proc_gb, hold_yn, hold_opd, COUNT(*)" in query
    assert all(word not in query for word in ("ptnt_nm", "birth_ymd", "memo", "ptnt_prsn_no"))


@pytest.mark.parametrize("rows", [[], [("30", "N", "N", 1, 1, 1)], [("30", "N", "N", 3, 3, 2)], [("private-name", "N", "N", 2, 2, 2)]])
def test_ambiguous_or_invalid_day_matches_rejected(rows):
    with pytest.raises(ComparisonStopped):
        summarize_states(rows, 2)


def test_only_codes_and_counts_leave_comparison():
    sample = UiSample((1, (2, 3)), ("TEST-NOT-OUTPUT-1", "TEST-NOT-OUTPUT-2"))
    result = compare_samples(sample, sample, date(2026, 10, 1), [("X", "N", None, 2, 2, 2)])
    assert result["source_states"] == [{"proc_gb": "X", "hold_yn": "N", "hold_opd": None, "count": 2}]
    assert "TEST-NOT-OUTPUT" not in json.dumps(result)
    assert "TEST-NOT-OUTPUT" not in repr(sample)
    assert result["production_mapping_enabled"] is False


def test_changed_selection_or_chart_sample_discards_result():
    with pytest.raises(ComparisonStopped, match="ui_changed"):
        compare_samples(UiSample((1,), ("1",)), UiSample((1,), ("2",)), date(2026, 10, 1), [("X", "N", "N", 1, 1, 1)])


def test_sample_reads_chart_value_only_and_caps_at_five():
    class Node:
        def __init__(self, kind, name, children=(), value=None):
            self.element_info = SimpleNamespace(control_type=kind, name=name, process_id=1, runtime_id=[1, 2])
            self._children, self._value = children, value

        def children(self):
            return self._children

        def is_visible(self):
            return True

        @property
        def iface_value(self):
            if self._value is None:
                raise AssertionError("Non-chart values must not be read")
            return SimpleNamespace(CurrentValue=self._value)

    rows = [Node("ListItem", f"Row {i}", (
        Node("DataItem", f"{CHART_HEADER} row {i}", value=str(i + 1)),
        Node("DataItem", f"\ud658\uc790\uba85 row {i}"),
    )) for i in range(8)]
    panel = Node("Custom", "Data Panel", rows)
    grid = Node("Table", "MainView", (panel,))
    tabs = [{"status": "known-state", "selected": True, "visible": True}]
    sample = read_chart_sample(grid, tabs, [grid], "known-state")
    assert sample.charts == ("1", "2", "3", "4", "5")
    with pytest.raises(ComparisonStopped, match="unexpected_ui_selection"):
        read_chart_sample(grid, tabs, [grid], "other-state")


def test_supervised_command_uses_shared_reader_and_rechecks_before_report(monkeypatch, tmp_path):
    output = tmp_path / "report.json"
    calls = []
    sample = UiSample((1,), ("111111", "222222"))

    def inspect(*args, observer, **kwargs):
        calls.append("ui")
        observer(None, None, None)
        return {"status": "passive_ui_read_complete"}

    def read(credential, query, **kwargs):
        assert credential == "private-credential"
        assert kwargs["statement_timeout_seconds"] == 2
        calls.append("shared_reader_closed")
        kwargs["timings"]["connection_closed"] = 0.1
        return [], [("X", "N", "N", 2, 2, 2)]

    monkeypatch.setattr("sys.argv", ["compare", "--output", str(output), "--point", "1", "2", "--clinic-day", "2026-10-01", "--state", "closed"])
    monkeypatch.setattr(comparison, "inspect_ui", inspect)
    monkeypatch.setattr(comparison, "read_chart_sample", lambda *args: sample)
    monkeypatch.setattr(comparison, "connection_setting", lambda: "private-credential")
    monkeypatch.setattr(comparison, "run_readonly_query", read)
    comparison.main()
    assert calls == ["ui", "shared_reader_closed", "ui"]
    result = output.read_text(encoding="utf-8")
    assert all(value not in result for value in ("111111", "222222", "private-credential", "SELECT"))
    assert json.loads(result)["source_connection_closed"] is True
