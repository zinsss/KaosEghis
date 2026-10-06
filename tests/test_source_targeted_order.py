from datetime import date, datetime, timedelta
from functools import partial
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from tests import source_targeted_order as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database

DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 12, tzinfo=probe.base.KST)
SYNTHETIC_CHART = "000000001"


def rows(**changes):
    values = dict.fromkeys(probe.BOUNDS, 0)
    values.update(current_day_matches=1)
    values.update(changes)
    return list(values.items())


def inspect(**changes):
    args = dict(chart_no=SYNTHETIC_CHART, clinic_day=DAY, now=lambda: NOW, approved=True)
    args.update(changes)
    return probe.inspect_target(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **args)


def test_exact_scope_connection_closes_before_aggregate_interpretation(database, monkeypatch, capsys, caplog):
    database.rows = rows(day_encounters=1, linked_orders=1, orders_on_day=1, compact_name_matches=1)
    original = probe.validate_rows
    def closed(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_rows", closed)
    report = inspect()
    assert report["counts"]["compact_name_matches"] == 1 and not report["authoritative_snapshot"]
    assert database.statements[-1] == (probe.QUERY, {
        "day": "20261006", "chart_no": SYNTHETIC_CHART, "compact_name": probe.base.CONFIRMED_CODE,
        "spaced_name": probe.base.ORDER_NAME, "encounter_limit": 11, "order_limit": 1001,
    })
    assert len(database.statements) == 3 and SYNTHETIC_CHART not in json.dumps(report)
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("data", [rows(), rows(day_encounters=1), rows(day_encounters=1, linked_orders=1, orders_off_day=1)])
def test_absent_visit_no_children_and_other_order_date_are_distinct_not_authoritative_empty(database, data):
    database.rows = data
    report = inspect()
    assert report["counts"] == dict(data) and not report["authoritative_snapshot"]
    assert EghisSourceDayReader().read_day(DAY, NOW).status is ReadStatus.UNAVAILABLE


@pytest.mark.parametrize("chart", [None, 1, True, "", "PRIVATE MARKER", "1' OR 1=1", "1" * 13, " 1", "\uff11"])
def test_identity_is_strict_bound_input_never_echoed(database, chart):
    report = inspect(chart_no=chart)
    assert report["status"] == "invalid_scope" and not database.connections
    assert "PRIVATE" not in json.dumps(report)


@pytest.mark.parametrize("approved", [False, 1, None])
def test_approval_required(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("day", [DAY - timedelta(days=1), DAY + timedelta(days=1), None, "2026-10-06"])
def test_no_historical_or_guessed_scope(database, day):
    assert inspect(clinic_day=day)["status"] in {"current_day_changed", "invalid_scope"}
    assert not database.connections


@pytest.mark.parametrize("moments", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_midnight_race_discards_counts(database, moments):
    database.rows = rows()
    clock = iter(moments)
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "current_day_changed" and "counts" not in report


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"), ("on", "0", "read committed")])
def test_readonly_verification_before_query(database, mode):
    database.mode = mode
    assert inspect()["status"] == "session_unverified" and len(database.statements) == 2


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failures_never_become_empty_and_never_echo_identity(database, stage, capsys, caplog):
    database.rows, database.stage = rows(), stage
    report = inspect()
    assert "counts" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and SYNTHETIC_CHART not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("key,cap", probe.BOUNDS.items())
def test_caps_have_sentinels(key, cap):
    with pytest.raises(probe.base.NamedOrderRejected, match="^source_overflow$"):
        probe.validate_rows(rows(**{key: cap + 1}))


@pytest.mark.parametrize("data", [rows()[:-1], rows() + [rows()[0]], [], None,
    [("PRIVATE_MARKER", 1)] + rows()[1:], rows(day_encounters=True)])
def test_malformed_partial_or_unknown_reports_fail_closed(database, data):
    database.rows = data
    report = inspect()
    assert "counts" not in report and "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("changes", [{"linked_orders": 1}, {"compact_name_matches": 1},
    {"exact_code_matches": 1}, {"orders_off_day": 1}, {"invalid_order_keys": 1}, {"duplicate_encounter_keys": 1}])
def test_inconsistent_and_key_anomalies_rejected(changes):
    with pytest.raises(probe.base.NamedOrderRejected):
        probe.validate_rows(rows(**changes))


@pytest.mark.parametrize("field", probe.base.PROOF_FIELDS)
def test_cleanup_must_be_verified_before_interpretation(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.base.PROOF_FIELDS, True))
        proof[field] = False
        return rows()
    monkeypatch.setattr(probe, "validate_rows", lambda *_: pytest.fail("Unverified cleanup"))
    result = probe.inspect_target(runner, chart_no=SYNTHETIC_CHART, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert result["status"] == "cleanup_or_session_unverified" and "counts" not in result


def test_query_pin_and_server_day_guard(database, monkeypatch):
    database.rows = rows(current_day_matches=0)
    assert inspect()["status"] == "current_day_changed"
    opened = len(database.connections)
    monkeypatch.setattr(probe, "QUERY", probe.QUERY + "\n")
    assert inspect()["status"] == "query_changed" and len(database.connections) == opened


def test_sql_only_returns_aggregates_with_no_raw_identifier_or_name():
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert "ptnt_no::text = %(chart_no)s" in sql and "clinic_ymd = %(day)s" in sql
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "LIMIT %(encounter_limit)s" in sql and "LIMIT %(order_limit)s" in sql
    assert sql.endswith("SELECT metric, n FROM summary ORDER BY metric\nLIMIT 13\n")
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    for forbidden in ("ptnt_nm", "hold_opd", "birth", "insurance", "phone", "address", "price", "SELECT *", SYNTHETIC_CHART):
        assert forbidden not in sql
    root = Path(__file__).parents[1]
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_targeted_order" not in path.read_text(encoding="utf-8-sig")
