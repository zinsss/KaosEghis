import builtins
import sys

import pytest

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
        def connect(self, connection_string: str, **options):
            self.connection_string = connection_string
            self.options = options
            return FakeConnection()

    fake_psycopg2 = FakePsycopg2Module()
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)

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
    assert executed_queries[0] == "SET statement_timeout = 3000"
    assert "public.h1opdin" in executed_queries[1]
    assert fake_psycopg2.options == {"connect_timeout": 5, "application_name": "KaosEghis-Flu"}


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
        def connect(self, connection_string: str, **options):
            self.connection_string = connection_string
            self.options = options
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
    assert executed_queries[0] == "SET statement_timeout = 3000"
    assert "public.h1opdin" not in executed_queries[1]
    assert "20260126" in executed_queries[1]
    assert "5 AS visit_count" in executed_queries[1]


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


def test_run_readonly_query_closes_cursor_and_connection_on_error(monkeypatch) -> None:
    import sys

    from KaosEghis.core.eghis_db import run_readonly_query

    events: list[str] = []

    class FakeCursor:
        description = [("age_group",), ("visit_count",), ("patient_count",)]

        def execute(self, query: str) -> None:
            events.append("execute")
            raise RuntimeError("boom")

        def close(self) -> None:
            events.append("cursor_close")

    class FakeConnection:
        autocommit = False

        def set_session(self, readonly: bool, autocommit: bool) -> None:
            events.append(f"set_session:{readonly}:{autocommit}")

        def cursor(self) -> FakeCursor:
            events.append("cursor")
            return FakeCursor()

        def close(self) -> None:
            events.append("connection_close")

    class FakePsycopg2Module:
        def connect(self, connection_string: str):
            events.append("connect")
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2Module())

    try:
        run_readonly_query("postgresql://example", "SELECT 1")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected RuntimeError")

    assert events == [
        "connect",
        "set_session:True:True",
        "cursor",
        "execute",
        "cursor_close",
        "connection_close",
    ]


@pytest.mark.parametrize("failure", [None, "readonly", "timeout_setup", "query", "fetch", "cursor_close"])
def test_bounded_query_closes_resources_and_records_stages(monkeypatch, failure):
    from types import SimpleNamespace
    from KaosEghis.core.eghis_db import EghisDbUnavailableError, run_readonly_query

    events = []
    timings = {}

    class FakeCursor:
        description = [("value",)]

        def execute(self, query):
            events.append(query)
            if failure == "timeout_setup" and query.startswith("SET"):
                raise RuntimeError("timeout setup failed")
            if failure == "query" and query == "SELECT 1":
                raise RuntimeError("query failed")

        def fetchall(self):
            if failure == "fetch":
                raise RuntimeError("fetch failed")
            return [(1,)]

        def close(self):
            events.append("cursor_close")
            if failure == "cursor_close":
                raise RuntimeError("cursor close failed")

    class FakeConnection:
        def set_session(self, **options):
            assert options == {"readonly": True, "autocommit": True}
            if failure == "readonly":
                raise RuntimeError("readonly failed")

        def cursor(self):
            return FakeCursor()

        def close(self):
            events.append("connection_close")

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection()))

    def run():
        return run_readonly_query(
            "postgresql://example", "SELECT 1", statement_timeout_seconds=0.125,
            timings=timings,
        )

    if failure is None:
        assert run() == (["value"], [(1,)])
    else:
        with pytest.raises(EghisDbUnavailableError if failure == "readonly" else RuntimeError):
            run()
    assert events[-1] == "connection_close"
    assert "connection_closed" in timings
    assert list(timings.values()) == sorted(timings.values())
    if failure == "readonly":
        assert events == ["connection_close"]
    else:
        assert events[0] == "SET statement_timeout = 125"
        assert "cursor_close" in events
    if failure in {"readonly", "timeout_setup"}:
        assert "SELECT 1" not in events
    if failure in {"readonly", "timeout_setup", "query"}:
        assert "query_finished" not in timings


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 2147484])
def test_statement_timeout_cannot_disable_limit_or_overflow(monkeypatch, timeout):
    from types import SimpleNamespace
    from KaosEghis.core.eghis_db import run_readonly_query

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(
        connect=lambda *_args, **_kwargs: pytest.fail("must validate before connecting"),
    ))
    with pytest.raises(ValueError):
        run_readonly_query("postgresql://example", "SELECT 1", statement_timeout_seconds=timeout)


def test_weekly_report_timeout_is_recognized_without_automatic_retry(monkeypatch):
    from KaosEghis.core import weekly_age_reporting as module

    class TimedOut(Exception):
        pgcode = "57014"

    calls = []
    stages = {}

    def run(_connection, _query, **kwargs):
        calls.append(kwargs)
        raise TimedOut("sensitive SQL/connection details")

    monkeypatch.setattr(module, "run_readonly_query", run)
    with pytest.raises(module.WeeklyAgeReportingTimeoutError) as error:
        module.fetch_weekly_age_report(
            {"eghis_db_connection_string": "postgresql://example"},
            year=2026, start_week=38, timings=stages,
        )
    assert len(calls) == 1
    assert calls[0]["statement_timeout_seconds"] == 3
    assert calls[0]["timings"] is stages
    assert "3-second DB limit" in str(error.value)
    assert "sensitive" not in str(error.value)
