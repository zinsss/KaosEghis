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
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from tests import source_named_order as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database


DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 12, tzinfo=probe.KST)
BUCKET = ("bucket", "", "SYNTH-FLU", "05", "INJ", "N", "N", 1)


def rows(*buckets, **changes):
    counts = dict.fromkeys(probe.BOUNDS, 0)
    counts.update(current_day_matches=1, **changes)
    return [("summary", key, "", "", "", "", "", n) for key, n in counts.items()] + list(buckets)


def populated(*buckets, **changes):
    counts = dict(encounters_in_scope=2, matched_orders=1, matched_encounters=1)
    counts.update(changes)
    return rows(*(buckets or (BUCKET,)), **counts)


def inspect(**changes):
    arguments = dict(clinic_day=DAY, now=lambda: NOW, approved=True)
    arguments.update(changes)
    return probe.inspect_named_order(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **arguments)


def test_exact_query_parameters_and_close_before_interpretation(database, monkeypatch):
    database.rows = populated()
    original = probe.validate_rows
    def closed(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        assert all(c.closed for c in database.connections)
        return original(data)
    monkeypatch.setattr(probe, "validate_rows", closed)
    report = inspect()
    assert report["status"] == "named_order_observed"
    assert report["findings"]["buckets"] == [{
        "catalog_code": "SYNTH-FLU", "order_type": "05", "department": "INJ",
        "dc_yn": "N", "act_yn": "N", "count": 1,
    }]
    assert all(report["closure"][key] is True for key in probe.PROOF_FIELDS)
    assert len(database.statements) == 3
    assert database.statements[-1] == (probe.QUERY, probe.parameters(DAY))
    assert probe.parameters(DAY)["order_name"] == "\uad6d\uac00\uc811\uc885 \ub3c5\uac10"
    assert probe.parameters(DAY)["encounter_limit"] == 10001
    assert probe.parameters(DAY)["order_limit"] == 1001


@pytest.mark.parametrize("data", [rows(), rows(encounters_in_scope=2), populated()])
def test_not_found_is_not_an_empty_day_or_runtime_authority(database, data):
    database.rows = data
    report = inspect()
    assert report["status"] in {"named_order_not_found", "named_order_observed"}
    assert report["authoritative_snapshot"] is False
    opened = len(database.connections)
    assert EghisSourceDayReader().read_day(DAY, NOW).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == opened


@pytest.mark.parametrize("dc,act", [("Y", "Y"), ("Y", "N"), ("N", "Y"), ("N", "N")])
def test_retained_flags_are_observed_without_exclusion_or_clinical_interpretation(dc, act):
    data = populated((*BUCKET[:5], dc, act, 1))
    bucket = probe.validate_rows(data)["buckets"][0]
    assert bucket["dc_yn"] == dc and bucket["act_yn"] == act
    assert set(bucket) == {"catalog_code", "order_type", "department", "dc_yn", "act_yn", "count"}


@pytest.mark.parametrize("position", [3, 4, 5, 6])
@pytest.mark.parametrize("mask", probe.MASKS)
def test_fixed_masks_do_not_guess_unknown_qualifiers_or_classifications(position, mask):
    bucket = list(BUCKET)
    bucket[position] = mask
    assert mask in probe.validate_rows(populated(tuple(bucket)))["buckets"][0].values()


@pytest.mark.parametrize("approved", [False, 0, 1, None, "yes"])
def test_approval_gate(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("day", [None, True, NOW, "2026-10-06", DAY - timedelta(days=1), DAY + timedelta(days=1)])
def test_current_day_only(database, day):
    assert inspect(clinic_day=day)["status"] in {"invalid_scope", "current_day_changed"}
    assert not database.connections


@pytest.mark.parametrize("clock", [None, lambda: DAY, lambda: NOW.replace(tzinfo=None), lambda: "PRIVATE_MARKER"])
def test_aware_clock_required(database, clock):
    assert inspect(now=clock)["status"] == "invalid_scope" and not database.connections


def test_utc_clock_is_converted(database):
    database.rows = rows()
    assert inspect(now=lambda: datetime(2026, 10, 5, 15, tzinfo=timezone.utc))["status"] == "named_order_not_found"


@pytest.mark.parametrize("moments", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_midnight_during_read_or_validation_discards_result(database, moments):
    database.rows = populated()
    clock = iter(moments)
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "current_day_changed" and "findings" not in report
    assert report["closure"]["connection_closed"]


def test_server_day_guard_rejects_read_that_waited_past_midnight(database):
    database.rows = [(row[:7] + (0,) if row[1] == "current_day_matches" else row) for row in rows()]
    assert inspect()["status"] == "current_day_changed"


def test_query_pin_prevents_unreviewed_changes(database, monkeypatch):
    monkeypatch.setattr(probe, "QUERY", probe.QUERY + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"),
                                  ("on", "0", "read committed"), ("on", "2s", "serializable")])
def test_verified_readonly_session_precedes_query(database, mode):
    database.mode = mode
    report = inspect()
    assert report["status"] == "session_unverified" and "findings" not in report
    assert len(database.statements) == 2 and report["closure"]["connection_closed"]


@pytest.mark.parametrize("by_code", [False, True])
@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failures_are_fixed_redacted_and_not_retried(database, stage, by_code, capsys, caplog):
    database.rows, database.stage = populated(), stage
    report = inspect(by_code=by_code)
    assert "findings" not in report and report["authoritative_snapshot"] is False
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect(by_code=by_code)["status"] == "reader_safety_stop" and len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_unverified_cleanup_cannot_reach_interpretation(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return populated()
    def forbidden(*args):
        pytest.fail("Interpretation before verified closure")
    monkeypatch.setattr(probe, "validate_rows", forbidden)
    report = probe.inspect_named_order(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("metric,cap", probe.BOUNDS.items())
def test_source_sentinels_reject_truncation(metric, cap):
    data = [(row[:7] + (cap + 1,) if row[1] == metric else row) for row in rows()]
    with pytest.raises(probe.NamedOrderRejected, match="^source_overflow$"):
        probe.validate_rows(data)


def test_group_overflow_sentinel_rejects_instead_of_dropping_catalog_codes():
    buckets = [("bucket", "", f"SYNTH-{n}", "05", "INJ", "N", "N", 1) for n in range(33)]
    with pytest.raises(probe.NamedOrderRejected, match="^report_overflow_or_incomplete$"):
        probe.validate_rows(populated(*buckets, matched_orders=33))


@pytest.mark.parametrize("metric", ["invalid_encounter_keys", "duplicate_encounter_keys", "invalid_order_keys", "duplicate_order_keys"])
def test_key_anomalies_fail_closed(metric):
    with pytest.raises(probe.NamedOrderRejected, match="^keys_unverified$"):
        probe.validate_rows(populated(**{metric: 1}))


@pytest.mark.parametrize("changes", [{"matched_orders": 2}, {"matched_encounters": 2},
    {"encounters_in_scope": 0}, {"matched_encounters": 0}])
def test_aggregate_consistency(changes):
    with pytest.raises(probe.NamedOrderRejected, match="^inconsistent_result$"):
        probe.validate_rows(populated(**changes))


@pytest.mark.parametrize("value", [None, True, -1, 0.0, "PRIVATE_MARKER", [], {}])
def test_count_types_are_strict(value):
    with pytest.raises(probe.NamedOrderRejected, match="^invalid_result$"):
        probe.validate_rows(populated(encounters_in_scope=value))


@pytest.mark.parametrize("code", [None, "", "A" * 33, "PRIVATE MARKER", "line\nbreak", "\uac00", 123, True])
def test_nonreviewed_catalog_codes_never_escape(code):
    with pytest.raises(probe.NamedOrderRejected, match="^catalog_code_unreviewed$"):
        probe.validate_rows(populated((*BUCKET[:2], code, *BUCKET[3:])))


@pytest.mark.parametrize("data", [None, [], rows()[:-1], rows() + [rows()[0]], populated(BUCKET, BUCKET),
    rows() + [("PRIVATE_MARKER",)], rows() + [("bucket", "", "SYNTH", "PRIVATE_MARKER", "INJ", "N", "N", 1)],
    rows() + [("bucket", "", "SYNTH", "05", "INJ", "N", "N", 0)]])
def test_malformed_partial_or_unexpected_results_never_become_empty(database, data):
    database.rows = data
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report)


def test_exact_caps_and_canonical_aggregate_order():
    data = populated((*BUCKET[:7], 1000), encounters_in_scope=10000, matched_orders=1000, matched_encounters=1000)
    assert probe.validate_rows(data) == probe.validate_rows(data[::-1])


@pytest.mark.parametrize("code,reason", [("57014", "query_timed_out"), ("42501", "permission_denied"),
    ("42703", "schema_mismatch"), ("42P01", "schema_mismatch"), ("other", "read_failed")])
def test_provider_errors_redacted(code, reason):
    calls = []
    def runner(*args, **kwargs):
        calls.append(True)
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    report = probe.inspect_named_order(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == reason and calls == [True]
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("elapsed", ["PRIVATE_MARKER", float("nan"), float("inf"), True, -1, 10**400])
def test_proof_only_contains_allowlisted_fields(elapsed):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof.update(PRIVATE_MARKER="PRIVATE_MARKER", elapsed_seconds=elapsed)
        return rows()
    report = probe.inspect_named_order(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert set(report["closure"]) == set(probe.PROOF_FIELDS)
    assert "PRIVATE_MARKER" not in json.dumps(report, allow_nan=False)


def test_fifo_serializes_requests_with_isolated_test_mutex(database):
    database.rows = populated()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: inspect(), range(4)))
    assert all(r["status"] == "named_order_observed" for r in results)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4


def test_pinned_sql_has_only_exact_name_current_day_and_aggregate_output():
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.parameters(DAY))
    assert "medfee_nm = %(order_name)s AND ord_ymd = %(day)s" in sql
    assert "EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)" in sql
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "LIMIT %(encounter_limit)s" in sql and "LIMIT %(order_limit)s" in sql
    assert "GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1" in sql
    assert sql.endswith("LIMIT 41\n")
    assert "SELECT section, metric, code, kind, department, dc, act, n FROM report" in sql
    assert "ord_cd::text ~ %(code_pattern)s" in sql
    for field in ("hold_opd", "ptnt_no", "ptnt_nm", "birth", "sex", "age", "phone", "address",
                  "diagnosis", "notes", "insurance", "SELECT *", "FOR UPDATE", "FOR SHARE", "mwl"):
        assert field not in sql
    assert "LIKE" not in sql and probe.ORDER_NAME not in sql


def test_no_runtime_importer_or_database_settings_delivery_logging_dependency():
    root = Path(__file__).parents[1]
    source = Path(probe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        "datetime", "pathlib", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue",
    }
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names} == {"hashlib", "math", "re"}
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_named_order" not in path.read_text(encoding="utf-8-sig")
    for text in ("psycopg2", "settings", "connection_string", "logging", "http", "getenv",
                 "write_text", "write_bytes", "print(", "hold_opd"):
        assert text not in source


def code_rows(name_match="COMPACT_NAME", **changes):
    return populated(("bucket", name_match, "CONFIRMED_CODE", "05", "INJ", "N", "N", 1), **changes)


@pytest.mark.parametrize("name_match", probe.NAME_MATCHES)
def test_operator_confirmed_code_returns_only_fixed_name_matches_after_closure(database, monkeypatch, name_match):
    database.rows = code_rows(name_match)
    original = probe.validate_rows
    def closed(data, **kwargs):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data, **kwargs)
    monkeypatch.setattr(probe, "validate_rows", closed)
    report = inspect(by_code=True)
    assert report["status"] == "named_order_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["buckets"][0]["catalog_name_match"] == name_match
    assert report["findings"]["buckets"][0]["catalog_code"] == probe.CONFIRMED_CODE
    assert database.statements[-1] == (probe.CODE_QUERY, probe.parameters(DAY, by_code=True))
    assert len(database.statements) == 3


@pytest.mark.parametrize("mode", [None, 0, 1, "yes", {}])
def test_lookup_mode_requires_explicit_bool(database, mode):
    assert inspect(by_code=mode)["status"] == "invalid_scope" and not database.connections


@pytest.mark.parametrize("name_match,code", [("PRIVATE_MARKER", "CONFIRMED_CODE"),
    ("COMPACT_NAME", "OTHER_CODE"), ("COMPACT_NAME", None), ("", "CONFIRMED_CODE")])
def test_code_lookup_rejects_unexpected_name_or_code_without_echo(database, name_match, code):
    database.rows = populated(("bucket", name_match, code, "05", "INJ", "N", "N", 1))
    report = inspect(by_code=True)
    assert "findings" not in report and "PRIVATE_MARKER" not in json.dumps(report)


def test_two_name_variants_for_same_code_remain_distinct_buckets():
    data = code_rows()
    data[-1] = (*data[-1][:7], 1)
    data.append(("bucket", "SPACED_NAME", "CONFIRMED_CODE", "05", "INJ", "N", "N", 1))
    data = [(row[:7] + (2,) if row[1] == "matched_orders" else row) for row in data]
    result = probe.validate_rows(data, by_code=True)
    assert len(result["buckets"]) == 2


def test_code_query_pin_prevents_unreviewed_retrieval(database, monkeypatch):
    monkeypatch.setattr(probe, "CODE_QUERY", probe.CODE_QUERY + "\n")
    report = inspect(by_code=True)
    assert report["status"] == "query_changed" and not database.connections
    assert not any(report["closure"].values())


@pytest.mark.parametrize("mode", [False, True])
def test_code_probe_does_not_treat_zero_matches_as_empty_day(database, mode):
    database.rows = rows(encounters_in_scope=2)
    report = inspect(by_code=mode)
    assert report["status"] == "named_order_not_found" and not report["authoritative_snapshot"]


def test_code_query_is_fixed_exact_parameter_and_never_returns_arbitrary_catalog_names():
    sql = probe.CODE_QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.CODE_QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.parameters(DAY, by_code=True))
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    assert "WHERE ord_cd = %(order_code)s AND ord_ymd = %(day)s" in sql
    assert "WHEN medfee_nm = %(compact_name)s THEN 'COMPACT_NAME'" in sql
    assert "WHEN medfee_nm = %(spaced_name)s THEN 'SPACED_NAME'" in sql
    assert "WHEN medfee_nm IS NULL THEN 'NULL_NAME'" in sql
    assert "ELSE 'OTHER_NAME' END AS name_match" in sql
    assert "UNION ALL SELECT 'bucket', name_match, 'CONFIRMED_CODE', kind, department, dc, act, n" in sql
    assert "LIMIT %(encounter_limit)s" in sql and "LIMIT %(order_limit)s" in sql and sql.endswith("LIMIT 41\n")
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1" in sql
    for value in ("hold_opd", "ptnt_no", "ptnt_nm", "birth", "insurance", "price", "amount", "notes",
                  "SELECT *", "LIKE", probe.CONFIRMED_CODE, probe.ORDER_NAME):
        assert value not in sql


def test_operator_compact_name_uses_same_reviewed_exact_statement(database):
    database.rows = populated()
    report = inspect(compact_name=True)
    assert report["status"] == "named_order_observed"
    query, params = database.statements[-1]
    assert query == probe.QUERY and params["order_name"] == probe.CONFIRMED_CODE
    assert "order_code" not in params
    assert params["day"] == "20261006" and len(database.connections) == 1
    assert all(report["closure"][key] is True for key in probe.PROOF_FIELDS)


@pytest.mark.parametrize("mode", [None, 0, 1, "yes", {}])
def test_compact_name_lookup_requires_explicit_bool(database, mode):
    assert inspect(compact_name=mode)["status"] == "invalid_scope" and not database.connections


def test_two_lookup_modes_cannot_be_mixed(database):
    assert inspect(by_code=True, compact_name=True)["status"] == "invalid_scope"
    assert not database.connections
