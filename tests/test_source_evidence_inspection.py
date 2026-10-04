import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from KaosEghis.core import eghis_db, emr_read_queue
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from KaosEghis.tools import inspect_source_evidence as evidence
from tests.test_emr_read_queue import isolated_coordinator


DAY = date(2026, 10, 2)


def empty_rows(**changes):
    counts = dict.fromkeys(evidence.SUMMARY_FIELDS, 0)
    counts.update(changes)
    return [("summary", key, "", "", "", value) for key, value in counts.items()]


def populated_rows():
    return empty_rows(encounters=2, orders=1, dated_orders=1,
                      no_order_encounters=1, sex_rows=2) + [
        ("reception", "10", "N", "N", "", 1),
        ("reception", "25", "N", "N", "", 1),
        ("orders", "03", "LAB", "N", "N", 1),
        ("sex", "M", "", "", "", 1),
        ("sex", "NULL", "", "", "", 1),
    ]


def schema_rows():
    return [(table, field, "varchar", True, "r", True)
            for table, names in evidence.SCHEMA_FIELDS.items() for field in sorted(names)]


@pytest.fixture
def database(monkeypatch):
    state = SimpleNamespace(rows=empty_rows(), stage=None, events=[], statements=[],
                            mode=("on", "2s", "read committed"), connections=[])
    def fail(stage):
        if state.stage == stage:
            error = RuntimeError("PRIVATE_MARKER provider SQL and credentials")
            error.pgcode = "57014" if stage == "query" else None
            raise error

    class Cursor:
        closed = False
        def execute(self, query, params=None):
            state.statements.append((query, params))
            fail("timeout_setup" if query.startswith("SET") else
                 "mode" if query.startswith("SELECT current_setting") else "query")
        def fetchone(self):
            return state.mode
        def fetchmany(self, count):
            assert count == evidence.REPORT_CAP + 1
            fail("fetch")
            return state.rows
        def close(self):
            fail("cursor_close")
            self.closed = state.stage != "cursor_still_open"
            state.events.append("cursor_closed")

    class Connection:
        closed = 0
        def set_session(self, **kwargs):
            assert kwargs == {"readonly": True, "autocommit": True,
                              "isolation_level": "READ COMMITTED"}
            fail("readonly")
        def cursor(self):
            fail("cursor")
            return Cursor()
        def close(self):
            fail("connection_close")
            self.closed = 0 if state.stage == "connection_still_open" else 1
            state.events.append("connection_closed")

    def connect(*args, **kwargs):
        assert threading.current_thread().name.startswith("KaosEghis-emr")
        assert args == ("mock-secret",)
        assert kwargs == {"connect_timeout": 3, "application_name": "KaosEghis-source-evidence"}
        fail("connect")
        connection = Connection()
        state.connections.append(connection)
        state.events.append("connected")
        return connection

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    return state


def inspect(**changes):
    arguments = dict(operation="day", clinic_day=DAY, expectation="empty", approved=True)
    arguments.update(changes)
    return evidence.inspect_evidence("mock-secret", **arguments)


def test_day_scope_query_and_postclosure_processing(database, monkeypatch):
    original = evidence._day_findings
    def validate(*args):
        assert database.events[-2:] == ["cursor_closed", "connection_closed"]
        assert all(c.closed for c in database.connections)
        return original(*args)
    monkeypatch.setattr(evidence, "_day_findings", validate)
    result = inspect()
    assert result["status"] == "observed_empty_scope"
    assert result["authoritative_snapshot"] is False
    assert all(result["closure"][key] is True for key in (
        "connection_opened", "readonly_verified", "cursor_closed", "connection_closed"))
    query, params = database.statements[-1]
    assert query == evidence.DAY_SQL
    assert params["day"] == "20261002"
    assert "20261002" not in query
    assert params["encounter_limit"] == 10001 and params["order_limit"] == 100001
    assert len(database.statements) == 3


def test_populated_scope_retains_no_order_encounters_and_raw_qualifiers(database):
    database.rows = populated_rows()
    result = inspect(expectation="populated")
    assert result["status"] == "observed_populated_scope"
    assert result["findings"]["counts"]["no_order_encounters"] == 1
    assert result["authoritative_snapshot"] is False


@pytest.mark.parametrize("metric,value", [
    ("no_order_encounters", 0), ("dated_orders", 0), ("missing_patient_links", 1),
])
def test_crosschecked_population_counts_must_agree(database, metric, value):
    database.rows = [((*row[:5], value) if row[0:2] == ("summary", metric) else row)
                     for row in populated_rows()]
    assert inspect(expectation="populated")["status"] == "inconsistent_result"


def test_schema_operation_is_fixed_bounded_and_closed(database):
    database.rows = schema_rows()
    result = inspect(operation="schema", clinic_day=None, expectation=None)
    assert result["status"] == "schema_observed"
    assert database.statements[-1][0] == evidence.SCHEMA_SQL
    assert result["closure"]["connection_closed"] is True


@pytest.mark.parametrize("change", [
    {"approved": False}, {"approved": 1}, {"clinic_day": "2026-10-02"},
    {"clinic_day": None}, {"expectation": None}, {"expectation": "guess"},
    {"operation": "arbitrary"}, {"operation": "schema"},
])
def test_bad_scope_or_missing_approval_never_connects(database, change):
    assert inspect(**change)["status"] in {"approval_required", "invalid_scope"}
    assert not database.connections


@pytest.mark.parametrize("mode", [("off", "2s", "read committed"),
                                  ("on", "0", "read committed"), None,
                                  ("on", "2s", "serializable")])
@pytest.mark.parametrize("operation", ["day", "reception"])
def test_session_verification_precedes_source_read(database, mode, operation):
    database.mode = mode
    result = inspect(operation=operation)
    assert result["status"] == "session_unverified"
    assert len(database.statements) == 2
    assert result["closure"]["cursor_closed"] and result["closure"]["connection_closed"]
    assert "findings" not in result


@pytest.mark.parametrize("stage", [
    "connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open",
])
@pytest.mark.parametrize("operation", ["day", "reception"])
def test_all_failure_stages_are_redacted_and_never_authoritative_empty(database, stage, operation):
    database.stage = stage
    result = inspect(operation=operation)
    assert result["status"] not in {"observed_empty_scope", "observed_populated_scope"}
    assert "findings" not in result and not result["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(result) and "mock-secret" not in json.dumps(result)
    if stage not in {"connect", "connection_close", "connection_still_open"}:
        assert result["closure"]["connection_closed"]
    if stage.startswith("connection_"):
        assert result["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect()["status"] == "reader_safety_stop"
        assert len(database.connections) == opened


@pytest.mark.parametrize("metric,limit", [
    ("encounters", 10001), ("sex_rows", 10001),
    ("orders", 100001), ("dated_orders", 100001),
])
def test_cap_plus_one_is_overflow_never_truncated_success(database, metric, limit):
    database.rows = empty_rows(**{metric: limit})
    result = inspect()
    assert result["status"] == "source_overflow"
    assert "findings" not in result


@pytest.mark.parametrize("rows", [
    [], empty_rows()[:-1], empty_rows() + [empty_rows()[0]],
    [("summary", "encounters", "", "", "", "PRIVATE_MARKER")],
    [("summary", "encounters", "", "", "", True)],
    [("summary", "encounters", "", "", "", -1)],
    [("summary", "private_column", "", "", "", 1)],
    [("sex", "PRIVATE_MARKER", "", "", "", 1)],
    [("reception", "10", "PRIVATE_MARKER", "N", "", 1)],
    [("orders", "03", "PRIVATE_MARKER", "Y", "N", 1)],
    [("summary", "encounters", "", "", "", 0)] * 257,
])
def test_partial_overflow_or_unallowlisted_results_fail_closed(database, rows):
    database.rows = rows
    result = inspect()
    assert "findings" not in result and not result["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("counts", [
    {"encounters": 1}, {"orders": 1}, {"sex_rows": 1},
    {"invalid_encounter_keys": 1}, {"duplicate_encounter_keys": 1},
    {"invalid_order_keys": 1}, {"duplicate_order_keys": 1},
    {"no_order_encounters": 1}, {"missing_patient_links": 1},
    {"orders_other_date": 1}, {"dated_orders_without_day_encounter": 1},
])
def test_inconsistent_counts_do_not_establish_completeness(database, counts):
    database.rows = empty_rows(**counts)
    result = inspect()
    assert result["status"] == "inconsistent_result"
    assert "findings" not in result


@pytest.mark.parametrize("expectation,rows", [
    ("populated", empty_rows()), ("empty", populated_rows()),
    ("empty", empty_rows(dated_orders=1, dated_orders_without_day_encounter=1)),
])
def test_operator_expectation_is_required_and_checked(database, expectation, rows):
    database.rows = rows
    assert inspect(expectation=expectation)["status"] == "operator_expectation_mismatch"


@pytest.mark.parametrize("mutation", ["missing", "extra", "view", "permission", "duplicate", "type"])
def test_schema_is_not_assumed(database, mutation):
    rows = schema_rows()
    if mutation == "missing":
        rows = []
    elif mutation == "extra":
        rows += [("h1opdin", "PRIVATE_MARKER", "text", False, "r", True)]
    elif mutation == "duplicate":
        rows += [rows[0]]
    else:
        row = list(rows[0])
        row[{"view": 4, "permission": 5, "type": 2}[mutation]] = {
            "view": "v", "permission": False, "type": "PRIVATE_MARKER"}[mutation]
        rows[0] = tuple(row)
    database.rows = rows
    result = inspect(operation="schema", clinic_day=None, expectation=None)
    assert "findings" not in result
    assert "PRIVATE_MARKER" not in json.dumps(result)


def test_shared_fifo_and_max_one_physical_connection(database):
    with ThreadPoolExecutor(max_workers=4) as callers:
        reports = list(callers.map(lambda _: inspect(), range(4)))
    assert all(r["status"] == "observed_empty_scope" for r in reports)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4
    assert evidence.run_verified_evidence_query is eghis_db.run_verified_evidence_query
    assert eghis_db.run_serialized_read is emr_read_queue.run_serialized_read


def test_fixed_sql_review_scope_privacy_and_one_statement():
    for sql in (evidence.DAY_SQL, evidence.SCHEMA_SQL, evidence.RECEPTION_SQL):
        assert ";" not in sql
        assert not any(word in sql.lower() for word in (
            "ptnt_nm", "birth_ymd", "jumin", "phone", "address", "diagnosis",
            "medfee_nm", "ord_nm", "for update", "for share", "pg_sleep"))
    assert "WHERE clinic_ymd=%(day)s" in evidence.DAY_SQL
    assert "SELECT 1 FROM h WHERE h.recept_no=x.recept_no" in evidence.DAY_SQL
    assert "GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no" in evidence.DAY_SQL
    assert "NOT EXISTS (SELECT 1 FROM o WHERE o.recept_no=h.recept_no)" in evidence.DAY_SQL
    assert "FROM h LEFT JOIN public.hz_mst_ptnt" in evidence.DAY_SQL
    assert "ELSE 'UNREVIEWED'" in evidence.DAY_SQL
    assert "LIMIT 257" in evidence.DAY_SQL


def reception_rows(code="10", hold="N", opd="N", count=1):
    return [("summary", "encounters", "", "", "", count)] + (
        [("reception", code, hold, opd, "", count)] if count else [])


@pytest.mark.parametrize("code,hold,opd", [
    ("10", "N", "N"), ("10", "Y", "Y"), ("20", "N", "Y"),
    ("NULL", "BLANK", "UNREVIEWED"),
])
def test_reception_only_scope_is_parameterized_and_processed_after_closure(
        database, monkeypatch, code, hold, opd):
    database.rows = reception_rows(code, hold, opd)
    original = evidence._reception_findings
    def validate(*args):
        assert database.events[-2:] == ["cursor_closed", "connection_closed"]
        assert all(c.closed for c in database.connections)
        return original(*args)
    monkeypatch.setattr(evidence, "_reception_findings", validate)
    result = inspect(operation="reception", expectation="populated")
    assert result["status"] == "observed_reception_scope"
    assert result["findings"] == {
        "counts": {"encounters": 1},
        "groups": {"reception": [{"values": [code, hold, opd], "count": 1}]}}
    assert result["authoritative_snapshot"] is False
    query, params = database.statements[-1]
    assert query == evidence.RECEPTION_SQL
    assert params == {"day": "20261002", "encounter_limit": 10001,
                      "proc": list(evidence.PROC), "flags": list(evidence.FLAGS)}
    assert len(database.statements) == 3
    assert "WHERE clinic_ymd=%(day)s" in query and "LIMIT 257" in query
    assert "LIMIT %(encounter_limit)s" in query
    for forbidden in ("recept_no", "ptnt_no", "hz_mst_ptnt", "h2opd", "sex", "JOIN"):
        assert forbidden not in query


@pytest.mark.parametrize("rows,status", [
    ([], "result_overflow_or_incomplete"),
    (reception_rows() * 129, "result_overflow_or_incomplete"),
    (reception_rows(count=10001), "source_overflow"),
    (reception_rows()[1:], "incomplete_result"),
    (reception_rows()[:1], "inconsistent_result"),
    (reception_rows() + [reception_rows()[0]], "invalid_result"),
    (reception_rows("PRIVATE_MARKER"), "invalid_result"),
    (reception_rows(hold="PRIVATE_MARKER"), "invalid_result"),
    (reception_rows(opd="PRIVATE_MARKER"), "invalid_result"),
    ([("summary", "encounters", "", "", "", True)], "invalid_result"),
    ([("summary", "encounters", "", "", "", -1)], "invalid_result"),
    ([("summary", "encounters", "", "", "", "PRIVATE_MARKER")], "invalid_result"),
    ([("summary", "PRIVATE_MARKER", "", "", "", 0)], "invalid_result"),
    ([("summary", "encounters")], "invalid_result"),
    (reception_rows(count=0), "operator_expectation_mismatch"),
])
def test_reception_only_invalid_results_fail_closed(database, rows, status):
    database.rows = rows
    result = inspect(operation="reception", expectation="populated")
    assert result["status"] == status
    assert "findings" not in result and result["authoritative_snapshot"] is False
    assert "PRIVATE_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("change", [
    {"approved": False}, {"approved": 1}, {"clinic_day": None},
    {"clinic_day": "2026-10-02"}, {"expectation": None}, {"expectation": "waiting"},
])
def test_reception_scope_requires_approval_date_and_expectation(database, change):
    arguments = dict(operation="reception", expectation="populated")
    arguments.update(change)
    assert inspect(**arguments)["status"] in {"approval_required", "invalid_scope"}
    assert not database.connections


def test_reception_only_empty_remains_non_authoritative(database):
    database.rows = reception_rows(count=0)
    result = inspect(operation="reception")
    assert result["status"] == "observed_reception_scope"
    assert result["findings"] == {"counts": {"encounters": 0}, "groups": {"reception": []}}
    assert result["authoritative_snapshot"] is False
    database.rows = reception_rows()
    assert inspect(operation="reception")["status"] == "operator_expectation_mismatch"


def test_evidence_is_disconnected_and_cannot_unblock_runtime_reader():
    source = Path(evidence.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    allowed = {"datetime", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue"}
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) else [])
        assert set(names) <= allowed
    for candidate in source.parents[1].rglob("*.py"):
        if candidate != source:
            assert "inspect_source_evidence" not in candidate.read_text(encoding="utf-8-sig")
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
