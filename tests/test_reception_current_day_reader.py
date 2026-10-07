import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from KaosEghis.core import reception_current_day_reader as reader


NOW = datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)
DAY = "20261007"


class SyntheticQueryRunner:
    def __init__(self, observed_at=NOW - timedelta(seconds=5)):
        self.observed_at = observed_at
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("ATTACH DATABASE ':memory:' AS public")
        self.connection.execute(
            "CREATE TABLE public.h1opdin "
            "(clinic_ymd TEXT, recept_no TEXT, ptnt_no TEXT, proc_gb TEXT)"
        )
        self.connection.execute(
            "CREATE TABLE public.hz_mst_ptnt (ptnt_no TEXT, ptnt_nm TEXT)"
        )
        self.connection.create_function(
            "statement_timestamp", 0, lambda: self.observed_at.isoformat()
        )
        self.connection.create_function("timezone", 2, self._timezone)
        self.connection.create_function("to_char", 2, self._to_char)
        self.connection.create_function("char_length", 1, self._char_length)
        self.connection.create_function("octet_length", 1, self._octet_length)
        self.calls = []

    @staticmethod
    def _timezone(zone, value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo(zone)).isoformat()

    @staticmethod
    def _to_char(value, pattern):
        assert pattern == "YYYYMMDD"
        return datetime.fromisoformat(value).strftime("%Y%m%d")

    @staticmethod
    def _char_length(value):
        return None if value is None else len(value)

    @staticmethod
    def _octet_length(value):
        return None if value is None else len(value.encode("utf-8"))

    def patient(self, key, name="Synthetic Patient"):
        self.connection.execute(
            "INSERT INTO public.hz_mst_ptnt VALUES (?, ?)", (key, name)
        )

    def encounter(self, key, patient_key=None, code="30", day=DAY):
        self.connection.execute(
            "INSERT INTO public.h1opdin VALUES (?, ?, ?, ?)",
            (day, key, patient_key or key, code),
        )

    def __call__(self, query, **kwargs):
        self.calls.append((query, kwargs))
        assert kwargs["connect_timeout_seconds"] == 3.0
        assert kwargs["statement_timeout_seconds"] == 2.0
        assert kwargs["application_name"] == "KaosEghis-reception-current-day"
        converted = re.sub(r"%\(([a-z_]+)\)s", r":\1", query)
        cursor = self.connection.execute(converted, kwargs["params"])
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
        kwargs["timings"].update({
            "connected": 0.01,
            "session_ready": 0.02,
            "timeout_set": 0.03,
            "query_finished": 0.04,
            "rows_fetched": 0.05,
            "cursor_closed": 0.06,
            "connection_closed": 0.07,
        })
        return columns, rows


@pytest.fixture
def database():
    source = SyntheticQueryRunner()
    try:
        yield source
    finally:
        source.connection.close()


def provider(database, **changes):
    return reader.BoundedReceptionDayProvider(database, **changes)


def test_literal_contract_query_and_bounds_are_not_self_derived(database):
    assert reader.PROVIDER_ID == "kaoseghis-reception-day-v1"
    assert reader.PROJECTION_ID == "reception-current-day-patients-v1"
    assert reader.MAPPING_REVISION == "eghis-proc-gb-2026-10-07"
    assert reader.MAX_ROWS == 10_000
    assert reader.ROW_SENTINEL == 10_001
    assert reader.MAX_RESULT_BYTES == 16_777_216
    assert reader.CONNECT_TIMEOUT_SECONDS == 3.0
    assert reader.STATEMENT_TIMEOUT_SECONDS == 2.0
    assert "WHERE h.clinic_ymd = %(clinic_day)s" in reader.QUERY
    assert "h.proc_gb IN ('30', '40')" in reader.QUERY
    assert (
        "SELECT DISTINCT clinic_ymd, selection_id, patient_key, source_status_code"
        in reader.QUERY
    )
    assert reader.QUERY.index("SELECT DISTINCT") < reader.QUERY.index(
        "LIMIT %(row_sentinel)s"
    )
    assert "LEFT JOIN public.hz_mst_ptnt" in reader.QUERY
    assert reader.QUERY.count("statement_timestamp()") == 2
    assert reader.QUERY.count(";") == 0
    assert not re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", reader.QUERY
    )


def test_complete_day_includes_only_30_40_and_orders_deterministically(database):
    for key, name, code in (
        ("synthetic-40", "Zulu", "40"),
        ("synthetic-30", "Alpha", "30"),
        ("synthetic-10", "Waiting", "10"),
        ("synthetic-25", "Hold", "25"),
        ("synthetic-50", "Cancelled", "50"),
        ("synthetic-null", "Null", None),
        ("synthetic-blank", "Blank", ""),
        ("synthetic-new", "Unknown", "UNREVIEWED"),
    ):
        database.patient(key, name)
        database.encounter(key, code=code)
    result = provider(database).read_current_day(NOW)
    assert [(item.selection_id, item.display_name, item.state.value) for item in result.patients] == [
        ("synthetic-30", "Alpha", "CONSULTATION_COMPLETED"),
        ("synthetic-40", "Zulu", "PAYMENT_COMPLETED"),
    ]
    assert result.source_id == "kaoseghis-reception-day-v1"
    assert result.projection_id == "reception-current-day-patients-v1"


def test_verified_empty_is_a_complete_authoritative_result(database):
    result = provider(database).read_current_day(NOW)
    assert result.patients == () and result.clinic_day.isoformat() == "2026-10-07"


def test_query_is_parameterized_and_day_value_never_enters_sql(database):
    provider(database).read_current_day(NOW)
    query, kwargs = database.calls[0]
    assert query == reader.QUERY
    assert kwargs["params"]["clinic_day"] == "20261007"
    assert "20261007" not in query
    assert set(kwargs["params"]) == {
        "clinic_day", "row_sentinel", "max_rows", "text_limit", "max_result_bytes"
    }
    assert len(database.calls) == 1


@pytest.mark.parametrize("kind", ["missing", "duplicate"])
def test_patient_master_join_must_match_exactly_once(database, kind):
    database.encounter("synthetic-1")
    if kind == "duplicate":
        database.patient("synthetic-1", "Synthetic One")
        database.patient("synthetic-1", "Synthetic Duplicate")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


def test_duplicate_encounter_identity_rejects_whole_day(database):
    database.patient("synthetic-1")
    database.encounter("synthetic-1", code="30")
    database.encounter("synthetic-1", code="40")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


def test_exact_duplicate_fact_collapses_before_logical_row_sentinel(
    database, monkeypatch
):
    monkeypatch.setattr(reader, "MAX_ROWS", 1)
    monkeypatch.setattr(reader, "ROW_SENTINEL", 2)
    database.patient("synthetic-1")
    database.encounter("synthetic-1", code="30")
    database.encounter("synthetic-1", code="30")
    result = provider(database).read_current_day(NOW)
    assert [(item.selection_id, item.state.value) for item in result.patients] == [
        ("synthetic-1", "CONSULTATION_COMPLETED")
    ]


def test_same_selection_id_with_different_patient_fact_rejects_whole_day(database):
    database.patient("synthetic-a")
    database.patient("synthetic-b")
    database.encounter("synthetic-1", patient_key="synthetic-a", code="30")
    database.encounter("synthetic-1", patient_key="synthetic-b", code="30")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


@pytest.mark.parametrize("identity", [None, "", " padded ", "S" * 129])
def test_invalid_encounter_identity_rejects_whole_day(database, identity):
    database.patient("synthetic-patient")
    database.encounter(identity, patient_key="synthetic-patient")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


@pytest.mark.parametrize("name", [None, "", " padded ", "S" * 129])
def test_invalid_display_name_rejects_whole_day(database, name):
    database.patient("synthetic-1", name)
    database.encounter("synthetic-1")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


def test_row_and_byte_sentinels_fail_closed(database, monkeypatch):
    monkeypatch.setattr(reader, "MAX_ROWS", 1)
    monkeypatch.setattr(reader, "ROW_SENTINEL", 2)
    for key in ("synthetic-1", "synthetic-2"):
        database.patient(key)
        database.encounter(key)
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)

    database.connection.execute("DELETE FROM public.h1opdin")
    database.connection.execute("DELETE FROM public.hz_mst_ptnt")
    monkeypatch.setattr(reader, "MAX_ROWS", 10_000)
    monkeypatch.setattr(reader, "ROW_SENTINEL", 10_001)
    monkeypatch.setattr(reader, "MAX_RESULT_BYTES", 1)
    database.patient("synthetic-1")
    database.encounter("synthetic-1")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW)


def test_clinic_day_and_freshness_are_fail_closed(database):
    database.patient("synthetic-1")
    database.encounter("synthetic-1")
    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_scope_unverified$"):
        provider(database).read_current_day(NOW + timedelta(days=1))

    database.observed_at = NOW - timedelta(seconds=301)
    with pytest.raises(reader.ReceptionDayReadRejected, match="^stale_read$"):
        provider(database).read_current_day(NOW)


@pytest.mark.parametrize("limit", [timedelta(0), timedelta(seconds=-1), timedelta(seconds=301)])
def test_freshness_limit_cannot_exceed_contract(limit, database):
    with pytest.raises(reader.ReceptionDayReadRejected, match="^invalid_freshness$"):
        provider(database, freshness_limit=limit)


def test_cleanup_and_time_proof_is_mandatory(database):
    original = database.__call__

    def missing_cleanup(*args, **kwargs):
        columns, rows = original(*args, **kwargs)
        kwargs["timings"].pop("connection_closed")
        return columns, rows

    with pytest.raises(reader.ReceptionDayReadRejected, match="^cleanup_unverified$"):
        reader.BoundedReceptionDayProvider(missing_cleanup).read_current_day(NOW)

    def slow_cleanup(*args, **kwargs):
        columns, rows = original(*args, **kwargs)
        kwargs["timings"]["connection_closed"] = 6.01
        return columns, rows

    with pytest.raises(reader.ReceptionDayReadRejected, match="^cleanup_unverified$"):
        reader.BoundedReceptionDayProvider(slow_cleanup).read_current_day(NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_clinic_day", "19990101"),
        ("selection_id", "synthetic-meta"),
        ("display_name", "Synthetic Meta"),
        ("source_status_code", "30"),
    ],
)
def test_meta_row_is_closed_and_bound_to_current_clinic_day(database, field, value):
    original = database.__call__

    def tampered(*args, **kwargs):
        columns, rows = original(*args, **kwargs)
        changed = [list(row) for row in rows]
        changed[0][columns.index(field)] = value
        return columns, [tuple(row) for row in changed]

    with pytest.raises(reader.ReceptionDayReadRejected, match="^invalid_result$"):
        reader.BoundedReceptionDayProvider(tampered).read_current_day(NOW)


def test_runner_failure_is_sanitized_without_patient_or_provider_text():
    def failed(*_args, **_kwargs):
        raise RuntimeError("PRIVATE PATIENT PROVIDER MESSAGE")

    with pytest.raises(reader.ReceptionDayReadRejected, match="^source_unavailable$") as error:
        reader.BoundedReceptionDayProvider(failed).read_current_day(NOW)
    assert "PRIVATE" not in repr(error.value)


def test_adapter_has_no_credential_runtime_wire_or_persistence_surface():
    tree = ast.parse(Path(reader.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not imports.intersection(
        {"sqlite3", "requests", "httpx", "json", "logging", "pathlib"}
    )
    assert not names.intersection(
        {"eghis_db_connection_string", "run_readonly_query", "settings", "token", "endpoint"}
    )
    assert repr(reader.BoundedReceptionDayProvider(lambda *_a, **_k: None)) == (
        "<BoundedReceptionDayProvider: redacted>"
    )
