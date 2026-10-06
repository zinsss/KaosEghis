import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from functools import partial
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db, pacs_polling, weekly_age_reporting
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import normalize_source_day_v2
from tests import source_order_coverage as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import policy
from tests.test_source_evidence_inspection import database


DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 12, tzinfo=probe.KST)


def rows(**changes):
    counts = dict.fromkeys(probe.BOUNDS, 0)
    counts.update(current_day_matches=1)
    counts.update(changes)
    return list(counts.items())


def synthetic_counts(encounters, orders):
    """Mock aggregate response from fictional four-part keys, not a SQL engine."""
    def linked_to_day(order):
        return order[0] is not None and order[0] in encounters
    linked = [order for order in orders if linked_to_day(order)]
    dated = [order for order in orders if order[1] == "20261006"]
    with_orders = sum(any(order[0] == encounter for order in linked) for encounter in encounters)
    duplicate_groups = lambda values: sum(count > 1 for count in Counter(values).values())
    invalid = lambda value: value is None or str(value).strip() == ""
    triples = defaultdict(set)
    for encounter, day, number, sequence in linked:
        if day is not None:
            triples[encounter, number, sequence].add(day)
    return rows(
        encounters=len(encounters), encounters_with_orders=with_orders,
        encounters_without_orders=len(encounters) - with_orders,
        invalid_encounter_keys=sum(invalid(key) for key in encounters),
        duplicate_encounter_keys=duplicate_groups(encounters),
        linked_orders=len(linked), dated_orders=len(dated),
        linked_orders_on_day=sum(order[1] == "20261006" for order in linked),
        linked_orders_off_day=sum(order[1] != "20261006" for order in linked),
        dated_orders_with_day_encounter=sum(linked_to_day(order) for order in dated),
        dated_orders_without_day_encounter=sum(not linked_to_day(order) for order in dated),
        linked_invalid_keys=sum(any(invalid(value) for value in key) for key in linked),
        dated_invalid_keys=sum(any(invalid(value) for value in key) for key in dated),
        linked_duplicate_keys=duplicate_groups(linked), dated_duplicate_keys=duplicate_groups(dated),
        linked_three_part_multi_date_keys=sum(len(days) > 1 for days in triples.values()),
    )


def populated():
    return synthetic_counts(["fictional-a", "fictional-b", "fictional-c"], [
        ("fictional-a", "20261006", "1", "1"), ("fictional-a", "20261006", "1", "2"),
        ("fictional-b", "20261006", "1", "1"),
    ])


def inspect(**changes):
    arguments = dict(clinic_day=DAY, now=lambda: NOW, approved=True)
    arguments.update(changes)
    return probe.inspect_coverage(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **arguments)


def test_exact_pinned_statement_is_serialized_and_physically_closed_before_processing(database, monkeypatch):
    database.rows = populated()
    original = probe.validate_rows
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        assert all(connection.closed for connection in database.connections)
        return original(data)
    monkeypatch.setattr(probe, "validate_rows", after_close)
    report = inspect()
    assert report["status"] == "order_counts_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["counts"] == dict(populated())
    assert report["findings"]["review_required"] == []
    assert all(report["closure"][key] is True for key in probe.PROOF_FIELDS)
    assert len(database.statements) == 3
    assert database.statements[-1] == (probe.QUERY, {"day": "20261006", "encounter_limit": 10001, "order_limit": 100001})


@pytest.mark.parametrize("encounters,orders,metric", [
    (["fictional-a"], [("fictional-a", "20261006", "1", "1")] * 2, "linked_duplicate_keys"),
    ([], [("fictional-outside-day", "20261006", "1", "1")], "dated_orders_without_day_encounter"),
    (["fictional-a"], [("fictional-a", "20261005", "1", "1")], "linked_orders_off_day"),
    (["fictional-a"], [("fictional-a", "20261006", "", "1")], "linked_invalid_keys"),
    ([None], [], "invalid_encounter_keys"),
    (["fictional-a", "fictional-a"], [("fictional-a", "20261006", "1", "1")], "duplicate_encounter_keys"),
])
def test_source_anomalies_are_only_fixed_aggregate_evidence(database, encounters, orders, metric):
    database.rows = synthetic_counts(encounters, orders)
    report = inspect()
    assert report["status"] == "coverage_anomalies_observed"
    assert metric in report["findings"]["review_required"]
    assert not report["authoritative_snapshot"]
    assert "fictional" not in json.dumps(report)


def test_different_order_dates_are_distinct_full_keys_not_three_part_duplicates(database):
    database.rows = synthetic_counts(["fictional-a"], [
        ("fictional-a", "20261005", "1", "1"), ("fictional-a", "20261006", "1", "1"),
    ])
    report = inspect()
    counts = report["findings"]["counts"]
    assert counts["linked_orders"] == 2 and counts["dated_orders"] == 1
    assert counts["linked_duplicate_keys"] == counts["dated_duplicate_keys"] == 0
    assert counts["linked_three_part_multi_date_keys"] == 1
    assert report["findings"]["review_required"] == ["linked_orders_off_day", "linked_three_part_multi_date_keys"]


def test_every_full_key_component_distinguishes_children():
    data = synthetic_counts(["fictional-a", "fictional-b"], [
        ("fictional-a", "20261006", "1", "1"), ("fictional-b", "20261006", "1", "1"),
        ("fictional-a", "20261005", "1", "1"), ("fictional-a", "20261006", "2", "1"),
        ("fictional-a", "20261006", "1", "2"),
    ])
    counts = probe.validate_rows(data)["counts"]
    assert counts["linked_orders"] == 5 and counts["linked_duplicate_keys"] == 0


@pytest.mark.parametrize("data", [rows(), rows(encounters=3, encounters_without_orders=3), populated()])
def test_success_and_no_order_counts_never_become_authoritative_empty_or_enable_reader(database, policy, data):
    database.rows = data
    report = inspect()
    assert report["status"] == "order_counts_observed" and not report["authoritative_snapshot"]
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    opened = len(database.connections)
    assert EghisSourceDayReader().read_day(DAY, NOW).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == opened


@pytest.mark.parametrize("approved", [False, 0, 1, None, "yes"])
def test_explicit_approval_required_before_connecting(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("day", [None, True, NOW, "2026-10-06", DAY - timedelta(days=1), DAY + timedelta(days=1)])
def test_only_current_kst_day_is_eligible(database, day):
    assert inspect(clinic_day=day)["status"] in {"invalid_scope", "current_day_changed"}
    assert not database.connections


@pytest.mark.parametrize("clock", [None, lambda: DAY, lambda: NOW.replace(tzinfo=None), lambda: "PRIVATE_MARKER"])
def test_clock_requires_trusted_aware_datetime(database, clock):
    assert inspect(now=clock)["status"] == "invalid_scope" and not database.connections


def test_utc_is_converted_to_kst(database):
    database.rows = rows()
    assert inspect(now=lambda: datetime(2026, 10, 5, 15, tzinfo=timezone.utc))["status"] == "order_counts_observed"


@pytest.mark.parametrize("moments", [[NOW, NOW + timedelta(days=1)], [NOW, NOW, NOW + timedelta(days=1)]])
def test_midnight_during_read_or_validation_discards_aggregates(database, moments):
    database.rows = populated()
    clock = iter(moments)
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "current_day_changed" and "findings" not in report
    assert report["closure"]["connection_closed"]


def test_server_guard_rejects_queued_prior_day(database):
    database.rows = rows(current_day_matches=0)
    report = inspect()
    assert report["status"] == "current_day_changed" and "findings" not in report


def test_query_hash_change_needs_new_review(database, monkeypatch):
    monkeypatch.setattr(probe, "QUERY", probe.QUERY + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"),
                                  ("on", "0", "read committed"), ("on", "2s", "serializable")])
def test_readonly_timeout_verification_precedes_source_query(database, mode):
    database.mode = mode
    report = inspect()
    assert report["status"] == "session_unverified" and "findings" not in report
    assert len(database.statements) == 2 and report["closure"]["connection_closed"]


@pytest.mark.parametrize("stage", [
    "connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open",
])
def test_every_failure_is_redacted_and_never_empty_or_retried(database, stage, capsys, caplog):
    database.rows, database.stage = populated(), stage
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_unverified_cleanup_cannot_be_interpreted(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return populated()
    def forbidden(*args):
        pytest.fail("Unverified cleanup must not reach interpretation")
    monkeypatch.setattr(probe, "validate_rows", forbidden)
    report = probe.inspect_coverage(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("field,cap", probe.BOUNDS.items())
def test_each_cap_plus_one_rejects_truncation(database, field, cap):
    database.rows = rows(**{field: cap + 1})
    report = inspect()
    assert report["status"] == "source_overflow" and "findings" not in report


@pytest.mark.parametrize("value", [None, True, -1, 0.0, "PRIVATE_MARKER", [], {}])
def test_strict_nonnegative_integer_counts(value):
    with pytest.raises(probe.CoverageRejected, match="^invalid_result$"):
        probe.validate_rows(rows(encounters=value))


@pytest.mark.parametrize("data", [None, [], rows()[:-1], rows() + [("encounters", 0)],
    rows()[:-1] + [("PRIVATE_MARKER", 0)], rows()[:-1] + [rows()[0]],
    rows()[:-1] + [("PRIVATE_MARKER",)], rows()[:-1] + [("linked_orders", "PRIVATE_MARKER")]])
def test_partial_unknown_duplicate_or_extra_report_never_empty(database, data):
    database.rows = data
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("change", [
    {"encounters": 4}, {"encounters_with_orders": 0}, {"encounters_without_orders": 0},
    {"linked_orders": 4}, {"dated_orders": 4}, {"linked_orders_on_day": 2},
    {"linked_orders_off_day": 1}, {"dated_orders_with_day_encounter": 2},
    {"dated_orders_without_day_encounter": 1}, {"invalid_encounter_keys": 4},
    {"duplicate_encounter_keys": 2}, {"linked_invalid_keys": 4}, {"dated_invalid_keys": 4},
    {"linked_duplicate_keys": 2}, {"dated_duplicate_keys": 2},
    {"linked_three_part_multi_date_keys": 1}, {"linked_invalid_keys": 1}, {"dated_duplicate_keys": 1},
])
def test_single_snapshot_set_equalities_and_subcounts_must_agree(change):
    counts = dict(populated())
    counts.update(change)
    with pytest.raises(probe.CoverageRejected, match="^inconsistent_result$"):
        probe.validate_rows(list(counts.items()))


def test_unique_parent_presence_cannot_exceed_order_count():
    with pytest.raises(probe.CoverageRejected, match="^inconsistent_result$"):
        probe.validate_rows(rows(encounters=2, encounters_with_orders=2, linked_orders=1,
                                 linked_orders_on_day=1, dated_orders=1, dated_orders_with_day_encounter=1))


def test_exact_caps_and_report_order_are_valid_not_authoritative():
    data = rows(encounters=10000, encounters_with_orders=10000, linked_orders=100000,
                linked_orders_on_day=100000, dated_orders=100000, dated_orders_with_day_encounter=100000)
    assert probe.validate_rows(data) == probe.validate_rows(data[::-1])


@pytest.mark.parametrize("code,reason", [("57014", "query_timed_out"), ("42501", "permission_denied"),
    ("42703", "schema_mismatch"), ("42P01", "schema_mismatch"), ("other", "read_failed")])
def test_provider_failure_is_fixed_redacted_no_retry(code, reason):
    calls = []
    def runner(*args, **kwargs):
        calls.append(True)
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    report = probe.inspect_coverage(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == reason and calls == [True]
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("elapsed", ["PRIVATE_MARKER", float("nan"), float("inf"), True, -1, 10**400])
def test_proof_output_is_allowlisted(elapsed):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof.update(PRIVATE_MARKER="PRIVATE_MARKER", elapsed_seconds=elapsed)
        return rows()
    report = probe.inspect_coverage(runner, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert set(report["closure"]) == set(probe.PROOF_FIELDS)
    assert "PRIVATE_MARKER" not in json.dumps(report, allow_nan=False)


def test_concurrent_requests_use_existing_fifo_and_test_mutex(database):
    database.rows = populated()
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: inspect(), range(4)))
    assert all(report["status"] == "order_counts_observed" for report in reports)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4


def test_sql_is_one_pinned_bounded_aggregate_statement_with_all_four_key_parts():
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.QUERY_SHA256
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.parameters(DAY))
    assert set(re.findall(r"SELECT '([a-z_]+)'", sql)) == set(probe.BOUNDS)
    assert "LIMIT %(encounter_limit)s" in sql and sql.count("LIMIT %(order_limit)s") == 2
    assert f"LIMIT {len(probe.BOUNDS) + 1}\n" in sql
    assert sql.count("GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1") == 2
    assert "GROUP BY recept_no, ord_no, ord_seq_no HAVING count(DISTINCT ord_ymd) > 1" in sql
    assert "ord_ymd IS DISTINCT FROM %(day)s" in sql
    assert sql.count("(SELECT matches FROM day_guard) = 1") == 2
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "SELECT metric, n FROM summary ORDER BY metric\nLIMIT 18" in sql
    linked_select = sql.split("), linked AS (", 1)[1].split("), dated AS (", 1)[0]
    assert "WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)" in linked_select
    assert "ord_ymd =" not in linked_select
    for forbidden in ("hold_opd", "hold_yn", "proc_gb", "ptnt_no", "birth", "name", "sex", "age",
                      "address", "phone", "diagnosis", "insurance", "ord_cd", "ord_type", "proc_dept_cd",
                      "dc_yn", "act_yn", "mwl", "hz_mst_ptnt", "SELECT *", "FOR UPDATE", "FOR SHARE",
                      "pg_sleep", "SET ROLE", "20261006"):
        assert forbidden not in sql


def test_builtin_pacs_and_flu_queries_have_different_scopes_not_all_order_authority():
    pacs = pacs_polling._build_default_image_order_query(DAY)
    assert "FROM public.mwl AS m" in pacs and "JOIN public.h2opd_doct_ord AS o" in pacs
    assert "o.proc_dept_cd = 'XRAY'" in pacs and "m.scheduled_proc_status = '100'" in pacs
    assert "o.ord_ymd" not in pacs and "public.h1opdin" not in pacs
    assert "'20261006'" in pacs and "scheduled_dttm" in pacs
    flu = weekly_age_reporting.build_weekly_age_report_query("20261005", "20261011")
    assert "FROM public.h1opdin h" in flu and "JOIN public.hz_mst_ptnt p" in flu
    assert "h.proc_gb IN ('30', '40')" in flu and "h2opd_doct_ord" not in flu
    assert "p.birth_ymd" in flu
    assert pacs_polling._resolve_image_study_query({"eghis_db_image_study_query": "SELECT 1"}) == "SELECT 1"
    assert weekly_age_reporting._resolve_weekly_age_report_query(
        settings={"eghis_db_weekly_age_report_query": "SELECT 1"}, year=2026, start_week=41,
        end_week=41, start_ymd="20261005", end_ymd="20261011",
    ) == "SELECT 1"


def test_no_runtime_importer_or_driver_settings_logging_delivery_dependency():
    root = Path(__file__).parents[1]
    source = Path(probe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        "datetime", "pathlib", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue",
    }
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names} == {"hashlib", "math"}
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_order_coverage" not in path.read_text(encoding="utf-8-sig")
    for forbidden in ("psycopg2", "settings", "connection_string", "logging", "http", "getenv",
                      "write_text", "write_bytes", "print(", "hold_opd"):
        assert forbidden not in source
