import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import inspect
import sys
import threading
import time

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

    def set(self, value):
        self.value = value


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
        close_raise=False, close_delay=0.0, execute_delay=0.0,
        fetch_delay=0.0, execute_completion_time=None,
        fetch_completion_time=None,
    ):
        self.events = events
        self.clock = clock
        self.execute_failure = execute_failure
        self.close_false = close_false
        self.close_raise = close_raise
        self.close_delay = close_delay
        self.execute_delay = execute_delay
        self.fetch_delay = fetch_delay
        self.execute_completion_time = execute_completion_time
        self.fetch_completion_time = fetch_completion_time
        self.current = None
        self.description = None
        self.closed = False

    def _assert_open(self):
        if self.closed:
            raise AssertionError("post-close cursor use")

    def execute(self, statement):
        self._assert_open()
        statement_id = statement.splitlines()[0].split()[-1]
        self.events.append(f"execute:{statement_id}")
        if self.execute_delay:
            time.sleep(self.execute_delay)
        if self.execute_completion_time is not None:
            self.clock.set(self.execute_completion_time)
        self.current = statement_id
        if statement_id == self.execute_failure:
            raise RuntimeError("PRIVATE_CANARY")
        spec = next(item for item in capture.STATEMENT_SPECS if item.statement_id == statement_id)
        self.description = (
            None if not spec.columns else tuple((name,) for name in spec.columns)
        )

    def fetchmany(self, _maximum):
        self._assert_open()
        self.events.append(f"fetch:{self.current}")
        if self.fetch_delay:
            time.sleep(self.fetch_delay)
        if self.fetch_completion_time is not None:
            self.clock.set(self.fetch_completion_time)
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
        if self.close_delay:
            time.sleep(self.close_delay)
        if self.close_raise:
            raise RuntimeError("PRIVATE_CANARY")
        if not self.close_false:
            self.closed = True


class RawConnection:
    notices = ()

    def __init__(
        self, events, *, clock, execute_failure=None, cursor_close_false=False,
        cursor_close_raise=False, cursor_close_delay=0.0,
        connection_close_false=False,
        connection_close_raise=False, cancel_raise=False, notices=(),
        cancel_delay=0.0, connection_close_delay=0.0,
        execute_delay=0.0, fetch_delay=0.0,
        execute_completion_time=None, fetch_completion_time=None,
        connection_close_completion_time=None,
    ):
        self.events = events
        self.clock = clock
        self.closed = 0
        self.connection_close_false = connection_close_false
        self.connection_close_raise = connection_close_raise
        self.cancel_raise = cancel_raise
        self.cancel_delay = cancel_delay
        self.connection_close_delay = connection_close_delay
        self.connection_close_completion_time = connection_close_completion_time
        self.notices = notices
        self.cursor_value = RawCursor(
            events,
            clock=clock,
            execute_failure=execute_failure,
            close_false=cursor_close_false,
            close_raise=cursor_close_raise,
            close_delay=cursor_close_delay,
            execute_delay=execute_delay,
            fetch_delay=fetch_delay,
            execute_completion_time=execute_completion_time,
            fetch_completion_time=fetch_completion_time,
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
        if self.cancel_delay:
            time.sleep(self.cancel_delay)
        if self.cancel_raise:
            raise RuntimeError("PRIVATE_CANARY")

    def close(self):
        self.events.append("raw_connection_close")
        if self.connection_close_delay:
            time.sleep(self.connection_close_delay)
        if self.connection_close_completion_time is not None:
            self.clock.set(self.connection_close_completion_time)
        if self.connection_close_raise:
            raise RuntimeError("PRIVATE_CANARY")
        if not self.connection_close_false:
            self.closed = 1
class FakePsycopg2:
    def __init__(
        self, events, physical, *, mode="return", delay=0.0,
    ):
        self.events = events
        self.physical = physical
        self.mode = mode
        self.delay = delay
        self.calls = 0
        self.arguments = None

    def connect(self, connection_string, **options):
        self.calls += 1
        self.arguments = (connection_string, options)
        self.events.append("path_called")
        if self.delay:
            time.sleep(self.delay)
        if self.mode == "raise":
            raise RuntimeError("PRIVATE_CANARY")
        return self.physical


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
    yield events, worker, monkeypatch
    worker.shutdown(wait=True)


def make_composition(
    events, monkeypatch, *, clock=None, path_mode="return",
    path_delay=0.0, connection_options=None,
):
    clock = clock or Clock()
    connection_options = connection_options or {}
    physical = RawConnection(events, clock=clock, **connection_options)

    driver = FakePsycopg2(
        events, physical, mode=path_mode, delay=path_delay,
    )
    monkeypatch.setitem(sys.modules, "psycopg2", driver)
    path = composition.Psycopg2SingleConnectionPath(
        "postgresql://synthetic.invalid/review",
    )
    comp = composition.build_disabled_orders_evidence_composition(
        path=path, monotonic=clock,
    )
    return comp, physical, clock, driver


def test_success_binds_frozen_inventory_serialized_path_cleanup_and_atomic_sink(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, driver = make_composition(events, monkeypatch)
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.COMPLETE
    assert comp.final_artifact == outcome.artifact
    assert events.index("mutex_acquired") < events.index("path_called")
    assert events.index("raw_cursor_close") < events.index("raw_connection_close")
    assert events.index("raw_connection_close") < events.index("mutex_released")
    assert events.count("path_called") == 1
    assert driver.calls == 1
    assert driver.arguments == (
        "postgresql://synthetic.invalid/review",
        {
            "connect_timeout": 10,
            "application_name": "KaosEghis-OrdersEvidence",
        },
    )
    assert events[events.index("raw_connection_close") + 1:] == ["mutex_released"]
    assert physical.closed == 1
    observation = comp.connection_observation
    assert observation.acquisition_count == 1
    assert observation.cursor_acquisition_count == 1
    assert observation.cursor_close_verified is True
    assert observation.physical_close_verified is True
    assert len(comp.statement_digests) == 9


def test_driver_failure_derives_no_connection_and_never_executes_or_publishes(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, _physical, _clock, driver = make_composition(
        events, monkeypatch, path_mode="raise",
    )
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert not any(item.startswith("execute:") for item in events)
    assert driver.calls == 1
    assert comp.connection_observation.no_connection_proven is True
    assert "mutex_released" in events


def test_exact_boundary_has_no_callback_or_caller_asserted_acquisition_result(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, _physical, _clock, driver = make_composition(events, monkeypatch)
    parameters = inspect.signature(
        composition.Psycopg2SingleConnectionPath.acquire_until,
    ).parameters
    assert tuple(parameters) == ("self", "deadline", "monotonic")
    assert not hasattr(composition, "PathAcquisition")
    assert not hasattr(composition, "InjectedSerializedCredentialReadPath")
    assert execute(comp).status is capture.RunStatus.COMPLETE
    assert driver.calls == 1


def test_concrete_owner_performs_one_driver_allocation_with_no_delivery_surface(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, driver = make_composition(events, monkeypatch)
    assert execute(comp).status is capture.RunStatus.COMPLETE
    assert driver.calls == 1 and physical.closed == 1
    source = Path(composition.__file__).read_text(encoding="utf-8")
    assert "receiver" not in source and "PathAcquisition" not in source
    assert source.count("driver.connect(") == 1


def test_source_failure_cancels_rolls_back_closes_and_never_echoes(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, _driver = make_composition(
        events, monkeypatch,
        connection_options={"execute_failure": "EKO-P00"},
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
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, _driver = make_composition(
        events, monkeypatch,
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
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, _driver = make_composition(
        events, monkeypatch, connection_options={option: True},
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert comp.connection_observation.cursor_close_verified is False
    assert physical.closed == 1
    assert events[-2:] == ["raw_connection_close", "mutex_retained"]
    assert emr_read_queue._unhealthy.is_set()


@pytest.mark.parametrize(
    "option", ["connection_close_false", "connection_close_raise"],
)
def test_physical_close_uncertainty_poisons_mutex_and_blocks_publication(
    isolated_serialized_boundary, option,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, _physical, _clock, _driver = make_composition(
        events, monkeypatch, connection_options={option: True},
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_released" not in events


def test_notice_is_rejected_without_echo_and_cleanup_precedes_result(
    isolated_serialized_boundary,
):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, physical, _clock, _driver = make_composition(
        events, monkeypatch,
        connection_options={"notices": ("PRIVATE_CANARY",)},
    )
    outcome = execute(comp)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None and comp.final_artifact is None
    assert physical.closed == 1
    assert "PRIVATE_CANARY" not in repr(outcome)


@pytest.mark.parametrize("delay", [0.20, 2.0], ids=["slow", "hanging"])
def test_acquisition_is_deadline_bounded_and_late_result_poisons(
    isolated_serialized_boundary, monkeypatch, delay,
):
    events, _worker, boundary_patch = isolated_serialized_boundary
    monkeypatch.setattr(capture, "GLOBAL_DEADLINE_SECONDS", 0.05)
    comp, _physical, _clock, driver = make_composition(
        events, boundary_patch, clock=time.monotonic, path_delay=delay,
    )
    started = time.monotonic()
    outcome = execute(comp)
    elapsed = time.monotonic() - started
    assert elapsed < 0.15
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert driver.calls == 1
    assert not any(item.startswith("execute:") for item in events)
    assert comp.connection_observation.no_connection_proven is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_released" not in events


@pytest.mark.parametrize(
    "options",
    [
        {"execute_failure": "EKO-P00", "cancel_delay": 0.20},
        {"execute_failure": "EKO-P00", "cancel_delay": 2.0},
        {"cursor_close_delay": 0.20},
        {"cursor_close_delay": 2.0},
        {"connection_close_delay": 0.20},
        {"connection_close_delay": 2.0},
    ],
    ids=[
        "slow-cancel", "hanging-cancel", "slow-cursor-close",
        "hanging-cursor-close", "slow-physical-close",
        "hanging-physical-close",
    ],
)
def test_cleanup_primitives_share_deadline_and_never_claim_timed_out_close(
    isolated_serialized_boundary, monkeypatch, options,
):
    events, _worker, boundary_patch = isolated_serialized_boundary
    monkeypatch.setattr(capture, "GLOBAL_DEADLINE_SECONDS", 0.05)
    comp, _physical, _clock, _driver = make_composition(
        events, boundary_patch, clock=time.monotonic,
        connection_options=options,
    )
    started = time.monotonic()
    outcome = execute(comp)
    elapsed = time.monotonic() - started
    assert elapsed < 0.15
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_released" not in events


@pytest.mark.parametrize(
    ("options", "expected_executes", "expected_fetches"),
    [
        ({"execute_delay": 0.20}, ["execute:EKO-C00"], []),
        ({"execute_delay": 2.0}, ["execute:EKO-C00"], []),
        (
            {"fetch_delay": 0.20},
            [
                "execute:EKO-C00", "execute:EKO-C01", "execute:EKO-C02",
                "execute:EKO-C03", "execute:EKO-P00",
            ],
            ["fetch:EKO-P00"],
        ),
        (
            {"fetch_delay": 2.0},
            [
                "execute:EKO-C00", "execute:EKO-C01", "execute:EKO-C02",
                "execute:EKO-C03", "execute:EKO-P00",
            ],
            ["fetch:EKO-P00"],
        ),
    ],
    ids=["slow-execute", "hanging-execute", "slow-fetch", "hanging-fetch"],
)
def test_execute_and_fetch_share_deadline_and_block_post_deadline_source_use(
    isolated_serialized_boundary, monkeypatch, options,
    expected_executes, expected_fetches,
):
    events, _worker, boundary_patch = isolated_serialized_boundary
    monkeypatch.setattr(capture, "GLOBAL_DEADLINE_SECONDS", 0.05)
    comp, _physical, _clock, _driver = make_composition(
        events, boundary_patch, clock=time.monotonic,
        connection_options=options,
    )
    started = time.monotonic()
    outcome = execute(comp)
    elapsed = time.monotonic() - started
    assert elapsed < 0.15
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert [item for item in events if item.startswith("execute:")] == expected_executes
    assert [item for item in events if item.startswith("fetch:")] == expected_fetches
    assert "execute:EKO-C99" not in events
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_released" not in events
    if 0.20 in options.values():
        time.sleep(0.22)
        assert [
            item for item in events
            if item.startswith(("execute:", "fetch:"))
        ] == expected_executes + expected_fetches


def test_bounded_call_accepts_exact_boundary_and_rejects_just_after():
    exact_clock = Clock()

    def complete_at_boundary():
        exact_clock.set(0.05)
        return "accepted"

    completed, value = composition._bounded_call(
        action=complete_at_boundary,
        deadline=0.05,
        monotonic=exact_clock,
    )
    assert completed is True and value == "accepted"

    late_clock = Clock()

    def complete_just_after():
        late_clock.set(0.050001)
        return "must-be-discarded"

    completed, value = composition._bounded_call(
        action=complete_just_after,
        deadline=0.05,
        monotonic=late_clock,
    )
    assert completed is False and value is None


@pytest.mark.parametrize(
    ("options", "expected_executes", "expected_fetches"),
    [
        (
            {"execute_completion_time": 0.050001},
            ["execute:EKO-C00"],
            [],
        ),
        (
            {"fetch_completion_time": 0.050001},
            [
                "execute:EKO-C00", "execute:EKO-C01", "execute:EKO-C02",
                "execute:EKO-C03", "execute:EKO-P00",
            ],
            ["fetch:EKO-P00"],
        ),
        (
            {"connection_close_completion_time": 0.050001},
            [
                "execute:EKO-C00", "execute:EKO-C01", "execute:EKO-C02",
                "execute:EKO-C03", "execute:EKO-P00", "execute:EKO-V01",
                "execute:EKO-M10", "execute:EKO-K20", "execute:EKO-C99",
            ],
            [
                "fetch:EKO-P00", "fetch:EKO-V01", "fetch:EKO-M10",
                "fetch:EKO-K20",
            ],
        ),
    ],
    ids=["execute-just-after", "fetch-just-after", "close-just-after"],
)
def test_just_after_deadline_completion_is_discarded_and_poisons_lease(
    isolated_serialized_boundary, monkeypatch, options,
    expected_executes, expected_fetches,
):
    events, _worker, boundary_patch = isolated_serialized_boundary
    monkeypatch.setattr(capture, "GLOBAL_DEADLINE_SECONDS", 0.05)
    comp, _physical, _clock, _driver = make_composition(
        events, boundary_patch, clock=Clock(), connection_options=options,
    )
    outcome = execute(comp)
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and comp.final_artifact is None
    assert [item for item in events if item.startswith("execute:")] == expected_executes
    assert [item for item in events if item.startswith("fetch:")] == expected_fetches
    assert comp.connection_observation.physical_close_verified is False
    assert emr_read_queue._unhealthy.is_set()
    assert "mutex_released" not in events


def test_composition_and_path_are_single_attempt(isolated_serialized_boundary):
    events, _worker, monkeypatch = isolated_serialized_boundary
    comp, _physical, _clock, _driver = make_composition(events, monkeypatch)
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
        path=composition.Psycopg2SingleConnectionPath(
            "postgresql://synthetic.invalid/review",
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
    _events, worker, monkeypatch = isolated_serialized_boundary
    comp, _physical, _clock, driver = make_composition([], monkeypatch)
    assert comp.final_artifact is None
    assert comp.connection_observation.acquisition_count == 0
    assert worker._work_queue.qsize() == 0
    assert driver.calls == 0


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
        "dataclasses", "datetime", "importlib", "math", "pathlib",
        "threading", "time",
        "KaosEghis",
    }
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "socket", "requests", "credential_store", "getenv(",
        "logging", "print(",
    ):
        assert forbidden not in source
    assert repr(
        composition.Psycopg2SingleConnectionPath(
            "postgresql://synthetic.invalid/review",
        )
    ) == "<Psycopg2SingleConnectionPath: redacted>"
    main_source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert "kaosorders_non_phi_evidence_composition" not in main_source
