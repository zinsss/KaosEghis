"""Pure volatile current-day provider lifecycle model.

This module contains immutable state and deterministic transitions only. It does
not read a source, acquire an OS lease, schedule a thread, serialize a response,
authenticate, persist, log, bind a socket, or mount runtime behavior.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from unicodedata import category
from zoneinfo import ZoneInfo


CLINIC_TIME_ZONE_NAME = "Asia/Seoul"
CLINIC_TIME_ZONE = ZoneInfo(CLINIC_TIME_ZONE_NAME)
IDENTITY_LIMIT = 128
MAX_COUNTER = (1 << 63) - 1
REFRESH_INTERVAL_SECONDS = 60
OBSERVATION_DEADLINE_SECONDS = 10
MAX_STABLE_JITTER_SECONDS = 5
FAILURE_DELAYS_SECONDS = (60, 120, 300)


class ProviderLifecycleRejected(ValueError):
    """A fixed nonclinical lifecycle rejection reason."""


class ProviderPhase(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STOPPING = "STOPPING"


class ProviderReason(StrEnum):
    NONE = "NONE"
    STARTUP = "STARTUP"
    DAY_ROLLOVER = "DAY_ROLLOVER"
    SOURCE_FAILURE = "SOURCE_FAILURE"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CLEANUP_UNCERTAIN = "CLEANUP_UNCERTAIN"
    OBSERVATION_INVALID = "OBSERVATION_INVALID"
    PROJECTION_INVALID = "PROJECTION_INVALID"
    LEASE_UNAVAILABLE = "LEASE_UNAVAILABLE"
    SHUTDOWN = "SHUTDOWN"


class ProjectionAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    VERIFIED_EMPTY = "VERIFIED_EMPTY"
    UNAVAILABLE = "UNAVAILABLE"


class SnapshotDisposition(StrEnum):
    NEWER = "NEWER"
    NEW_GENERATION = "NEW_GENERATION"
    IDEMPOTENT_RETRY = "IDEMPOTENT_RETRY"


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


def _fixed_text(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > IDENTITY_LIMIT
        or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise ProviderLifecycleRejected("invalid_identity")
    return value


def _aware(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ProviderLifecycleRejected("invalid_time")
    return value


def _positive_counter(value: object, reason: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_COUNTER:
        raise ProviderLifecycleRejected(reason)
    return value


def clinic_day_at(now: datetime) -> date:
    """Resolve the current clinic day from an injected aware clock value."""

    return _aware(now).astimezone(CLINIC_TIME_ZONE).date()


@dataclass(frozen=True, slots=True, repr=False)
class OpaqueIdentity(_Redacted):
    """Equality-only opaque identity; no ordering or chronology is defined."""

    value: str

    def __post_init__(self) -> None:
        _fixed_text(self.value)


@dataclass(frozen=True, slots=True, repr=False)
class SingletonLeaseClaim(_Redacted):
    scope: OpaqueIdentity
    token: OpaqueIdentity
    held: bool

    def __post_init__(self) -> None:
        if type(self.scope) is not OpaqueIdentity or type(self.token) is not OpaqueIdentity:
            raise ProviderLifecycleRejected("invalid_lease")
        if type(self.held) is not bool:
            raise ProviderLifecycleRejected("invalid_lease")


@dataclass(frozen=True, slots=True, repr=False)
class DestinationState(_Redacted):
    availability: ProjectionAvailability
    item_count: int | None
    content_marker: int | None

    def __post_init__(self) -> None:
        if type(self.availability) is not ProjectionAvailability:
            raise ProviderLifecycleRejected("invalid_projection")
        if self.availability is ProjectionAvailability.AVAILABLE:
            if (
                type(self.item_count) is not int
                or self.item_count <= 0
                or type(self.content_marker) is not int
                or self.content_marker <= 0
            ):
                raise ProviderLifecycleRejected("invalid_projection")
        elif self.availability is ProjectionAvailability.VERIFIED_EMPTY:
            if self.item_count != 0 or self.content_marker != 0:
                raise ProviderLifecycleRejected("invalid_projection")
        elif self.item_count is not None or self.content_marker is not None:
            raise ProviderLifecycleRejected("invalid_projection")


@dataclass(frozen=True, slots=True, repr=False)
class ObservationCandidate(_Redacted):
    clinic_day: date
    observed_at: datetime
    orders: DestinationState
    reception: DestinationState

    def __post_init__(self) -> None:
        if type(self.clinic_day) is not date:
            raise ProviderLifecycleRejected("invalid_day")
        _aware(self.observed_at)
        if (
            type(self.orders) is not DestinationState
            or type(self.reception) is not DestinationState
        ):
            raise ProviderLifecycleRejected("invalid_projection")


@dataclass(frozen=True, slots=True, repr=False)
class ProviderCursor(_Redacted):
    provider_session_id: OpaqueIdentity
    provider_generation: OpaqueIdentity
    clinic_day: date
    snapshot_sequence: int

    def __post_init__(self) -> None:
        if (
            type(self.provider_session_id) is not OpaqueIdentity
            or type(self.provider_generation) is not OpaqueIdentity
            or type(self.clinic_day) is not date
        ):
            raise ProviderLifecycleRejected("invalid_cursor")
        _positive_counter(self.snapshot_sequence, "invalid_sequence")

    @property
    def pair(self) -> tuple[OpaqueIdentity, OpaqueIdentity]:
        return self.provider_session_id, self.provider_generation


@dataclass(frozen=True, slots=True, repr=False)
class ProviderSnapshot(_Redacted):
    cursor: ProviderCursor
    observed_at: datetime
    orders: DestinationState
    reception: DestinationState

    def __post_init__(self) -> None:
        if type(self.cursor) is not ProviderCursor:
            raise ProviderLifecycleRejected("invalid_snapshot")
        _aware(self.observed_at)
        if (
            type(self.orders) is not DestinationState
            or type(self.reception) is not DestinationState
        ):
            raise ProviderLifecycleRejected("invalid_snapshot")


@dataclass(frozen=True, slots=True, repr=False)
class RefreshTicket(_Redacted):
    provider_session_id: OpaqueIdentity
    provider_generation: OpaqueIdentity
    clinic_day: date
    ticket: int
    lease_token: OpaqueIdentity
    started_at: datetime
    deadline_at: datetime

    def __post_init__(self) -> None:
        if (
            type(self.provider_session_id) is not OpaqueIdentity
            or type(self.provider_generation) is not OpaqueIdentity
            or type(self.clinic_day) is not date
            or type(self.lease_token) is not OpaqueIdentity
        ):
            raise ProviderLifecycleRejected("invalid_ticket")
        _positive_counter(self.ticket, "invalid_ticket")
        start = _aware(self.started_at)
        deadline = _aware(self.deadline_at)
        if deadline - start != timedelta(seconds=OBSERVATION_DEADLINE_SECONDS):
            raise ProviderLifecycleRejected("invalid_ticket")


@dataclass(frozen=True, slots=True, repr=False)
class ProviderState(_Redacted):
    provider_session_id: OpaqueIdentity
    provider_generation: OpaqueIdentity
    clinic_day: date
    lease: SingletonLeaseClaim
    stable_jitter_seconds: int
    phase: ProviderPhase
    reason: ProviderReason
    snapshot: ProviderSnapshot | None
    in_flight: RefreshTicket | None
    successor_pending: bool
    next_ticket: int
    consecutive_failures: int
    next_refresh_at: datetime | None
    retired_pairs: frozenset[tuple[OpaqueIdentity, OpaqueIdentity]]

    def __post_init__(self) -> None:
        if (
            type(self.provider_session_id) is not OpaqueIdentity
            or type(self.provider_generation) is not OpaqueIdentity
            or type(self.clinic_day) is not date
            or type(self.lease) is not SingletonLeaseClaim
            or type(self.phase) is not ProviderPhase
            or type(self.reason) is not ProviderReason
            or type(self.successor_pending) is not bool
            or type(self.retired_pairs) is not frozenset
        ):
            raise ProviderLifecycleRejected("invalid_state")
        if (
            type(self.stable_jitter_seconds) is not int
            or not 0 <= self.stable_jitter_seconds <= MAX_STABLE_JITTER_SECONDS
            or type(self.consecutive_failures) is not int
            or self.consecutive_failures < 0
        ):
            raise ProviderLifecycleRejected("invalid_state")
        _positive_counter(self.next_ticket, "invalid_state")
        if self.snapshot is not None and type(self.snapshot) is not ProviderSnapshot:
            raise ProviderLifecycleRejected("invalid_state")
        if self.in_flight is not None and type(self.in_flight) is not RefreshTicket:
            raise ProviderLifecycleRejected("invalid_state")
        if self.next_refresh_at is not None:
            _aware(self.next_refresh_at)
        if self.pair in self.retired_pairs or any(
            type(pair) is not tuple
            or len(pair) != 2
            or any(type(item) is not OpaqueIdentity for item in pair)
            for pair in self.retired_pairs
        ):
            raise ProviderLifecycleRejected("invalid_state")
        if self.snapshot is not None and (
            self.snapshot.cursor.provider_session_id != self.provider_session_id
            or self.snapshot.cursor.provider_generation != self.provider_generation
            or self.snapshot.cursor.clinic_day != self.clinic_day
        ):
            raise ProviderLifecycleRejected("invalid_state")
        if self.in_flight is not None and (
            self.in_flight.provider_session_id != self.provider_session_id
            or self.in_flight.provider_generation != self.provider_generation
            or self.in_flight.clinic_day != self.clinic_day
            or self.in_flight.lease_token != self.lease.token
            or self.in_flight.ticket >= self.next_ticket
        ):
            raise ProviderLifecycleRejected("invalid_state")
        if self.successor_pending and self.in_flight is None:
            raise ProviderLifecycleRejected("invalid_state")
        if self.phase is ProviderPhase.STOPPING and (
            self.lease.held
            or self.snapshot is not None
            or self.in_flight is not None
            or self.next_refresh_at is not None
        ):
            raise ProviderLifecycleRejected("invalid_state")

    @property
    def pair(self) -> tuple[OpaqueIdentity, OpaqueIdentity]:
        return self.provider_session_id, self.provider_generation


def start_provider(
    *,
    now: datetime,
    provider_session_id: OpaqueIdentity,
    provider_generation: OpaqueIdentity,
    lease: SingletonLeaseClaim,
    stable_jitter_seconds: int,
) -> ProviderState:
    """Create one unavailable owner session with an immediate refresh due."""

    current = _aware(now)
    if (
        type(provider_session_id) is not OpaqueIdentity
        or type(provider_generation) is not OpaqueIdentity
    ):
        raise ProviderLifecycleRejected("invalid_identity")
    if type(lease) is not SingletonLeaseClaim or lease.held is not True:
        raise ProviderLifecycleRejected("lease_unavailable")
    return ProviderState(
        provider_session_id=provider_session_id,
        provider_generation=provider_generation,
        clinic_day=clinic_day_at(current),
        lease=lease,
        stable_jitter_seconds=stable_jitter_seconds,
        phase=ProviderPhase.STARTING,
        reason=ProviderReason.STARTUP,
        snapshot=None,
        in_flight=None,
        successor_pending=False,
        next_ticket=1,
        consecutive_failures=0,
        next_refresh_at=current,
        retired_pairs=frozenset(),
    )


def request_refresh(
    state: ProviderState, *, now: datetime
) -> tuple[ProviderState, RefreshTicket | None]:
    """Start one due cycle or coalesce a trigger behind the active cycle."""

    current = _aware(now)
    if state.phase is ProviderPhase.STOPPING:
        raise ProviderLifecycleRejected("stopping")
    if state.lease.held is not True:
        raise ProviderLifecycleRejected("lease_unavailable")
    if clinic_day_at(current) != state.clinic_day:
        raise ProviderLifecycleRejected("day_rollover_required")
    if state.in_flight is not None:
        return replace(state, successor_pending=True), None
    if state.next_refresh_at is None or current < state.next_refresh_at:
        raise ProviderLifecycleRejected("refresh_not_due")
    if state.next_ticket >= MAX_COUNTER:
        raise ProviderLifecycleRejected("ticket_exhausted")
    ticket = RefreshTicket(
        state.provider_session_id,
        state.provider_generation,
        state.clinic_day,
        state.next_ticket,
        state.lease.token,
        current,
        current + timedelta(seconds=OBSERVATION_DEADLINE_SECONDS),
    )
    return replace(state, in_flight=ticket, next_ticket=state.next_ticket + 1), ticket


def rollover(
    state: ProviderState,
    *,
    now: datetime,
    provider_generation: OpaqueIdentity,
    lease: SingletonLeaseClaim,
) -> ProviderState:
    """Invalidate the old clinic day before making a new day refreshable."""

    current = _aware(now)
    new_day = clinic_day_at(current)
    _require_lease(state, lease)
    if state.phase is ProviderPhase.STOPPING:
        raise ProviderLifecycleRejected("stopping")
    if new_day == state.clinic_day:
        raise ProviderLifecycleRejected("rollover_not_required")
    if new_day < state.clinic_day:
        raise ProviderLifecycleRejected("day_regression")
    if type(provider_generation) is not OpaqueIdentity:
        raise ProviderLifecycleRejected("invalid_identity")
    new_pair = (state.provider_session_id, provider_generation)
    retired = state.retired_pairs | {state.pair}
    if new_pair == state.pair or new_pair in retired:
        raise ProviderLifecycleRejected("retired_pair")
    return replace(
        state,
        provider_generation=provider_generation,
        clinic_day=new_day,
        phase=ProviderPhase.UNAVAILABLE,
        reason=ProviderReason.DAY_ROLLOVER,
        snapshot=None,
        in_flight=None,
        successor_pending=False,
        next_ticket=1,
        consecutive_failures=0,
        next_refresh_at=current,
        retired_pairs=frozenset(retired),
    )


def complete_success(
    state: ProviderState,
    ticket: RefreshTicket,
    candidate: ObservationCandidate,
    *,
    now: datetime,
    lease: SingletonLeaseClaim,
) -> ProviderState:
    """Publish one complete immutable candidate with one atomic state replacement."""

    current = _aware(now)
    _require_final_fence(state, ticket, current, lease)
    if current > ticket.deadline_at:
        return _finish_failure(state, current, ProviderReason.DEADLINE_EXCEEDED)
    if type(candidate) is not ObservationCandidate:
        raise ProviderLifecycleRejected("invalid_candidate")
    if (
        candidate.clinic_day != state.clinic_day
        or clinic_day_at(candidate.observed_at) != state.clinic_day
        or candidate.observed_at > current
    ):
        raise ProviderLifecycleRejected("candidate_scope_mismatch")
    previous_sequence = 0 if state.snapshot is None else state.snapshot.cursor.snapshot_sequence
    if previous_sequence >= MAX_COUNTER:
        raise ProviderLifecycleRejected("sequence_exhausted")
    cursor = ProviderCursor(
        state.provider_session_id,
        state.provider_generation,
        state.clinic_day,
        previous_sequence + 1,
    )
    snapshot = ProviderSnapshot(
        cursor, candidate.observed_at, candidate.orders, candidate.reception
    )
    available = sum(
        item.availability is not ProjectionAvailability.UNAVAILABLE
        for item in (candidate.orders, candidate.reception)
    )
    phase = ProviderPhase.READY if available == 2 else (
        ProviderPhase.DEGRADED if available == 1 else ProviderPhase.UNAVAILABLE
    )
    reason = ProviderReason.NONE if available == 2 else ProviderReason.PROJECTION_INVALID
    next_refresh = current if state.successor_pending else current + timedelta(
        seconds=REFRESH_INTERVAL_SECONDS + state.stable_jitter_seconds
    )
    return replace(
        state,
        phase=phase,
        reason=reason,
        snapshot=snapshot,
        in_flight=None,
        successor_pending=False,
        consecutive_failures=0,
        next_refresh_at=next_refresh,
    )


def complete_failure(
    state: ProviderState,
    ticket: RefreshTicket,
    *,
    now: datetime,
    lease: SingletonLeaseClaim,
    reason: ProviderReason,
) -> ProviderState:
    """Finish one failed cycle without replacing the active immutable snapshot."""

    current = _aware(now)
    _require_final_fence(state, ticket, current, lease)
    if reason not in {
        ProviderReason.SOURCE_FAILURE,
        ProviderReason.DEADLINE_EXCEEDED,
        ProviderReason.CLEANUP_UNCERTAIN,
        ProviderReason.OBSERVATION_INVALID,
    }:
        raise ProviderLifecycleRejected("invalid_failure_reason")
    if current > ticket.deadline_at:
        reason = ProviderReason.DEADLINE_EXCEEDED
    return _finish_failure(state, current, reason)


def lose_lease(state: ProviderState, *, lease: SingletonLeaseClaim) -> ProviderState:
    """Fail closed when the injected singleton lease is no longer held."""

    if type(lease) is not SingletonLeaseClaim or lease.token != state.lease.token or lease.held:
        raise ProviderLifecycleRejected("invalid_lease_loss")
    return replace(
        state,
        lease=lease,
        phase=ProviderPhase.UNAVAILABLE,
        reason=ProviderReason.LEASE_UNAVAILABLE,
        snapshot=None,
        in_flight=None,
        successor_pending=False,
        next_refresh_at=None,
    )


def shutdown(state: ProviderState) -> ProviderState:
    """Stop admission/serving and drop all volatile references."""

    return replace(
        state,
        lease=replace(state.lease, held=False),
        phase=ProviderPhase.STOPPING,
        reason=ProviderReason.SHUTDOWN,
        snapshot=None,
        in_flight=None,
        successor_pending=False,
        next_refresh_at=None,
    )


def read_snapshot(state: ProviderState) -> ProviderSnapshot | None:
    """Return the current immutable reference; callers observe old or new, never mixed."""

    return state.snapshot


def snapshot_disposition(
    current: ProviderSnapshot | None,
    incoming: ProviderSnapshot,
    *,
    retired_pairs: frozenset[tuple[OpaqueIdentity, OpaqueIdentity]],
) -> SnapshotDisposition:
    """Classify a complete snapshot without ordering opaque identities."""

    if type(incoming) is not ProviderSnapshot or type(retired_pairs) is not frozenset:
        raise ProviderLifecycleRejected("invalid_snapshot")
    if incoming.cursor.pair in retired_pairs:
        raise ProviderLifecycleRejected("retired_pair")
    if current is None:
        return SnapshotDisposition.NEWER
    if type(current) is not ProviderSnapshot:
        raise ProviderLifecycleRejected("invalid_snapshot")
    if incoming.cursor.clinic_day != current.cursor.clinic_day:
        raise ProviderLifecycleRejected("scope_mismatch")
    if incoming.cursor.pair != current.cursor.pair:
        return SnapshotDisposition.NEW_GENERATION
    if incoming.cursor.snapshot_sequence < current.cursor.snapshot_sequence:
        raise ProviderLifecycleRejected("sequence_regression")
    if incoming.cursor.snapshot_sequence == current.cursor.snapshot_sequence:
        if incoming == current:
            return SnapshotDisposition.IDEMPOTENT_RETRY
        raise ProviderLifecycleRejected("sequence_conflict")
    return SnapshotDisposition.NEWER


def _require_lease(state: ProviderState, lease: SingletonLeaseClaim) -> None:
    if (
        type(lease) is not SingletonLeaseClaim
        or lease.held is not True
        or state.lease.held is not True
        or lease != state.lease
    ):
        raise ProviderLifecycleRejected("lease_fence")


def _require_final_fence(
    state: ProviderState,
    ticket: RefreshTicket,
    now: datetime,
    lease: SingletonLeaseClaim,
) -> None:
    _require_lease(state, lease)
    if state.phase is ProviderPhase.STOPPING:
        raise ProviderLifecycleRejected("stopping")
    if type(ticket) is not RefreshTicket or state.in_flight != ticket:
        raise ProviderLifecycleRejected("stale_refresh")
    if (
        ticket.provider_session_id != state.provider_session_id
        or ticket.provider_generation != state.provider_generation
        or ticket.clinic_day != state.clinic_day
        or ticket.lease_token != state.lease.token
    ):
        raise ProviderLifecycleRejected("stale_refresh")
    if clinic_day_at(now) != state.clinic_day:
        raise ProviderLifecycleRejected("day_rollover_required")


def _finish_failure(state: ProviderState, now: datetime, reason: ProviderReason) -> ProviderState:
    failures = state.consecutive_failures + 1
    delay = FAILURE_DELAYS_SECONDS[min(failures - 1, len(FAILURE_DELAYS_SECONDS) - 1)]
    next_refresh = now + timedelta(seconds=delay + state.stable_jitter_seconds)
    phase = ProviderPhase.DEGRADED if state.snapshot is not None else ProviderPhase.UNAVAILABLE
    return replace(
        state,
        phase=phase,
        reason=reason,
        in_flight=None,
        successor_pending=False,
        consecutive_failures=failures,
        next_refresh_at=next_refresh,
    )
