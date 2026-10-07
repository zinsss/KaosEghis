"""Exercise candidate relational logic in synthetic in-memory SQLite only.

This does not establish PostgreSQL plan/type behavior or EMR source authority.
Only DB-API parameter syntax and PostgreSQL clock/string functions are adapted.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus


SQL_PATH = Path(__file__).parent / "fixtures" / "source_current_day_orders_candidate_v1.sql"
SQL = SQL_PATH.read_text(encoding="utf-8")
DAY = "20261007"
ALLOWED_COLUMNS = {
    "h1opdin": {"clinic_ymd", "recept_no", "proc_gb", "hold_yn"},
    "h2opd_doct_ord": {"recept_no", "ord_ymd", "ord_no", "ord_seq_no", "ord_cd",
                       "medfee_nm", "user_cd", "user_nm", "qty", "divide", "days",
                       "ord_type", "proc_dept_cd", "dc_yn", "act_yn"},
}
SOURCE_COLUMNS = ("source_clinic_day", "source_encounter_id", "source_reception_code", "hold_yn",
                  "source_order_encounter_id", "source_order_date", "source_order_number",
                  "source_order_sequence", "catalog_code", "catalog_name", "user_code", "user_name",
                  "source_qty", "source_divide", "source_days", "order_type", "department_code", "dc_yn", "act_yn")


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ':memory:' AS public")
    connection.execute("CREATE TABLE public.h1opdin (clinic_ymd TEXT, recept_no INTEGER, proc_gb TEXT, hold_yn TEXT)")
    connection.execute("""CREATE TABLE public.h2opd_doct_ord (
        recept_no INTEGER, ord_ymd TEXT, ord_no INTEGER, ord_seq_no INTEGER,
        ord_cd TEXT, medfee_nm TEXT, user_cd TEXT, user_nm TEXT,
        qty TEXT, divide TEXT, days TEXT, ord_type TEXT,
        proc_dept_cd TEXT, dc_yn TEXT, act_yn TEXT)""")
    connection.execute("CREATE INDEX public.test_child_link ON h2opd_doct_ord (recept_no)")
    connection.create_function("statement_timestamp", 0, lambda: "2026-10-07T09:00:00+00:00")
    connection.create_function("timezone", 2, lambda zone, value:
                               datetime.fromisoformat(value).astimezone(ZoneInfo(zone)).isoformat())
    connection.create_function("to_char", 2, lambda value, fmt:
                               datetime.fromisoformat(value).strftime("%Y%m%d") if fmt == "YYYYMMDD" else None)
    connection.create_function("char_length", 1, lambda value: None if value is None else len(value))
    try:
        yield connection
    finally:
        connection.close()


def parent(db, key=1, *, day=DAY, code="40", hold="N"):
    db.execute("INSERT INTO public.h1opdin VALUES (?, ?, ?, ?)", (day, key, code, hold))


def child(db, key=1, *, day=DAY, number=1, sequence=1, **changes):
    values = dict(catalog_code="SYNTHETIC-CATALOG", catalog_name="Synthetic catalog",
                  user_code="SYNTHETIC-USER", user_name="Synthetic order",
                  source_qty="1.25", source_divide="3", source_days="7", order_type="03",
                  department_code="LAB", dc_yn="N", act_yn="N")
    values.update(changes)
    db.execute("INSERT INTO public.h2opd_doct_ord VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (key, day, number, sequence, *values.values()))


def query(db, *, day=DAY, encounter_cap=10000, order_cap=100000):
    converted = re.sub(r"%\(([a-z_]+)\)s", r":\1", SQL)
    db.execute("PRAGMA query_only = ON")
    try:
        rows = db.execute(converted, dict(day=day, encounter_cap=encounter_cap, order_cap=order_cap)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.execute("PRAGMA query_only = OFF")


def rejected(rows, reason):
    assert len(rows) == 1
    assert rows[0]["row_kind"] == "META" and rows[0]["extraction_status"] == reason
    assert rows[0]["expected_result_rows"] == 1 and not rows[0]["order_present"]
    assert all(rows[0][key] is None for key in SOURCE_COLUMNS)


def test_no_order_parent_and_every_linked_child_retained(database):
    parent(database, 1)
    parent(database, 2, code="10")
    child(database, 1)
    child(database, 1, sequence=2, dc_yn="Y", order_type="FEE", department_code=None)
    child(database, 1, sequence=3, order_type="UNCLASSIFIED", department_code="")
    rows = query(database)
    assert len(rows) == 4 and all(row["expected_result_rows"] == 4 for row in rows)
    assert {row["source_encounter_id"] for row in rows} == {1, 2}
    assert sum(row["order_present"] for row in rows) == 3
    assert rows[-1]["source_encounter_id"] == 2 and rows[-1]["catalog_code"] is None
    assert rows[1]["dc_yn"] == "Y" and rows[2]["order_type"] == "UNCLASSIFIED"


@pytest.mark.parametrize("code", ["10", "20", "25", "30", "40", "50", "UNREVIEWED", "", None])
def test_reception_codes_preserved_not_mapped_or_filtered(database, code):
    parent(database, code=code)
    row = query(database)[0]
    assert row["source_reception_code"] == code and row["extraction_status"] == "candidate_rows"
    assert "state" not in row


@pytest.mark.parametrize("field", ["catalog_code", "catalog_name", "user_code", "user_name",
                                   "order_type", "department_code"])
@pytest.mark.parametrize("value", [None, "", " ", "  Synthetic  ", "e\u0301", "\u00e9", "\uac00"])
def test_exact_null_empty_space_and_unicode_text_preserved(database, field, value):
    parent(database)
    child(database, **{field: value})
    assert query(database)[0][field] == value


@pytest.mark.parametrize("field", ["source_qty", "source_divide", "source_days"])
@pytest.mark.parametrize("value", [None, "", "0", "0.125", "1.00", "3", "7", "28", "-1"])
def test_numeric_candidates_not_coerced_multiplied_defaulted_or_assigned_units(database, field, value):
    # TEXT in this synthetic database tests preservation, not PostgreSQL NUMERIC adaptation.
    parent(database)
    child(database, **{field: value})
    row = query(database)[0]
    assert row[field] == value
    assert not {"quantity", "frequency", "daily_dose", "total_dose", "units"}.intersection(row)


def test_requested_name_and_three_numeric_candidates_are_independent(database):
    parent(database)
    child(database, catalog_name=None, user_name="Synthetic prescription",
          source_qty="0.5", source_divide="3", source_days="5")
    row = query(database)[0]
    assert (row["user_name"], row["source_qty"], row["source_divide"], row["source_days"]) == (
        "Synthetic prescription", "0.5", "3", "5")
    assert row["catalog_name"] is None


@pytest.mark.parametrize("dc,act,hold", [(d, a, h) for d in ("Y", "N") for a in ("Y", "N") for h in ("Y", "N")])
def test_flags_preserved_without_clinical_meaning(database, dc, act, hold):
    parent(database, hold=hold)
    child(database, dc_yn=dc, act_yn=act)
    row = query(database)[0]
    assert (row["dc_yn"], row["act_yn"], row["hold_yn"]) == (dc, act, hold)
    assert "state" not in row


@pytest.mark.parametrize("field", ["dc_yn", "act_yn", "hold_yn"])
@pytest.mark.parametrize("value", [None, "", "y", " N", "UNKNOWN"])
def test_unreviewed_flags_reject_whole_result(database, field, value):
    parent(database, hold=value if field == "hold_yn" else "N")
    child(database, **({field: value} if field != "hold_yn" else {}))
    rejected(query(database), "invalid_retained_flag")


@pytest.mark.parametrize("field,cap", [("catalog_code", 128), ("catalog_name", 256), ("user_code", 128),
                                      ("user_name", 256), ("order_type", 128), ("department_code", 128)])
def test_text_cap_exact_and_overflow_without_truncation(database, field, cap):
    parent(database)
    child(database, **{field: "\uac00" * cap})
    assert query(database)[0][field] == "\uac00" * cap
    child(database, sequence=2, **{field: "\uac00" * (cap + 1)})
    rejected(query(database), "field_overflow")


def test_caps_allow_exact_total_and_reject_sentinel(database):
    parent(database, 1)
    child(database, 1)
    assert query(database, encounter_cap=1, order_cap=1)[0]["extraction_status"] == "candidate_rows"
    child(database, 1, sequence=2)
    rejected(query(database, order_cap=1), "order_overflow")
    parent(database, 2)
    rejected(query(database, encounter_cap=1), "encounter_overflow")


@pytest.mark.parametrize("limits", [{"encounter_cap": 0}, {"order_cap": 0},
                                    {"encounter_cap": 10001}, {"order_cap": 100001},
                                    {"encounter_cap": None}, {"order_cap": None}])
def test_invalid_limits_never_look_like_empty_success(database, limits):
    rejected(query(database, **limits), "invalid_limits")


@pytest.mark.parametrize("day", [None, "20261006", "20261008", "20261007' OR 1=1 --"])
def test_wrong_day_and_bound_input_do_not_return_source_data(database, day):
    parent(database)
    child(database)
    rejected(query(database, day=day), "wrong_day")


def test_zero_rows_return_metadata_not_verified_empty(database):
    row = query(database)[0]
    assert row["row_kind"] == "META" and row["extraction_status"] == "candidate_rows"
    assert row["encounter_count"] == row["order_count"] == 0
    assert row["expected_result_rows"] == 1 and not row["order_present"]
    assert "complete" not in row and "authoritative_snapshot" not in row


def test_only_today_parents_drive_scope(database):
    parent(database, 1)
    parent(database, 2, day="20261006")
    child(database, 1)
    child(database, 2)
    child(database, 3)
    rows = query(database)
    assert len(rows) == 1 and rows[0]["source_encounter_id"] == 1


def test_off_day_child_not_silently_dropped(database):
    parent(database)
    child(database)
    child(database, day="20261006", sequence=2)
    rejected(query(database), "off_day_child")


def test_duplicate_parent_and_four_part_order_keys_reject(database):
    parent(database)
    child(database)
    child(database)
    rejected(query(database), "duplicate_order_key")
    parent(database)
    rejected(query(database), "duplicate_encounter_key")


@pytest.mark.parametrize("component", ["number", "sequence", "day"])
def test_null_order_key_rejects(database, component):
    parent(database)
    child(database, **{component: None})
    rejected(query(database), "invalid_order_key")


def test_null_parent_key_rejects(database):
    parent(database, None)
    rejected(query(database), "invalid_encounter_key")


def test_full_key_order_and_content_edits(database):
    parent(database, 2)
    parent(database, 1)
    for key, number, sequence in [(2, 1, 1), (1, 2, 1), (1, 1, 2), (1, 1, 1)]:
        child(database, key, number=number, sequence=sequence)
    before = query(database)
    keys = [(r["source_order_encounter_id"], r["source_order_date"],
             r["source_order_number"], r["source_order_sequence"]) for r in before]
    assert keys == sorted(keys) and len(set(keys)) == 4
    database.execute("UPDATE public.h2opd_doct_ord SET user_nm = ?, dc_yn = ? WHERE recept_no = ?",
                     ("Synthetic edited", "Y", 1))
    after = query(database)
    assert after[0]["user_name"] == "Synthetic edited" and after[0]["dc_yn"] == "Y"
    database.execute("DELETE FROM public.h2opd_doct_ord WHERE recept_no = ?", (1,))
    absent = query(database)
    assert not absent[0]["order_present"] and absent[0]["source_encounter_id"] == 1
    child(database, 1, user_name="Synthetic reused or restored")
    assert query(database)[0]["user_name"] == "Synthetic reused or restored"


def test_source_column_access_allowlist_and_no_production_reader(database):
    parent(database)
    child(database)
    seen = set()
    def authorize(action, table, column, schema, context):
        if action == sqlite3.SQLITE_READ and table in ALLOWED_COLUMNS and column:
            assert column in ALLOWED_COLUMNS[table]
            seen.add((table, column))
        return sqlite3.SQLITE_OK
    database.set_authorizer(authorize)
    query(database)
    assert seen == {(table, column) for table, columns in ALLOWED_COLUMNS.items() for column in columns}
    assert EghisSourceDayReader().read_day(datetime(2026, 10, 7).date(),
                                         datetime(2026, 10, 7, tzinfo=timezone.utc)).status is ReadStatus.UNAVAILABLE


def test_statement_has_no_forbidden_fields_or_writes_and_exact_params():
    assert set(re.findall(r"%\(([a-z_]+)\)s", SQL)) == {"day", "encounter_cap", "order_cap"}
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|COPY|CALL|EXECUTE)\b", SQL, re.I)
    for forbidden in ("hold_opd", "ptnt_no", "hz_mst_ptnt", "dob", "phone", "address", "diagnosis",
                      "quantity", "frequency", "COALESCE", "regexp_replace"):
        assert forbidden.lower() not in SQL.lower()
    assert "SELECT *" not in SQL and "OFFSET" not in SQL
    assert "candidate_rows" in SQL and "CURRENT_DATE" not in SQL
    assert hashlib.sha256(SQL.encode("utf-8")).hexdigest() == "72dd31f8379606e4818988d4e1f6971d106c376b47a7cea2ca42932ca3bbe918"
