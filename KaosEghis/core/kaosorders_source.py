"""Legacy disabled board projection, separate from the shared EMR source model.

No production query is approved. These projection aliases are not database columns.
Categories, static display specs and board eligibility remain reference-only here.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping, Protocol

from KaosEghis.core.emr_source import (
    ReadStatus, SnapshotRejected, _PrivateModel, _fields, _rules, _text, _timestamp,
)

class Category(StrEnum):
    XRAY = "XRAY"
    BLOOD = "BLOOD"
    URINE = "URINE"
    ECG = "ECG"
    BMD = "BMD"
    INJECTION = "INJECTION"


CATEGORY_LABELS = dict(zip(Category, (
    "\uc5d1\uc2a4\ub808\uc774", "\ucc44\ud608", "\uc18c\ubcc0\uac80\uc0ac",
    "\uc2ec\uc804\ub3c4", "\uace8\ubc00\ub3c4", "\uc8fc\uc0ac",
)))
SPEC_FIELDS = {
    Category.XRAY: {"exam", "body_part", "view"},
    Category.BLOOD: {"study"}, Category.URINE: {"study"},
    Category.ECG: {"exam"}, Category.BMD: {"exam", "site"},
    Category.INJECTION: {"medication", "dose", "route"},
}


class ReceptionState(StrEnum):
    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class OrderState(StrEnum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True, repr=False)
class SourceDayRead(_PrivateModel):
    clinic_day: date
    observed_at: datetime
    status: ReadStatus
    encounters: tuple[Mapping, ...] = ()
    orders: tuple[Mapping, ...] = ()
    # These are assertions by an approved reader, not proof supplied by SQL rows.
    stable_keys_verified: bool = False
    states_verified: bool = False
    whole_day: bool = False
    untruncated: bool = False
    consistent_snapshot: bool = False
    timestamps_verified: bool = False


class DayReader(Protocol):
    def read_day(self, clinic_day: date, observed_at: datetime) -> SourceDayRead:
        """Return detached data after the shared reader closes its connection."""


class EghisKaosOrdersDayReader:
    """Hard block until source keys, states, scope and reviewed SQL are approved."""

    def read_day(self, clinic_day: date, observed_at: datetime) -> SourceDayRead:
        return SourceDayRead(clinic_day, observed_at, ReadStatus.UNAVAILABLE)


@dataclass(frozen=True, repr=False)
class MappingPolicy(_PrivateModel):
    reception_states: tuple[tuple[str, ReceptionState], ...] = ()
    order_states: tuple[tuple[str, OrderState], ...] = ()
    categories: tuple[tuple[str, Category | None], ...] = ()
    # None category is an explicitly reviewed unrelated code, not a fallback.
    details: tuple[tuple[Category, str, tuple[tuple[str, str], ...]], ...] = ()


@dataclass(frozen=True, repr=False)
class NormalizedOrder(_PrivateModel):
    order_id: str
    category: Category
    state: OrderState
    display_spec: tuple[tuple[str, str], ...] = ()
    ordered_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, repr=False)
class NormalizedEncounter(_PrivateModel):
    encounter_id: str
    chart_no: str
    patient_name: str
    sex_age: str
    state: ReceptionState
    received_at: datetime | None
    orders: tuple[NormalizedOrder, ...]

    @property
    def board_eligible(self) -> bool:
        return self.state == ReceptionState.ON_HOLD and any(
            order.state == OrderState.ACTIVE for order in self.orders
        )


@dataclass(frozen=True, repr=False)
class DailySnapshot(_PrivateModel):
    clinic_day: date
    observed_at: datetime
    encounters: tuple[NormalizedEncounter, ...]


def _optional_timestamp(value, read):
    if value is None:
        return None
    if read.timestamps_verified is not True:
        raise SnapshotRejected("unverified_time")
    result = _timestamp(value)
    if result > read.observed_at:
        raise SnapshotRejected("future_source_time")
    return result


def normalize_day(read: SourceDayRead, policy: MappingPolicy) -> DailySnapshot:
    """Reject the entire uncertain day, preserving the prior validated snapshot.

    Policies map exact approved codes to static display specifications. Raw order
    descriptions, clinical free text and DOB are never accepted by this boundary.
    """
    if type(read.clinic_day) is not date:
        raise SnapshotRejected("invalid_day")
    _timestamp(read.observed_at)
    if read.status is not ReadStatus.COMPLETE or not all(flag is True for flag in (
        read.stable_keys_verified, read.states_verified, read.whole_day,
        read.untruncated, read.consistent_snapshot,
    )):
        raise SnapshotRejected("incomplete_source")
    reception_rules = _rules(policy.reception_states, ReceptionState)
    order_rules = _rules(policy.order_states, OrderState)
    categories = _rules(policy.categories, Category)
    if (set(reception_rules.values()) != set(ReceptionState)
            or set(order_rules.values()) != set(OrderState)
            or set(categories.values()) - {None} != set(Category)):
        raise SnapshotRejected("incomplete_mapping")
    details = {}
    for category, code, fields in policy.details:
        if not isinstance(category, Category) or (category, code) in details:
            raise SnapshotRejected("invalid_mapping")
        _text(code)
        if len(dict(fields)) != len(fields) or set(dict(fields)) - SPEC_FIELDS[category]:
            raise SnapshotRejected("invalid_display_spec")
        details[category, code] = tuple(sorted((key, _text(value, limit=80)) for key, value in fields))

    encounters = {}
    for row in read.encounters:
        _fields(row, {"encounter_id", "chart_no", "patient_name", "sex", "age", "state_code"}, {"received_at"})
        identifier = _text(row["encounter_id"])
        if identifier in encounters:
            raise SnapshotRejected("duplicate_encounter")
        state = reception_rules.get(_text(row["state_code"]))
        if not isinstance(state, ReceptionState):
            raise SnapshotRejected("unknown_reception_state")
        if not isinstance(row["sex"], str) or row["sex"] not in {"\ub0a8", "\uc5ec"} or type(row["age"]) is not int or not 0 <= row["age"] <= 130:
            raise SnapshotRejected("invalid_demographics")
        encounters[identifier] = NormalizedEncounter(
            identifier, _text(row["chart_no"]), _text(row["patient_name"]),
            f"{row['sex']}/{row['age']}", state, _optional_timestamp(row.get("received_at"), read), (),
        )

    orders = {key: {} for key in encounters}
    seen_order_keys = set()
    for row in read.orders:
        _fields(row, {"encounter_id", "order_id", "category_code", "state_code"},
                {"detail_code", "ordered_at", "updated_at"})
        # Ignored fee rows must not conceal an ambiguous or orphan source key.
        encounter_id, order_id = _text(row["encounter_id"]), _text(row["order_id"])
        if encounter_id not in encounters:
            raise SnapshotRejected("orphan_order")
        key = (encounter_id, order_id)
        if key in seen_order_keys:
            raise SnapshotRejected("duplicate_order")
        seen_order_keys.add(key)
        category_code = _text(row["category_code"])
        if category_code not in categories:
            raise SnapshotRejected("unknown_category")
        category = categories[category_code]
        if category is None:
            continue
        state = order_rules.get(_text(row["state_code"]))
        if not isinstance(state, OrderState):
            raise SnapshotRejected("unknown_order_state")
        detail_code = row.get("detail_code")
        if detail_code is not None:
            _text(detail_code)
        ordered_at = _optional_timestamp(row.get("ordered_at"), read)
        updated_at = _optional_timestamp(row.get("updated_at"), read)
        if ordered_at is not None and updated_at is not None and updated_at < ordered_at:
            raise SnapshotRejected("invalid_source_time")
        orders[encounter_id][order_id] = NormalizedOrder(
            order_id, category, state, details.get((category, detail_code), ()), ordered_at, updated_at,
        )

    return DailySnapshot(read.clinic_day, read.observed_at, tuple(
        replace(encounters[key], orders=tuple(orders[key][oid] for oid in sorted(orders[key])))
        for key in sorted(encounters)
    ))
