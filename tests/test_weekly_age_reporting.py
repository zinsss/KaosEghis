import builtins
import sys

from KaosEghis.core.weekly_age_reporting import (
    WeeklyAgeReportingUnavailableError,
    build_weekly_age_report_query,
    expand_week_range,
    fetch_weekly_age_report,
    iso_week_range,
)


def test_iso_week_range_returns_monday_to_sunday() -> None:
    assert iso_week_range(2026, 1) == ("20251229", "20260104")


def test_iso_week_range_rejects_invalid_week() -> None:
    try:
        iso_week_range(2026, 54)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError")

    assert message == "Invalid ISO week: 2026-W54"


def test_expand_week_range_rejects_reverse_range() -> None:
    try:
        expand_week_range(2026, 10, 9)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError")

    assert message == "End week must be greater than or equal to start week."


def test_build_weekly_age_report_query_contains_expected_tables() -> None:
    query = build_weekly_age_report_query("20260101", "20260107")

    assert "public.h1opdin" in query
    assert "public.hz_mst_ptnt" in query
    assert "COUNT(DISTINCT ptnt_no)::int AS patient_count" in query
    assert "clinic_ymd BETWEEN '20260101' AND '20260107'" in query


def test_fetch_weekly_age_report_returns_rows(monkeypatch) -> None:
    from KaosEghis.core import weekly_age_reporting

    executed_queries: list[str] = []

    class FakeCursor:
        description = [("age_group",), ("visit_count",), ("patient_count",)]

        def execute(self, query: str) -> None:
            executed_queries.append(query)

        def fetchall(self) -> list[tuple[str, int, int]]:
            return [("19-49", 12, 8), ("65 over", 4, 3)]

        def close(self) -> None:
            return None

    class FakeConnection:
        def __init__(self) -> None:
            self.readonly = None
            self.autocommit = None

        def set_session(self, readonly: bool, autocommit: bool) -> None:
            self.readonly = readonly
            self.autocommit = autocommit

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    class FakePsycopg2Module:
        def connect(self, connection_string: str):
            self.connection_string = connection_string
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2Module())

    rows = weekly_age_reporting.fetch_weekly_age_report(
        {"eghis_db_connection_string": "postgresql://example"},
        year=2026,
        start_week=5,
        end_week=5,
    )

    assert [(row.age_group, row.visit_count, row.patient_count) for row in rows] == [
        ("19-49", 12, 8),
        ("65 over", 4, 3),
    ]
    assert "public.h1opdin" in executed_queries[0]


def test_fetch_weekly_age_report_uses_configured_query_template(monkeypatch) -> None:
    from KaosEghis.core import weekly_age_reporting

    executed_queries: list[str] = []

    class FakeCursor:
        description = [("age_group",), ("visit_count",), ("patient_count",)]

        def execute(self, query: str) -> None:
            executed_queries.append(query)

        def fetchall(self) -> list[tuple[str, int, int]]:
            return [("~0", 1, 1)]

        def close(self) -> None:
            return None

    class FakeConnection:
        def set_session(self, readonly: bool, autocommit: bool) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    class FakePsycopg2Module:
        def connect(self, connection_string: str):
            self.connection_string = connection_string
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2Module())

    rows = weekly_age_reporting.fetch_weekly_age_report(
        {
            "eghis_db_connection_string": "postgresql://example",
            "eghis_db_weekly_age_report_query": (
                "SELECT '{start_ymd}' AS age_group, {start_week} AS visit_count, "
                "{end_week} AS patient_count"
            ),
        },
        year=2026,
        start_week=5,
        end_week=5,
    )

    assert rows[0].age_group == "~0"
    assert "public.h1opdin" not in executed_queries[0]
    assert "20260126" in executed_queries[0]
    assert "5 AS visit_count" in executed_queries[0]


def test_fetch_weekly_age_report_returns_empty_without_connection_string() -> None:
    assert fetch_weekly_age_report({}, year=2026, start_week=5) == []


def test_fetch_weekly_age_report_raises_when_psycopg2_missing(monkeypatch) -> None:
    original_import = builtins.__import__
    monkeypatch.delitem(sys.modules, "psycopg2", raising=False)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "psycopg2":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        fetch_weekly_age_report(
            {"eghis_db_connection_string": "postgresql://example"},
            year=2026,
            start_week=5,
        )
    except WeeklyAgeReportingUnavailableError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected WeeklyAgeReportingUnavailableError")

    assert "psycopg2" in message
