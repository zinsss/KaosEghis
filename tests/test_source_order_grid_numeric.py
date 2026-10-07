from dataclasses import replace
from contextlib import closing
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus
from tests import source_order_grid_numeric as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database


DAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 12, tzinfo=probe.KST)
SAMPLE = probe.GridSample((99, (1, 2), (3, 4)), "000000001", "SYNTHETIC-CODE", "SYNTHETIC-NAME",
                          Decimal("4.25"), Decimal("2"), Decimal("7"))
ROW = (1, 1, 0, 0, 1, 1, 1, "numeric", "integer", "numeric")


def inspect(**kwargs):
    args = dict(sample_reader=lambda: SAMPLE, clinic_day=DAY, now=lambda: NOW, approved=True)
    args.update(kwargs)
    return probe.inspect(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **args)


def test_one_query_closed_before_second_ui_read_or_interpretation(database, monkeypatch, capsys, caplog):
    database.rows = [ROW]
    reads = []
    def reader():
        if reads:
            assert database.events == ["connected", "cursor_closed", "connection_closed"]
        reads.append(True)
        return SAMPLE
    original = probe.validate_result
    def closed(rows):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(rows)
    monkeypatch.setattr(probe, "validate_result", closed)
    report = inspect(sample_reader=reader)
    assert report["status"] == "one_row_numeric_match" and not report["authoritative_snapshot"]
    assert len(reads) == 2 and len(database.connections) == 1 and len(database.statements) == 3
    assert all(report["closure"][key] for key in probe.storage.PROOF_FIELDS)
    assert database.statements[-1] == (probe.QUERY, {
        "day": "20261007", "chart_no": SAMPLE.chart_no, "code": SAMPLE.code, "name": SAMPLE.name,
        "daily": SAMPLE.daily, "frequency": SAMPLE.frequency, "days": SAMPLE.days})
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("approval", [False, None, 1, "yes"])
def test_no_approval_no_ui_or_db(database, approval):
    report = inspect(approved=approval, sample_reader=lambda: pytest.fail("No UI without approval"))
    assert report["status"] == "approval_required" and not database.connections


@pytest.mark.parametrize("change", [
    {"chart_no": "private ' OR 1=1"}, {"chart_no": ""}, {"code": ""}, {"code": " "},
    {"code": "x" * 129}, {"name": "x" * 257}, {"name": "x\nprivate"}, {"name": "\ud800"},
    {"daily": 4.25}, {"daily": 4}, {"daily": Decimal("NaN")}, {"daily": Decimal("Infinity")},
    {"daily": Decimal("-1")}, {"daily": Decimal("100000000")}, {"daily": Decimal("0.000000001")},
    {"frequency": SAMPLE.days}, {"owner": []}, {"owner": ()},
])
def test_invalid_or_nondiscriminating_sample_never_queries(database, change):
    report = inspect(sample_reader=lambda: replace(SAMPLE, **change))
    assert report["status"] == "ui_or_day_scope_unverified" and not database.connections


@pytest.mark.parametrize("value", [None, 1, 1.0, "NaN", "Infinity", "1e2", "1,000", " 1", "1 ", "-1", ".5", "1.", "1.000000001", "100000000"])
def test_display_numbers_no_guess_or_float(value):
    with pytest.raises(probe.storage.StorageRejected, match="^source_scope_unverified$"):
        probe.parse_display_number(value)


def test_exact_numbers_and_text_preservation():
    assert probe.parse_display_number("0.12500000").as_tuple() == Decimal("0.12500000").as_tuple()
    sample = replace(SAMPLE, code=" SYNTHETIC-CODE ", name=" SYNTHETIC-NAME ")
    probe.validate_sample(sample)
    assert sample.code.startswith(" ") and sample.name.endswith(" ")
    assert repr(sample) == "<GridSample: redacted>"


@pytest.mark.parametrize("field,value", [
    ("owner", (100,)), ("chart_no", "000000002"), ("code", "SYNTHETIC-OTHER"),
    ("name", "SYNTHETIC-OTHER"), ("daily", Decimal("3")),
    ("frequency", Decimal("3")), ("days", Decimal("8")),
])
def test_ui_changes_discard_matches_after_close(database, field, value):
    database.rows = [ROW]
    samples = iter([SAMPLE, replace(SAMPLE, **{field: value})])
    report = inspect(sample_reader=lambda: next(samples))
    assert report["status"] == "source_scope_unverified" and "findings" not in report
    assert report["closure"]["connection_closed"]


@pytest.mark.parametrize("position", range(4))
def test_midnight_rejects_before_or_after_connection(database, position):
    database.rows = [ROW]
    moments = iter([NOW] * position + [NOW + timedelta(days=1)])
    report = inspect(now=lambda: next(moments))
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert bool(database.connections) == (position >= 2)


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failures_no_retry_no_raw_output(database, stage, capsys, caplog):
    database.rows, database.stage = [ROW], stage
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    for secret in ("PRIVATE_MARKER", "mock-secret", SAMPLE.chart_no, SAMPLE.code, SAMPLE.name):
        assert secret not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("field", probe.storage.PROOF_FIELDS)
def test_unverified_closure_forbids_interpretation_and_second_ui_read(field):
    calls = []
    def reader():
        calls.append(True)
        return SAMPLE
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.storage.PROOF_FIELDS, True))
        proof[field] = False
        return [ROW]
    report = probe.inspect(run, reader, clinic_day=DAY, now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and calls == [True]


@pytest.mark.parametrize("position,value", [(0, 0), (0, 2), (1, 0), (1, 2), (2, 1), (3, 1), (4, 2), (5, 2), (6, 2),
    (7, "double precision"), (8, "real"), (9, "PRIVATE_MARKER"), (9, None)])
def test_ambiguous_missing_invalid_or_inexact_types_rejected(position, value):
    row = list(ROW)
    row[position] = value
    with pytest.raises(probe.storage.StorageRejected):
        probe.validate_result([row])


@pytest.mark.parametrize("data", [[], None, [ROW, ROW], [ROW[:9]], [(True, *ROW[1:])]])
def test_partial_or_malformed_result_never_empty(data):
    with pytest.raises(probe.storage.StorageRejected):
        probe.validate_result(data)


@pytest.mark.parametrize("position", [4, 5, 6])
def test_numeric_mismatch_is_not_mapping_evidence(database, position):
    row = list(ROW)
    row[position] = 0
    database.rows = [row]
    assert inspect()["status"] == "numeric_mapping_not_matched"


def test_query_hash_guard_and_no_runtime_import(database, monkeypatch):
    sql = probe.QUERY
    assert hashlib.sha256(sql.encode()).hexdigest() == probe.QUERY_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"public\.([a-z0-9_]+)", sql)) == {"h1opdin", "h2opd_doct_ord"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == {"day", "chart_no", "code", "name", "daily", "frequency", "days"}
    assert sql.count("LIMIT 2") == 3
    for forbidden in ("hold_opd", "ptnt_nm", "medfee_nm", "birth", "insurance", "notes", "price", "SELECT *", "LIKE", "array_agg", "json_agg", "string_agg"):
        assert forbidden not in sql
    for path in (Path(__file__).parents[1] / "KaosEghis").rglob("*.py"):
        assert "source_order_grid_numeric" not in path.read_text(encoding="utf-8-sig")
    monkeypatch.setattr(probe, "QUERY", sql + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("scenario", ["match", "no_visit", "multiple_visits", "no_order", "multiple_orders", "wrong_code", "wrong_name", "off_day", "null_qty", "wrong_qty", "null_key"])
def test_actual_select_relational_guards_with_synthetic_sqlite(scenario):
    # Only PostgreSQL syntax/type introspection is adapted; values are synthetic.
    sql = re.sub(r"%\((\w+)\)s", r":\1", probe.QUERY)
    sql = sql.replace("public.", "").replace("::text", "")
    sql = sql.replace("to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD')", ":day")
    sql = sql.replace("IS DISTINCT FROM", "IS NOT")
    with closing(sqlite3.connect(":memory:")) as db:
        db.create_function("btrim", 1, lambda s: str(s).strip() if s is not None else None)
        db.create_function("pg_typeof", 1, lambda _: "numeric")
        db.execute("CREATE TABLE h1opdin (clinic_ymd,ptnt_no,recept_no)")
        db.execute("CREATE TABLE h2opd_doct_ord (recept_no,ord_ymd,ord_no,ord_seq_no,user_cd,user_nm,qty,divide,days)")
        visits = [("20261007", SAMPLE.chart_no, "SYNTHETIC-VISIT")]
        order = ["SYNTHETIC-VISIT", "20261007", "1", "1", SAMPLE.code, SAMPLE.name, 4.25, 2, 7]
        if scenario == "no_visit":
            visits = []
        if scenario == "multiple_visits":
            visits *= 2
        if scenario == "wrong_code":
            order[4] = "SYNTHETIC-OTHER"
        if scenario == "wrong_name":
            order[5] = "SYNTHETIC-OTHER"
        if scenario == "off_day":
            order[1] = "20261006"
        if scenario == "null_qty":
            order[6] = None
        if scenario == "wrong_qty":
            order[6] = 3
        if scenario == "null_key":
            order[3] = None
        orders = [] if scenario == "no_order" else [order]
        if scenario == "multiple_orders":
            orders *= 2
        db.executemany("INSERT INTO h1opdin VALUES (?,?,?)", visits)
        db.executemany("INSERT INTO h2opd_doct_ord VALUES (?,?,?,?,?,?,?,?,?)", orders)
        rows = db.execute(sql, {"day": "20261007", "chart_no": SAMPLE.chart_no, "code": SAMPLE.code,
                              "name": SAMPLE.name, "daily": 4.25, "frequency": 2, "days": 7}).fetchall()
    if scenario in {"match", "null_qty", "wrong_qty"}:
        assert probe.validate_result(rows)["daily_equals_qty"] == (scenario == "match")
    else:
        with pytest.raises(probe.storage.StorageRejected):
            probe.validate_result(rows)
