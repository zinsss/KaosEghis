"""Shared read-only Eghis PostgreSQL query helpers."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
import re
from time import perf_counter

from KaosEghis.core.emr_read_queue import EmrConnectionCloseError, run_serialized_read

_WRITE_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|EXEC|CALL)\b",
    re.IGNORECASE,
)


class EghisDbUnavailableError(RuntimeError):
    """Raised when the optional PostgreSQL adapter is unavailable."""


class EghisDbQueryRejectedError(RuntimeError):
    """Raised when a configured SQL statement fails the read-only safety gate."""


class EghisEvidenceRejectedError(RuntimeError):
    """Fixed diagnostic reason, without provider text or query values."""


def run_verified_evidence_query(connection_string, query, *, params, proof):
    """Explicit inspection only: trusted aggregate SQL, at most 257 result rows.

    No existing consumer uses this stricter entry point. The caller must reject
    the 257th sentinel row and may process aggregates only after this returns.
    """
    if _WRITE_SQL_PATTERN.search(query):
        raise EghisEvidenceRejectedError("query_rejected")
    params = deepcopy(params)
    return run_serialized_read(lambda: _verified_evidence_read(connection_string, query, params, proof))


def _verified_evidence_read(connection_string, query, params, proof):
    import psycopg2

    started = perf_counter()
    connection = cursor = None
    try:
        connection = psycopg2.connect(
            connection_string, connect_timeout=3,
            application_name="KaosEghis-source-evidence",
        )
        proof["connection_opened"] = True
        connection.set_session(readonly=True, autocommit=True,
                               isolation_level="READ COMMITTED")
        cursor = connection.cursor()
        cursor.execute("SET statement_timeout = 2000")
        cursor.execute("SELECT current_setting('transaction_read_only'), "
                       "current_setting('statement_timeout'), "
                       "current_setting('transaction_isolation')")
        # Session proof must be checked before executing the source statement.
        if cursor.fetchone() != ("on", "2s", "read committed"):
            raise EghisEvidenceRejectedError("session_unverified")
        proof["readonly_verified"] = True
        cursor.execute(query, params)
        rows = cursor.fetchmany(257)
    finally:
        try:
            if cursor is not None:
                cursor.close()
                if getattr(cursor, "closed", False) is not True:
                    raise EghisEvidenceRejectedError("cursor_close_unverified")
                proof["cursor_closed"] = True
        finally:
            if connection is not None:
                try:
                    connection.close()
                    closed = getattr(connection, "closed", 0)
                    if type(closed) is not int or closed <= 0:
                        raise RuntimeError()
                    proof["connection_closed"] = True
                except BaseException:
                    raise EmrConnectionCloseError("connection_close_unverified") from None
            proof["elapsed_seconds"] = round(perf_counter() - started, 4)
    return rows


def run_readonly_query(
    connection_string: str,
    query: str,
    *,
    params: tuple[object, ...] | list[object] | Mapping[str, object] | None = None,
    connect_timeout_seconds: float | None = 5.0,
    statement_timeout_seconds: float | None = 5.0,
    application_name: str | None = None,
    timings: dict[str, float] | None = None,
) -> tuple[list[str], list[tuple | list | object]]:
    """Run trusted SQL with optional bound values and return only after cleanup."""
    # Requests may wait in the FIFO while the caller edits its original values.
    if isinstance(params, Mapping):
        params = deepcopy(dict(params))
    elif isinstance(params, (tuple, list)):
        params = deepcopy(tuple(params))
    elif params is not None:
        raise TypeError("Query parameters must be a tuple, list, or mapping.")

    return run_serialized_read(lambda: _read_and_close(
        connection_string, query, params=params,
        connect_timeout_seconds=5.0 if connect_timeout_seconds is None else connect_timeout_seconds,
        statement_timeout_seconds=5.0 if statement_timeout_seconds is None else statement_timeout_seconds,
        application_name=application_name or "KaosEghis-emr", timings=timings,
    ))


def _read_and_close(
    connection_string, query, *, params, connect_timeout_seconds,
    statement_timeout_seconds, application_name, timings,
):
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
            if params is None:
                cursor.execute(query)
            else:
                cursor.execute(query, params)
            record_stage("query_finished")
            column_names = [column[0] for column in cursor.description or []]
            rows = cursor.fetchall()
            record_stage("rows_fetched")
        finally:
            cursor.close()
            record_stage("cursor_closed")
    finally:
        try:
            connection.close()
            if not getattr(connection, "closed", True):
                raise RuntimeError("Connection remains open after close.")
        except BaseException as exc:
            raise EmrConnectionCloseError(
                "EMR connection closure could not be confirmed. Further reads are blocked."
            ) from exc
        record_stage("connection_closed")

    return column_names, rows
