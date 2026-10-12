"""Independent synthetic current-day facts; no reader, wire or runtime wiring."""

from dataclasses import InitVar, dataclass, fields
from datetime import date
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from unicodedata import category


CONTRACT_ID = "kaosorders.current-day-orders"
CONTRACT_VERSION = 1
PROJECTION_ID = "kaosorders-current-day-orders-v1"
CLINIC_TIMEZONE = "Asia/Seoul"
MAX_ENCOUNTERS = 10_000
MAX_ORDERS = 100_000
CODE_LIMIT = 128
NAME_LIMIT = 256
MAX_DECIMAL_INTEGER_DIGITS = 18
MAX_DECIMAL_SCALE = 12
KEY_FIELDS = ("encounter_id", "order_date", "order_number", "order_sequence")
TEXT_FIELDS = (
    "catalog_code", "catalog_name", "user_code", "user_name", "order_type", "department_code",
)
DECIMAL_FIELDS = ("daily_quantity", "frequency_count", "day_count")
_FORBIDDEN_TEXT = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


class CurrentDayOrdersRejected(ValueError):
    """Only fixed non-identifying validation reasons."""


class _Private:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: redacted>"

    def __str__(self):
        return self.__repr__()


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


def _synthetic(value):
    if value is not True:
        raise CurrentDayOrdersRejected("synthetic_fixture_required")


def _text(value, limit, *, key=False):
    reason = "invalid_order_key" if key else "invalid_order_text"
    if value is None and not key:
        return
    if type(value) is not str or len(value) > limit:
        raise CurrentDayOrdersRejected(reason)
    if key and (not value or value != value.strip()):
        raise CurrentDayOrdersRejected(reason)
    if any(category(char) in _FORBIDDEN_TEXT for char in value):
        raise CurrentDayOrdersRejected(reason)


def _decimal(value):
    if value is None:
        return
    if type(value) is not Decimal or not value.is_finite():
        raise CurrentDayOrdersRejected("invalid_exact_decimal")
    parts = value.as_tuple()
    if (max(len(parts.digits) + parts.exponent, 0) > MAX_DECIMAL_INTEGER_DIGITS
            or max(-parts.exponent, 0) > MAX_DECIMAL_SCALE):
        raise CurrentDayOrdersRejected("invalid_exact_decimal")


def _clone(value, kind, reason):
    names = tuple(field.name for field in fields(kind))
    if type(value) is not kind or not all(hasattr(value, name) for name in names):
        raise CurrentDayOrdersRejected(reason)
    return kind(**{name: getattr(value, name) for name in names}, synthetic_fixture=True)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticDayContext(_Private):
    clinic_day: date
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        if type(self.clinic_day) is not date:
            raise CurrentDayOrdersRejected("invalid_day_context")

    @property
    def contract_id(self):
        return CONTRACT_ID

    @property
    def contract_version(self):
        return CONTRACT_VERSION

    @property
    def projection_id(self):
        return PROJECTION_ID

    @property
    def clinic_timezone(self):
        return CLINIC_TIMEZONE


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticEncounter(_Private):
    encounter_id: str
    state: EncounterState
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        _text(self.encounter_id, CODE_LIMIT, key=True)
        if type(self.state) is not EncounterState:
            raise CurrentDayOrdersRejected("invalid_encounter_state")


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOrderKey(_Private):
    encounter_id: str
    order_date: date
    order_number: str
    order_sequence: str
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        for value in (self.encounter_id, self.order_number, self.order_sequence):
            _text(value, CODE_LIMIT, key=True)
        if type(self.order_date) is not date:
            raise CurrentDayOrdersRejected("invalid_order_key")

    @property
    def value(self):
        return tuple(getattr(self, name) for name in KEY_FIELDS)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOrderQualifiers(_Private):
    dc_yn: Flag
    act_yn: Flag
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        if type(self.dc_yn) is not Flag or type(self.act_yn) is not Flag:
            raise CurrentDayOrdersRejected("invalid_order_qualifiers")


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class SyntheticOrder(_Private):
    key: SyntheticOrderKey
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
    qualifiers: SyntheticOrderQualifiers
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        object.__setattr__(self, "key", _clone(self.key, SyntheticOrderKey, "invalid_order_key"))
        for name in TEXT_FIELDS:
            _text(getattr(self, name), NAME_LIMIT if name.endswith("name") else CODE_LIMIT)
        for name in DECIMAL_FIELDS:
            _decimal(getattr(self, name))
        if type(self.state) is not OrderState:
            raise CurrentDayOrdersRejected("invalid_order_state")
        object.__setattr__(self, "qualifiers", _clone(
            self.qualifiers, SyntheticOrderQualifiers, "invalid_order_qualifiers",
        ))

    def _content(self):
        # Decimal equality alone collapses scale and signed zero observations.
        return (
            self.key,
            *(getattr(self, name) for name in TEXT_FIELDS),
            *(None if getattr(self, name) is None else getattr(self, name).as_tuple()
              for name in DECIMAL_FIELDS),
            self.state, self.qualifiers,
        )

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self._content() == other._content()

    def __hash__(self):
        return hash(self._content())


def _graph(encounters, orders):
    if type(encounters) is not tuple or type(orders) is not tuple:
        raise CurrentDayOrdersRejected("invalid_collection")
    if len(encounters) > MAX_ENCOUNTERS or len(orders) > MAX_ORDERS:
        raise CurrentDayOrdersRejected("invalid_row_bound")
    parents = tuple(_clone(item, SyntheticEncounter, "invalid_encounter") for item in encounters)
    children = tuple(_clone(item, SyntheticOrder, "invalid_order") for item in orders)
    parent_ids = {item.encounter_id for item in parents}
    if len(parent_ids) != len(parents):
        raise CurrentDayOrdersRejected("duplicate_encounter")
    if len({item.key.value for item in children}) != len(children):
        raise CurrentDayOrdersRejected("duplicate_order")
    if any(item.key.encounter_id not in parent_ids for item in children):
        raise CurrentDayOrdersRejected("orphan_order")
    return parents, children


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCollection(_Private):
    context: SyntheticDayContext
    encounters: tuple[SyntheticEncounter, ...]
    orders: tuple[SyntheticOrder, ...]
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        _synthetic(synthetic_fixture)
        context = _clone(self.context, SyntheticDayContext, "invalid_day_context")
        parents, children = _graph(self.encounters, self.orders)
        if any(item.state is EncounterState.CANCELLED for item in parents):
            raise CurrentDayOrdersRejected("invalid_collection")
        parent_keys = tuple(item.encounter_id for item in parents)
        child_keys = tuple(item.key.value for item in children)
        if parent_keys != tuple(sorted(parent_keys)) or child_keys != tuple(sorted(child_keys)):
            raise CurrentDayOrdersRejected("noncanonical_collection")
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "encounters", parents)
        object.__setattr__(self, "orders", children)


def build_synthetic_collection(context, encounters, orders, *, synthetic_fixture=False):
    """Explicit synthetic complete inputs only, not source results or a parser."""
    _synthetic(synthetic_fixture)
    context = _clone(context, SyntheticDayContext, "invalid_day_context")
    parents, children = _graph(encounters, orders)
    # Validate even excluded children before applying the parent scope decision.
    included = {item.encounter_id for item in parents if item.state is not EncounterState.CANCELLED}
    return SyntheticCollection(
        context,
        tuple(sorted((item for item in parents if item.encounter_id in included),
                     key=lambda item: item.encounter_id)),
        tuple(sorted((item for item in children if item.key.encounter_id in included),
                     key=lambda item: item.key.value)),
        synthetic_fixture=True,
    )


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticComparison(_Private):
    encounter_added: int
    encounter_replaced: int
    encounter_removed: int
    order_added: int
    order_replaced: int
    order_removed: int


def compare_synthetic_collections(previous, current):
    """Counts of observed set changes, never clinical events or event times."""
    current = _clone(current, SyntheticCollection, "invalid_collection")
    if previous is not None:
        previous = _clone(previous, SyntheticCollection, "invalid_collection")
        if previous.context != current.context:
            raise CurrentDayOrdersRejected("day_context_changed")
    counts = []
    for attribute in ("encounters", "orders"):
        key = (lambda item: item.encounter_id) if attribute == "encounters" else (lambda item: item.key.value)
        old = {key(item): item for item in getattr(previous, attribute)} if previous is not None else {}
        new = {key(item): item for item in getattr(current, attribute)}
        counts.extend((
            len(new.keys() - old.keys()),
            sum(old[identifier] != new[identifier] for identifier in old.keys() & new.keys()),
            len(old.keys() - new.keys()),
        ))
    return SyntheticComparison(*counts)


class SyntheticCollectionMemory(_Private):
    """One synthetic day's RAM-only proof, without clock/session/transport."""

    def __init__(self, context, *, synthetic_fixture=False):
        _synthetic(synthetic_fixture)
        self._context = _clone(context, SyntheticDayContext, "invalid_day_context")
        self._current = None
        self._lock = Lock()

    def current(self):
        with self._lock:
            return (_clone(self._current, SyntheticCollection, "invalid_collection")
                    if self._current is not None else None)

    def replace(self, encounters, orders, *, synthetic_fixture=False):
        candidate = build_synthetic_collection(
            self._context, encounters, orders, synthetic_fixture=synthetic_fixture,
        )
        with self._lock:
            comparison = compare_synthetic_collections(self._current, candidate)
            self._current = candidate
            return comparison
