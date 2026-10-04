"""Offline, destination-neutral EMR source model. No SQL or production mappings.

Input aliases describe a proposed detached projection, not an approved live query
or wire contract. Normalize only after the shared reader closes its connection.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Mapping, Protocol


MAX_ENCOUNTERS = 10000
MAX_ORDERS = 100000


class ReadStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    UNAVAILABLE = "unavailable"


class SnapshotRejected(ValueError):
    """A fixed reason code only, never raw source values or provider text."""


class _PrivateModel:
    def __repr__(self):
        return f"<{type(self).__name__}: redacted>"


def _text(value, *, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise SnapshotRejected("invalid_text")
    if any(ord(char) < 32 for char in value):
        raise SnapshotRejected("invalid_text")
    return value


def _timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SnapshotRejected("unverified_time")
    return value


def _fields(row, required, optional=()):
    if not isinstance(row, Mapping) or not required <= row.keys() or row.keys() - (required | set(optional)):
        raise SnapshotRejected("invalid_fields")


def _rules(pairs, kind):
    result = {}
    if not isinstance(pairs, (tuple, list)):
        raise SnapshotRejected("invalid_mapping")
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise SnapshotRejected("invalid_mapping")
        code, value = pair
        _text(code)
        if code in result or (value is not None and not isinstance(value, kind)):
            raise SnapshotRejected("invalid_mapping")
        result[code] = value
    return result


class ReceptionState(StrEnum):
    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    CANCELLED = "CANCELLED"


class OrderState(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, repr=False)
class SourcePolicy(_PrivateModel):
    revision: str = ""
    reception_states: tuple[tuple[str, ReceptionState], ...] = ()
    order_states: tuple[tuple[str, OrderState], ...] = ()


@dataclass(frozen=True, repr=False)
class EmrDayRead(_PrivateModel):
    source_id: str
    projection_id: str
    clinic_day: date
    observed_at: datetime
    status: ReadStatus
    encounters: tuple[Mapping, ...] = ()
    orders: tuple[Mapping, ...] = ()
    # Reader assertions, not proof of approval or of physical connection cleanup.
    keys_verified: bool = False
    states_verified: bool = False
    whole_day: bool = False
    untruncated: bool = False
    consistent_snapshot: bool = False
    connection_closed: bool = False
    structured_fields_verified: bool = False


class EmrDayReader(Protocol):
    def read_day(self, clinic_day: date, observed_at: datetime) -> EmrDayRead:
        """Return detached rows only after the shared read boundary closes."""


class EghisSourceDayReader:
    """Blocked until a reviewed complete-day source operation is approved."""

    def read_day(self, clinic_day: date, observed_at: datetime) -> EmrDayRead:
        return EmrDayRead("unconfigured", "unverified", clinic_day, observed_at,
                          ReadStatus.UNAVAILABLE)


@dataclass(frozen=True, order=True, repr=False)
class OrderKey(_PrivateModel):
    encounter_id: str
    order_date: date
    order_number: str
    order_sequence: str


@dataclass(frozen=True, repr=False)
class ReceptionQualifiers(_PrivateModel):
    hold_yn: str
    hold_opd: str

    def __post_init__(self):
        _source_flag(self.hold_yn)
        _source_flag(self.hold_opd)


@dataclass(frozen=True, repr=False)
class OrderQualifiers(_PrivateModel):
    dc_yn: str
    act_yn: str

    def __post_init__(self):
        _source_flag(self.dc_yn)
        _source_flag(self.act_yn)


def _source_flag(value):
    if type(value) is not str or value not in ("Y", "N"):
        raise SnapshotRejected("invalid_qualifier")
    return value


def _qualifiers(row, kind):
    names = ("hold_yn", "hold_opd") if kind is ReceptionQualifiers else ("dc_yn", "act_yn")
    _fields(row, set(names))
    return kind(*(_source_flag(row[name]) for name in names))


@dataclass(frozen=True, repr=False)
class EncounterFacts(_PrivateModel):
    encounter_id: str
    chart_no: str
    patient_name: str
    sex: str | None
    age: int | None
    source_state_code: str
    state: ReceptionState
    qualifiers: ReceptionQualifiers


@dataclass(frozen=True, repr=False)
class OrderFacts(_PrivateModel):
    key: OrderKey
    order_code: str
    order_type: str
    department_code: str
    source_state_code: str
    state: OrderState
    qualifiers: OrderQualifiers
    quantity: Decimal | None = None
    days: Decimal | None = None
    frequency: Decimal | None = None


@dataclass(frozen=True, repr=False)
class SourceSnapshot(_PrivateModel):
    source_id: str
    projection_id: str
    clinic_day: date
    observed_at: datetime
    mapping_revision: str
    encounters: tuple[EncounterFacts, ...]
    orders: tuple[OrderFacts, ...]

    @property
    def scope(self) -> tuple[str, str, date]:
        return self.source_id, self.projection_id, self.clinic_day


def _decimal(value, read):
    if value is None:
        return None
    if read.structured_fields_verified is not True:
        raise SnapshotRejected("unverified_structured_fields")
    return _decimal_value(value)


def _decimal_value(value):
    # Exact decimals only: no float rounding or guessed clinical dose conversion.
    if type(value) not in (str, int, Decimal) or len(str(value)) > 32:
        raise SnapshotRejected("invalid_number")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise SnapshotRejected("invalid_number") from None
    if (not result.is_finite() or result.copy_abs() > Decimal("1000000000")
            or not -12 <= result.as_tuple().exponent <= 12):
        raise SnapshotRejected("invalid_number")
    return result


def normalize_source_day(read: EmrDayRead, policy: SourcePolicy) -> SourceSnapshot:
    """Validate a complete source scope without category, fee or visibility rules."""
    if type(read.clinic_day) is not date:
        raise SnapshotRejected("invalid_day")
    _timestamp(read.observed_at)
    if read.status is not ReadStatus.COMPLETE or not all(flag is True for flag in (
        read.keys_verified, read.states_verified, read.whole_day, read.untruncated,
        read.consistent_snapshot, read.connection_closed,
    )):
        raise SnapshotRejected("incomplete_source")
    source_id, projection_id = _text(read.source_id), _text(read.projection_id)
    if not policy.revision or not policy.reception_states or not policy.order_states:
        raise SnapshotRejected("incomplete_mapping")
    revision = _text(policy.revision)
    reception_rules = _rules(policy.reception_states, ReceptionState)
    order_rules = _rules(policy.order_states, OrderState)
    if None in reception_rules.values() or None in order_rules.values():
        raise SnapshotRejected("invalid_mapping")
    if (not isinstance(read.encounters, tuple) or not isinstance(read.orders, tuple)
            or len(read.encounters) > MAX_ENCOUNTERS or len(read.orders) > MAX_ORDERS):
        raise SnapshotRejected("invalid_row_bound")

    encounters = {}
    for row in read.encounters:
        _fields(row, {"encounter_id", "chart_no", "patient_name", "sex", "age", "state_code", "qualifiers"})
        identifier = _text(row["encounter_id"])
        if identifier in encounters:
            raise SnapshotRejected("duplicate_encounter")
        state_code = _text(row["state_code"])
        state = reception_rules.get(state_code)
        if state is None:
            raise SnapshotRejected("unknown_reception_state")
        age, sex = row["age"], row["sex"]
        if ((sex is not None and (type(sex) is not str or sex not in {"M", "F", "O", ""}))
                or (age is not None and (type(age) is not int or not 0 <= age <= 130))):
            raise SnapshotRejected("invalid_demographics")
        encounters[identifier] = EncounterFacts(
            identifier, _text(row["chart_no"]), _text(row["patient_name"]),
            sex, age, state_code, state, _qualifiers(row["qualifiers"], ReceptionQualifiers),
        )

    orders = {}
    for row in read.orders:
        _fields(row, {"encounter_id", "order_date", "order_number", "order_sequence",
                      "order_code", "order_type", "department_code", "state_code", "qualifiers"},
                {"quantity", "days", "frequency"})
        encounter_id = _text(row["encounter_id"])
        if encounter_id not in encounters:
            raise SnapshotRejected("orphan_order")
        if type(row["order_date"]) is not date:
            raise SnapshotRejected("invalid_order_date")
        key = OrderKey(encounter_id, row["order_date"], _text(row["order_number"]),
                       _text(row["order_sequence"]))
        if key in orders:
            raise SnapshotRejected("duplicate_order")
        state_code = _text(row["state_code"])
        state = order_rules.get(state_code)
        if state is None:
            raise SnapshotRejected("unknown_order_state")
        department = row["department_code"]
        if department != "":
            _text(department)
        orders[key] = OrderFacts(
            key, _text(row["order_code"]), _text(row["order_type"]), department,
            state_code, state, _qualifiers(row["qualifiers"], OrderQualifiers),
            *(_decimal(row.get(name), read)
                                for name in ("quantity", "days", "frequency")),
        )

    return SourceSnapshot(source_id, projection_id, read.clinic_day, read.observed_at,
                          revision, tuple(encounters[key] for key in sorted(encounters)),
                          tuple(orders[key] for key in sorted(orders)))
