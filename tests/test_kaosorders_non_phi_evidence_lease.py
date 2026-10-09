import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_read_queue
from KaosEghis.core import kaosorders_non_phi_evidence_executor as executor
from KaosEghis.core import kaosorders_non_phi_evidence_lease as lease_module


@pytest.fixture
def isolated_fifo(monkeypatch):
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evidence-lease-test")
    retained = []
    events = []

    @contextmanager
    def exclusive_reader(**_kwargs):
        events.append("mutex:acquired")
        try:
            yield
        finally:
            events.append("mutex:released")

    monkeypatch.setattr(emr_read_queue, "_worker", worker)
    monkeypatch.setattr(emr_read_queue, "_capacity", threading.BoundedSemaphore(64))
    monkeypatch.setattr(emr_read_queue, "_exclusive_reader", exclusive_reader)
    monkeypatch.setattr(emr_read_queue, "_unhealthy", threading.Event())
    monkeypatch.setattr(emr_read_queue, "_retained_mutexes", retained)
    yield events, worker
    worker.shutdown(wait=True)


def test_disabled_factory_constructs_without_worker_submission(isolated_fifo):
    _events, worker = isolated_fifo
    lease = lease_module.build_disabled_orders_evidence_lease()
    assert type(lease) is executor.SerializedReadLease
    assert lease.acquisition_count == 0 and lease.held is False
    assert worker._work_queue.qsize() == 0


def test_concrete_backend_acquires_and_releases_existing_fifo_mutex(isolated_fifo):
    events, _worker = isolated_fifo
    lease = lease_module.build_disabled_orders_evidence_lease()
    deadline = time.monotonic() + 1
    lease.acquire(deadline)
    assert lease.acquisition_count == 1
    assert lease.acquisition_verified is True and lease.held is True
    lease.release_owned(deadline)
    assert lease.release_count == 1
    assert lease.release_verified is True and lease.held is False
    assert events == ["mutex:acquired", "mutex:released"]


def test_backend_queues_behind_existing_serialized_read(isolated_fifo):
    _events, _worker = isolated_fifo
    entered = threading.Event()
    release = threading.Event()

    def existing_read():
        entered.set()
        assert release.wait(2)

    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(emr_read_queue.run_serialized_read, existing_read)
        assert entered.wait(1)
        lease = lease_module.build_disabled_orders_evidence_lease()
        deadline = time.monotonic() + 1
        second = callers.submit(lease.acquire, deadline)
        time.sleep(0.02)
        assert second.done() is False
        release.set()
        first.result(1)
        second.result(1)
        assert lease.held is True
        lease.release_owned(deadline)
        assert lease.release_verified is True


def test_queued_deadline_cancels_before_mutex_and_proves_no_lease(isolated_fifo):
    _events, _worker = isolated_fifo
    entered = threading.Event()
    release = threading.Event()

    def existing_read():
        entered.set()
        assert release.wait(2)

    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(emr_read_queue.run_serialized_read, existing_read)
        assert entered.wait(1)
        lease = lease_module.build_disabled_orders_evidence_lease()
        lease.acquire(time.monotonic() + 0.03)
        assert lease.acquisition_count == 0
        assert lease.no_lease_proven is True and lease.held is False
        release.set()
        first.result(1)


def test_unreleased_deadline_marks_reader_unhealthy_and_remains_held(isolated_fifo):
    _events, _worker = isolated_fifo
    backend = lease_module.EghisFifoMutexLeaseBackend()
    deadline = time.monotonic() + 0.03
    assert backend.acquire_until(deadline) is True
    limit = time.monotonic() + 1
    while not emr_read_queue._unhealthy.is_set():
        assert time.monotonic() < limit
        time.sleep(0.005)
    assert backend.held_by_caller() is True
    assert backend.release_owned(deadline) is False
    with pytest.raises(emr_read_queue.EmrReadSafetyError):
        emr_read_queue._check_health()


def test_backend_is_single_attempt_even_after_verified_release(isolated_fifo):
    _events, _worker = isolated_fifo
    backend = lease_module.EghisFifoMutexLeaseBackend()
    deadline = time.monotonic() + 1
    assert backend.acquire_until(deadline) is True
    assert backend.release_owned(deadline) is True
    with pytest.raises(lease_module.EvidenceLeaseRejected, match="^lease_reused$"):
        backend.acquire_until(deadline)


@pytest.mark.parametrize("remaining,expected", [(0.123, 123), (-0.001, 0)])
def test_windows_named_mutex_wait_uses_bounded_deadline(monkeypatch, remaining, expected):
    waits = []
    fake_event = SimpleNamespace(
        WAIT_OBJECT_0=0,
        WAIT_ABANDONED=128,
        CreateMutex=lambda *_args: object(),
        WaitForSingleObject=lambda _handle, milliseconds: waits.append(milliseconds) or 0,
        ReleaseMutex=lambda _handle: None,
    )
    fake_api = SimpleNamespace(CloseHandle=lambda _handle: None)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "win32event", fake_event)
    monkeypatch.setitem(sys.modules, "win32api", fake_api)
    with emr_read_queue._exclusive_reader(
        deadline=10 + remaining, monotonic=lambda: 10,
    ):
        pass
    assert waits == [expected]


def test_static_boundary_has_no_source_driver_credentials_or_activation():
    path = Path(lease_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports <= {"math", "threading", "time", "KaosEghis"}
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "psycopg", "connection_string", "getenv", "settings", "execute(",
        "cursor", "patient", "socket", "requests", "logging", "print(",
    ):
        assert forbidden not in source
    assert repr(lease_module.EghisFifoMutexLeaseBackend()) == (
        "<EghisFifoMutexLeaseBackend: redacted>"
    )
