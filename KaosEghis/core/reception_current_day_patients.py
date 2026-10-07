"""Pure current-day Reception patient projection; no source reader or I/O.

The production source mapping is documented, but this module deliberately accepts
only explicitly synthetic detached reads until a complete source reader and a
cross-project contract are separately approved.
"""

from dataclasses import InitVar, dataclass, fields
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol
from unicodedata import category
from zoneinfo import ZoneInfo


CLINIC_TIME_ZONE_NAME = "Asia/Seoul"
CLINIC_TIME_ZONE = ZoneInfo(CLINIC_TIME_ZONE_NAME)
PROVIDER_ID = "eghis.reception-current-day-patients"
PROJECTION_ID = "reception-current-day-patients-v1"
MAX_ROWS = 10_000
TEXT_LIMIT = 128


class CurrentDayPatientsRejected(ValueError):
    """Fixed reason codes only; never patient or source values."""


class SourceReadStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class IncludedPatientState(StrEnum):
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"


# Exact operator-confirmed source meanings. None means explicitly excluded.
SOURCE_STATUS_MAPPING = (
    ("10", None),
    ("25", None),
    ("30", IncludedPatientState.CONSULTATION_COMPLETED),
    ("40", IncludedPatientState.PAYMENT_COMPLETED),
)


class _RedactedModel:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


def _aware(value: object) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise CurrentDayPatientsRejected("invalid_time")
    return value


def _text(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > TEXT_LIMIT
        or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise CurrentDayPatientsRejected("invalid_text")
    return value


def _source_status(value: object) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or len(value) > TEXT_LIMIT
        or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise CurrentDayPatientsRejected("invalid_source_status")
    return value


def _exact_model(value: object, kind: type, reason: str) -> None:
    if type(value) is not kind or {item.name for item in fields(value)} != {
        item.name for item in fields(kind)
    }:
        raise CurrentDayPatientsRejected(reason)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticReceptionRow(_RedactedModel):
    clinic_day: date
    selection_id: str
    display_name: str
    source_status_code: str | None
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayPatientsRejected("synthetic_fixture_required")
        if type(self.clinic_day) is not date:
            raise CurrentDayPatientsRejected("invalid_day")
        _text(self.selection_id)
        _text(self.display_name)
        _source_status(self.source_status_code)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticReceptionDayRead(_RedactedModel):
    clinic_day: date
    observed_at: datetime
    status: SourceReadStatus
    rows: tuple[SyntheticReceptionRow, ...]
    whole_day: bool
    untruncated: bool
    consistent_snapshot: bool
    connection_closed: bool
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise CurrentDayPatientsRejected("synthetic_fixture_required")
        if type(self.clinic_day) is not date:
            raise CurrentDayPatientsRejected("invalid_day")
        _aware(self.observed_at)
        if type(self.status) is not SourceReadStatus:
            raise CurrentDayPatientsRejected("invalid_status")
        if type(self.rows) is not tuple or len(self.rows) > MAX_ROWS:
            raise CurrentDayPatientsRejected("invalid_row_bound")
        for row in self.rows:
            _exact_model(row, SyntheticReceptionRow, "invalid_row")
            row.__post_init__(True)
            if row.clinic_day != self.clinic_day:
                raise CurrentDayPatientsRejected("scope_mismatch")
        for flag in (
            self.whole_day,
            self.untruncated,
            self.consistent_snapshot,
            self.connection_closed,
        ):
            if type(flag) is not bool:
                raise CurrentDayPatientsRejected("invalid_completeness")


@dataclass(frozen=True, slots=True, repr=False)
class CurrentDayPatient(_RedactedModel):
    selection_id: str
    display_name: str
    state: IncludedPatientState

    def __post_init__(self) -> None:
        _text(self.selection_id)
        _text(self.display_name)
        if type(self.state) is not IncludedPatientState:
            raise CurrentDayPatientsRejected("invalid_included_state")


@dataclass(frozen=True, slots=True, repr=False)
class CurrentDayPatientList(_RedactedModel):
    source_id: str
    projection_id: str
    clinic_day: date
    observed_at: datetime
    patients: tuple[CurrentDayPatient, ...]


class CurrentDayPatientProvider(Protocol):
    def read_current_day(self, now: datetime) -> CurrentDayPatientList:
        """Return one fresh, complete, detached clinic-local current-day list."""


def build_synthetic_source_row(
    source_row: object, *, synthetic_fixture: bool = False
) -> SyntheticReceptionRow:
    """Apply the reviewed source-field aliases without parsing or source access."""

    if synthetic_fixture is not True:
        raise CurrentDayPatientsRejected("synthetic_fixture_required")
    if type(source_row) is not dict or set(source_row) != {
        "clinic_ymd",
        "recept_no",
        "ptnt_nm",
        "proc_gb",
    }:
        raise CurrentDayPatientsRejected("invalid_fields")
    return SyntheticReceptionRow(
        clinic_day=source_row["clinic_ymd"],
        selection_id=source_row["recept_no"],
        display_name=source_row["ptnt_nm"],
        source_status_code=source_row["proc_gb"],
        synthetic_fixture=True,
    )


def project_synthetic_current_day(
    read: SyntheticReceptionDayRead,
    *,
    now: datetime,
    freshness_limit: timedelta,
    synthetic_fixture: bool = False,
) -> CurrentDayPatientList:
    """Project one fresh complete synthetic read, excluding every unapproved state."""

    if synthetic_fixture is not True:
        raise CurrentDayPatientsRejected("synthetic_fixture_required")
    _exact_model(read, SyntheticReceptionDayRead, "invalid_read")
    read.__post_init__(True)
    current_time = _aware(now)
    if type(freshness_limit) is not timedelta or freshness_limit <= timedelta(0):
        raise CurrentDayPatientsRejected("invalid_freshness")
    clinic_day = current_time.astimezone(CLINIC_TIME_ZONE).date()
    if (
        read.clinic_day != clinic_day
        or read.observed_at.astimezone(CLINIC_TIME_ZONE).date() != clinic_day
    ):
        raise CurrentDayPatientsRejected("not_current_clinic_day")
    age = current_time.astimezone(timezone.utc) - read.observed_at.astimezone(timezone.utc)
    if age < timedelta(0):
        raise CurrentDayPatientsRejected("future_observation")
    if age > freshness_limit:
        raise CurrentDayPatientsRejected("stale_read")
    if read.status is not SourceReadStatus.COMPLETE or not all(
        flag is True
        for flag in (
            read.whole_day,
            read.untruncated,
            read.consistent_snapshot,
            read.connection_closed,
        )
    ):
        raise CurrentDayPatientsRejected("incomplete_read")

    unique: dict[str, SyntheticReceptionRow] = {}
    for row in read.rows:
        prior = unique.get(row.selection_id)
        if prior is not None and prior != row:
            raise CurrentDayPatientsRejected("conflicting_duplicate")
        unique[row.selection_id] = row

    rules = dict(SOURCE_STATUS_MAPPING)
    patients = []
    for selection_id in sorted(unique):
        row = unique[selection_id]
        state = rules.get(row.source_status_code)
        if state is not None:
            patients.append(CurrentDayPatient(selection_id, row.display_name, state))
    return CurrentDayPatientList(
        PROVIDER_ID,
        PROJECTION_ID,
        clinic_day,
        read.observed_at,
        tuple(patients),
    )
