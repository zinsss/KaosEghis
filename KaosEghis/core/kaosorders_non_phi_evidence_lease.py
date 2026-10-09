"""Disabled concrete FIFO/mutex lease for the reviewed evidence executor.

This module opens no connection and is not imported by application runtime code.
It reuses the existing EMR read queue and exclusive-reader mutex only when an
explicit caller constructs and acquires the lease.
"""

import math
import threading
import time

from KaosEghis.core import emr_read_queue
from KaosEghis.core.kaosorders_non_phi_evidence_executor import SerializedReadLease


class EvidenceLeaseRejected(RuntimeError):
    """Fixed, non-sensitive lease rejection."""


class EghisFifoMutexLeaseBackend:
    """Single-attempt lease backed by the existing FIFO worker and named mutex."""

    __slots__ = (
        "_acquired", "_attempted", "_capacity", "_exclusive_reader",
        "_finished", "_future", "_health_check", "_held", "_lock",
        "_monotonic", "_poisoned", "_release_permitted", "_release_requested",
        "_release_verified",
        "_ownership_uncertain", "_unhealthy", "_worker", "_worker_state",
    )

    def __init__(self, *, monotonic=time.monotonic):
        self._monotonic = monotonic
        self._worker = emr_read_queue._worker
        self._capacity = emr_read_queue._capacity
        self._exclusive_reader = emr_read_queue._exclusive_reader
        self._health_check = emr_read_queue._check_health
        self._unhealthy = emr_read_queue._unhealthy
        self._worker_state = emr_read_queue._worker_state
        self._lock = threading.Lock()
        self._acquired = threading.Event()
        self._release_requested = threading.Event()
        self._finished = threading.Event()
        self._future = None
        self._attempted = False
        self._held = False
        self._release_verified = False
        self._release_permitted = False
        self._poisoned = False
        self._ownership_uncertain = False

    def __repr__(self) -> str:
        return "<EghisFifoMutexLeaseBackend: redacted>"

    @staticmethod
    def _valid_deadline(deadline: object) -> bool:
        return (
            type(deadline) in (int, float)
            and math.isfinite(deadline)
            and deadline >= 0
        )

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - self._monotonic())

    def _set_held(self, value: bool) -> None:
        with self._lock:
            self._held = value

    def held_by_caller(self) -> bool:
        with self._lock:
            return self._held or self._ownership_uncertain

    def acquire_until(self, deadline: float) -> bool:
        if not self._valid_deadline(deadline):
            raise EvidenceLeaseRejected("invalid_deadline")
        with self._lock:
            if self._attempted:
                raise EvidenceLeaseRejected("lease_reused")
            self._attempted = True
        if self._monotonic() > deadline:
            return False
        self._health_check()
        if getattr(self._worker_state, "running", False):
            raise EvidenceLeaseRejected("nested_lease")
        if not self._capacity.acquire(blocking=False):
            return False

        def run():
            self._worker_state.running = True
            entered = False
            try:
                self._health_check()
                if self._monotonic() > deadline:
                    return
                with self._exclusive_reader(
                    deadline=deadline, monotonic=self._monotonic,
                ):
                    self._health_check()
                    if self._monotonic() > deadline:
                        return
                    entered = True
                    self._set_held(True)
                    self._acquired.set()
                    if not self._release_requested.wait(self._remaining(deadline)):
                        self._unhealthy.set()
                        raise emr_read_queue.EmrReadSafetyError(
                            "Serialized lease cleanup is uncertain; operator recovery required."
                        )
                    with self._lock:
                        release_permitted = (
                            self._release_permitted and not self._poisoned
                        )
                    if not release_permitted:
                        raise emr_read_queue.EmrReadSafetyError(
                            "Serialized lease cleanup is uncertain; operator recovery required."
                        )
                self._set_held(False)
                with self._lock:
                    self._release_verified = self._release_requested.is_set()
            except emr_read_queue.EmrReadSafetyError:
                self._unhealthy.set()
                raise
            except BaseException:
                if entered:
                    self._unhealthy.set()
                raise
            finally:
                self._acquired.set()
                self._worker_state.running = False

        try:
            self._future = self._worker.submit(run)
        except BaseException:
            self._capacity.release()
            raise EvidenceLeaseRejected("lease_unavailable") from None

        def finished(_future):
            with self._lock:
                if not self._held:
                    self._ownership_uncertain = False
                self._finished.set()
            self._capacity.release()

        self._future.add_done_callback(finished)

        if not self._acquired.wait(self._remaining(deadline)):
            self._release_requested.set()
            cancelled = self._future.cancel()
            if not cancelled:
                with self._lock:
                    if self._finished.is_set():
                        return False
                    self._ownership_uncertain = True
                self._unhealthy.set()
            return False
        return self.held_by_caller()

    def release_owned(
        self, deadline: float, *, connection_cleanup_verified: bool,
    ) -> bool:
        if not self._valid_deadline(deadline):
            raise EvidenceLeaseRejected("invalid_deadline")
        if type(connection_cleanup_verified) is not bool:
            raise EvidenceLeaseRejected("invalid_cleanup_proof")
        with self._lock:
            if connection_cleanup_verified:
                if not self._poisoned:
                    self._release_permitted = True
            else:
                self._poisoned = True
                self._ownership_uncertain = True
                self._unhealthy.set()
        self._release_requested.set()
        future = self._future
        if future is None:
            return (
                connection_cleanup_verified
                and self.held_by_caller() is False
            )
        if not self._finished.wait(self._remaining(deadline)):
            self._unhealthy.set()
            return False
        try:
            future.result(timeout=0)
        except BaseException:
            return False
        with self._lock:
            return self._release_verified and not self._held


def build_disabled_orders_evidence_lease(
    *, monotonic=time.monotonic,
) -> SerializedReadLease:
    """Build the reviewed lease without activating any reader or runtime path."""

    return SerializedReadLease(EghisFifoMutexLeaseBackend(monotonic=monotonic))
