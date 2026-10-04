import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, make_dataclass, replace
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from KaosEghis.core import kaosorders_outbox_shadow as module
from KaosEghis.core.kaosorders_outbox_shadow import (
    MAX_SEQUENCE_VALUE, OutboxRejected, SyntheticAcknowledgement, SyntheticOutbox,
)
from tests.test_kaosorders_normalized_source import (
    expected, snapshot, source_policy, source_read,
)


DAY = date(2026, 10, 1)
RECEIVER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BATCH1 = "11111111-1111-4111-8111-111111111111"
BATCH2 = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "orders.synthetic.sqlite3"


def create(path, **changes):
    fields = dict(clinic_id="fixture-clinic", source_id="fixture-eghis",
                  projection_id="fixture-all-orders-v1", mapping_revision="synthetic-v1",
                  source_epoch=1, receiver_generation=RECEIVER, synthetic_fixture=True)
    fields.update(changes)
    return SyntheticOutbox.create(path, **fields)


@pytest.fixture
def queue(path):
    return create(path)


def reopen(path):
    return SyntheticOutbox(path, synthetic_fixture=True)


def seal(queue, snapshot, batch_id=BATCH1):
    generation = queue.request_refresh(snapshot.clinic_day)
    return queue.seal(snapshot, batch_id=batch_id, refresh_generation=generation)


def ack(pending, **changes):
    fields = dict(outcome="accepted", receiver_generation=RECEIVER,
                  request=pending.cursor, committed=pending.cursor)
    fields.update(changes)
    return SyntheticAcknowledgement(**fields)


def execute(path, statement, args=()):
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(statement, args)
    finally:
        connection.close()


def test_full_fixture_exact_bytes_survive_restart_and_retry(queue, path, snapshot):
    pending = seal(queue, snapshot)
    assert json.loads(pending.body) == expected()
    for _ in range(3):
        queue = reopen(path)
        assert queue.pending(DAY) == pending
        assert queue.pending(DAY).body == pending.body
        assert queue.state(DAY).allocated_revision == 1
    assert queue.acknowledge(ack(pending, outcome="duplicate")) == "acknowledged"
    assert reopen(path).pending(DAY) is None
    assert not queue.state(DAY).refresh_required
    assert queue.acknowledge(ack(pending)) == "already_acknowledged"


def test_verified_empty_day_is_a_full_batch(queue, snapshot):
    other = replace(snapshot, clinic_day=date(2026, 10, 2), encounters=(), orders=(),
                    observed_at=snapshot.observed_at + timedelta(days=1))
    assert json.loads(seal(queue, other, BATCH2).body) == expected("empty")


def test_revision_per_day_epoch_shared_and_no_automatic_reset(queue, snapshot, path):
    first = seal(queue, snapshot)
    second_day = seal(queue, replace(snapshot, clinic_day=DAY + timedelta(days=1)), BATCH2)
    assert first.cursor.revision == second_day.cursor.revision == 1
    assert second_day.cursor.source_epoch == first.cursor.source_epoch == 1
    queue.acknowledge(ack(first))
    queue = reopen(path)
    third = seal(queue, snapshot, "33333333-3333-4333-8333-333333333333")
    assert third.cursor.revision == 2 and third.cursor.source_epoch == 1
    assert queue.pending(DAY + timedelta(days=1)) == second_day


def test_pending_is_never_replaced_and_refreshes_coalesce(queue, snapshot, path):
    first = seal(queue, snapshot)
    for _ in range(10):
        generation = queue.request_refresh(DAY)
    with pytest.raises(OutboxRejected, match="^pending_unresolved$"):
        queue.seal(snapshot, batch_id=BATCH2, refresh_generation=generation)
    assert reopen(path).pending(DAY) == first
    queue.acknowledge(ack(first))
    state = reopen(path).state(DAY)
    assert state.refresh_required and state.acknowledged_generation == 1
    second = queue.seal(snapshot, batch_id=BATCH2, refresh_generation=generation)
    assert second.cursor.revision == 2 and second.refresh_generation == 11
    queue.acknowledge(ack(second))
    assert not reopen(path).state(DAY).refresh_required


def test_request_arriving_during_read_is_not_swallowed_by_seal(queue, snapshot):
    ticket = queue.request_refresh(DAY)
    queue.request_refresh(DAY)
    pending = queue.seal(snapshot, batch_id=BATCH1, refresh_generation=ticket)
    queue.acknowledge(ack(pending))
    assert queue.state(DAY).requested_generation == 2
    assert queue.state(DAY).acknowledged_generation == 1
    assert queue.state(DAY).refresh_required


@pytest.mark.parametrize("bad", [0, -1, True, 1.2, "1", MAX_SEQUENCE_VALUE + 1, 2])
def test_invalid_generation_never_allocates(queue, snapshot, bad):
    queue.request_refresh(DAY)
    with pytest.raises(OutboxRejected):
        queue.seal(snapshot, batch_id=BATCH1, refresh_generation=bad)
    assert queue.state(DAY).allocated_revision == 0
    assert queue.pending(DAY) is None


def test_stale_generation_and_reused_batch_ids_are_rejected(queue, snapshot):
    first = seal(queue, snapshot)
    queue.acknowledge(ack(first))
    generation = queue.request_refresh(DAY)
    with pytest.raises(OutboxRejected, match="^invalid_refresh_generation$"):
        queue.seal(snapshot, batch_id=BATCH2, refresh_generation=1)
    with pytest.raises(OutboxRejected, match="^batch_id_reused$"):
        queue.seal(snapshot, batch_id=BATCH1, refresh_generation=generation)
    assert queue.state(DAY).allocated_revision == 1


def test_batch_id_cannot_be_reused_on_another_day(queue, snapshot):
    first = seal(queue, snapshot)
    queue.acknowledge(ack(first))
    other = replace(snapshot, clinic_day=DAY + timedelta(days=1))
    ticket = queue.request_refresh(other.clinic_day)
    with pytest.raises(OutboxRejected, match="^batch_id_reused$"):
        queue.seal(other, batch_id=BATCH1, refresh_generation=ticket)
    assert queue.state(other.clinic_day).allocated_revision == 0


def test_old_ack_cannot_clear_a_newer_pending_batch(queue, snapshot):
    first = seal(queue, snapshot)
    queue.acknowledge(ack(first))
    second = seal(queue, snapshot, BATCH2)
    with pytest.raises(OutboxRejected, match="^ack_mismatch$"):
        queue.acknowledge(ack(first))
    assert queue.pending(DAY) == second


@pytest.mark.parametrize("field", ["source_id", "projection_id", "mapping_revision"])
def test_mapping_and_scope_cannot_change_in_place(queue, snapshot, field):
    generation = queue.request_refresh(DAY)
    with pytest.raises(OutboxRejected, match="^scope_mismatch$"):
        queue.seal(replace(snapshot, **{field: "fixture-different"}),
                   batch_id=BATCH1, refresh_generation=generation)
    assert queue.state(DAY).allocated_revision == 0


@pytest.mark.parametrize("kind", ["source", "batch_id", "byte_limit"])
def test_validation_failure_retains_request_and_does_not_consume_revision(queue, snapshot, kind, monkeypatch):
    generation = queue.request_refresh(DAY)
    batch_id = BATCH1
    if kind == "source":
        snapshot = replace(snapshot, encounters=(replace(snapshot.encounters[0], sex=""),))
    elif kind == "batch_id":
        batch_id = "PRIVATE_TEST_MARKER"
    else:
        monkeypatch.setattr(module, "MAX_SYNTHETIC_BYTES", 1)
    with pytest.raises(OutboxRejected) as error:
        queue.seal(snapshot, batch_id=batch_id, refresh_generation=generation)
    assert "PRIVATE_TEST_MARKER" not in str(error.value)
    assert queue.state(DAY).refresh_required and queue.state(DAY).allocated_revision == 0


@pytest.mark.parametrize("outcome", ["accepted", "duplicate"])
def test_acknowledgement_atomically_removes_body_but_retains_receipt(queue, snapshot, path, outcome):
    pending = seal(queue, snapshot)
    assert queue.acknowledge(ack(pending, outcome=outcome)) == "acknowledged"
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT body, digest FROM batches").fetchone() == (None, pending.cursor.content_sha256)
    finally:
        connection.close()
    assert reopen(path).state(DAY).acknowledged_revision == 1


@pytest.mark.parametrize("outcome", ["stale", "conflict", "resync_required"])
def test_negative_ack_is_durably_paused_without_discarding_batch(queue, snapshot, path, outcome):
    pending = seal(queue, snapshot)
    assert queue.acknowledge(ack(pending, outcome=outcome, committed=None)) == "paused"
    queue = reopen(path)
    assert queue.state(DAY).paused_reason == outcome
    assert queue.pending(DAY) == pending
    with pytest.raises(OutboxRejected, match="^scope_paused$"):
        queue.acknowledge(ack(pending))


@pytest.mark.parametrize("field,value", [("batch_id", BATCH2), ("source_epoch", 2),
                                        ("revision", 2), ("content_sha256", "0" * 64)])
def test_ack_binds_all_request_cursor_fields(queue, snapshot, field, value):
    pending = seal(queue, snapshot)
    changed = replace(pending.cursor, **{field: value})
    with pytest.raises(OutboxRejected, match="^ack_mismatch$"):
        queue.acknowledge(ack(pending, request=changed, committed=changed))
    assert queue.pending(DAY) == pending


@pytest.mark.parametrize("field,value", [("clinic_id", "fixture-other"), ("source_id", "fixture-other"),
                                        ("projection_id", "fixture-other"), ("mapping_revision", "fixture-other"),
                                        ("clinic_day", DAY + timedelta(days=1))])
def test_ack_binds_entire_scope(queue, snapshot, field, value):
    pending = seal(queue, snapshot)
    changed = replace(pending.cursor, scope=replace(pending.cursor.scope, **{field: value}))
    with pytest.raises(OutboxRejected, match="^ack_mismatch$"):
        queue.acknowledge(ack(pending, request=changed, committed=changed))
    assert queue.pending(DAY) == pending


@pytest.mark.parametrize("change,reason", [
    ({"receiver_generation": BATCH2}, "receiver_generation_mismatch"),
    ({"committed": None}, "receiver_cursor_mismatch"),
    ({"outcome": "PRIVATE_TEST_MARKER"}, "invalid_ack_outcome"),
])
def test_unknown_or_incomplete_ack_cannot_clear_pending(queue, snapshot, change, reason):
    pending = seal(queue, snapshot)
    with pytest.raises(OutboxRejected, match=f"^{reason}$"):
        queue.acknowledge(ack(pending, **change))
    assert queue.pending(DAY) == pending


def test_receiver_ahead_duplicate_does_not_clear_pending(queue, snapshot):
    pending = seal(queue, snapshot)
    with pytest.raises(OutboxRejected, match="^receiver_cursor_mismatch$"):
        queue.acknowledge(ack(pending, outcome="duplicate", committed=replace(pending.cursor, revision=2)))
    assert queue.pending(DAY) == pending


# Field/receipt shapes reviewed against KaosOrders 40c6a496385a4c6fd48c6532554748db23d4e3cb.
# No receiver module is imported and no HTTP encoding is defined by these tests.
def test_pinned_receiver_internal_field_layout_matches_sender_models():
    assert [field.name for field in fields(SyntheticAcknowledgement)] == [
        "outcome", "receiver_generation", "request", "committed",
    ]
    assert [field.name for field in fields(module.BatchCursor)] == [
        "scope", "source_epoch", "revision", "batch_id", "content_sha256",
    ]
    assert [field.name for field in fields(module.DeliveryScope)] == [
        "clinic_id", "source_id", "projection_id", "clinic_day", "mapping_revision",
    ]


@pytest.mark.parametrize("outcome,change", [
    ("stale", "newer_revision"), ("stale", "newer_epoch"),
    ("stale", "same_day_epoch"),  # A newer producer epoch may exist on another day.
    ("conflict", "different_content"), ("conflict", "different_mapping"),
])
def test_negative_receipt_with_committed_cursor_pauses_and_preserves_work(queue, snapshot, path, outcome, change):
    pending = seal(queue, snapshot)
    queue.request_refresh(DAY)
    committed = pending.cursor
    if change == "newer_revision":
        committed = replace(committed, revision=3, batch_id=BATCH2, content_sha256="a" * 64)
    elif change == "newer_epoch":
        committed = replace(committed, source_epoch=2, batch_id=BATCH2, content_sha256="a" * 64)
    elif change in ("different_content", "same_day_epoch"):
        committed = replace(committed, batch_id=BATCH2, content_sha256="a" * 64)
    elif change == "different_mapping":
        committed = replace(committed, scope=replace(committed.scope, mapping_revision="synthetic-old"),
                            batch_id=BATCH2, content_sha256="a" * 64)
    assert queue.acknowledge(ack(pending, outcome=outcome, committed=committed)) == "paused"
    restored = reopen(path)
    assert restored.pending(DAY) == pending
    state = restored.state(DAY)
    assert state.paused_reason == outcome and state.acknowledged_revision == 0
    assert state.requested_generation == 2 and state.refresh_required
    with pytest.raises(OutboxRejected, match="^scope_paused$"):
        restored.acknowledge(ack(pending))


def test_resync_receipt_for_unsupported_restart_preserves_new_epoch_batch(path, snapshot):
    queue = create(path, source_epoch=2)
    first = seal(queue, snapshot)
    queue.acknowledge(ack(first))
    pending = seal(queue, snapshot, BATCH2)
    # The receiver still has epoch 1; epoch 2 revision 2 cannot enroll/restart it.
    old = replace(first.cursor, source_epoch=1, content_sha256="a" * 64)
    assert queue.acknowledge(ack(pending, outcome="resync_required", committed=old)) == "paused"
    restored = reopen(path)
    assert restored.pending(DAY) == pending
    assert restored.state(DAY).acknowledged_revision == 1
    assert restored.state(DAY).paused_reason == "resync_required"


@pytest.mark.parametrize("outcome", ["accepted", "duplicate"])
@pytest.mark.parametrize("change", ["epoch", "batch_id", "digest", "mapping", "day"])
def test_success_receipt_cannot_hide_a_different_committed_cursor(queue, snapshot, path, outcome, change):
    pending = seal(queue, snapshot)
    committed = pending.cursor
    if change == "epoch":
        committed = replace(committed, source_epoch=2)
    elif change == "batch_id":
        committed = replace(committed, batch_id=BATCH2)
    elif change == "digest":
        committed = replace(committed, content_sha256="a" * 64)
    elif change == "mapping":
        committed = replace(committed, scope=replace(committed.scope, mapping_revision="synthetic-v2"))
    else:
        committed = replace(committed, scope=replace(committed.scope, clinic_day=DAY + timedelta(days=1)))
    with pytest.raises(OutboxRejected, match="^receiver_cursor_mismatch$"):
        queue.acknowledge(ack(pending, outcome=outcome, committed=committed))
    assert reopen(path).pending(DAY) == pending
    assert queue.state(DAY).acknowledged_revision == 0


def test_accepted_receipt_with_receiver_ahead_revision_is_rejected(queue, snapshot):
    pending = seal(queue, snapshot)
    with pytest.raises(OutboxRejected, match="^receiver_cursor_mismatch$"):
        queue.acknowledge(ack(pending, committed=replace(pending.cursor, revision=2)))
    assert queue.pending(DAY) == pending


@pytest.mark.parametrize("location", ["receipt", "cursor", "scope"])
def test_same_fields_do_not_authorize_foreign_receipt_object_types(queue, snapshot, location):
    pending = seal(queue, snapshot)
    receipt = ack(pending)
    original = {"receipt": receipt, "cursor": receipt.request, "scope": receipt.request.scope}[location]
    foreign_type = make_dataclass("SyntheticForeignModel", [field.name for field in fields(original)], repr=False)
    foreign = foreign_type(**vars(original))
    if location == "receipt":
        receipt = foreign
    elif location == "cursor":
        receipt = replace(receipt, request=foreign)
    else:
        receipt = replace(receipt, request=replace(receipt.request, scope=foreign))
    with pytest.raises(OutboxRejected, match="^invalid_input$"):
        queue.acknowledge(receipt)
    assert queue.pending(DAY) == pending


@pytest.mark.parametrize("operation", ["seal", "ack"])
def test_midtransaction_failure_rolls_back_all_progress(queue, snapshot, path, operation):
    generation = queue.request_refresh(DAY)
    if operation == "ack":
        pending = queue.seal(snapshot, batch_id=BATCH1, refresh_generation=generation)
    trigger = ("CREATE TRIGGER fail BEFORE INSERT ON batches BEGIN SELECT RAISE(ABORT, 'PRIVATE_TEST_MARKER'); END"
               if operation == "seal" else
               "CREATE TRIGGER fail BEFORE UPDATE OF body ON batches BEGIN SELECT RAISE(ABORT, 'PRIVATE_TEST_MARKER'); END")
    execute(path, trigger)
    with pytest.raises(OutboxRejected, match="^store_unavailable$"):
        if operation == "seal":
            queue.seal(snapshot, batch_id=BATCH1, refresh_generation=generation)
        else:
            queue.acknowledge(ack(pending))
    state = reopen(path).state(DAY)
    assert state.acknowledged_revision == 0
    assert state.allocated_revision == (1 if operation == "ack" else 0)
    assert queue.pending(DAY) == (pending if operation == "ack" else None)


@pytest.mark.parametrize("operation", ["seal", "ack"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_process_exit_at_commit_boundary(queue, snapshot, path, operation, when):
    generation = queue.request_refresh(DAY)
    if operation == "ack":
        pending = queue.seal(snapshot, batch_id=BATCH1, refresh_generation=generation)
    script = r'''
import os, sqlite3, sys
from datetime import date
from KaosEghis.core.kaosorders_outbox_shadow import SyntheticOutbox, SyntheticAcknowledgement
from tests.test_kaosorders_normalized_source import source_read, source_policy
from KaosEghis.core.emr_source import normalize_source_day
queue = SyntheticOutbox(sys.argv[1], synthetic_fixture=True)
snapshot = normalize_source_day(source_read.__wrapped__(), source_policy.__wrapped__())
pending = queue.pending(date(2026, 10, 1))
original = sqlite3.connect
class Crash(sqlite3.Connection):
    def commit(self):
        if sys.argv[3] == "before":
            os._exit(81)
        super().commit()
        os._exit(82)
sqlite3.connect = lambda *a, **k: original(*a, **k, factory=Crash)
if sys.argv[2] == "seal":
    queue.seal(snapshot, batch_id="11111111-1111-4111-8111-111111111111", refresh_generation=1)
else:
    queue.acknowledge(SyntheticAcknowledgement("accepted", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", pending.cursor, pending.cursor))
'''
    result = subprocess.run([sys.executable, "-c", script, str(path), operation, when],
                            capture_output=True, timeout=20)
    assert result.returncode == (81 if when == "before" else 82)
    queue = reopen(path)
    state = queue.state(DAY)
    if operation == "seal":
        assert state.allocated_revision == (1 if when == "after" else 0)
        assert bool(queue.pending(DAY)) == (when == "after")
    else:
        assert state.acknowledged_revision == (1 if when == "after" else 0)
        assert queue.pending(DAY) == (None if when == "after" else pending)


def test_two_store_instances_cannot_allocate_two_pending_batches(queue, snapshot, path):
    generation = queue.request_refresh(DAY)
    def attempt(batch_id):
        try:
            return reopen(path).seal(snapshot, batch_id=batch_id, refresh_generation=generation)
        except OutboxRejected as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, [BATCH1, BATCH2]))
    assert sum(isinstance(result, module.PendingBatch) for result in results) == 1
    assert "pending_unresolved" in results
    assert queue.state(DAY).allocated_revision == 1


@pytest.mark.parametrize("flag", [False, None, 1, "true"])
def test_synthetic_gate_precedes_file_creation(path, flag):
    with pytest.raises(OutboxRejected, match="^synthetic_fixture_required$"):
        create(path, synthetic_fixture=flag)
    assert not path.exists()
    with pytest.raises(OutboxRejected, match="^synthetic_fixture_required$"):
        SyntheticOutbox(path, synthetic_fixture=flag)


@pytest.mark.parametrize("changes", [
    {"source_epoch": 0}, {"source_epoch": True}, {"source_epoch": MAX_SEQUENCE_VALUE + 1},
    {"receiver_generation": "PRIVATE_TEST_MARKER"}, {"clinic_id": " "},
])
def test_invalid_enrollment_does_not_create_file(path, changes):
    with pytest.raises(OutboxRejected, match="^invalid_identity$"):
        create(path, **changes)
    assert not path.exists()


@pytest.mark.parametrize("value", [None, 42, {}, ""])
def test_invalid_paths_have_fixed_errors(value):
    with pytest.raises(OutboxRejected, match="^invalid_path$"):
        create(value)
    with pytest.raises(OutboxRejected, match="^invalid_path$"):
        reopen(value)


def test_missing_state_is_not_recreated_and_existing_file_not_overwritten(queue, path):
    with pytest.raises(OutboxRejected, match="^store_already_exists$"):
        create(path)
    path.unlink()
    with pytest.raises(OutboxRejected, match="^store_unavailable$"):
        reopen(path)
    assert not path.exists()


def test_unrelated_sqlite_database_is_not_initialized(path):
    execute(path, "CREATE TABLE unrelated(value TEXT)")
    with pytest.raises(OutboxRejected, match="^store_unverified$"):
        reopen(path)


@pytest.mark.parametrize("statement,args", [
    ("UPDATE batches SET body=?", (b'PRIVATE_TEST_MARKER',)),
    ("UPDATE batches SET digest=?", ("0" * 64,)),
    ("UPDATE batches SET revision=2", ()),
    ("UPDATE batches SET body=NULL", ()),
    ("UPDATE days SET acknowledged=2", ()),
])
def test_corruption_fails_closed_without_resealing(queue, snapshot, path, statement, args):
    seal(queue, snapshot)
    execute(path, statement, args)
    with pytest.raises(OutboxRejected, match="^store_corrupt$"):
        reopen(path).pending(DAY)


def test_counter_overflow_never_wraps(queue, path):
    queue.request_refresh(DAY)
    execute(path, "UPDATE days SET requested=?", (MAX_SEQUENCE_VALUE,))
    with pytest.raises(OutboxRejected, match="^sequence_exhausted$"):
        queue.request_refresh(DAY)


def test_allocated_revision_overflow_never_wraps(queue, path, snapshot):
    queue.request_refresh(DAY)
    execute(path, "UPDATE days SET requested=?, acknowledged_generation=?, allocated=?, acknowledged=?",
            (MAX_SEQUENCE_VALUE, MAX_SEQUENCE_VALUE - 1, MAX_SEQUENCE_VALUE, MAX_SEQUENCE_VALUE))
    # A damaged counter state must be rejected before an allocation is considered.
    with pytest.raises(OutboxRejected, match="^store_corrupt$"):
        queue.seal(snapshot, batch_id=BATCH1, refresh_generation=MAX_SEQUENCE_VALUE)


def test_each_operation_closes_its_local_connection(queue, snapshot, monkeypatch):
    original = sqlite3.connect
    live = set()
    class Tracked(sqlite3.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            live.add(id(self))

        def close(self):
            try:
                super().close()
            finally:
                live.discard(id(self))
    monkeypatch.setattr(module.sqlite3, "connect", lambda *a, **k: original(*a, **k, factory=Tracked))
    pending = seal(queue, snapshot)
    assert not live
    assert queue.pending(DAY) == pending
    assert not live
    with pytest.raises(OutboxRejected):
        queue.acknowledge(ack(pending, committed=None))
    assert not live
    queue.acknowledge(ack(pending))
    assert not live


def test_models_and_store_representations_are_redacted(queue, snapshot):
    pending = seal(queue, snapshot)
    for value in (queue, pending, pending.cursor, pending.cursor.scope, ack(pending), queue.state(DAY)):
        assert repr(value) == str(value) == f"<{type(value).__name__}: redacted>"


def test_extra_ack_fields_are_rejected(queue, snapshot):
    pending = seal(queue, snapshot)
    receipt = ack(pending)
    object.__setattr__(receipt, "raw_payload", "PRIVATE_TEST_MARKER")
    with pytest.raises(OutboxRejected, match="^invalid_input$"):
        queue.acknowledge(receipt)
    assert queue.pending(DAY) == pending


def test_no_runtime_network_emr_or_trigger_dependency():
    path = Path(module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed = {"contextlib", "dataclasses", "datetime", "hashlib", "json", "pathlib", "sqlite3", "uuid",
               "KaosEghis.core.emr_source", "KaosEghis.core.kaosorders_normalized_source"}
    for node in ast.walk(tree):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) else [])
        assert set(names) <= allowed
    for candidate in path.parents[1].rglob("*.py"):
        if candidate != path:
            assert "kaosorders_outbox_shadow" not in candidate.read_text(encoding="utf-8-sig")
