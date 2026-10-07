"""Pure synthetic current-day Orders facts and in-memory comparison.

No source reader, mapping, serializer, wire/session protocol, persistence, runtime
hook, PACS/Reception behavior or I/O belongs in this module.
"""

from dataclasses import InitVar, dataclass, fields
from datetime import date
from enum import StrEnum
from unicodedata import category


CONTRACT_ID = "kaosorders.current-day-orders"
CONTRACT_VERSION = 1
PROJECTION_ID = "kaosorders-current-day-orders-v1"
MAX_PARENTS = 10_000
MAX_CHILDREN = 100_000
CODE_LIMIT = 128
NAME_LIMIT = 256

PARENT_FIELDS = (
    "encounter_id",
    "chart_number",
    "patient_name",
    "sex",
    "age",
    "state",
    "hold_yn",
)
KEY_FIELDS = ("encounter_id", "order_date", "order_number", "order_sequence")
CHILD_TEXT_FIELDS = (
    "catalog_code",
    "catalog_name",
    "user_code",
    "user_name",
    "order_type",
    "department_code",
)
CHILD_FIELDS = ("key", *CHILD_TEXT_FIELDS, "state", "dc_yn", "act_yn")


class CurrentDayFactRejected(ValueError):
    """Fixed rejection reasons only; never source or patient values."""


class IncludedParentState(StrEnum):
    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"


class ChildState(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class _RedactedModel:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


def _has_forbidden_character(value: str) -> bool:
    return any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)


def _required_text(value: object, limit: int) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > limit
        or _has_forbidden_character(value)
    ):
        raise CurrentDayFactRejected("invalid_text")
    return value


def _nullable_exact_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    if type(value) is not str or len(value) > limit or _has_forbidden_character(value):
        raise CurrentDayFactRejected("invalid_text")
    return value


def _flag(value: object) -> str:
    if type(value) is not str or value not in {"Y", "N"}:
        raise CurrentDayFactRejected("invalid_flag")
    return value


def _closed_dict(value: object, names: tuple[str, ...]) -> dict:
    if type(value) is not dict or set(value) != set(names):
        raise CurrentDayFactRejected("invalid_fields")
    return value


def _exact_model(value: object, kind: type, reason: str) -> None:
    if type(value) is not kind:
        raise CurrentDayFactRejected(reason)
    expected = {field.name for field in fields(kind)}
    if {field.name for field in fields(value)} != expected:
        raise CurrentDayFactRejected(reason)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCurrentDayParent(_RedactedModel):
    encounter_id: str
    chart_number: str
    patient_name: str
    sex: str | None
    age: int | None
    state: IncludedParentState
    hold_yn: str
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayFactRejected("synthetic_fixture_required")
        _required_text(self.encounter_id, CODE_LIMIT)
        _required_text(self.chart_number, CODE_LIMIT)
        _required_text(self.patient_name, NAME_LIMIT)
        if self.sex not in {None, "M", "F"} or (
            self.age is not None
            and (type(self.age) is not int or not 0 <= self.age <= 130)
        ):
            raise CurrentDayFactRejected("invalid_demographics")
        if type(self.state) is not IncludedParentState:
            raise CurrentDayFactRejected("invalid_parent_state")
        _flag(self.hold_yn)


@dataclass(frozen=True, slots=True, order=True, repr=False)
class CurrentDayOrderKey(_RedactedModel):
    encounter_id: str
    order_date: date
    order_number: str
    order_sequence: str
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayFactRejected("synthetic_fixture_required")
        _required_text(self.encounter_id, CODE_LIMIT)
        if type(self.order_date) is not date:
            raise CurrentDayFactRejected("invalid_key")
        _required_text(self.order_number, CODE_LIMIT)
        _required_text(self.order_sequence, CODE_LIMIT)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCurrentDayChild(_RedactedModel):
    key: CurrentDayOrderKey
    catalog_code: str | None
    catalog_name: str | None
    user_code: str | None
    user_name: str | None
    order_type: str | None
    department_code: str | None
    state: ChildState
    dc_yn: str
    act_yn: str
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayFactRejected("synthetic_fixture_required")
        _exact_model(self.key, CurrentDayOrderKey, "invalid_key")
        self.key.__post_init__(True)
        for name in CHILD_TEXT_FIELDS:
            limit = NAME_LIMIT if name.endswith("name") else CODE_LIMIT
            _nullable_exact_text(getattr(self, name), limit)
        if type(self.state) is not ChildState:
            raise CurrentDayFactRejected("invalid_child_state")
        _flag(self.dc_yn)
        _flag(self.act_yn)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCurrentDayFacts(_RedactedModel):
    clinic_day: date
    parents: tuple[SyntheticCurrentDayParent, ...]
    children: tuple[SyntheticCurrentDayChild, ...]
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayFactRejected("synthetic_fixture_required")
        if type(self.clinic_day) is not date:
            raise CurrentDayFactRejected("invalid_day")
        if (
            type(self.parents) is not tuple
            or type(self.children) is not tuple
            or len(self.parents) > MAX_PARENTS
            or len(self.children) > MAX_CHILDREN
        ):
            raise CurrentDayFactRejected("invalid_row_bound")

        parent_ids: set[str] = set()
        for parent in self.parents:
            _exact_model(parent, SyntheticCurrentDayParent, "invalid_parent")
            parent.__post_init__(True)
            if parent.encounter_id in parent_ids:
                raise CurrentDayFactRejected("duplicate_parent")
            parent_ids.add(parent.encounter_id)

        child_keys: set[CurrentDayOrderKey] = set()
        for child in self.children:
            _exact_model(child, SyntheticCurrentDayChild, "invalid_child")
            child.__post_init__(True)
            if child.key.encounter_id not in parent_ids:
                raise CurrentDayFactRejected("orphan_child")
            if child.key in child_keys:
                raise CurrentDayFactRejected("duplicate_child")
            child_keys.add(child.key)

        object.__setattr__(self, "parents", tuple(sorted(self.parents, key=lambda row: row.encounter_id)))
        object.__setattr__(self, "children", tuple(sorted(self.children, key=lambda row: row.key)))


@dataclass(frozen=True, slots=True, repr=False)
class CurrentDayComparison(_RedactedModel):
    full_replacement: bool
    current: SyntheticCurrentDayFacts
    parent_upserts: tuple[SyntheticCurrentDayParent, ...]
    child_upserts: tuple[SyntheticCurrentDayChild, ...]
    missing_parent_ids: tuple[str, ...]
    missing_child_keys: tuple[CurrentDayOrderKey, ...]


def build_synthetic_parent(row: object, *, synthetic_fixture: bool = False) -> SyntheticCurrentDayParent:
    if synthetic_fixture is not True:
        raise CurrentDayFactRejected("synthetic_fixture_required")
    values = _closed_dict(row, PARENT_FIELDS)
    return SyntheticCurrentDayParent(
        *(values[name] for name in PARENT_FIELDS), synthetic_fixture=True
    )


def build_synthetic_child(row: object, *, synthetic_fixture: bool = False) -> SyntheticCurrentDayChild:
    if synthetic_fixture is not True:
        raise CurrentDayFactRejected("synthetic_fixture_required")
    values = _closed_dict(row, CHILD_FIELDS)
    key_values = _closed_dict(values["key"], KEY_FIELDS)
    key = CurrentDayOrderKey(
        *(key_values[name] for name in KEY_FIELDS), synthetic_fixture=True
    )
    return SyntheticCurrentDayChild(
        key,
        *(values[name] for name in CHILD_TEXT_FIELDS),
        values["state"],
        values["dc_yn"],
        values["act_yn"],
        synthetic_fixture=True,
    )


def validate_synthetic_collection(
    clinic_day: date,
    parents: tuple[SyntheticCurrentDayParent, ...],
    children: tuple[SyntheticCurrentDayChild, ...],
    *,
    synthetic_fixture: bool = False,
) -> SyntheticCurrentDayFacts:
    """Validate one detached synthetic complete fact set; no source authority implied."""

    return SyntheticCurrentDayFacts(
        clinic_day,
        parents,
        children,
        synthetic_fixture=synthetic_fixture,
    )


def compare_synthetic_collections(
    previous: SyntheticCurrentDayFacts | None,
    current: SyntheticCurrentDayFacts,
) -> CurrentDayComparison:
    """Compare two already validated same-day facts without retaining state."""

    _exact_model(current, SyntheticCurrentDayFacts, "invalid_collection")
    current.__post_init__(True)
    if previous is not None:
        _exact_model(previous, SyntheticCurrentDayFacts, "invalid_collection")
        previous.__post_init__(True)
        if previous.clinic_day != current.clinic_day:
            raise CurrentDayFactRejected("scope_mismatch")

    old_parents = {} if previous is None else {
        row.encounter_id: row for row in previous.parents
    }
    old_children = {} if previous is None else {row.key: row for row in previous.children}
    new_parents = {row.encounter_id: row for row in current.parents}
    new_children = {row.key: row for row in current.children}
    return CurrentDayComparison(
        previous is None,
        current,
        tuple(row for key, row in new_parents.items() if old_parents.get(key) != row),
        tuple(row for key, row in new_children.items() if old_children.get(key) != row),
        tuple(sorted(old_parents.keys() - new_parents.keys())),
        tuple(sorted(old_children.keys() - new_children.keys())),
    )
