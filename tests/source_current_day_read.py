"""Explicit current-day read experiment; aggregate output, no runtime consumer."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import math
from pathlib import Path
from time import perf_counter, process_time
from zoneinfo import ZoneInfo

from KaosEghis.core.eghis_db import _WRITE_SQL_PATTERN
from KaosEghis.core.emr_read_queue import (
    EmrConnectionCloseError, EmrReadSafetyError, run_serialized_read,
)


QUERY = (Path(__file__).parent / "fixtures" / "source_current_day_orders_read_probe_v1.sql").read_text(encoding="utf-8")
QUERY_HASH = "82e942bfbdf68e751c0bbe86528b8130f5dab50f727506a7d97aab55f619702e"
ENCOUNTER_CAP = 1000
ORDER_CAP = 10000
RESULT_CAP = ENCOUNTER_CAP + ORDER_CAP
KST = ZoneInfo("Asia/Seoul")
FIELDS = (
    "row_kind", "extraction_status", "observed_at", "day_matches", "encounter_count",
    "order_count", "no_order_encounter_count", "expected_result_rows", "source_clinic_day",
    "source_encounter_id", "source_reception_code", "hold_yn", "order_present",
    "source_order_encounter_id", "source_order_date", "source_order_number", "source_order_sequence",
    "catalog_code", "catalog_name", "user_code", "user_name", "source_qty", "source_divide",
    "source_days", "order_type", "department_code", "dc_yn", "act_yn",
)
SQL_FAILURES = frozenset({"invalid_limits", "wrong_day", "encounter_overflow", "order_overflow",
    "invalid_encounter_key", "duplicate_encounter_key", "invalid_order_key", "duplicate_order_key",
    "off_day_child", "invalid_retained_flag", "field_overflow"})
REASONS = SQL_FAILURES | {"invalid_scope", "query_changed", "session_unverified", "cursor_close_unverified",
    "cleanup_unverified", "result_overflow", "result_shape_unverified", "inconsistent_result",
    "source_text_unreviewed", "source_number_unreviewed", "source_key_unreviewed"}
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")


class ReadRejected(ValueError):
    """Fixed redacted reason only."""


@dataclass(repr=False)
class DetachedRows:
    columns: tuple
    rows: list
    driver_rowcount: int

    def __repr__(self):
        return "<DetachedRows: redacted>"


def check_day(day, now):
    current = now()
    if (type(day) is not date or type(current) is not datetime or current.utcoffset() is None
            or current.astimezone(KST).date() != day):
        raise ReadRejected("invalid_scope")


def _text(value, cap, *, nullable=True):
    if value is None and nullable:
        return
    if (type(value) is not str or len(value) > cap
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ReadRejected("source_text_unreviewed")


def _key(value):
    if type(value) is str:
        _text(value, 128, nullable=False)
        if not value.strip():
            raise ReadRejected("source_key_unreviewed")
    elif type(value) is int:
        if len(str(value)) > 128:
            raise ReadRejected("source_key_unreviewed")
    elif type(value) is Decimal:
        if not _decimal_bounded(value):
            raise ReadRejected("source_key_unreviewed")
    else:
        raise ReadRejected("source_key_unreviewed")
    return type(value).__name__, value


def _decimal_bounded(value):
    if not value.is_finite():
        return False
    parts = value.as_tuple()
    digits, exponent = len(parts.digits), parts.exponent
    length = (digits + exponent if exponent >= 0 else max(1, digits + exponent) + 1 - exponent)
    return digits <= 128 and length + parts.sign <= 128


def summarize(batch, day):
    if type(batch) is not DetachedRows or batch.columns != FIELDS or type(batch.rows) is not list:
        raise ReadRejected("result_shape_unverified")
    if len(batch.rows) > RESULT_CAP:
        raise ReadRejected("result_overflow")
    if (not batch.rows or type(batch.driver_rowcount) is not int
            or batch.driver_rowcount != len(batch.rows)):
        raise ReadRejected("inconsistent_result")
    if any(type(row) not in (tuple, list) or len(row) != len(FIELDS) for row in batch.rows):
        raise ReadRejected("result_shape_unverified")
    first = dict(zip(FIELDS, batch.rows[0]))
    status = first["extraction_status"]
    if type(status) is not str:
        raise ReadRejected("result_shape_unverified")
    if status in SQL_FAILURES:
        raise ReadRejected(status)
    if status != "candidate_rows" or first["day_matches"] is not True:
        raise ReadRejected("inconsistent_result")
    observed = first["observed_at"]
    if type(observed) is not datetime or observed.utcoffset() is None or observed.astimezone(KST).date() != day:
        raise ReadRejected("invalid_scope")
    totals = [first[key] for key in ("encounter_count", "order_count", "no_order_encounter_count", "expected_result_rows")]
    if any(type(v) is not int or v < 0 for v in totals):
        raise ReadRejected("inconsistent_result")
    encounters, orders, without, expected = totals
    if encounters > ENCOUNTER_CAP or orders > ORDER_CAP or without > encounters:
        raise ReadRejected("result_overflow")
    if expected != (orders + without if encounters else 1) or expected != len(batch.rows):
        raise ReadRejected("inconsistent_result")
    parents, order_keys, empty_parents, parents_with_orders = {}, set(), set(), set()
    numeric_nulls = dict.fromkeys(("source_qty", "source_divide", "source_days"), 0)
    name_nulls = 0
    metadata = tuple(batch.rows[0][1:8])
    day_text = day.strftime("%Y%m%d")
    for values in batch.rows:
        row = dict(zip(FIELDS, values))
        if (tuple(values[1:8]) != metadata or row["day_matches"] is not True or type(row["order_present"]) is not bool
                or any(type(row[k]) is not int for k in ("encounter_count", "order_count", "no_order_encounter_count", "expected_result_rows"))):
            raise ReadRejected("inconsistent_result")
        if not encounters:
            if (orders or without or row["row_kind"] != "META" or row["order_present"]
                    or any(row[k] is not None for k in FIELDS[8:] if k != "order_present")):
                raise ReadRejected("inconsistent_result")
            continue
        if row["row_kind"] != "DATA" or row["source_clinic_day"] != day_text:
            raise ReadRejected("inconsistent_result")
        parent_key = _key(row["source_encounter_id"])
        _text(row["source_reception_code"], 128)
        if row["hold_yn"] not in ("Y", "N"):
            raise ReadRejected("invalid_retained_flag")
        parent = row["source_clinic_day"], row["source_reception_code"], row["hold_yn"]
        if parent_key in parents and parents[parent_key] != parent:
            raise ReadRejected("inconsistent_result")
        parents[parent_key] = parent
        if not row["order_present"]:
            if parent_key in empty_parents or any(row[k] is not None for k in FIELDS[13:]):
                raise ReadRejected("inconsistent_result")
            empty_parents.add(parent_key)
            continue
        if _key(row["source_order_encounter_id"]) != parent_key or row["source_order_date"] != day_text:
            raise ReadRejected("inconsistent_result")
        key = parent_key, row["source_order_date"], _key(row["source_order_number"]), _key(row["source_order_sequence"])
        if key in order_keys:
            raise ReadRejected("duplicate_order_key")
        order_keys.add(key)
        parents_with_orders.add(parent_key)
        for field in ("catalog_code", "catalog_name", "user_code", "user_name", "order_type", "department_code"):
            _text(row[field], 256 if field.endswith("name") else 128)
        name_nulls += row["user_name"] is None
        for field in numeric_nulls:
            value = row[field]
            if value is None:
                numeric_nulls[field] += 1
            elif type(value) is not Decimal or not _decimal_bounded(value):
                raise ReadRejected("source_number_unreviewed")
        if row["dc_yn"] not in ("Y", "N") or row["act_yn"] not in ("Y", "N"):
            raise ReadRejected("invalid_retained_flag")
    if (len(parents) != encounters or len(order_keys) != orders or len(empty_parents) != without
            or empty_parents & parents_with_orders or len(parents_with_orders) + without != encounters):
        raise ReadRejected("inconsistent_result")
    return {"candidate_encounters": encounters, "orders": orders, "no_order_encounters": without,
            "encounters_with_orders": len(parents_with_orders), "returned_rows": len(batch.rows),
            "row_counts_consistent": True, "unique_four_part_keys": True,
            "no_order_encounters_preserved": True, "all_children_linked_to_scoped_parent": True,
            "user_name_null_count": name_nulls, "numeric_null_counts": numeric_nulls}


def _read(connection_string, params, proof, timings, queued_at):
    import psycopg2

    started = perf_counter()
    timings["queue_wait_ms"] = (started - queued_at) * 1000
    connection = cursor = None
    try:
        connection = psycopg2.connect(connection_string, connect_timeout=3,
                                      application_name="KaosEghis-day-read-evidence")
        proof["connection_opened"] = True
        connection.set_session(readonly=True, autocommit=True, isolation_level="READ COMMITTED")
        cursor = connection.cursor()
        cursor.execute("SET statement_timeout = 2000")
        cursor.execute("SELECT current_setting('transaction_read_only'), current_setting('statement_timeout'), current_setting('transaction_isolation')")
        if cursor.fetchone() != ("on", "2s", "read committed"):
            raise ReadRejected("session_unverified")
        proof["readonly_verified"] = True
        point = perf_counter()
        timings["connection_setup_ms"] = (point - started) * 1000
        cursor.execute(QUERY, params)
        timings["execute_ms"] = (perf_counter() - point) * 1000
        point = perf_counter()
        columns = tuple(item[0] for item in cursor.description or ())
        rows = cursor.fetchmany(RESULT_CAP + 1)
        count = cursor.rowcount
        timings["fetch_ms"] = (perf_counter() - point) * 1000
    finally:
        point = perf_counter()
        try:
            if cursor is not None:
                cursor.close()
                if getattr(cursor, "closed", False) is not True:
                    raise ReadRejected("cursor_close_unverified")
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
            timings["cleanup_ms"] = (perf_counter() - point) * 1000
            timings["connection_lifecycle_ms"] = (perf_counter() - started) * 1000
    return DetachedRows(columns, rows, count)


def inspect(connection_string, *, clinic_day, now, approved=False):
    started, cpu = perf_counter(), process_time()
    proof = dict.fromkeys(PROOF_FIELDS, False)
    timings = {}
    report = {"status": "not_run", "authoritative_snapshot": False}
    batch = None
    try:
        if approved is not True:
            report["status"] = "approval_required"
        elif hashlib.sha256(QUERY.encode()).hexdigest() != QUERY_HASH or _WRITE_SQL_PATTERN.search(QUERY):
            report["status"] = "query_changed"
        else:
            check_day(clinic_day, now)
            params = {"day": clinic_day.strftime("%Y%m%d"), "encounter_cap": ENCOUNTER_CAP, "order_cap": ORDER_CAP}
            queued_at = perf_counter()
            def operation():
                check_day(clinic_day, now)
                return _read(connection_string, params, proof, timings, queued_at)
            batch = run_serialized_read(operation)
            if not all(proof[key] is True for key in PROOF_FIELDS):
                raise ReadRejected("cleanup_unverified")
            check_day(clinic_day, now)
            point = perf_counter()
            findings = summarize(batch, clinic_day)
            check_day(clinic_day, now)
            timings["post_close_validation_ms"] = (perf_counter() - point) * 1000
            report.update(status="populated_candidate_observed" if findings["candidate_encounters"]
                          else "zero_candidate_not_verified_empty", findings=findings)
    except ReadRejected as error:
        report["status"] = str(error) if str(error) in REASONS else "read_failed"
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {"57014": "query_timed_out", "42501": "permission_denied",
                            "42703": "schema_mismatch", "42P01": "schema_mismatch"}.get(getattr(error, "pgcode", None), "read_failed")
    finally:
        if batch is not None and type(batch.rows) is list:
            batch.rows.clear()
    timings["probe_wall_ms"] = (perf_counter() - started) * 1000
    timings["client_process_cpu_ms"] = (process_time() - cpu) * 1000
    report["closure"] = {key: proof[key] is True for key in PROOF_FIELDS}
    report["timings_ms"] = {key: round(value, 3) for key, value in timings.items()
                            if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 86400000}
    return report
