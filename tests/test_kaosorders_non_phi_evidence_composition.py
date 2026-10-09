import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import threading

import pytest

from KaosEghis.core import emr_read_queue
from KaosEghis.core import kaosorders_non_phi_evidence_capture as capture
from KaosEghis.core import kaosorders_non_phi_evidence_composition as composition
from KaosEghis.core import kaosorders_non_phi_evidence_executor as executor


KST = timezone(timedelta(hours=9), "KST")
DAY = date(2026, 10, 9)
NOW = datetime(2026, 10, 9, 21, 0, tzinfo=KST)
COMMIT = "a" * 40
HEX = "b" * 64
STATEMENTS_DOC = (
    Path(__file__).parents[1]
    / "docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md"
)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def expire(self):
        self.value = capture.GLOBAL_DEADLINE_SECONDS + 0.001


def prerequisites():
    p00 = next(item for item in capture.STATEMENT_SPECS if item.statement_id == "EKO-P00")
    return (
        executor.IdentityPathAttestation(
            executor.ATTESTATION_CONTRACT,
            "approved",
            HEX,
            executor.IDENTITY_CLASS,
            executor.PATH_CLASS,
            p00.sha256_hex,
            executor.AUTHORITY_ROLE,
            DAY,
            DAY + timedelta(days=1),
        ),
        executor.ExecutorApproval(
            executor.EXECUTOR_APPROVAL_CONTRACT,
            "approved",
            HEX,
            COMMIT,
            executor.REVIEWER_ROLE,
            capture.PACKAGE_REVISION,
        ),
        executor.ExecutionWindow(
            executor.WINDOW_CONTRACT,
            "approved",
            HEX,
            NOW - timedelta(minutes=1),
            NOW + timedelta(minutes=1),
            "operator-1",
            "cancel-owner-1",
        ),
    )


def execute(comp):
    identity, approval, window = prerequisites()
    return comp.execute_once(
        identity=identity,
        approval=approval,
        window=window,
        runtime_commit=COMMIT,
        evidence_date=DAY,
        now=NOW,
    )


def m10_rows():
    return [
        (relation, column, True, "text", False, False, False)
        for relation, column in capture.M10_IDENTITIES
    ]


def k20_rows():
    return [
        (relation, key, 1, True, False, True, True, "btree")
        for relation, key in capture.K20_IDENTITIES
    ]


class RawCursor:
    def __init__(
        self, events, *, clock, execute_failure=None, close_false=False,
        close_raise=False,
    ):
        self.events = events
        self.clock = clock
        self.execute_failure = execute_failure
        self.close_false = close_false
        self.close_raise = close_raise
        self.current = None
        self.description = None
        self.closed = False

    def _assert_open(self):
        if self.closed:
            raise AssertionError("post-close cursor use")

    def execute(self, statement):
        self._assert_open()
        statement_id = statement.splitlines()[0].split()[-1]
        self.current = statement_id
        self.events.append(f"execute:{statement_id}")
        if statement_id == self.execute_failure:
            raise RuntimeError("PRIVATE_CANARY")
        spec = next(item for item in capture.STATEMENT_SPECS if item.statement_id == statement_id)
        self.description = (
            None if not spec.columns else tuple((name,) for name in spec.columns)
        )

    def fetchmany(self, _maximum):
        self._assert_open()
        self.events.append(f"fetch:{self.current}")
        if self.current == "EKO-P00":
            return [tuple(True for _ in capture.P00_COLUMNS)]
        if self.current == "EKO-V01":
            return [("150000",)]
        if self.current == "EKO-M10":
            return m10_rows()
        if self.current == "EKO-K20":
            return k20_rows()
        raise AssertionError("unexpected fetch")

    def close(self):
        self.events.append("raw_cursor_close")
        if self.close_raise:
            raise RuntimeError("PRIVATE_CANARY")
        if not self.close_false:
            self.closed = True


class RawConnection:
    notices = ()

    def __init__(
        self, events, *, clock, execute_failure=None, cursor_close_false=False,
        cursor_close_raise=False, connection_close_false=False,
        connection_close_raise=False, cancel_raise=False, notices=(),
    ):
        self.events = events
        self.clock = clock
        self.closed = 0
        self.connection_close_false = connection_close_false
        self.connection_close_raise = connection_close_raise
        self.cancel_raise = cancel_raise
        self.notices = notices
        self.cursor_value = RawCursor(
            events,
            clock=clock,
            execute_failure=execute_failure,
            close_false=cursor_close_false,
            close_raise=cursor_close_raise,
        )

    def _assert_open(self):
        if self.closed:
            raise AssertionError("post-close connection use")

    def cursor(self):
        self._assert_open()
        self.events.append("raw_cursor_create")
        return self.cursor_value

    def cancel(self):
        self._assert_open()
        self.events.append("raw_cancel")
        if self.cancel_raise:
            raise RuntimeError("PRIVATE_CANARY")

    def close(self):
        self.events.append("raw_connection_close")
        if self.connection_close_raise:
            raise RuntimeError("PRIVATE_CANARY")
        if not self.connection_close_false:
            self.closed = 1


@pytest.fixture
def isolated_serialized_boundary(monkeypatch):
    events = []
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="composition-test")

    @contextmanager
    def exclusive_reader(**_kwargs):
        events.append("mutex_acquired")
        try:
            yield
        except emr_read_queue.EmrReadSafetyError:
            events.append("mutex_retained")
            raise
        else:
            events.append("mutex_released")

    monkeypatch.setattr(emr_read_queue, "_worker", worker)
    monkeypatch.setattr(emr_read_queue, "_capacity", threading.BoundedSemaphore(64))
    monkeypatch.setattr(emr_read_queue, "_exclusive_reader", exclusive_reader)
    monkeypatch.setattr(emr_read_queue, "_unhealthy", threading.Event())
    yield events, worker
    worker.shutdown(wait=True)


def make_composition(
    events, *, clock=None, path_mode="delivered", connection_options=None,
):
    clock = clock or Clock()
    connection_options = connection_options or {}
    physical = RawConnection(events, clock=clock, **connection_options)

    def acquire_one(deadline, receiver):
        events.append("path_called")
        assert deadline == capture.GLOBAL_DEADLINE_SECONDS
        if path_mode == "no_connection":
            return composition.PathAcquisition.NO_CONNECTION
        if path_mode == "raise_before":
            raise RuntimeError("PRIVATE_CANARY")
        receiver(physical)
        if path_mode == "deliver_twice":
            receiver(physical)
        if path_mode == "raise_after":
            raise RuntimeError("PRIVATE_CANARY")
        if path_mode == "expire_after_delivery":
            clock.expire()
        return composition.PathAcquisition.DELIVERED

    path = composition.InjectedSerializedCredentialReadPath(acquire_one)
    comp = composition.build_disabled_orders_evidence_composition(
        path=path, monotonic=clock,
    )
    return comp, physical, clock


def test_success_binds_frozen_inventory_serialized_path_cleanup_and_atomic_sink(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(events)
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.COMPLETE
    assert comp.final_artifact == outcome.artifact
    assert events.index("mutex_acquired") < events.index("path_called")
    assert events.index("raw_cursor_close") < events.index("raw_connection_close")
    assert events.index("raw_connection_close") < events.index("mutex_released")
    assert events.count("path_called") == 1
    assert events[events.index("raw_connection_close") + 1:] == ["mutex_released"]
    assert physical.closed == 1
    observation = comp.connection_observation
    assert observation.acquisition_count == 1
    assert observation.cursor_acquisition_count == 1
    assert observation.cursor_close_verified is True
    assert observation.physical_close_verified is True
    assert len(comp.statement_digests) == 9


@pytest.mark.parametrize("path_mode", ["no_connection", "raise_before"])
def test_acquire_failure_is_closed_and_never_executes_or_publishes(
    isolated_serialized_boundary, path_mode,
):
    events, _worker = isolated_serialized_boundary
    comp, _physical, _clock = make_composition(events, path_mode=path_mode)
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert not any(item.startswith("execute:") for item in events)
    if path_mode == "no_connection":
        assert comp.connection_observation.no_connection_proven is True
        assert "mutex_released" in events
    else:
        assert comp.connection_observation.no_connection_proven is False
        assert emr_read_queue._unhealthy.is_set()
        assert "mutex_retained" in events


def test_allocate_then_raise_is_owned_closed_and_never_published(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(events, path_mode="raise_after")
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert physical.closed == 1
    assert comp.connection_observation.physical_close_verified is True
    assert "mutex_released" in events and "mutex_retained" not in events


def test_second_connection_delivery_is_uncertain_and_poisons_serialization(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(events, path_mode="deliver_twice")
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert physical.closed == 1
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_retained" in events and "mutex_released" not in events


def test_shared_deadline_covers_path_and_all_cleanup(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(
        events, path_mode="expire_after_delivery",
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert physical.closed == 1
    assert comp.connection_observation.physical_close_verified is True


def test_source_failure_cancels_rolls_back_closes_and_never_echoes(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(
        events, connection_options={"execute_failure": "EKO-P00"},
    )
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert "raw_cancel" in events
    assert events.count("execute:EKO-C99") == 1
    assert physical.closed == 1
    assert "PRIVATE_CANARY" not in repr(outcome)


def test_cancel_failure_is_cleanup_uncertain_but_still_closes_every_resource(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(
        events,
        connection_options={
            "execute_failure": "EKO-P00",
            "cancel_raise": True,
        },
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert "raw_cancel" in events
    assert physical.cursor_value.closed is True and physical.closed == 1
    assert "PRIVATE_CANARY" not in repr(outcome)


@pytest.mark.parametrize("option", ["cursor_close_false", "cursor_close_raise"])
def test_cursor_close_uncertainty_blocks_without_post_close_use(
    isolated_serialized_boundary, option,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(
        events, connection_options={option: True},
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert comp.connection_observation.cursor_close_verified is False
    assert physical.closed == 1
    assert events[-2:] == ["raw_connection_close", "mutex_released"]


@pytest.mark.parametrize(
    "option", ["connection_close_false", "connection_close_raise"],
)
def test_physical_close_uncertainty_poisons_mutex_and_blocks_publication(
    isolated_serialized_boundary, option,
):
    events, _worker = isolated_serialized_boundary
    comp, _physical, _clock = make_composition(
        events, connection_options={option: True},
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_retained" in events and "mutex_released" not in events


def test_notice_is_rejected_without_echo_and_cleanup_precedes_result(
    isolated_serialized_boundary,
):
    events, _worker = isolated_serialized_boundary
    comp, physical, _clock = make_composition(
        events, connection_options={"notices": ("PRIVATE_CANARY",)},
    )
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert physical.closed == 1
    assert "PRIVATE_CANARY" not in repr(outcome)


def test_composition_and_path_are_single_attempt(isolated_serialized_boundary):
    events, _worker = isolated_serialized_boundary
    comp, _physical, _clock = make_composition(events)
    assert execute(comp).status is capture.RunStatus.COMPLETE
    with pytest.raises(composition.CompositionRejected, match="^composition_reused$"):
        execute(comp)


def test_atomic_sink_never_overwrites_or_discards_preexisting_final():
    sink = composition.AtomicNoOverwriteMemorySink(existing_final=b"existing")
    assert sink.final_exists() is True
    with pytest.raises(composition.CompositionRejected, match="^artifact_exists$"):
        sink.create_new_no_overwrite()
    sink.discard_all()
    assert sink.final_bytes == b"existing"


def test_frozen_statement_bytes_order_and_digests_match_document():
    comp = composition.build_disabled_orders_evidence_composition(
        path=composition.InjectedSerializedCredentialReadPath(
            lambda _deadline, _receiver: composition.PathAcquisition.NO_CONNECTION
        ),
        monotonic=Clock(),
    )
    lines = STATEMENTS_DOC.read_text(encoding="utf-8").splitlines(keepends=True)
    expected = []
    for spec in capture.STATEMENT_SPECS:
        begin = lines.index(f"-- BEGIN {spec.statement_id}\n")
        end = lines.index(f"-- END {spec.statement_id}\n", begin) + 1
        value = "".join(lines[begin:end]).encode("utf-8")
        expected.append((spec.statement_id, capture.sha256(value).hexdigest()))
    assert comp.statement_digests == tuple(expected)


def test_construction_is_disabled_and_submits_no_worker(
    isolated_serialized_boundary,
):
    _events, worker = isolated_serialized_boundary
    comp, _physical, _clock = make_composition([])
    assert comp.final_artifact is None
    assert comp.connection_observation.acquisition_count == 0
    assert worker._work_queue.qsize() == 0


def test_static_boundary_has_no_driver_credentials_runtime_or_activation():
    path = Path(composition.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported <= {
        "dataclasses", "datetime", "enum", "math", "pathlib", "time",
        "KaosEghis",
    }
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "psycopg", "socket", "requests", "credential_store", "getenv(",
        "logging", "print(",
    ):
        assert forbidden not in source
    assert repr(
        composition.InjectedSerializedCredentialReadPath(
            lambda _deadline, _receiver: composition.PathAcquisition.NO_CONNECTION
        )
    ) == "<InjectedSerializedCredentialReadPath: redacted>"
    main_source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert "kaosorders_non_phi_evidence_composition" not in main_source
