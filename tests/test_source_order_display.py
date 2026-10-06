from functools import partial
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from tests import source_order_display as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database, DAY


def rows(*columns):
    values = columns or (("column", "synthetic_user_cd", "varchar", True, True, 1),)
    return [("summary", "relations", "", False, False, 1),
            ("summary", "columns", "", False, False, len(values)), *values]


def inspect(**kwargs):
    return probe.inspect_metadata(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **kwargs)


def test_metadata_only_after_verified_physical_close(database, monkeypatch, capsys, caplog):
    database.rows = rows()
    original = probe.validate_metadata
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_metadata", after_close)
    report = inspect(approved=True)
    assert report["status"] == "storage_metadata_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["candidate_columns"] == {
        "synthetic_user_cd": {"type": "varchar", "nullable": True, "selectable": True}}
    assert database.statements[-1] == (probe.METADATA_QUERY, probe.metadata_parameters())
    assert len(database.statements) == 3 and len(database.connections) == 1
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("approval", [None, False, 1, "yes"])
def test_explicit_approval(database, approval):
    assert inspect(approved=approval)["status"] == "approval_required" and not database.connections


def test_query_hash_guard(database, monkeypatch):
    monkeypatch.setattr(probe, "METADATA_QUERY", probe.METADATA_QUERY + "\n")
    assert inspect(approved=True)["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_fixed_failures_no_retry_no_raw_diagnostics(database, stage, capsys, caplog):
    database.rows, database.stage = rows(), stage
    report = inspect(approved=True)
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        assert inspect(approved=True)["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"), ("on", "0", "read committed")])
def test_readonly_mode_verified_before_metadata(database, mode):
    database.mode = mode
    assert inspect(approved=True)["status"] == "session_unverified" and len(database.statements) == 2


@pytest.mark.parametrize("field", probe.storage.PROOF_FIELDS)
def test_cleanup_must_precede_metadata_validation(field, monkeypatch):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.storage.PROOF_FIELDS, True))
        proof[field] = False
        return rows()
    monkeypatch.setattr(probe, "validate_metadata", lambda *_: pytest.fail("Unverified closure"))
    report = probe.inspect_metadata(run, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("data", [[], None, rows()[:-1], rows() + [rows()[0]],
    [("summary", "relations", "", False, False, 0), *rows()[1:]],
    [("summary", "relations", "", False, False, 2), *rows()[1:]],
    [("summary", "relations", "", False, False, 1), ("summary", "columns", "", False, False, 129)]])
def test_incomplete_ambiguous_and_overflow_metadata_not_empty(database, data):
    database.rows = data
    report = inspect(approved=True)
    assert "findings" not in report and not report["authoritative_snapshot"]


@pytest.mark.parametrize("name", ["PRIVATE MARKER", "UNREVIEWED", "ptnt_nm", "patient_name", "hold_opd", "unrelated", "user_" + "x" * 60])
def test_unknown_excluded_or_bad_identifiers_not_echoed(database, name):
    database.rows = rows(("column", name, "varchar", True, True, 1))
    report = inspect(approved=True)
    assert "findings" not in report and name not in json.dumps(report)


def test_nonselectable_or_unknown_type_is_metadata_not_permission_to_read():
    report = probe.validate_metadata(rows(("column", "synthetic_ord_nm", "OTHER_TYPE", True, False, 1)))
    assert report["candidate_columns"]["synthetic_ord_nm"] == {"type": "OTHER_TYPE", "nullable": True, "selectable": False}


def test_exact_cap_and_sentinel():
    columns = [("column", f"synthetic_user_cd_{n}", "varchar", True, True, 1) for n in range(129)]
    assert probe.validate_metadata(rows(*columns[:128]))["count"] == 128
    with pytest.raises(probe.storage.StorageRejected, match="^metadata_overflow$"):
        probe.validate_metadata(rows(*columns))


def test_no_clinical_table_reads_or_definitions_and_no_runtime_importer():
    sql = probe.METADATA_QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.METADATA_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert "public." not in sql and "pg_get" not in sql and "description" not in sql
    assert set(re.findall(r"pg_catalog\.([a-z_]+)", sql)) == {"pg_class", "pg_namespace", "pg_attribute", "pg_type"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.metadata_parameters())
    assert "LIMIT 129" in sql and sql.endswith("LIMIT 131\n")
    root = Path(__file__).parents[1]
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_order_display" not in path.read_text(encoding="utf-8-sig")


NOW = datetime(2026, 10, 7, 1, tzinfo=probe.singleton.KST)
SYNTHETIC_CHART = "000000001"
MATCH_ROW = (1, 1, 0, 0, 1, 1)


def inspect_match(**changes):
    args = dict(clinic_day=date(2026, 10, 6), chart_no=SYNTHETIC_CHART, now=lambda: NOW, approved=True)
    args.update(changes)
    return probe.inspect_match(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **args)


def test_exact_match_reads_no_raw_name_or_identifier_and_interprets_after_close(database, monkeypatch, capsys, caplog):
    database.rows = [MATCH_ROW]
    original = probe.validate_match
    def closed(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_match", closed)
    report = inspect_match()
    assert report["status"] == "display_pair_matched" and not report["authoritative_snapshot"]
    assert report["findings"] == {"single_visit_order_confirmed": True,
                                  "expected_user_code_matches": 1, "expected_user_name_matches": 1}
    assert database.statements[-1] == (probe.MATCH_QUERY, {
        "day": "20261006", "chart_no": SYNTHETIC_CHART, "read_day": "20261007",
        "expected_code": probe.CONFIRMED_CODE, "expected_name": probe.ORDER_NAME})
    assert len(database.statements) == 3 and len(database.connections) == 1
    assert SYNTHETIC_CHART not in json.dumps(report) and probe.ORDER_NAME not in json.dumps(report, ensure_ascii=False)
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("code,name", [(0, 0), (1, 0), (0, 1)])
def test_partial_or_no_match_is_not_a_confirmed_mapping(database, code, name):
    database.rows = [(1, 1, 0, 0, code, name)]
    assert inspect_match()["status"] == "display_pair_not_matched"


@pytest.mark.parametrize("args,reason", [
    ({"approved": False}, "approval_required"), ({"approved": 1}, "approval_required"),
    ({"clinic_day": date(2026, 10, 5)}, "invalid_scope"), ({"clinic_day": date(2026, 10, 7)}, "invalid_scope"),
    ({"chart_no": "PRIVATE MARKER"}, "invalid_scope"), ({"chart_no": "1' OR 1=1"}, "invalid_scope"),
    ({"now": lambda: NOW + timedelta(days=1)}, "approved_window_changed"),
    ({"now": lambda: NOW - timedelta(days=1)}, "approved_window_changed"),
    ({"now": lambda: NOW.replace(tzinfo=None)}, "invalid_scope"),
])
def test_only_explicit_point_scope_and_approved_window(database, args, reason):
    report = inspect_match(**args)
    assert report["status"] == reason and not database.connections
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("moments", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_window_change_during_read_or_interpretation_discards_matches(database, moments):
    database.rows = [MATCH_ROW]
    clock = iter(moments)
    report = inspect_match(now=lambda: next(clock))
    assert report["status"] == "source_scope_unverified" and "findings" not in report


@pytest.mark.parametrize("position,value", [(0, 0), (0, 2), (1, 0), (1, 2), (2, 1), (3, 1), (4, 2), (5, 2)])
def test_singleton_key_date_and_count_guards(position, value):
    row = list(MATCH_ROW)
    row[position] = value
    with pytest.raises(probe.storage.StorageRejected):
        probe.validate_match([row])


@pytest.mark.parametrize("data", [[], None, [MATCH_ROW, MATCH_ROW], [MATCH_ROW[:5]], [(True, *MATCH_ROW[1:])],
    [(*MATCH_ROW[:5], "PRIVATE_MARKER")]])
def test_match_reports_strict_no_partial_no_text(data):
    with pytest.raises(probe.storage.StorageRejected, match="^invalid_result$"):
        probe.validate_match(data)


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_match_failure_preserves_closure_boundary_and_redaction(database, stage, capsys, caplog):
    database.rows, database.stage = [MATCH_ROW], stage
    report = inspect_match()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and SYNTHETIC_CHART not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        assert inspect_match()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("field", probe.storage.PROOF_FIELDS)
def test_match_cannot_be_processed_before_verified_close(field, monkeypatch):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.storage.PROOF_FIELDS, True))
        proof[field] = False
        return [MATCH_ROW]
    monkeypatch.setattr(probe, "validate_match", lambda *_: pytest.fail("Unverified closure"))
    report = probe.inspect_match(run, clinic_day=date(2026, 10, 6), chart_no=SYNTHETIC_CHART, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


def test_match_hash_and_sql_never_returns_user_fields_or_patient_identity(database, monkeypatch):
    sql = probe.MATCH_QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.MATCH_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert sql.count("LIMIT 2") == 3
    assert "user_cd = %(expected_code)s AS code_matches" in sql
    assert "user_nm = %(expected_name)s AS name_matches" in sql
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "ptnt_no::text = %(chart_no)s" in sql
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    for value in ("hold_opd", "ptnt_nm", "birth", "insurance", "notes", "price", "SELECT *", "LIKE",
                  "array_agg", "json_agg", "string_agg", "min(user", "max(user", SYNTHETIC_CHART, probe.ORDER_NAME):
        assert value not in sql
    monkeypatch.setattr(probe, "MATCH_QUERY", sql + "\n")
    assert inspect_match()["status"] == "query_changed" and not database.connections
