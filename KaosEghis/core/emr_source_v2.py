"""Synthetic-only v2 source projection. No reader, SQL, persistence or runtime.

Separate types prevent reinterpretation of v1 snapshots. Input aliases are an
offline test boundary, not an approved production query or source-state mapping.
"""

from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping

from KaosEghis.core.emr_source import (
    MAX_ENCOUNTERS, MAX_ORDERS, OrderFacts, OrderKey, OrderQualifiers, OrderState,
    ReadStatus, ReceptionState, SnapshotRejected, SourcePolicy, _decimal,
    _decimal_value, _fields, _rules, _source_flag, _text, _timestamp,
)


PROJECTION_ID = "kaosorders-all-orders-v2"
SYNTHETIC_MAPPING_REVISION = "synthetic-v2"


class _PrivateV2:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: redacted>"


@dataclass(frozen=True, slots=True, repr=False)
class ReceptionQualifiersV2(_PrivateV2):
    hold_yn: str

    def __post_init__(self):
        _source_flag(self.hold_yn)


@dataclass(frozen=True, slots=True, repr=False)
class EncounterFactsV2(_PrivateV2):
    encounter_id: str
    chart_no: str
    patient_name: str
    sex: str | None
    age: int | None
    source_state_code: str
    state: ReceptionState
    qualifiers: ReceptionQualifiersV2


@dataclass(frozen=True, slots=True, repr=False)
class EmrDayReadV2(_PrivateV2):
    source_id: str
    projection_id: str
    clinic_day: date
    observed_at: datetime
    status: ReadStatus
    encounters: tuple[Mapping, ...] = ()
    orders: tuple[Mapping, ...] = ()
    # Synthetic caller assertions, not evidence of a production snapshot/cleanup.
    keys_verified: bool = False
    states_verified: bool = False
    whole_day: bool = False
    untruncated: bool = False
    consistent_snapshot: bool = False
    connection_closed: bool = False
    structured_fields_verified: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class SourceSnapshotV2(_PrivateV2):
    source_id: str
    projection_id: str
    clinic_day: date
    observed_at: datetime
    mapping_revision: str
    encounters: tuple[EncounterFactsV2, ...]
    orders: tuple[OrderFacts, ...]

    @property
    def scope(self) -> tuple[str, str, date]:
        return self.source_id, self.projection_id, self.clinic_day


def _require_model(value, kind):
    names = {field.name for field in fields(kind)}
    if (type(value) is not kind
            or set(getattr(value, "__dict__", {})) - names
            or not all(hasattr(value, name) for name in names)):
        raise SnapshotRejected("invalid_snapshot")


def _wire_text(value, *, allow_empty=False):
    if type(value) is not str or value != value.strip():
        raise SnapshotRejected("invalid_text")
    if allow_empty and value == "":
        return value
    return _text(value)


def _row_bounds(encounters, orders):
    if (type(encounters) is not tuple or type(orders) is not tuple
            or len(encounters) > MAX_ENCOUNTERS or len(orders) > MAX_ORDERS):
        raise SnapshotRejected("invalid_row_bound")


def _identity(projection_id, mapping_revision):
    if (type(projection_id) is not str or projection_id != PROJECTION_ID
            or type(mapping_revision) is not str
            or mapping_revision != SYNTHETIC_MAPPING_REVISION):
        raise SnapshotRejected("unsupported_projection")


def decimal_text(value):
    if value is None:
        return None
    if type(value) is not Decimal:
        raise SnapshotRejected("invalid_number")
    _decimal_value(value)
    if value.is_zero():
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if len(text) > 32:
        raise SnapshotRejected("invalid_number")
    return text


def validate_source_snapshot_v2(snapshot: SourceSnapshotV2) -> None:
    """Revalidate direct constructions too; this does not certify source evidence."""
    _require_model(snapshot, SourceSnapshotV2)
    _identity(snapshot.projection_id, snapshot.mapping_revision)
    _wire_text(snapshot.source_id)
    if type(snapshot.clinic_day) is not date:
        raise SnapshotRejected("invalid_day")
    _timestamp(snapshot.observed_at)
    _row_bounds(snapshot.encounters, snapshot.orders)
    encounters = set()
    for item in snapshot.encounters:
        _require_model(item, EncounterFactsV2)
        _require_model(item.qualifiers, ReceptionQualifiersV2)
        _source_flag(item.qualifiers.hold_yn)
        for value in (item.encounter_id, item.chart_no, item.patient_name, item.source_state_code):
            _wire_text(value)
        if item.sex == "":
            raise SnapshotRejected("unverified_sex")
        if ((item.sex is not None and (type(item.sex) is not str or item.sex not in ("M", "F", "O")))
                or (item.age is not None and (type(item.age) is not int or not 0 <= item.age <= 130))):
            raise SnapshotRejected("invalid_demographics")
        if type(item.state) is not ReceptionState:
            raise SnapshotRejected("unknown_reception_state")
        if item.encounter_id in encounters:
            raise SnapshotRejected("duplicate_encounter")
        encounters.add(item.encounter_id)
    keys = set()
    for item in snapshot.orders:
        _require_model(item, OrderFacts)
        _require_model(item.key, OrderKey)
        _require_model(item.qualifiers, OrderQualifiers)
        _source_flag(item.qualifiers.dc_yn)
        _source_flag(item.qualifiers.act_yn)
        for value in (item.key.encounter_id, item.key.order_number, item.key.order_sequence,
                      item.order_code, item.order_type, item.source_state_code):
            _wire_text(value)
        _wire_text(item.department_code, allow_empty=True)
        if type(item.key.order_date) is not date:
            raise SnapshotRejected("invalid_order_date")
        if type(item.state) is not OrderState:
            raise SnapshotRejected("unknown_order_state")
        if item.key.encounter_id not in encounters:
            raise SnapshotRejected("orphan_order")
        if item.key in keys:
            raise SnapshotRejected("duplicate_order")
        keys.add(item.key)
        for value in (item.quantity, item.days, item.frequency):
            decimal_text(value)


def normalize_source_day_v2(
    read: EmrDayReadV2, policy: SourcePolicy, *, synthetic_fixture=False,
) -> SourceSnapshotV2:
    if synthetic_fixture is not True:
        raise SnapshotRejected("synthetic_fixture_required")
    _require_model(read, EmrDayReadV2)
    _require_model(policy, SourcePolicy)
    if read.status is not ReadStatus.COMPLETE or not all(flag is True for flag in (
        read.keys_verified, read.states_verified, read.whole_day, read.untruncated,
        read.consistent_snapshot, read.connection_closed,
    )):
        raise SnapshotRejected("incomplete_source")
    _identity(read.projection_id, policy.revision)
    _row_bounds(read.encounters, read.orders)
    if not policy.reception_states or not policy.order_states:
        raise SnapshotRejected("incomplete_mapping")
    reception_rules = _rules(policy.reception_states, ReceptionState)
    order_rules = _rules(policy.order_states, OrderState)
    if None in reception_rules.values() or None in order_rules.values():
        raise SnapshotRejected("invalid_mapping")

    encounters = []
    for row in read.encounters:
        _fields(row, {"encounter_id", "chart_no", "patient_name", "sex", "age", "state_code", "qualifiers"})
        _fields(row["qualifiers"], {"hold_yn"})
        state_code = _wire_text(row["state_code"])
        state = reception_rules.get(state_code)
        if state is None:
            raise SnapshotRejected("unknown_reception_state")
        encounters.append(EncounterFactsV2(
            row["encounter_id"], row["chart_no"], row["patient_name"], row["sex"], row["age"],
            state_code, state, ReceptionQualifiersV2(row["qualifiers"]["hold_yn"]),
        ))
    orders = []
    for row in read.orders:
        _fields(row, {"encounter_id", "order_date", "order_number", "order_sequence",
                      "order_code", "order_type", "department_code", "state_code", "qualifiers"},
                {"quantity", "days", "frequency"})
        _fields(row["qualifiers"], {"dc_yn", "act_yn"})
        state_code = _wire_text(row["state_code"])
        state = order_rules.get(state_code)
        if state is None:
            raise SnapshotRejected("unknown_order_state")
        orders.append(OrderFacts(
            OrderKey(row["encounter_id"], row["order_date"], row["order_number"], row["order_sequence"]),
            row["order_code"], row["order_type"], row["department_code"], state_code, state,
            OrderQualifiers(row["qualifiers"]["dc_yn"], row["qualifiers"]["act_yn"]),
            *(_decimal(row.get(name), read) for name in ("quantity", "days", "frequency")),
        ))
    snapshot = SourceSnapshotV2(read.source_id, read.projection_id, read.clinic_day,
                                read.observed_at, policy.revision, tuple(encounters), tuple(orders))
    validate_source_snapshot_v2(snapshot)
    return SourceSnapshotV2(snapshot.source_id, snapshot.projection_id, snapshot.clinic_day,
                            snapshot.observed_at, snapshot.mapping_revision,
                            tuple(sorted(encounters, key=lambda item: item.encounter_id)),
                            tuple(sorted(orders, key=lambda item: item.key)))
