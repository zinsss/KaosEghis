"""Shared read-only Eghis PostgreSQL query helpers."""

from __future__ import annotations

import re

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
) -> tuple[list[str], list[tuple | list | object]]:
    if _WRITE_SQL_PATTERN.search(query):
        raise EghisDbQueryRejectedError(
            "Configured SQL was rejected by the read-only safety gate."
        )

    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise EghisDbUnavailableError("psycopg2 is not installed.") from exc

    connection = psycopg2.connect(connection_string)
    try:
        try:
            connection.set_session(readonly=True, autocommit=True)
        except Exception:
            connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            column_names = [column[0] for column in cursor.description or []]
            rows = cursor.fetchall()
        finally:
            close_cursor = getattr(cursor, "close", None)
            if callable(close_cursor):
                close_cursor()
    finally:
        close_connection = getattr(connection, "close", None)
        if callable(close_connection):
            close_connection()

    return column_names, rows
