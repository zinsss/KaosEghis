import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from KaosEghis.core import current_day_provider_lifecycle as lifecycle


NOW = datetime(2026, 10, 8, 1, 0, tzinfo=timezone.utc)


def identity(value):
    return lifecycle.OpaqueIdentity(value)


def lease(*, token="lease-a", held=True):
    return lifecycle.SingletonLeaseClaim(identity("scope-a"), identity(token), held)


def owner(*, now=NOW, session="session-a", generation="generation-a", jitter=0):
    return lifecycle.start_provider(
        now=now,
        provider_session_id=identity(session),
        provider_generation=identity(generation),
        lease=lease(),
        stable_jitter_seconds=jitter,
    )


def destination(status, *, count=None, marker=None):
    return lifecycle.DestinationState(status, count, marker)


def candidate(
    *,
    day=date(2026, 10, 8),
    observed_at=NOW,
    orders=None,
    reception=None,
):
    return lifecycle.ObservationCandidate(
        day,
        observed_at,
        orders or destination(lifecycle.ProjectionAvailability.AVAILABLE, count=2, marker=11),
        reception or destination(lifecycle.ProjectionAvailability.AVAILABLE, count=1, marker=21),
    )


def begin(state, *, now=NOW):
    current, ticket = lifecycle.request_refresh(state, now=now)
    assert ticket is not None
    return current, ticket


def publish(state, *, now=NOW, observation=None):
    current, ticket = begin(state, now=now)
    return lifecycle.complete_success(
        current,
        ticket,
        observation or candidate(observed_at=now),
        now=now,
        lease=current.lease,
    )


def test_contract_values_are_literal_and_ids_are_equality_only():
    assert lifecycle.CLINIC_TIME_ZONE_NAME == "Asia/Seoul"
    assert lifecycle.REFRESH_INTERVAL_SECONDS == 60
    assert lifecycle.OBSERVATION_DEADLINE_SECONDS == 10
    assert lifecycle.MAX_STABLE_JITTER_SECONDS == 5
    assert lifecycle.FAILURE_DELAYS_SECONDS == (60, 120, 300)
    assert {item.value for item in lifecycle.ProviderPhase} == {
        "STARTING", "READY", "DEGRADED", "UNAVAILABLE", "STOPPING"
    }
    assert identity("same") == identity("same")
    assert identity("same") != identity("other")
    with pytest.raises(TypeError):
        identity("a") < identity("b")
    assert repr(identity("hidden")) == "<OpaqueIdentity: redacted>"


def test_startup_is_empty_unavailable_and_due_immediately():
    state = owner(jitter=5)
    assert state.phase is lifecycle.ProviderPhase.STARTING
    assert state.reason is lifecycle.ProviderReason.STARTUP
    assert state.snapshot is None
    assert state.next_refresh_at == NOW
    assert state.clinic_day == date(2026, 10, 8)
    assert state.lease.held is True
    assert lifecycle.read_snapshot(state) is None


@pytest.mark.parametrize("jitter", [-1, 6, True, 1.5])
def test_stable_jitter_is_injected_and_bounded(jitter):
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^invalid_state$"):
        owner(jitter=jitter)


def test_refresh_ticket_has_exact_deadline_and_single_flight_coalesces_once():
    active, first = begin(owner(jitter=2))
    assert first.ticket == 1
    assert first.deadline_at - first.started_at == timedelta(seconds=10)
    once, second = lifecycle.request_refresh(active, now=NOW)
    twice, third = lifecycle.request_refresh(once, now=NOW + timedelta(seconds=1))
    assert second is None and third is None
    assert once.successor_pending is True and twice.successor_pending is True
    completed = lifecycle.complete_success(
        twice, first, candidate(), now=NOW + timedelta(seconds=2), lease=twice.lease
    )
    assert completed.next_refresh_at == NOW + timedelta(seconds=2)
    successor, ticket = lifecycle.request_refresh(completed, now=completed.next_refresh_at)
    assert ticket.ticket == 2
    assert successor.in_flight == ticket and successor.successor_pending is False


def test_success_publishes_one_sequence_and_schedules_from_completion():
    completed_at = NOW + timedelta(seconds=3)
    active, ticket = begin(owner(jitter=4))
    result = lifecycle.complete_success(
        active, ticket, candidate(observed_at=NOW), now=completed_at, lease=active.lease
    )
    assert result.phase is lifecycle.ProviderPhase.READY
    assert result.reason is lifecycle.ProviderReason.NONE
    assert result.snapshot.cursor.snapshot_sequence == 1
    assert result.snapshot.cursor.provider_session_id == identity("session-a")
    assert result.snapshot.cursor.provider_generation == identity("generation-a")
    assert result.next_refresh_at == completed_at + timedelta(seconds=64)
    assert result.consecutive_failures == 0


def test_failure_backoff_resets_and_caps_without_in_cycle_retry():
    state = owner(jitter=2)
    expected_delays = (62, 122, 302, 302)
    current_time = NOW
    for failures, expected in enumerate(expected_delays, start=1):
        active, ticket = begin(state, now=current_time)
        finished = current_time + timedelta(seconds=1)
        state = lifecycle.complete_failure(
            active,
            ticket,
            now=finished,
            lease=active.lease,
            reason=lifecycle.ProviderReason.SOURCE_FAILURE,
        )
        assert state.in_flight is None
        assert state.consecutive_failures == failures
        assert state.next_refresh_at == finished + timedelta(seconds=expected)
        current_time = state.next_refresh_at

    active, ticket = begin(state, now=current_time)
    recovered = lifecycle.complete_success(
        active,
        ticket,
        candidate(observed_at=current_time),
        now=current_time,
        lease=active.lease,
    )
    assert recovered.consecutive_failures == 0
    assert recovered.next_refresh_at == current_time + timedelta(seconds=62)


def test_coalesced_trigger_does_not_bypass_failure_backoff():
    active, ticket = begin(owner(jitter=3))
    coalesced, duplicate = lifecycle.request_refresh(active, now=NOW)
    assert duplicate is None and coalesced.successor_pending is True
    failed = lifecycle.complete_failure(
        coalesced,
        ticket,
        now=NOW + timedelta(seconds=1),
        lease=coalesced.lease,
        reason=lifecycle.ProviderReason.SOURCE_FAILURE,
    )
    assert failed.next_refresh_at == NOW + timedelta(seconds=64)
    assert failed.successor_pending is False


def test_completion_after_ten_second_deadline_is_failure_not_publication():
    active, ticket = begin(owner())
    result = lifecycle.complete_success(
        active,
        ticket,
        candidate(),
        now=NOW + timedelta(seconds=10, microseconds=1),
        lease=active.lease,
    )
    assert result.snapshot is None
    assert result.phase is lifecycle.ProviderPhase.UNAVAILABLE
    assert result.reason is lifecycle.ProviderReason.DEADLINE_EXCEEDED
    assert result.consecutive_failures == 1


def test_success_resets_failure_backoff_and_advances_sequence():
    first = publish(owner())
    due = first.next_refresh_at
    active, ticket = begin(first, now=due)
    failed = lifecycle.complete_failure(
        active,
        ticket,
        now=due,
        lease=active.lease,
        reason=lifecycle.ProviderReason.OBSERVATION_INVALID,
    )
    assert failed.snapshot is first.snapshot
    active, ticket = begin(failed, now=failed.next_refresh_at)
    recovered = lifecycle.complete_success(
        active,
        ticket,
        candidate(observed_at=failed.next_refresh_at),
        now=failed.next_refresh_at,
        lease=active.lease,
    )
    assert recovered.snapshot.cursor.snapshot_sequence == 2
    assert recovered.consecutive_failures == 0


def test_kst_midnight_invalidates_before_new_day_and_fences_late_result():
    before_midnight = datetime(2026, 10, 8, 14, 58, 0, tzinfo=timezone.utc)
    state = publish(owner(now=before_midnight), now=before_midnight)
    active, old_ticket = begin(state, now=state.next_refresh_at)
    after_midnight = datetime(2026, 10, 8, 15, 0, 1, tzinfo=timezone.utc)
    rolled = lifecycle.rollover(
        active,
        now=after_midnight,
        provider_generation=identity("generation-b"),
        lease=active.lease,
    )
    assert rolled.clinic_day == date(2026, 10, 9)
    assert rolled.snapshot is None
    assert rolled.phase is lifecycle.ProviderPhase.UNAVAILABLE
    assert rolled.next_refresh_at == after_midnight
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^stale_refresh$"):
        lifecycle.complete_success(
            rolled,
            old_ticket,
            candidate(day=date(2026, 10, 9), observed_at=after_midnight),
            now=after_midnight,
            lease=rolled.lease,
        )


def test_generation_a_b_a_is_rejected_without_ordering_ids():
    before_midnight = datetime(2026, 10, 8, 14, 59, 59, tzinfo=timezone.utc)
    state = owner(now=before_midnight, generation="generation-a")
    day_two = lifecycle.rollover(
        state,
        now=datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc),
        provider_generation=identity("generation-b"),
        lease=state.lease,
    )
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^retired_pair$"):
        lifecycle.rollover(
            day_two,
            now=datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc),
            provider_generation=identity("generation-a"),
            lease=day_two.lease,
        )


def test_restart_ticket_and_wrong_lease_are_final_fenced():
    active, old_ticket = begin(owner())
    restarted = owner(session="session-b", generation="generation-b")
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^stale_refresh$"):
        lifecycle.complete_success(
            restarted, old_ticket, candidate(), now=NOW, lease=restarted.lease
        )
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^lease_fence$"):
        lifecycle.complete_success(
            active, old_ticket, candidate(), now=NOW, lease=lease(token="lease-b")
        )


def test_lease_loss_clears_serving_and_fences_active_work():
    ready = publish(owner())
    active, ticket = begin(ready, now=ready.next_refresh_at)
    lost_claim = replace(active.lease, held=False)
    lost = lifecycle.lose_lease(active, lease=lost_claim)
    assert lost.snapshot is None and lost.in_flight is None
    assert lost.phase is lifecycle.ProviderPhase.UNAVAILABLE
    assert lost.reason is lifecycle.ProviderReason.LEASE_UNAVAILABLE
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^lease_fence$"):
        lifecycle.complete_success(
            lost,
            ticket,
            candidate(observed_at=ready.next_refresh_at),
            now=ready.next_refresh_at,
            lease=lost.lease,
        )


def test_verified_empty_is_a_success_not_unavailable():
    empty = destination(lifecycle.ProjectionAvailability.VERIFIED_EMPTY, count=0, marker=0)
    result = publish(owner(), observation=candidate(orders=empty, reception=empty))
    assert result.phase is lifecycle.ProviderPhase.READY
    assert result.snapshot.orders.availability is lifecycle.ProjectionAvailability.VERIFIED_EMPTY
    assert result.snapshot.reception.availability is lifecycle.ProjectionAvailability.VERIFIED_EMPTY
    assert result.snapshot.orders.item_count == 0


def test_destination_validation_failure_isolated_on_one_common_sequence():
    unavailable = destination(lifecycle.ProjectionAvailability.UNAVAILABLE)
    available = destination(lifecycle.ProjectionAvailability.AVAILABLE, count=1, marker=31)
    result = publish(owner(), observation=candidate(orders=unavailable, reception=available))
    assert result.phase is lifecycle.ProviderPhase.DEGRADED
    assert result.reason is lifecycle.ProviderReason.PROJECTION_INVALID
    assert result.snapshot.cursor.snapshot_sequence == 1
    assert result.snapshot.orders.availability is lifecycle.ProjectionAvailability.UNAVAILABLE
    assert result.snapshot.reception.availability is lifecycle.ProjectionAvailability.AVAILABLE


def test_atomic_replacement_leaves_old_state_and_snapshot_unchanged():
    first = publish(owner())
    old_snapshot = lifecycle.read_snapshot(first)
    due = first.next_refresh_at
    active, ticket = begin(first, now=due)
    second = lifecycle.complete_success(
        active,
        ticket,
        candidate(
            observed_at=due,
            orders=destination(lifecycle.ProjectionAvailability.AVAILABLE, count=3, marker=12),
        ),
        now=due,
        lease=active.lease,
    )
    assert lifecycle.read_snapshot(first) is old_snapshot
    assert old_snapshot.orders.content_marker == 11
    assert lifecycle.read_snapshot(second).orders.content_marker == 12
    assert lifecycle.read_snapshot(second).cursor.snapshot_sequence == 2
    with pytest.raises(FrozenInstanceError):
        second.snapshot.orders.item_count = 99


def test_state_rejects_mixed_cursor_ticket_and_successor_invariants():
    ready = publish(owner())
    wrong_cursor = replace(
        ready.snapshot.cursor, provider_generation=identity("generation-other")
    )
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^invalid_state$"):
        replace(ready, snapshot=replace(ready.snapshot, cursor=wrong_cursor))
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^invalid_state$"):
        replace(ready, successor_pending=True)


def test_sequence_retry_conflict_regression_and_new_generation_are_explicit():
    current = publish(owner()).snapshot
    assert lifecycle.snapshot_disposition(
        current, current, retired_pairs=frozenset()
    ) is lifecycle.SnapshotDisposition.IDEMPOTENT_RETRY
    conflict = replace(
        current,
        orders=destination(lifecycle.ProjectionAvailability.AVAILABLE, count=9, marker=99),
    )
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^sequence_conflict$"):
        lifecycle.snapshot_disposition(current, conflict, retired_pairs=frozenset())
    regression = replace(current, cursor=replace(current.cursor, snapshot_sequence=1))
    newer_current = replace(current, cursor=replace(current.cursor, snapshot_sequence=2))
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^sequence_regression$"):
        lifecycle.snapshot_disposition(newer_current, regression, retired_pairs=frozenset())
    new_generation = replace(
        current,
        cursor=replace(current.cursor, provider_generation=identity("generation-b")),
    )
    assert lifecycle.snapshot_disposition(
        current, new_generation, retired_pairs=frozenset()
    ) is lifecycle.SnapshotDisposition.NEW_GENERATION
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^retired_pair$"):
        lifecycle.snapshot_disposition(
            current, new_generation, retired_pairs=frozenset({new_generation.cursor.pair})
        )


def test_shutdown_stops_admission_and_drops_all_references():
    ready = publish(owner())
    active, _ticket = begin(ready, now=ready.next_refresh_at)
    stopped = lifecycle.shutdown(active)
    assert stopped.phase is lifecycle.ProviderPhase.STOPPING
    assert stopped.reason is lifecycle.ProviderReason.SHUTDOWN
    assert stopped.snapshot is None and stopped.in_flight is None
    assert stopped.next_refresh_at is None and stopped.lease.held is False
    with pytest.raises(lifecycle.ProviderLifecycleRejected, match="^stopping$"):
        lifecycle.request_refresh(stopped, now=NOW)


def test_models_errors_and_module_boundary_are_redacted_and_io_free():
    state = owner()
    assert repr(state) == "<ProviderState: redacted>"
    assert repr(state.lease) == "<SingletonLeaseClaim: redacted>"
    with pytest.raises(lifecycle.ProviderLifecycleRejected) as error:
        lifecycle.OpaqueIdentity("private\nmarker")
    assert str(error.value) == "invalid_identity"
    assert "private" not in repr(error.value)

    source_path = Path(lifecycle.__file__)
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports <= {"dataclasses", "datetime", "enum", "unicodedata", "zoneinfo"}
    assert not imports.intersection(
        {
            "asyncio", "http", "logging", "os", "pathlib", "psycopg2", "requests",
            "socket", "sqlite3", "subprocess", "threading",
        }
    )
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called_names.intersection({"open", "print", "exec", "eval", "compile"})
    for forbidden in (
        "run_readonly_query", "Authorization", "Bearer ", "QTimer", "EghisSourceDayReader"
    ):
        assert forbidden not in text
