import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from functools import partial
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import normalize_source_day_v2
from tests import source_current_day_counts as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import policy
from tests.test_source_evidence_inspection import database


DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 12, tzinfo=probe.KST)


def rows(buckets=(), **changes):
    summary = dict.fromkeys(probe.SUMMARY_FIELDS, 0)
    summary.update(current_day_matches=1, encounters=sum(bucket[-1] for bucket in buckets))
    summary.update(changes)
    return [("summary", key, "", "", value) for key, value in summary.items()] + [
        ("bucket", *bucket) for bucket in buckets
    ]


def populated():
    return rows([
        ("10", "N", "WITHOUT_ORDERS", 2), ("25", "N", "WITH_ORDERS", 1),
        ("30", "N", "WITHOUT_ORDERS", 1), ("40", "N", "WITH_ORDERS", 1),
        ("50", "N", "WITH_ORDERS", 1), ("50", "N", "WITHOUT_ORDERS", 1),
    ])


def inspect(**changes):
    arguments = dict(clinic_day=DAY, now=lambda: NOW, approved=True)
    arguments.update(changes)
    return probe.inspect_counts(partial(eghis_db.run_verified_evidence_query, "mock-secret"),
                                **arguments)


def test_exact_query_runs_once_with_finite_limits_and_closes_before_processing(database, monkeypatch):
    database.rows = populated()
    original = probe.validate_rows
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        assert all(connection.closed for connection in database.connections)
        return original(data)
    monkeypatch.setattr(probe, "validate_rows", after_close)
    report = inspect()
    assert report["status"] == "counts_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["counts"] == {"encounters": 7, "with_orders": 3, "without_orders": 4}
    assert all(report["closure"][key] is True for key in probe.PROOF_FIELDS)
    assert len(database.statements) == 3
    assert database.statements[-1] == (probe.QUERY, probe.parameters(DAY))
    assert probe.parameters(DAY) == {
        "day": "20261006", "encounter_limit": 10001,
        "codes": ["10", "20", "25", "30", "40", "50"], "flags": ["Y", "N"],
    }


@pytest.mark.parametrize("code", probe.CODES)
@pytest.mark.parametrize("presence", probe.PRESENCE)
def test_no_state_or_no_order_bucket_is_filtered_or_given_clinical_meaning(code, presence):
    findings = probe.validate_rows(rows([(code, "Y", presence, 1)]))
    assert findings["buckets"] == [{"code": code, "hold_yn": "Y", "order_presence": presence, "count": 1}]
    assert "state" not in json.dumps(findings) and "cancelled" not in json.dumps(findings)


@pytest.mark.parametrize("code", probe.MASKS)
@pytest.mark.parametrize("flag", probe.MASKS)
def test_masked_unreviewed_buckets_are_counted_not_guessed_or_silently_dropped(code, flag):
    findings = probe.validate_rows(rows([(code, flag, "WITHOUT_ORDERS", 1)]))
    assert findings["buckets"][0]["code"] == code
    assert findings["buckets"][0]["hold_yn"] == flag
    assert findings["counts"]["encounters"] == findings["counts"]["without_orders"] == 1


@pytest.mark.parametrize("data", [rows(), populated()])
def test_success_including_zero_never_enables_reader_or_normalization(database, policy, data):
    database.rows = data
    report = inspect()
    assert report["status"] == "counts_observed" and not report["authoritative_snapshot"]
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    count = len(database.connections)
    assert EghisSourceDayReader().read_day(DAY, NOW).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == count


@pytest.mark.parametrize("approved", [False, 1, 0, None, "yes"])
def test_approval_is_explicit(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required"
    assert not database.connections


@pytest.mark.parametrize("day", [None, "2026-10-06", NOW, True, DAY - timedelta(days=1), DAY + timedelta(days=1)])
def test_only_exact_current_day_is_eligible(database, day):
    assert inspect(clinic_day=day)["status"] in {"invalid_scope", "current_day_changed"}
    assert not database.connections


@pytest.mark.parametrize("clock", [None, lambda: DAY, lambda: NOW.replace(tzinfo=None), lambda: "PRIVATE_MARKER"])
def test_clock_requires_aware_datetime(database, clock):
    report = inspect(now=clock)
    assert report["status"] == "invalid_scope" and not database.connections
    assert "PRIVATE_MARKER" not in json.dumps(report)


def test_utc_date_is_converted_to_kst(database):
    database.rows = rows()
    assert inspect(now=lambda: datetime(2026, 10, 5, 15, tzinfo=timezone.utc))["status"] == "counts_observed"


def test_midnight_while_queued_is_rejected_by_server_day_guard(database):
    database.rows = rows(current_day_matches=0)
    report = inspect()
    assert report["status"] == "current_day_changed" and "findings" not in report
    assert report["closure"]["connection_closed"]


@pytest.mark.parametrize("instants", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_midnight_during_read_or_validation_discards_findings(database, instants):
    database.rows = populated()
    clock = iter(instants)
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "current_day_changed" and "findings" not in report
    assert report["closure"]["connection_closed"]


def test_query_change_requires_review_without_connecting(database, monkeypatch):
    monkeypatch.setattr(probe, "QUERY", probe.QUERY + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"),
                                  ("on", "0", "read committed"), ("on", "2s", "serializable")])
def test_readonly_and_timeout_verified_before_source_statement(database, mode):
    database.mode = mode
    report = inspect()
    assert report["status"] == "session_unverified" and "findings" not in report
    assert len(database.statements) == 2 and report["closure"]["connection_closed"]


@pytest.mark.parametrize("stage", [
    "connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open",
])
def test_each_read_failure_is_redacted_never_empty_and_never_retried(database, stage, capsys, caplog):
    database.rows, database.stage = populated(), stage
    report = inspect()
    assert report["status"] != "counts_observed"
    assert not report["authoritative_snapshot"] and "findings" not in report
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_missing_closure_proof_prevents_interpretation(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return populated()
    def forbidden(*args):
        pytest.fail("Unverified read must not be interpreted")
    monkeypatch.setattr(probe, "validate_rows", forbidden)
    report = probe.inspect_counts(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("data", [
    [], rows()[:-1], rows() + [rows()[0]], rows() * 24,
    [("summary", "encounters", "", "", "PRIVATE_MARKER")],
    rows() + [("bucket", "PRIVATE_MARKER", "N", "WITHOUT_ORDERS", 1)],
    rows() + [("bucket", "10", "PRIVATE_MARKER", "WITHOUT_ORDERS", 1)],
    rows() + [("bucket", "10", "N", "PRIVATE_MARKER", 1)],
    rows() + [("bucket", "10", "N", "WITHOUT_ORDERS", 0)],
    rows() + [("summary", "PRIVATE_MARKER", "", "", 1)],
    rows() + [("PRIVATE_MARKER",)],
    rows() + [("bucket", "10", "N", "WITHOUT_ORDERS", 1)] * 2,
])
def test_malformed_unknown_duplicate_or_partial_reports_fail_closed(database, data):
    database.rows = data
    report = inspect()
    assert report["status"] != "counts_observed" and "findings" not in report
    assert not report["authoritative_snapshot"] and "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("value", [None, True, -1, 0.0, "PRIVATE_MARKER", [], {}])
def test_counts_are_strict_nonnegative_integers(value):
    with pytest.raises(probe.CountsRejected, match="^invalid_result$"):
        probe.validate_rows(rows(encounters=value))


@pytest.mark.parametrize("field", probe.SUMMARY_FIELDS)
def test_cap_plus_one_rejects_source_truncation(field):
    with pytest.raises(probe.CountsRejected, match="^source_overflow$"):
        probe.validate_rows(rows(**{field: probe.ENCOUNTER_CAP + 1}))


def test_exact_source_cap_is_accepted_but_never_authoritative():
    data = rows([("10", "N", "WITHOUT_ORDERS", probe.ENCOUNTER_CAP)])
    assert probe.validate_rows(data)["counts"]["encounters"] == probe.ENCOUNTER_CAP


@pytest.mark.parametrize("changes,reason", [
    ({"encounters": 1}, "inconsistent_result"),
    ({"current_day_matches": 2}, "inconsistent_result"),
    ({"invalid_encounter_keys": 1}, "encounter_keys_unverified"),
    ({"duplicate_encounter_keys": 1}, "encounter_keys_unverified"),
])
def test_crosschecks_reject_inconsistent_counts_and_invalid_keys(changes, reason):
    with pytest.raises(probe.CountsRejected, match=f"^{reason}$"):
        probe.validate_rows(rows(**changes))


def test_bucket_order_is_canonical_and_all_allowlisted_combinations_fit():
    data = rows([(code, flag, presence, 1) for code in probe.CODES + probe.MASKS
                 for flag in probe.FLAGS + probe.MASKS for presence in probe.PRESENCE])
    assert len(data) == probe.REPORT_CAP == 94
    assert probe.validate_rows(data) == probe.validate_rows(data[::-1])


@pytest.mark.parametrize("code,reason", [
    ("57014", "query_timed_out"), ("42501", "permission_denied"),
    ("42703", "schema_mismatch"), ("42P01", "schema_mismatch"), ("unknown", "read_failed"),
])
def test_provider_errors_never_leak_or_retry(code, reason):
    calls = []
    def runner(*args, **kwargs):
        calls.append(True)
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    report = probe.inspect_counts(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == reason and calls == [True]
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("elapsed", ["PRIVATE_MARKER", float("inf"), float("nan"), True, -1, 10**400])
def test_only_fixed_closure_fields_and_bounded_timing_are_output(elapsed):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof.update(PRIVATE_MARKER="PRIVATE_MARKER", elapsed_seconds=elapsed)
        return rows()
    report = probe.inspect_counts(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert set(report["closure"]) == set(probe.PROOF_FIELDS)
    assert "PRIVATE_MARKER" not in json.dumps(report, allow_nan=False)


def test_shared_fifo_and_mutex_prevent_overlapping_connections(database):
    database.rows = populated()
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: inspect(), range(4)))
    assert all(report["status"] == "counts_observed" for report in reports)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4


def test_sql_is_pinned_minimal_parameterized_and_aggregate_only():
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.parameters(DAY))
    assert "SELECT recept_no, proc_gb, hold_yn" in sql
    assert "WHERE clinic_ymd = %(day)s AND (SELECT matches FROM day_guard) = 1" in sql
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "LIMIT %(encounter_limit)s" in sql and "LIMIT 95\n" in sql
    assert "SELECT 1 FROM public.h2opd_doct_ord o WHERE o.recept_no = h.recept_no" in sql
    assert "EXISTS" in sql and "FROM h\n" in sql
    final = sql[sql.index("SELECT 'summary' AS section"):]
    assert "recept_no" not in final and "public." not in final
    for forbidden in ("hold_opd", "ptnt_no", "name", "sex", "age", "birth", "jumin", "phone",
                      "address", "diagnosis", "insurance", "ord_type", "dc_yn", "act_yn",
                      "proc_dept_cd", "ord_ymd", "ord_no", "ord_seq_no", "SELECT *",
                      "FOR UPDATE", "FOR SHARE", "pg_sleep", "SET ROLE", "20261006"):
        assert forbidden not in sql


def test_no_runtime_importer_driver_settings_output_or_delivery():
    root = Path(__file__).parents[1]
    source = Path(probe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        "datetime", "pathlib", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue",
    }
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names} == {"hashlib", "math"}
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_current_day_counts" not in path.read_text(encoding="utf-8-sig")
    for forbidden in ("psycopg2", "settings", "connection_string", "getenv", "logging", "http",
                      "write_text", "write_bytes", "print(", "hold_opd"):
        assert forbidden not in source
