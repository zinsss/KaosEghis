import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from KaosEghis.core.emr_source import (
    EghisSourceDayReader, EmrDayRead, EncounterFacts, OrderFacts, OrderState,
    ReadStatus, ReceptionState, SnapshotRejected, SourcePolicy, normalize_source_day,
)
from KaosEghis.core.emr_source_shadow import SourceLedger


@pytest.fixture
def policy():
    return SourcePolicy(
        "synthetic-v1",
        tuple((f"TEST_{state.value}", state) for state in ReceptionState),
        tuple((f"TEST_{state.value}", state) for state in OrderState),
    )


@pytest.fixture
def read():
    day = date(2026, 10, 1)
    return EmrDayRead(
        source_id="fixture-clinic", projection_id="fixture-all-orders-v1",
        clinic_day=day, observed_at=datetime.fromisoformat("2026-10-01T09:00:00+09:00"),
        status=ReadStatus.COMPLETE,
        encounters=({"encounter_id": "fixture-visit", "chart_no": "TEST-0001",
                     "patient_name": "Synthetic patient", "sex": "F", "age": 53,
                     "state_code": "TEST_ON_HOLD", "qualifiers": {"hold_yn": "N", "hold_opd": "N"}},),
        orders=({"encounter_id": "fixture-visit", "order_date": day,
                 "order_number": "1", "order_sequence": "1", "order_code": "TEST_DRUG",
                 "order_type": "TEST_INJECTION", "department_code": "TEST_INJ",
                 "state_code": "TEST_ACTIVE", "qualifiers": {"dc_yn": "N", "act_yn": "N"},
                 "quantity": "1.00", "days": 1, "frequency": 1},
                {"encounter_id": "fixture-visit", "order_date": day,
                 "order_number": "2", "order_sequence": "1", "order_code": "TEST_FEE",
                 "order_type": "TEST_FEE", "department_code": "", "state_code": "TEST_ACTIVE",
                 "qualifiers": {"dc_yn": "N", "act_yn": "N"}}),
        keys_verified=True, states_verified=True, whole_day=True, untruncated=True,
        consistent_snapshot=True, connection_closed=True, structured_fields_verified=True,
    )


def advance(read, *, encounter=None, order=None, **kwargs):
    encounters, orders = deepcopy(read.encounters), deepcopy(read.orders)
    if encounter:
        encounters[0].update(encounter)
    if order:
        orders[0].update(order)
    return replace(read, observed_at=read.observed_at + timedelta(seconds=30),
                   **dict({"encounters": encounters, "orders": orders}, **kwargs))


def baseline(read, policy):
    ledger = SourceLedger()
    ledger.observe(read, policy)
    return ledger


def test_neutral_snapshot_preserves_source_facts_fees_and_no_order_encounters(read, policy):
    no_order = dict(read.encounters[0], encounter_id="fixture-empty")
    snapshot = normalize_source_day(replace(read, encounters=read.encounters + (no_order,)), policy)
    assert len(snapshot.encounters) == 2 and len(snapshot.orders) == 2
    assert snapshot.orders[1].order_code == "TEST_FEE"
    assert snapshot.orders[1].department_code == ""
    assert snapshot.orders[0].source_state_code == "TEST_ACTIVE"
    assert snapshot.orders[0].quantity == Decimal("1")
    assert not {"category", "display_spec", "board_eligible"} & {field.name for field in fields(OrderFacts)}
    assert not hasattr(snapshot.encounters[0], "board_eligible")


@pytest.mark.parametrize("state", list(ReceptionState))
def test_all_reception_states_preserve_active_child_orders(read, policy, state):
    source = advance(read, encounter={"state_code": f"TEST_{state.value}"})
    snapshot = normalize_source_day(source, policy)
    assert snapshot.encounters[0].state is state
    assert snapshot.encounters[0].source_state_code == f"TEST_{state.value}"
    assert len(snapshot.orders) == 2
    assert all(order.state is OrderState.ACTIVE for order in snapshot.orders)


def test_clinical_completion_and_payment_are_distinct_without_guessing_production_codes(read, policy):
    completed = normalize_source_day(advance(read, encounter={"state_code": "TEST_CONSULTATION_COMPLETED"}), policy)
    paid = normalize_source_day(advance(read, encounter={"state_code": "TEST_PAYMENT_COMPLETED"}), policy)
    assert completed.encounters[0].state != paid.encounters[0].state
    assert not hasattr(ReceptionState, "CLOSED")
    for code in ("30", "40"):
        with pytest.raises(SnapshotRejected, match="unknown_reception_state"):
            normalize_source_day(advance(read, encounter={"state_code": code}), policy)


def test_cancel_restore_and_return_to_hold_are_source_updates_not_child_cancellations(read, policy):
    ledger = baseline(read, policy)
    for state in (ReceptionState.CONSULTATION_COMPLETED, ReceptionState.PAYMENT_COMPLETED,
                  ReceptionState.ON_HOLD, ReceptionState.CANCELLED,
                  ReceptionState.REGISTERED, ReceptionState.ON_HOLD):
        read = advance(read, encounter={"state_code": f"TEST_{state.value}"})
        change = ledger.observe(read, policy)
        assert change.encounter_upserts[0].state is state
        assert not change.order_upserts and not change.missing_order_keys
        assert not change.missing_encounter_ids
        assert all(order.state is OrderState.ACTIVE for order in change.snapshot.orders)


@pytest.mark.parametrize("field,value", [("quantity", "2.25"), ("days", 5), ("frequency", "3"),
                                        ("order_code", "TEST_OTHER"), ("order_type", "TEST_NEW"),
                                        ("department_code", "TEST_LAB")])
def test_same_key_edits_detected_while_patient_remains_paid(read, policy, field, value):
    read = advance(read, encounter={"state_code": "TEST_PAYMENT_COMPLETED"})
    ledger = baseline(read, policy)
    change = ledger.observe(advance(read, order={field: value}), policy)
    assert len(change.order_upserts) == 1 and not change.encounter_upserts
    assert change.order_upserts[0].key == change.snapshot.orders[0].key
    assert not change.missing_order_keys


def test_source_removal_return_and_key_replacement_never_infer_lifetime_identity(read, policy):
    ledger = baseline(read, policy)
    removed_read = advance(read, orders=read.orders[1:])
    removal = ledger.observe(removed_read, policy)
    assert len(removal.missing_order_keys) == 1 and not removal.missing_encounter_ids
    restored = advance(read, order={"order_code": "TEST_REPLACEMENT", "order_type": "TEST_LAB"})
    restored = replace(restored, observed_at=removed_read.observed_at + timedelta(seconds=30))
    change = ledger.observe(restored, policy)
    assert change.order_upserts[0].key == removal.missing_order_keys[0]
    assert change.order_upserts[0].order_code == "TEST_REPLACEMENT"
    assert not change.missing_order_keys
    assert not hasattr(change.order_upserts[0], "lifetime_id")


def test_explicit_order_cancellation_and_disappearance_are_different(read, policy):
    ledger = baseline(read, policy)
    cancelled = advance(read, order={"state_code": "TEST_CANCELLED"})
    change = ledger.observe(cancelled, policy)
    assert change.order_upserts[0].state is OrderState.CANCELLED
    assert not change.missing_order_keys
    change = ledger.observe(advance(cancelled, orders=()), policy)
    assert len(change.missing_order_keys) == 2
    assert not change.missing_encounter_ids
    assert change.snapshot.encounters[0].state is ReceptionState.ON_HOLD


def test_reception_removal_reports_missing_parent_and_orders_not_cancel_events(read, policy):
    change = baseline(read, policy).observe(advance(read, encounters=(), orders=()), policy)
    assert change.missing_encounter_ids == ("fixture-visit",)
    assert len(change.missing_order_keys) == 2 and not change.encounter_upserts
    assert not hasattr(change, "encounter_withdrawals")


@pytest.mark.parametrize("status", [status for status in ReadStatus if status is not ReadStatus.COMPLETE])
def test_failed_read_preserves_baseline_and_cannot_remove(read, policy, status):
    ledger = baseline(read, policy)
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        ledger.observe(advance(read, status=status, encounters=(), orders=()), policy)
    retry = ledger.observe(advance(read), policy)
    assert not retry.full_reconciliation
    assert retry.encounter_upserts == retry.order_upserts == retry.missing_order_keys == ()


@pytest.mark.parametrize("flag", ["keys_verified", "states_verified", "whole_day", "untruncated",
                                  "consistent_snapshot", "connection_closed"])
@pytest.mark.parametrize("value", [False, "true", 1])
def test_read_evidence_requires_explicit_true(read, policy, flag, value):
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        normalize_source_day(replace(read, **{flag: value}), policy)


@pytest.mark.parametrize("field", ["resident_id", "birth_date", "phone", "address", "diagnosis",
                                   "notes", "sql", "token", "updated_at", "display_spec", "category"])
@pytest.mark.parametrize("row_type", ["encounter", "order"])
def test_unapproved_fields_rejected_without_leaking_values(read, policy, field, row_type):
    with pytest.raises(SnapshotRejected) as error:
        normalize_source_day(advance(read, **{row_type: {field: "PRIVATE_TEST_MARKER"}}), policy)
    assert str(error.value) == "invalid_fields"
    assert "PRIVATE_TEST_MARKER" not in repr(error.value)


@pytest.mark.parametrize("row_type,field,value,reason", [
    ("encounter", "state_code", "UNKNOWN", "unknown_reception_state"),
    ("order", "state_code", "UNKNOWN", "unknown_order_state"),
    ("encounter", "encounter_id", "", "invalid_text"),
    ("encounter", "age", True, "invalid_demographics"),
    ("encounter", "age", -1, "invalid_demographics"),
    ("encounter", "sex", "UNKNOWN", "invalid_demographics"),
    ("order", "encounter_id", "UNKNOWN", "orphan_order"),
    ("order", "order_number", "", "invalid_text"),
    ("order", "order_date", "20261001", "invalid_order_date"),
    ("order", "department_code", None, "invalid_text"),
])
def test_bad_values_reject_whole_observation(read, policy, row_type, field, value, reason):
    ledger = baseline(read, policy)
    with pytest.raises(SnapshotRejected, match=reason):
        ledger.observe(advance(read, **{row_type: {field: value}}), policy)
    assert not ledger.observe(advance(read), policy).order_upserts


@pytest.mark.parametrize("number", [True, 1.5, "NaN", "Infinity", "-Infinity", "1e100",
                                    "1e999999999", "1e-999999999", "abc"])
def test_invalid_numbers_are_fixed_failures(read, policy, number):
    with pytest.raises(SnapshotRejected, match="invalid_number"):
        normalize_source_day(advance(read, order={"quantity": number}), policy)


def test_structured_fields_are_gated_and_not_clinical_dose_strings(read, policy):
    with pytest.raises(SnapshotRejected, match="unverified_structured_fields"):
        normalize_source_day(replace(read, structured_fields_verified=False), policy)
    without = tuple({key: value for key, value in row.items() if key not in {"quantity", "days", "frequency"}}
                    for row in read.orders)
    snapshot = normalize_source_day(replace(read, orders=without, structured_fields_verified=False), policy)
    assert all(order.quantity is None for order in snapshot.orders)
    assert not hasattr(snapshot.orders[0], "dose")


def test_unknown_catalog_code_is_retained_not_silently_filtered(read, policy):
    snapshot = normalize_source_day(advance(read, order={"order_code": "TEST_UNMAPPED"}), policy)
    assert snapshot.orders[0].order_code == "TEST_UNMAPPED"


def test_full_key_includes_date_and_encounter_and_does_not_merge_by_chart(read, policy):
    another = dict(read.encounters[0], encounter_id="fixture-second-visit")
    different_day = dict(read.orders[0], order_date=read.clinic_day - timedelta(days=1))
    different_visit = dict(read.orders[0], encounter_id=another["encounter_id"])
    snapshot = normalize_source_day(replace(read, encounters=read.encounters + (another,),
                                           orders=read.orders + (different_day, different_visit)), policy)
    assert len(snapshot.encounters) == 2 and len({order.key for order in snapshot.orders}) == 4
    with pytest.raises(SnapshotRejected, match="duplicate_order"):
        normalize_source_day(replace(read, orders=read.orders + (read.orders[1],)), policy)
    with pytest.raises(SnapshotRejected, match="duplicate_encounter"):
        normalize_source_day(replace(read, encounters=read.encounters * 2), policy)


def test_no_default_production_mapping_even_for_empty_day(read):
    with pytest.raises(SnapshotRejected, match="incomplete_mapping"):
        normalize_source_day(replace(read, encounters=(), orders=()), SourcePolicy())
    unavailable = EghisSourceDayReader().read_day(read.clinic_day, read.observed_at)
    assert unavailable.status is ReadStatus.UNAVAILABLE and not unavailable.connection_closed


@pytest.mark.parametrize("rules", [None, (None,), (("TEST",),), (("TEST", "bad-state"),),
                                   (("TEST", None),), (("TEST", OrderState.ACTIVE),)])
def test_invalid_policy_has_only_fixed_rejection_codes(read, policy, rules):
    with pytest.raises(SnapshotRejected):
        normalize_source_day(read, replace(policy, reception_states=rules))


def test_duplicate_mapping_codes_are_not_silently_overwritten(read, policy):
    policy = replace(policy, reception_states=policy.reception_states + (policy.reception_states[0],))
    with pytest.raises(SnapshotRejected, match="invalid_mapping"):
        normalize_source_day(read, policy)


@pytest.mark.parametrize("change,reason", [
    ({"clinic_day": "2026-10-01"}, "invalid_day"),
    ({"observed_at": datetime(2026, 10, 1)}, "unverified_time"),
    ({"source_id": ""}, "invalid_text"),
    ({"projection_id": ""}, "invalid_text"),
    ({"encounters": []}, "invalid_row_bound"),
])
def test_snapshot_metadata_is_validated(read, policy, change, reason):
    with pytest.raises(SnapshotRejected, match=reason):
        normalize_source_day(replace(read, **change), policy)


@pytest.mark.parametrize("row_type,limit", [("encounters", 10001), ("orders", 100001)])
def test_oversized_read_fails_instead_of_truncating(read, policy, row_type, limit):
    with pytest.raises(SnapshotRejected, match="invalid_row_bound"):
        normalize_source_day(replace(read, **{row_type: (getattr(read, row_type)[0],) * limit}), policy)


def test_input_mutation_cannot_change_normalized_baseline(read, policy):
    ledger = SourceLedger()
    initial = ledger.observe(read, policy)
    read.orders[0]["order_code"] = "TEST_MUTATED"
    read.encounters[0]["patient_name"] = "Changed synthetic patient"
    assert initial.snapshot.orders[0].order_code == "TEST_DRUG"
    assert initial.snapshot.encounters[0].patient_name == "Synthetic patient"
    with pytest.raises(FrozenInstanceError):
        initial.snapshot.orders[0].order_code = "TEST_OTHER"


def test_repr_and_summary_are_redacted(read, policy):
    change = SourceLedger().observe(read, policy)
    for value in (read, policy, change, change.snapshot, *change.snapshot.encounters,
                  *change.snapshot.orders, change.snapshot.orders[0].key):
        assert repr(value) == f"<{type(value).__name__}: redacted>"
    assert change.summary() == {"status": "source_shadow_only", "encounter_upserts": 1,
                                "order_upserts": 2, "missing_encounters": 0, "missing_orders": 0}


def test_read_order_is_canonical_and_exact_retry_is_idempotent(read, policy):
    ledger = SourceLedger()
    first = ledger.observe(read, policy)
    assert ledger.observe(replace(read, orders=tuple(reversed(read.orders))), policy) is first
    with ThreadPoolExecutor(4) as workers:
        assert all(change is first for change in workers.map(lambda _: ledger.observe(read, policy), range(12)))


def test_source_progress_does_not_wait_for_either_receiver_ack(read, policy):
    ledger = SourceLedger()
    first = ledger.observe(read, policy)
    changed_read = advance(read, order={"quantity": "2"})
    second = ledger.observe(changed_read, policy)
    latest = ledger.observe(advance(changed_read), policy)
    assert first.observation_id != second.observation_id != latest.observation_id
    assert not latest.order_upserts
    assert latest.snapshot.orders[0].quantity == Decimal("2")
    assert len(latest.snapshot.orders) == 2  # A missed consumer can use the full snapshot.
    assert not hasattr(ledger, "acknowledge")


@pytest.mark.parametrize("mode", ["stale", "conflict", "identity", "mapping"])
def test_conflicts_preserve_previous_baseline(read, policy, mode):
    ledger = baseline(read, policy)
    if mode == "stale":
        bad, used_policy, reason = replace(read, observed_at=read.observed_at - timedelta(seconds=1)), policy, "stale_observation"
    elif mode == "conflict":
        bad, used_policy, reason = replace(read, orders=()), policy, "conflicting_observation"
    elif mode == "identity":
        bad, used_policy, reason = advance(read, encounter={"chart_no": "TEST-OTHER"}), policy, "encounter_identity_changed"
    else:
        bad, used_policy, reason = advance(read), replace(policy, revision="synthetic-v2"), "mapping_revision_changed"
    with pytest.raises(SnapshotRejected, match=reason):
        ledger.observe(bad, used_policy)
    assert not ledger.observe(advance(read), policy).order_upserts


def test_policy_cannot_change_meaning_under_same_revision(read, policy):
    ledger = baseline(read, policy)
    revised = replace(policy, reception_states=tuple(
        (code, ReceptionState.CANCELLED if state is ReceptionState.ON_HOLD else state)
        for code, state in policy.reception_states
    ))
    with pytest.raises(SnapshotRejected, match="mapping_revision_changed"):
        ledger.observe(advance(read), revised)
    assert not ledger.observe(advance(read), policy).encounter_upserts


def test_equivalent_policy_row_order_and_decimal_spelling_are_not_edits(read, policy):
    ledger = baseline(read, policy)
    reordered = replace(policy, reception_states=tuple(reversed(policy.reception_states)))
    change = ledger.observe(advance(read, order={"quantity": Decimal("1.000")}), reordered)
    assert not change.order_upserts and not change.encounter_upserts


def test_mutable_policy_input_cannot_rewrite_prior_meanings(read, policy):
    pairs = [list(pair) for pair in policy.reception_states]
    policy = replace(policy, reception_states=pairs)
    ledger = baseline(read, policy)
    next(pair for pair in pairs if pair[0] == "TEST_ON_HOLD")[1] = ReceptionState.CANCELLED
    with pytest.raises(SnapshotRejected, match="mapping_revision_changed"):
        ledger.observe(advance(read), policy)


def test_change_then_revert_between_reads_is_not_claimed_as_an_event(read, policy):
    change = baseline(read, policy).observe(advance(read), policy)
    assert not change.order_upserts and not change.encounter_upserts
    assert not hasattr(change.snapshot.orders[0], "updated_at")
    assert change.snapshot.observed_at > read.observed_at


@pytest.mark.parametrize("scope_field", ["source_id", "projection_id", "clinic_day"])
def test_different_source_scope_cannot_remove_another_scopes_rows(read, policy, scope_field):
    ledger = baseline(read, policy)
    value = read.clinic_day + timedelta(days=1) if scope_field == "clinic_day" else "fixture-other"
    changed = advance(read, encounters=(), orders=(), **{scope_field: value})
    result = ledger.observe(changed, policy)
    assert result.full_reconciliation and not result.missing_encounter_ids and not result.missing_order_keys
    assert not ledger.observe(advance(read), policy).full_reconciliation


def test_restart_and_eviction_require_full_reconciliation_not_removal(read, policy):
    ledger = SourceLedger(retained_snapshots=1)
    ledger.observe(read, policy)
    other = advance(read, clinic_day=read.clinic_day + timedelta(days=1), encounters=(), orders=())
    assert ledger.observe(other, policy).full_reconciliation
    restored = ledger.observe(advance(advance(read)), policy)
    assert restored.full_reconciliation and len(restored.order_upserts) == 2
    assert not restored.missing_order_keys
    assert SourceLedger().observe(read, policy).full_reconciliation


@pytest.fixture
def fake_db(monkeypatch):
    from KaosEghis.core import emr_read_queue

    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KaosEghis-emr-test")
    monkeypatch.setattr(emr_read_queue, "_worker", worker)
    monkeypatch.setattr(emr_read_queue, "_capacity", threading.BoundedSemaphore(64))
    monkeypatch.setattr(emr_read_queue, "_unhealthy", threading.Event())
    state = SimpleNamespace(live=0, maximum=0, events=[], error=None)

    class Cursor:
        description = [("synthetic",)]

        def execute(self, query, params=None):
            if query.startswith("SELECT") and state.error is not None:
                raise state.error

        def fetchall(self):
            return [(1,)]

        def close(self):
            state.events.append("cursor_closed")

    class Connection:
        closed = False

        def set_session(self, **options):
            assert options == {"readonly": True, "autocommit": True}

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True
            state.live -= 1
            state.events.append("connection_closed")

    def connect(*args, **kwargs):
        state.live += 1
        state.maximum = max(state.maximum, state.live)
        state.events.append("connected")
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    yield state
    worker.shutdown(wait=True)


def test_source_processing_runs_after_cleanup_and_does_not_occupy_reader(read, policy, fake_db):
    from KaosEghis.core import eghis_db

    processing, release = threading.Event(), threading.Event()
    ledger = SourceLedger()

    def observe_after_read():
        eghis_db.run_readonly_query("mock", "SELECT 'synthetic-only'")
        assert fake_db.live == 0
        assert fake_db.events[-2:] == ["cursor_closed", "connection_closed"]
        processing.set()
        assert release.wait(5)
        return ledger.observe(read, policy)

    with ThreadPoolExecutor(2) as callers:
        result = callers.submit(observe_after_read)
        try:
            assert processing.wait(3)
            # A health/flu/PACS read can finish while source processing is pending.
            other = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 1")
            assert other.result(3) == (["synthetic"], [(1,)])
        finally:
            release.set()
        assert result.result(3).full_reconciliation
    assert fake_db.live == 0 and fake_db.maximum == 1


@pytest.mark.parametrize("error", [RuntimeError("synthetic failure"), TimeoutError("synthetic timeout")])
def test_read_failure_cannot_reach_comparison_and_cleanup_allows_next_job(read, policy, fake_db, error):
    from KaosEghis.core import eghis_db

    ledger = baseline(read, policy)
    fake_db.error = error
    with pytest.raises(type(error)):
        eghis_db.run_readonly_query("mock", "SELECT 'synthetic-only'")
        pytest.fail("failed source read reached normalization")
    assert fake_db.live == 0 and fake_db.events[-1] == "connection_closed"
    fake_db.error = None
    eghis_db.run_readonly_query("mock", "SELECT 1")
    assert not ledger.observe(advance(read), policy).order_upserts


def test_shared_models_have_no_runtime_io_or_board_dependency():
    import KaosEghis.core.emr_order_text_shadow as order_text
    import KaosEghis.core.emr_source as source
    import KaosEghis.core.emr_source_shadow as shadow

    forbidden = {"psycopg2", "sqlite3", "socket", "requests", "urllib", "httpx", "logging", "pathlib"}
    for module in (source, shadow, order_text):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any(name.split(".")[0] in forbidden or "kaosorders" in name for name in names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "print", "exec", "eval"}
    allowed = {"emr_source.py", "emr_source_shadow.py", "kaosorders_source.py", "kaosorders_normalized_source.py",
               "kaosorders_outbox_shadow.py", "emr_source_v2.py", "kaosorders_normalized_source_v2.py",
               "emr_order_text_shadow.py"}
    for path in Path(source.__file__).parents[1].rglob("*.py"):
        if path.name not in allowed:
            assert "core.emr_source" not in path.read_text(encoding="utf-8-sig")


def test_old_board_reference_reuses_only_common_validation_types():
    from KaosEghis.core import emr_source, kaosorders_source

    assert kaosorders_source.ReadStatus is ReadStatus
    assert kaosorders_source.SnapshotRejected is SnapshotRejected
    assert kaosorders_source._fields is emr_source._fields
    assert kaosorders_source.ReceptionState is not ReceptionState
    assert not hasattr(EncounterFacts, "board_eligible")
