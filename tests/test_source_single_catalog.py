from datetime import date, datetime, timedelta
from functools import partial
import hashlib
import json
from pathlib import Path

import pytest

from KaosEghis.core import eghis_db
from tests import source_single_catalog as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database

NOW = datetime(2026, 10, 7, 1, tzinfo=probe.KST)
CHART = "000000001"
ROW = (1, 1, 0, 0, 0, "SYNTH-CODE", "Fictional catalog item")


def inspect(**changes):
    args = dict(clinic_day=probe.APPROVED_VISIT_DAY, chart_no=CHART, now=lambda: NOW, approved=True)
    args.update(changes)
    return probe.inspect_catalog(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **args)


def test_only_catalog_text_after_singleton_and_connection_closure(database, monkeypatch, capsys, caplog):
    database.rows = [ROW]
    original = probe.validate_rows
    def closed(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_rows", closed)
    report = inspect()
    assert report["catalog"] == {"code": "SYNTH-CODE", "name": "Fictional catalog item"}
    assert not report["authoritative_snapshot"] and CHART not in json.dumps(report)
    assert len(database.statements) == 3
    assert database.statements[-1] == (probe.QUERY, {"day": "20261006", "chart_no": CHART, "read_day": "20261007"})
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("approved", [False, 1, "yes", None])
def test_separate_operator_approval_required(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("day", [None, "2026-10-06", date(2026, 10, 5), date(2026, 10, 7)])
def test_cannot_broaden_approved_visit_date(database, day):
    assert inspect(clinic_day=day)["status"] == "invalid_scope" and not database.connections


@pytest.mark.parametrize("chart", [None, 1, "", "PRIVATE MARKER", "1' OR 1=1", "1" * 13])
def test_identity_is_bound_not_echoed(database, chart):
    report = inspect(chart_no=chart)
    assert report["status"] == "invalid_scope" and not database.connections
    assert "PRIVATE" not in json.dumps(report)


@pytest.mark.parametrize("when", [NOW - timedelta(days=1), NOW + timedelta(days=1), NOW.replace(tzinfo=None)])
def test_inspection_window_is_not_reusable(database, when):
    assert inspect(now=lambda: when)["status"] in {"invalid_scope", "approved_window_changed"}
    assert not database.connections


@pytest.mark.parametrize("moments", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_window_expiry_discards_catalog(database, moments):
    database.rows = [ROW]
    clock = iter(moments)
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "approved_window_changed" and "catalog" not in report


@pytest.mark.parametrize("position,value", [(0, 0), (0, 2), (1, 0), (1, 2), (2, 1), (3, 1), (4, 1)])
def test_ambiguous_missing_wrong_day_or_withheld_scope_never_returns_text(database, position, value):
    row = list(ROW)
    row[position] = value
    database.rows = [row]
    report = inspect()
    assert "catalog" not in report and "Fictional" not in json.dumps(report)


@pytest.mark.parametrize("value", [None, "", "  Fictional name  ", "\uac00\uc0c1 \ucc98\ubc29"])
def test_permitted_null_blank_unicode_and_whitespace_are_not_reinterpreted(value):
    assert probe.validate_rows([(*ROW[:6], value)])["name"] == value


@pytest.mark.parametrize("value", ["a" * 257, "PRIVATE\nMARKER", "\u200bPRIVATE", "000000-1000000", "010-0000-0000", 123, {}])
def test_forbidden_text_shapes_fail_with_fixed_reason(value):
    with pytest.raises(probe.CatalogRejected, match="^catalog_text_withheld$"):
        probe.validate_rows([(*ROW[:6], value)])


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failure_and_cleanup_paths_no_text_leak_retry_or_authority(database, stage, capsys, caplog):
    database.rows, database.stage = [ROW], stage
    report = inspect()
    assert "catalog" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"), ("on", "0", "read committed")])
def test_verified_session_before_source_statement(database, mode):
    database.mode = mode
    assert inspect()["status"] == "session_unverified" and len(database.statements) == 2


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_unverified_cleanup_prevents_text_interpretation(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return [ROW]
    monkeypatch.setattr(probe, "validate_rows", lambda *_: pytest.fail("Unverified closure"))
    report = probe.inspect_catalog(runner, clinic_day=probe.APPROVED_VISIT_DAY, chart_no=CHART, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "catalog" not in report


@pytest.mark.parametrize("rows", [[], None, [ROW, ROW], [ROW[:6]], [(True, *ROW[1:])]])
def test_no_partial_or_overflow_results(rows):
    with pytest.raises(probe.CatalogRejected, match="^invalid_result$"):
        probe.validate_rows(rows)


def test_query_pin_and_no_runtime_or_financial_fields(database, monkeypatch):
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert sql.count("LIMIT 2") == 3
    assert "clinic_ymd = %(day)s AND ptnt_no::text = %(chart_no)s" in sql
    assert "= %(read_day)s" in sql
    assert sql.count("encounters = 1 AND orders = 1 AND invalid_keys = 0 AND off_day = 0 AND withheld = 0") == 2
    for value in ("ptnt_nm", "hold_opd", "birth", "insurance", "notes", "phone", "address", "price", "SELECT *", CHART):
        assert value not in sql
    root = Path(__file__).parents[1]
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_single_catalog" not in path.read_text(encoding="utf-8-sig")
    monkeypatch.setattr(probe, "QUERY", sql + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections
