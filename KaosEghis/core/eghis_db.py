"""Shared read-only Eghis PostgreSQL query helpers."""

from __future__ import annotations

import math
import re
from time import perf_counter

_WRITE_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|EXEC|CALL)\b",
    re.IGNORECASE,
)


class EghisDbUnavailableError(RuntimeError):
    """Raised when the optional PostgreSQL adapter is unavailable."""


class EghisDbQueryRejectedError(RuntimeError):
    """Raised when a configured SQL statement fails the read-only safety gate."""


def run_readonly_query(
    connection_string: str,
    query: str,
    *,
    connect_timeout_seconds: float | None = None,
    statement_timeout_seconds: float | None = None,
    application_name: str | None = None,
    timings: dict[str, float] | None = None,
) -> tuple[list[str], list[tuple | list | object]]:
    started = perf_counter()

    def record_stage(name: str) -> None:
        if timings is not None:
            timings[name] = round(perf_counter() - started, 4)

    if _WRITE_SQL_PATTERN.search(query):
        raise EghisDbQueryRejectedError(
            "Configured SQL was rejected by the read-only safety gate."
        )

    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise EghisDbUnavailableError("psycopg2 is not installed.") from exc

    connection_options = {}
    statement_timeout_ms = None
    if statement_timeout_seconds is not None:
        value = float(statement_timeout_seconds)
        if not math.isfinite(value) or value <= 0 or value > 2147483:
            raise ValueError("Statement timeout must be a positive, finite number of seconds.")
        statement_timeout_ms = math.ceil(value * 1000)
    if connect_timeout_seconds is not None:
        connection_options["connect_timeout"] = max(
            1, math.ceil(float(connect_timeout_seconds))
        )
    if application_name is not None:
        connection_options["application_name"] = application_name
    connection = psycopg2.connect(connection_string, **connection_options)
    try:
        record_stage("connected")
        try:
            connection.set_session(readonly=True, autocommit=True)
        except Exception as exc:
            raise EghisDbUnavailableError("Read-only database session could not be established.") from exc
        record_stage("session_ready")
        cursor = connection.cursor()
        try:
            if statement_timeout_ms is not None:
                # Session-local and compatible with the clinic's PostgreSQL 9.2.
                cursor.execute(f"SET statement_timeout = {statement_timeout_ms}")
                record_stage("timeout_set")
            cursor.execute(query)
            record_stage("query_finished")
            column_names = [column[0] for column in cursor.description or []]
            rows = cursor.fetchall()
            record_stage("rows_fetched")
        finally:
            close_cursor = getattr(cursor, "close", None)
            if callable(close_cursor):
                close_cursor()
                record_stage("cursor_closed")
    finally:
        close_connection = getattr(connection, "close", None)
        if callable(close_connection):
            close_connection()
            record_stage("connection_closed")

    return column_names, rows
