from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_read_queue
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from tests import source_current_day_read as probe
from tests import test_source_current_day_orders_candidate as relational
from tests.test_emr_read_queue import isolated_coordinator


DAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 12, tzinfo=probe.KST)


def row(**changes):
    fields = dict(zip(probe.FIELDS, (
        "DATA", "candidate_rows", NOW, True, 2, 1, 1, 2, "20261007", "SYNTHETIC-A", "40", "N", True,
        "SYNTHETIC-A", "20261007", Decimal("1"), Decimal("1"), "SYNTHETIC-CATALOG", "Synthetic catalog",
        "SYNTHETIC-USER", "Synthetic prescription", Decimal("1.25"), Decimal("3"), Decimal("7"),
        "03", "LAB", "N", "N")))
    fields.update(changes)
    return tuple(fields[k] for k in probe.FIELDS)


def no_order(**changes):
    return row(**{**dict.fromkeys(probe.FIELDS[13:]), "order_present": False,
                 "source_encounter_id": "SYNTHETIC-B", "source_reception_code": "10", **changes})


def populated():
    return [row(), no_order()]


def empty():
    return row(**{**dict.fromkeys(probe.FIELDS[8:]), "row_kind": "META", "order_present": False,
                  "encounter_count": 0, "order_count": 0, "no_order_encounter_count": 0, "expected_result_rows": 1})


def batch(rows=None):
    values = populated() if rows is None else rows
    return probe.DetachedRows(probe.FIELDS, values, len(values))


@pytest.fixture
def database(monkeypatch):
    state = SimpleNamespace(rows=populated(), stage=None, events=[], statements=[], connections=[],
                            mode=("on", "2s", "read committed"), columns=probe.FIELDS, rowcount=None)
    def fail(stage):
        if state.stage == stage:
            error = RuntimeError("PRIVATE_MARKER source, SQL and credentials")
            error.pgcode = "57014" if stage == "query" else None
            raise error
    class Cursor:
        closed = False
        @property
        def description(self):
            return tuple((name,) for name in state.columns)
        @property
        def rowcount(self):
            return len(state.rows) if state.rowcount is None else state.rowcount
        def execute(self, query, params=None):
            state.statements.append((query, params))
            fail("timeout_setup" if query.startswith("SET") else "mode" if query.startswith("SELECT current_setting") else "query")
        def fetchone(self):
            return state.mode
        def fetchmany(self, count):
            assert count == probe.RESULT_CAP + 1
            fail("fetch")
            return list(state.rows)
        def close(self):
            fail("cursor_close")
            self.closed = state.stage != "cursor_still_open"
            state.events.append("cursor_closed")
    class Connection:
        closed = 0
        def set_session(self, **kwargs):
            assert kwargs == {"readonly": True, "autocommit": True, "isolation_level": "READ COMMITTED"}
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
        assert emr_read_queue._mutex_name.startswith("Local\\KaosEghis-test-")
        assert args == ("mock-secret",)
        assert kwargs == {"connect_timeout": 3, "application_name": "KaosEghis-day-read-evidence"}
        fail("connect")
        connection = Connection()
        state.connections.append(connection)
        state.events.append("connected")
        return connection
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    return state


def inspect(**changes):
    args = dict(clinic_day=DAY, now=lambda: NOW, approved=True)
    args.update(changes)
    return probe.inspect("mock-secret", **args)


def test_one_statement_full_fetch_and_physical_close_before_interpretation(database, monkeypatch, capsys, caplog):
    original = probe.summarize
    batches = []
    def after_close(result, day):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        assert all(c.closed for c in database.connections)
        batches.append(result)
        return original(result, day)
    monkeypatch.setattr(probe, "summarize", after_close)
    report = inspect()
    assert report["status"] == "populated_candidate_observed" and not report["authoritative_snapshot"]
    assert report["findings"] == {"candidate_encounters": 2, "orders": 1, "no_order_encounters": 1,
        "encounters_with_orders": 1, "returned_rows": 2, "row_counts_consistent": True,
        "unique_four_part_keys": True, "no_order_encounters_preserved": True,
        "all_children_linked_to_scoped_parent": True, "user_name_null_count": 0,
        "numeric_null_counts": {"source_qty": 0, "source_divide": 0, "source_days": 0}}
    assert all(report["closure"].values()) and batches[0].rows == []
    assert repr(batches[0]) == "<DetachedRows: redacted>"
    assert len(database.statements) == 3 and len(database.connections) == 1
    assert database.statements[-1] == (probe.QUERY, {"day": "20261007", "encounter_cap": 1000, "order_cap": 10000})
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("approval", [None, False, 1, "yes"])
def test_explicit_approval_before_connection(database, approval):
    assert inspect(approved=approval)["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("scope", [None, "2026-10-07", DAY - timedelta(days=1), DAY + timedelta(days=1)])
def test_only_current_kst_day(database, scope):
    assert inspect(clinic_day=scope)["status"] == "invalid_scope" and not database.connections


@pytest.mark.parametrize("position", range(4))
def test_midnight_before_enqueue_in_queue_after_read_or_after_validation(database, position):
    moments = iter([NOW] * position + [NOW + timedelta(days=1)])
    report = inspect(now=lambda: next(moments))
    assert report["status"] == "invalid_scope" and "findings" not in report
    assert bool(database.connections) == (position >= 2)
    if database.connections:
        assert all(report["closure"].values())


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failed_partial_timeout_cleanup_no_retry_no_data(database, stage, capsys, caplog):
    database.stage = stage
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    for text in ("PRIVATE_MARKER", "mock-secret", "SYNTHETIC", "Synthetic"):
        assert text not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"), ("on", "0", "read committed"), ("on", "2s", "serializable")])
def test_session_proof_before_select(database, mode):
    database.mode = mode
    assert inspect()["status"] == "session_unverified" and len(database.statements) == 2


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_missing_closure_proof_forbids_processing(database, monkeypatch, field):
    def read(_connection, _params, proof, _timings, _queued):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return batch()
    monkeypatch.setattr(probe, "_read", read)
    monkeypatch.setattr(probe, "summarize", lambda *_: pytest.fail("Processed before close"))
    assert inspect()["status"] == "cleanup_unverified" and not database.connections


def test_empty_is_observed_zero_never_verified_empty(database):
    database.rows = [empty()]
    report = inspect()
    assert report["status"] == "zero_candidate_not_verified_empty" and not report["authoritative_snapshot"]
    assert report["findings"]["candidate_encounters"] == 0
    database.rows = []
    assert inspect()["status"] == "inconsistent_result"


@pytest.mark.parametrize("reason", sorted(probe.SQL_FAILURES))
def test_sql_rejection_not_empty_and_no_partial_findings(database, reason):
    database.rows = [row(row_kind="META", extraction_status=reason)]
    report = inspect()
    assert report["status"] == reason and "findings" not in report and not report["authoritative_snapshot"]


@pytest.mark.parametrize("change", [
    {"row_kind": "PRIVATE_MARKER"}, {"extraction_status": "PRIVATE_MARKER"}, {"observed_at": NOW.replace(tzinfo=None)},
    {"day_matches": 1}, {"encounter_count": True}, {"order_count": 2}, {"expected_result_rows": 1},
    {"source_clinic_day": "20261006"}, {"source_order_date": "20261006"}, {"source_encounter_id": None},
    {"source_encounter_id": True}, {"source_order_encounter_id": "SYNTHETIC-OTHER"}, {"source_order_number": 1.0},
    {"source_order_sequence": " "}, {"order_present": 1}, {"dc_yn": "unknown"}, {"act_yn": None},
    {"hold_yn": ""}, {"source_reception_code": "x" * 129}, {"user_name": "x" * 257},
    {"user_name": "private\nnotes"}, {"catalog_code": "\ud800"}, {"source_qty": 1.25},
    {"source_qty": "1.25"}, {"source_divide": Decimal("NaN")}, {"source_days": Decimal("Infinity")},
    {"source_qty": Decimal("1E+1000")}, {"source_qty": Decimal("1E-1000")},
])
def test_malformed_facts_rejected_without_values(change):
    with pytest.raises(probe.ReadRejected) as caught:
        probe.summarize(batch([row(**change), no_order()]), DAY)
    assert str(caught.value) in probe.REASONS and "PRIVATE_MARKER" not in str(caught.value)


@pytest.mark.parametrize("value", [None, 0, False, -1, 3])
def test_driver_row_count_disagreement(value):
    with pytest.raises(probe.ReadRejected):
        probe.summarize(replace(batch(), driver_rowcount=value), DAY)


def test_partial_extra_column_truncated_and_overflow_results(database):
    for rows, columns in [([row()], probe.FIELDS), ([row()[:-1]], probe.FIELDS),
                          ([row(), no_order()], (*probe.FIELDS, "forbidden"))]:
        database.rows, database.columns = rows, columns
        assert "findings" not in inspect()
    with pytest.raises(probe.ReadRejected, match="^result_overflow$"):
        probe.summarize(batch([row()] * (probe.RESULT_CAP + 1)), DAY)


def test_duplicates_parent_conflicts_and_no_order_conflict():
    variants = [
        [row(encounter_count=1, order_count=2, no_order_encounter_count=0)] * 2,
        [row(order_count=2, no_order_encounter_count=0),
         row(order_count=2, no_order_encounter_count=0, source_order_sequence=Decimal("2"), hold_yn="Y")],
        [row(), no_order(source_encounter_id="SYNTHETIC-A")],
        [row(), no_order(encounter_count=True)],
    ]
    for rows in variants:
        with pytest.raises(probe.ReadRejected):
            probe.summarize(batch(rows), DAY)


@pytest.mark.parametrize("code", ["10", "20", "25", "30", "40", "50", None, "UNKNOWN"])
def test_opaque_states_and_cancelled_children_not_mapped_or_filtered(code):
    result = probe.summarize(batch([row(source_reception_code=code, dc_yn="Y", act_yn="Y"), no_order()]), DAY)
    assert result["candidate_encounters"] == 2 and result["orders"] == 1
    assert "state" not in result


def test_nulls_and_exact_decimals_preserved_without_calculation():
    result = probe.summarize(batch([row(user_name=None, source_qty=None,
        source_divide=Decimal("-0.25"), source_days=Decimal("0.001")), no_order()]), DAY)
    assert result["user_name_null_count"] == result["numeric_null_counts"]["source_qty"] == 1
    assert not {"units", "total_dose", "daily_dose", "source_qty"}.intersection(result)


def test_full_four_part_key_and_same_parent_repetition():
    rows = [row(order_count=2, expected_result_rows=3),
            row(order_count=2, expected_result_rows=3, source_order_sequence=Decimal("2")),
            no_order(order_count=2, expected_result_rows=3)]
    assert probe.summarize(batch(rows), DAY)["orders"] == 2


def test_query_hash_source_scope_and_runtime_unchanged(database, monkeypatch):
    assert hashlib.sha256(probe.QUERY.encode()).hexdigest() == probe.QUERY_HASH
    assert not probe._WRITE_SQL_PATTERN.search(probe.QUERY)
    assert "char_length(CAST(qty AS text)) > 128" in probe.QUERY
    assert "char_length(CAST(divide AS text)) > 128" in probe.QUERY
    assert "char_length(CAST(days AS text)) > 128" in probe.QUERY
    for forbidden in ("hold_opd", "ptnt_nm", "ptnt_no", "birth", "phone", "address", "diagnosis", "notes", "insurance"):
        assert forbidden not in probe.QUERY
    for path in (Path(__file__).parents[1] / "KaosEghis").rglob("*.py"):
        assert "source_current_day_read" not in path.read_text(encoding="utf-8-sig")
    monkeypatch.setattr(probe, "QUERY", probe.QUERY + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.fixture
def relational_db(request):
    yield from relational.database.__wrapped__()


@pytest.mark.parametrize("field", ["source_qty", "source_divide", "source_days"])
def test_actual_sql_numeric_cell_cap_before_source_return(relational_db, monkeypatch, field):
    monkeypatch.setattr(relational, "SQL", probe.QUERY)
    relational.parent(relational_db)
    relational.child(relational_db, **{field: "1" * 128})
    assert relational.query(relational_db)[0]["extraction_status"] == "candidate_rows"
    relational.child(relational_db, sequence=2, **{field: "1" * 129})
    relational.rejected(relational.query(relational_db), "field_overflow")


def test_actual_statement_membership_null_child_and_sql_to_validator(relational_db, monkeypatch):
    monkeypatch.setattr(relational, "SQL", probe.QUERY)
    relational.parent(relational_db, 1)
    relational.parent(relational_db, 2, code="10")
    relational.child(relational_db, 1)
    relational.child(relational_db, 1, sequence=2, dc_yn="Y", order_type="FEE")
    rows = relational.query(relational_db)
    for record in rows:
        record["observed_at"] = datetime.fromisoformat(record["observed_at"])
        record["day_matches"] = bool(record["day_matches"])
        record["order_present"] = bool(record["order_present"])
        for name in ("source_qty", "source_divide", "source_days"):
            if record[name] is not None:
                record[name] = Decimal(record[name])
    result = probe.summarize(batch([tuple(r[k] for k in probe.FIELDS) for r in rows]), DAY)
    assert result["candidate_encounters"] == 2 and result["orders"] == 2 and result["no_order_encounters"] == 1


def test_actual_statement_reception_code_diagnostic_bound(relational_db, monkeypatch):
    monkeypatch.setattr(relational, "SQL", probe.QUERY)
    relational.parent(relational_db, code="x" * 129)
    relational.rejected(relational.query(relational_db), "field_overflow")
