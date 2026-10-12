"""Disabled-by-default production boundary for current-day KaosOrders facts.

The reader performs one bounded, read-only source statement through the shared
EMR queue.  Detached rows are interpreted only after physical connection close.
No transport, acknowledgement, scheduler, persistence, or runtime hook lives
here.  Errors use fixed codes and models redact their representations.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import hashlib
from pathlib import Path
import sqlite3
from unicodedata import category
from urllib.parse import quote
from zoneinfo import ZoneInfo

from KaosEghis.core.eghis_db import _WRITE_SQL_PATTERN
from KaosEghis.core.emr_read_queue import EmrConnectionCloseError, run_serialized_read


CONTRACT_ID = "kaosorders.current-day-orders"
CONTRACT_VERSION = 1
PROJECTION_ID = "kaosorders-current-day-orders-v1"
MAPPING_REVISION = "eghis-current-day-orders-2026-10-12"
KST = ZoneInfo("Asia/Seoul")
ENCOUNTER_CAP = 10_000
ORDER_CAP = 100_000
RESULT_CAP = ENCOUNTER_CAP + ORDER_CAP
QUERY_PATH = Path(__file__).with_name("sql") / "kaosorders_current_day_v1.sql"
QUERY_SHA256 = "60e5b06e1e1e7e3ac1f0f7f76e5d12a2da1bc09db30e2ac57176964f473df76c"
FIELDS = (
    "row_kind", "extraction_status", "observed_at", "day_matches", "encounter_count",
    "order_count", "no_order_encounter_count", "expected_result_rows", "source_clinic_day",
    "source_encounter_id", "source_reception_code", "hold_yn", "order_present",
    "source_order_encounter_id", "source_order_date", "source_order_number",
    "source_order_sequence", "catalog_code", "catalog_name", "user_code", "user_name",
    "source_qty", "source_divide", "source_days", "order_type", "department_code",
    "dc_yn", "act_yn",
)
_FORBIDDEN_TEXT = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_RECEPTION_STATES = {
    "10": "REGISTERED", "20": "IN_PROGRESS", "25": "ON_HOLD",
    "30": "CONSULTATION_COMPLETED", "40": "PAYMENT_COMPLETED", "50": "CANCELLED",
}
_SQL_FAILURES = frozenset({
    "invalid_limits", "wrong_day", "encounter_overflow", "order_overflow",
    "invalid_encounter_key", "duplicate_encounter_key", "invalid_order_key",
    "duplicate_order_key", "off_day_child", "invalid_retained_flag", "field_overflow",
})


class CurrentDaySourceRejected(ValueError):
    """Fixed non-identifying reason code only."""


class _Redacted:
    def __repr__(self):
        return f"<{type(self).__name__}: redacted>"


class EncounterState(StrEnum):
    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    CANCELLED = "CANCELLED"


class OrderState(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Flag(StrEnum):
    YES = "Y"
    NO = "N"


def _fail(reason):
    raise CurrentDaySourceRejected(reason)


def _text(value, limit, *, key=False):
    reason = "invalid_order_key" if key else "invalid_order_text"
    if value is None and not key:
        return value
    if type(value) is not str or len(value) > limit:
        _fail(reason)
    if key and (not value or value != value.strip()):
        _fail(reason)
    if any(category(char) in _FORBIDDEN_TEXT for char in value):
        _fail(reason)
    return value


def _key_text(value):
    if type(value) is str:
        return _text(value, 128, key=True)
    if type(value) is int and type(value) is not bool:
        value = str(value)
    elif type(value) is Decimal and value.is_finite():
        value = str(value)
    else:
        _fail("invalid_order_key")
    return _text(value, 128, key=True)


def _exact_decimal(value):
    if value is None:
        return None
    if type(value) is not Decimal or not value.is_finite():
        _fail("invalid_exact_decimal")
    parts = value.as_tuple()
    if max(len(parts.digits) + parts.exponent, 0) > 18 or max(-parts.exponent, 0) > 12:
        _fail("invalid_exact_decimal")
    return value


@dataclass(frozen=True, repr=False)
class CanonicalEncounter(_Redacted):
    encounter_id: str
    state: EncounterState

    def __post_init__(self):
        _text(self.encounter_id, 128, key=True)
        if type(self.state) is not EncounterState:
            _fail("invalid_encounter_state")


@dataclass(frozen=True, order=True, repr=False)
class CanonicalOrderKey(_Redacted):
    encounter_id: str
    order_date: date
    order_number: str
    order_sequence: str

    def __post_init__(self):
        _text(self.encounter_id, 128, key=True)
        _text(self.order_number, 128, key=True)
        _text(self.order_sequence, 128, key=True)
        if type(self.order_date) is not date:
            _fail("invalid_order_key")


@dataclass(frozen=True, repr=False)
class CanonicalOrder(_Redacted):
    key: CanonicalOrderKey
    catalog_code: str | None
    catalog_name: str | None
    user_code: str | None
    user_name: str | None
    order_type: str | None
    department_code: str | None
    daily_quantity: Decimal | None
    frequency_count: Decimal | None
    day_count: Decimal | None
    state: OrderState
    dc_yn: Flag
    act_yn: Flag

    def __post_init__(self):
        if type(self.key) is not CanonicalOrderKey:
            _fail("invalid_order_key")
        for name in ("catalog_code", "user_code", "order_type", "department_code"):
            _text(getattr(self, name), 128)
        for name in ("catalog_name", "user_name"):
            _text(getattr(self, name), 256)
        for name in ("daily_quantity", "frequency_count", "day_count"):
            _exact_decimal(getattr(self, name))
        if type(self.state) is not OrderState:
            _fail("invalid_order_state")
        if type(self.dc_yn) is not Flag or type(self.act_yn) is not Flag:
            _fail("invalid_order_qualifiers")


@dataclass(frozen=True, repr=False)
class CanonicalSnapshot(_Redacted):
    clinic_day: date
    observed_at: datetime
    encounters: tuple[CanonicalEncounter, ...]
    orders: tuple[CanonicalOrder, ...]

    @property
    def schema_identity(self):
        return CONTRACT_ID, CONTRACT_VERSION, PROJECTION_ID, MAPPING_REVISION


@dataclass(frozen=True, repr=False)
class ReadOutcome(_Redacted):
    status: str
    snapshot: CanonicalSnapshot | None
    diagnostics: tuple[tuple[str, int | bool], ...] = ()


@dataclass(repr=False)
class _DetachedRows(_Redacted):
    columns: tuple
    rows: list
    driver_rowcount: int


def validate_canonical_snapshot(value):
    if type(value) is not CanonicalSnapshot or type(value.clinic_day) is not date:
        _fail("invalid_snapshot")
    if (type(value.observed_at) is not datetime or value.observed_at.utcoffset() is None
            or value.observed_at.astimezone(KST).date() != value.clinic_day):
        _fail("invalid_scope")
    if type(value.encounters) is not tuple or type(value.orders) is not tuple:
        _fail("invalid_snapshot")
    if len(value.encounters) > ENCOUNTER_CAP or len(value.orders) > ORDER_CAP:
        _fail("invalid_row_bound")
    if any(type(item) is not CanonicalEncounter for item in value.encounters):
        _fail("invalid_encounter")
    if any(type(item) is not CanonicalOrder for item in value.orders):
        _fail("invalid_order")
    parent_ids = tuple(item.encounter_id for item in value.encounters)
    order_keys = tuple(item.key for item in value.orders)
    if parent_ids != tuple(sorted(parent_ids)) or len(parent_ids) != len(set(parent_ids)):
        _fail("noncanonical_snapshot")
    if order_keys != tuple(sorted(order_keys)) or len(order_keys) != len(set(order_keys)):
        _fail("noncanonical_snapshot")
    included = set(parent_ids)
    if any(item.state is EncounterState.CANCELLED for item in value.encounters):
        _fail("cancelled_parent_retained")
    if any(item.key.encounter_id not in included or item.key.order_date != value.clinic_day
           for item in value.orders):
        _fail("invalid_order_scope")
    return value


def _current_day(day, now):
    current = now()
    if (type(day) is not date or type(current) is not datetime or current.utcoffset() is None
            or current.astimezone(KST).date() != day):
        _fail("invalid_scope")


def load_connection_string_readonly(db_path):
    """Read only the approved setting without creating or mutating SQLite."""
    path = Path(db_path).resolve(strict=True)
    uri = f"file:{quote(path.as_posix(), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only = ON")
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("eghis_db_connection_string",),
        ).fetchone()
    finally:
        connection.close()
    if row is None or len(row) != 1 or type(row[0]) is not str or not row[0].strip():
        _fail("connection_unconfigured")
    return row[0].strip()


def _query_text():
    query = QUERY_PATH.read_text(encoding="utf-8")
    if hashlib.sha256(query.encode()).hexdigest() != QUERY_SHA256 or _WRITE_SQL_PATTERN.search(query):
        _fail("query_changed")
    return query


def _read_source(connection_string, query, params):
    import psycopg2
    connection = cursor = None
    try:
        connection = psycopg2.connect(
            connection_string, connect_timeout=3,
            application_name="KaosEghis-current-day-orders",
        )
        connection.set_session(readonly=True, autocommit=True, isolation_level="READ COMMITTED")
        cursor = connection.cursor()
        cursor.execute("SET statement_timeout = 2000")
        cursor.execute(
            "SELECT current_setting('transaction_read_only'), "
            "current_setting('statement_timeout'), current_setting('transaction_isolation')"
        )
        if cursor.fetchone() != ("on", "2s", "read committed"):
            _fail("session_unverified")
        cursor.execute(query, params)
        columns = tuple(item[0] for item in cursor.description or ())
        rows = cursor.fetchmany(RESULT_CAP + 1)
        rowcount = cursor.rowcount
    finally:
        try:
            if cursor is not None:
                cursor.close()
                if getattr(cursor, "closed", False) is not True:
                    _fail("cursor_close_unverified")
        finally:
            if connection is not None:
                try:
                    connection.close()
                    if type(getattr(connection, "closed", None)) is not int or connection.closed <= 0:
                        raise RuntimeError
                except BaseException:
                    raise EmrConnectionCloseError("connection_close_unverified") from None
    return _DetachedRows(columns, rows, rowcount)


def _map_rows(batch, clinic_day):
    if (type(batch) is not _DetachedRows or batch.columns != FIELDS or type(batch.rows) is not list
            or not batch.rows or len(batch.rows) > RESULT_CAP
            or batch.driver_rowcount != len(batch.rows)):
        _fail("result_shape_unverified")
    first = dict(zip(FIELDS, batch.rows[0]))
    status = first.get("extraction_status")
    if status in _SQL_FAILURES:
        _fail(status)
    if status != "candidate_rows" or first.get("day_matches") is not True:
        _fail("inconsistent_result")
    observed = first.get("observed_at")
    if type(observed) is not datetime or observed.utcoffset() is None:
        _fail("invalid_scope")
    expected = first.get("expected_result_rows")
    counts = tuple(first.get(name) for name in (
        "encounter_count", "order_count", "no_order_encounter_count",
    ))
    if (any(type(item) is not int or item < 0 for item in (*counts, expected))
            or expected != len(batch.rows)):
        _fail("inconsistent_result")
    encounter_count, order_count, no_order_count = counts
    if expected != (order_count + no_order_count if encounter_count else 1):
        _fail("inconsistent_result")
    # The approved contract does not establish that a zero-row database result
    # authoritatively means an empty clinic day. Never turn it into removals.
    if encounter_count == 0:
        _fail("empty_day_unverified")
    parents = {}
    orders = {}
    no_order_parents = set()
    parents_with_orders = set()
    metadata = tuple(batch.rows[0][1:8])
    day_text = clinic_day.strftime("%Y%m%d")
    for values in batch.rows:
        if type(values) not in (tuple, list) or len(values) != len(FIELDS):
            _fail("result_shape_unverified")
        row = dict(zip(FIELDS, values))
        if tuple(values[1:8]) != metadata:
            _fail("inconsistent_result")
        if not encounter_count:
            if row["row_kind"] != "META" or row["order_present"] is not False:
                _fail("inconsistent_result")
            continue
        if row["row_kind"] != "DATA" or row["source_clinic_day"] != day_text:
            _fail("invalid_scope")
        encounter_id = _key_text(row["source_encounter_id"])
        code = _key_text(row["source_reception_code"])
        if code not in _RECEPTION_STATES:
            _fail("unknown_reception_state")
        try:
            hold = Flag(row["hold_yn"])
        except (ValueError, TypeError):
            _fail("invalid_reception_qualifier")
        parent = CanonicalEncounter(encounter_id, EncounterState(_RECEPTION_STATES[code]))
        prior = parents.setdefault(encounter_id, (parent, hold))
        if prior != (parent, hold):
            _fail("inconsistent_result")
        if row["order_present"] is False:
            if (encounter_id in no_order_parents
                    or any(row[name] is not None for name in FIELDS[13:])):
                _fail("inconsistent_result")
            no_order_parents.add(encounter_id)
            continue
        if row["order_present"] is not True or _key_text(row["source_order_encounter_id"]) != encounter_id:
            _fail("orphan_order")
        if row["source_order_date"] != day_text:
            _fail("invalid_order_scope")
        key = CanonicalOrderKey(
            encounter_id, clinic_day, _key_text(row["source_order_number"]),
            _key_text(row["source_order_sequence"]),
        )
        if key in orders:
            _fail("duplicate_order")
        parents_with_orders.add(encounter_id)
        try:
            dc, act = Flag(row["dc_yn"]), Flag(row["act_yn"])
        except (ValueError, TypeError):
            _fail("invalid_order_qualifiers")
        orders[key] = CanonicalOrder(
            key, row["catalog_code"], row["catalog_name"], row["user_code"], row["user_name"],
            row["order_type"], row["department_code"], _exact_decimal(row["source_qty"]),
            _exact_decimal(row["source_divide"]), _exact_decimal(row["source_days"]),
            OrderState.CANCELLED if dc is Flag.YES else OrderState.ACTIVE, dc, act,
        )
    if (len(parents) != encounter_count or len(orders) != order_count
            or len(no_order_parents) != no_order_count
            or no_order_parents & parents_with_orders
            or len(no_order_parents | parents_with_orders) != encounter_count):
        _fail("inconsistent_result")
    included = {key for key, (parent, _) in parents.items() if parent.state is not EncounterState.CANCELLED}
    snapshot = CanonicalSnapshot(
        clinic_day, observed,
        tuple(parents[key][0] for key in sorted(included)),
        tuple(orders[key] for key in sorted(orders) if key.encounter_id in included),
    )
    validate_canonical_snapshot(snapshot)
    diagnostics = (
        ("source_encounters", encounter_count), ("source_orders", order_count),
        ("included_encounters", len(snapshot.encounters)), ("included_orders", len(snapshot.orders)),
        ("cancelled_encounters_excluded", encounter_count - len(included)),
        ("cancelled_orders", sum(item.state is OrderState.CANCELLED for item in snapshot.orders)),
        ("no_order_encounters", no_order_count), ("complete", True),
    )
    return snapshot, diagnostics


def read_current_day_orders(db_path, *, clinic_day, now, enabled=False):
    """Perform one explicit read. The literal opt-in has no configured runtime caller."""
    if enabled is not True:
        return ReadOutcome("disabled", None)
    batch = None
    try:
        _current_day(clinic_day, now)
        query = _query_text()
        connection_string = load_connection_string_readonly(db_path)
        params = {"day": clinic_day.strftime("%Y%m%d"), "encounter_cap": ENCOUNTER_CAP,
                  "order_cap": ORDER_CAP}
        batch = run_serialized_read(lambda: _read_source(connection_string, query, params))
        _current_day(clinic_day, now)
        snapshot, diagnostics = _map_rows(batch, clinic_day)
        _current_day(clinic_day, now)
        return ReadOutcome("complete", snapshot, diagnostics)
    except CurrentDaySourceRejected as error:
        return ReadOutcome(str(error), None)
    except EmrConnectionCloseError:
        return ReadOutcome("reader_safety_stop", None)
    except Exception as error:
        status = {"57014": "query_timed_out", "42501": "permission_denied",
                  "42703": "schema_mismatch", "42P01": "schema_mismatch"}.get(
                      getattr(error, "pgcode", None), "read_failed")
        return ReadOutcome(status, None)
    finally:
        if batch is not None and type(batch.rows) is list:
            batch.rows.clear()
