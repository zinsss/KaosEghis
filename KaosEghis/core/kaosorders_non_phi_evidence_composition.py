"""Disabled composition for the reviewed Orders non-PHI evidence package.

This module has no runtime import, credential lookup, scheduler, route, or
activation.  A future approved caller must inject one opaque connection string
into the exact one-shot psycopg2 boundary.  Construction and tests perform no
authentication or source access.
"""

from dataclasses import dataclass
from datetime import date, datetime
import importlib
import math
from pathlib import Path
import threading
import time

from KaosEghis.core import kaosorders_non_phi_evidence_capture as capture
from KaosEghis.core import kaosorders_non_phi_evidence_executor as executor
from KaosEghis.core.kaosorders_non_phi_evidence_lease import (
    build_disabled_orders_evidence_lease,
)


_STATEMENT_DOCUMENT = (
    Path(__file__).parents[2]
    / "docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md"
)


class CompositionRejected(RuntimeError):
    """Fixed non-sensitive composition rejection."""


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


def _valid_deadline(deadline: object) -> bool:
    return (
        type(deadline) in (int, float)
        and math.isfinite(deadline)
        and deadline >= 0
    )


def _raise_if_late(*, monotonic: object, deadline: float) -> None:
    if not callable(monotonic) or monotonic() > deadline:
        raise CompositionRejected("deadline_exceeded")


_FAILED = object()


def _bounded_call(*, action: object, deadline: float, monotonic: object):
    """Run one potentially blocking driver primitive within an absolute fence.

    The daemon containment thread is never treated as proof of completion.  A
    timeout returns immediately and the caller must retain/poison its lease.
    Exceptions and values remain private to this module and are never echoed.
    """

    if not callable(action) or not _valid_deadline(deadline):
        raise CompositionRejected("invalid_deadline_operation")
    finished = threading.Event()
    state: dict[str, object] = {}

    def target() -> None:
        try:
            state["value"] = action()
        except BaseException:
            state["value"] = _FAILED
        finally:
            finished.set()

    threading.Thread(
        target=target,
        name="eghis-evidence-bounded-call",
        daemon=True,
    ).start()
    try:
        remaining = max(0.0, deadline - monotonic())
    except Exception:
        raise CompositionRejected("invalid_clock") from None
    if not finished.wait(remaining):
        return False, None
    return True, state.get("value", _FAILED)


def _load_frozen_statements() -> tuple[tuple[str, bytes], ...]:
    """Load only the fixed repository document and reproduce reviewed bytes."""

    try:
        lines = _STATEMENT_DOCUMENT.read_text(encoding="utf-8").splitlines(
            keepends=True,
        )
        statements = []
        for spec in capture.STATEMENT_SPECS:
            begin = lines.index(f"-- BEGIN {spec.statement_id}\n")
            end = lines.index(f"-- END {spec.statement_id}\n", begin) + 1
            value = "".join(lines[begin:end]).encode("utf-8")
            if capture.sha256(value).hexdigest() != spec.sha256_hex:
                raise CompositionRejected("statement_inventory_mismatch")
            statements.append((spec.statement_id, value))
    except CompositionRejected:
        raise
    except Exception:
        raise CompositionRejected("statement_inventory_unavailable") from None
    if tuple(item[0] for item in statements) != tuple(
        spec.statement_id for spec in capture.STATEMENT_SPECS
    ):
        raise CompositionRejected("statement_inventory_mismatch")
    return tuple(statements)


class Psycopg2SingleConnectionPath(_Redacted):
    """Exact one-shot allocation owner; never a caller-supplied allocator.

    The opaque value is consumed once by this exact implementation, cleared
    immediately, and never exposed by repr, observations, errors, or artifacts.
    The driver call is contained by the shared deadline.  If it returns late,
    this owner closes the returned object itself while the serialized lease
    remains poisoned because timely cleanup was not proven.
    """

    __slots__ = (
        "_attempted", "_connection_string", "_late_close", "_lock",
        "_no_connection_proven", "_owned", "_ownership_uncertain",
    )

    def __init__(self, connection_string: object):
        if type(connection_string) is not str or not connection_string:
            raise CompositionRejected("invalid_connection_path")
        self._connection_string = connection_string
        self._attempted = False
        self._lock = threading.Lock()
        self._owned = None
        self._late_close = False
        self._no_connection_proven = False
        self._ownership_uncertain = False

    @property
    def no_connection_proven(self) -> bool:
        return self._no_connection_proven

    @property
    def ownership_uncertain(self) -> bool:
        return self._ownership_uncertain

    @staticmethod
    def _connect(
        *, connection_string: str, connect_timeout: int,
    ) -> object:
        driver = importlib.import_module("psycopg2")
        return driver.connect(
            connection_string,
            connect_timeout=connect_timeout,
            application_name="KaosEghis-OrdersEvidence",
        )

    def acquire_until(self, *, deadline: float, monotonic: object) -> object:
        if self._attempted or not _valid_deadline(deadline):
            raise CompositionRejected("connection_path_reused")
        self._attempted = True
        try:
            remaining = deadline - monotonic()
        except Exception:
            raise CompositionRejected("invalid_clock") from None
        if remaining <= 0:
            self._connection_string = ""
            self._ownership_uncertain = True
            raise CompositionRejected("deadline_exceeded")
        connection_string = self._connection_string
        self._connection_string = ""
        connect_timeout = max(1, min(10, math.ceil(remaining)))
        done = threading.Event()
        state: dict[str, object] = {}

        def target() -> None:
            physical = None
            try:
                physical = self._connect(
                    connection_string=connection_string,
                    connect_timeout=connect_timeout,
                )
                if physical is None:
                    state["failed"] = True
                else:
                    with self._lock:
                        if self._late_close:
                            state["late"] = physical
                        else:
                            self._owned = physical
            except BaseException:
                state["failed"] = True
            finally:
                done.set()
            late = state.get("late")
            if late is not None:
                try:
                    late.close()
                except BaseException:
                    pass

        threading.Thread(
            target=target,
            name="eghis-evidence-connect",
            daemon=True,
        ).start()
        try:
            wait_remaining = max(0.0, deadline - monotonic())
            clock_failed = False
        except Exception:
            wait_remaining = 0.0
            clock_failed = True
        completed = done.wait(wait_remaining)
        if clock_failed or not completed:
            with self._lock:
                self._late_close = True
                physical = self._owned
                self._owned = None
            self._ownership_uncertain = True
            if physical is not None:
                self._owned = physical
            raise CompositionRejected("deadline_exceeded")
        with self._lock:
            physical = self._owned
            self._owned = None
        if state.get("failed") is True and physical is None:
            self._no_connection_proven = True
            raise CompositionRejected("connection_unavailable")
        if physical is None:
            self._ownership_uncertain = True
            raise CompositionRejected("connection_acquisition_failed")
        return physical

    def take_owned_after_failure(self) -> object | None:
        with self._lock:
            physical = self._owned
            self._owned = None
        return physical


class _OwnedCursor(_Redacted):
    __slots__ = ("_adapter", "_cursor")

    def __init__(self, adapter: object, cursor: object):
        self._adapter = adapter
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    @property
    def closed(self) -> bool:
        return self._adapter.cursor_close_verified is True

    def execute(self, statement: str) -> None:
        self._adapter._before_source_operation()
        completed, value = _bounded_call(
            action=lambda: self._cursor.execute(statement),
            deadline=self._adapter._deadline,
            monotonic=self._adapter._monotonic,
        )
        if not completed:
            self._adapter._ownership_uncertain = True
            raise CompositionRejected("source_operation_timeout")
        if value is _FAILED:
            raise CompositionRejected("source_operation_failed") from None
        self._adapter._after_source_operation()

    def fetchmany(self, maximum: int):
        self._adapter._before_source_operation()
        completed, rows = _bounded_call(
            action=lambda: self._cursor.fetchmany(maximum),
            deadline=self._adapter._deadline,
            monotonic=self._adapter._monotonic,
        )
        if not completed:
            self._adapter._ownership_uncertain = True
            raise CompositionRejected("source_operation_timeout")
        if rows is _FAILED:
            raise CompositionRejected("source_operation_failed") from None
        self._adapter._after_source_operation()
        return rows

    def close(self) -> None:
        self._adapter._events.append("cursor_close_started")
        completed, value = _bounded_call(
            action=self._cursor.close,
            deadline=self._adapter._deadline,
            monotonic=self._adapter._monotonic,
        )
        verified = (
            completed and value is not _FAILED
            and getattr(self._cursor, "closed", None) is True
        )
        self._adapter._cursor_close_verified = verified
        if not verified:
            self._adapter._ownership_uncertain = True
            raise CompositionRejected("cursor_close_unverified")
        self._adapter._events.append("cursor_close_verified")


class _OwnedConnection(_Redacted):
    __slots__ = ("_adapter", "_connection")

    def __init__(self, adapter: object, connection: object):
        self._adapter = adapter
        self._connection = connection

    @property
    def notices(self):
        return getattr(self._connection, "notices", ())

    def cursor(self) -> _OwnedCursor:
        self._adapter._before_source_operation()
        if self._adapter.cursor_acquisition_count != 0:
            raise CompositionRejected("cursor_reused")
        completed, cursor = _bounded_call(
            action=self._connection.cursor,
            deadline=self._adapter._deadline,
            monotonic=self._adapter._monotonic,
        )
        if not completed or cursor is _FAILED:
            self._adapter._ownership_uncertain = True
            raise CompositionRejected("cursor_acquisition_failed") from None
        if cursor is None:
            raise CompositionRejected("cursor_acquisition_failed")
        self._adapter._cursor_acquisition_count = 1
        self._adapter._events.append("cursor_acquired")
        self._adapter._after_source_operation()
        return _OwnedCursor(self._adapter, cursor)

    def cancel(self) -> None:
        self._adapter._events.append("cancel_started")
        completed, value = _bounded_call(
            action=self._connection.cancel,
            deadline=self._adapter._deadline,
            monotonic=self._adapter._monotonic,
        )
        if not completed or value is _FAILED:
            self._adapter._ownership_uncertain = True
            raise CompositionRejected("cancel_failed") from None
        self._adapter._events.append("cancel_finished")


@dataclass(frozen=True, slots=True, repr=False)
class ConnectionObservation(_Redacted):
    acquisition_count: int
    no_connection_proven: bool
    acquisition_complete: bool
    cursor_acquisition_count: int
    cursor_close_verified: bool
    physical_close_verified: bool
    events: tuple[str, ...]


class ResourceOwningConnectionAdapter(_Redacted):
    """Own one injected physical connection until verified close."""

    __slots__ = (
        "_acquisition_complete", "_acquisition_count", "_attempted",
        "_close_attempted", "_close_verified", "_connection", "_deadline",
        "_events", "_monotonic", "_no_connection_proven", "_path",
        "_physical", "_ownership_uncertain", "_cursor_acquisition_count",
        "_cursor_close_verified",
    )

    def __init__(
        self, path: Psycopg2SingleConnectionPath, *,
        monotonic=time.monotonic,
    ):
        if type(path) is not Psycopg2SingleConnectionPath:
            raise CompositionRejected("invalid_connection_path")
        if not callable(monotonic):
            raise CompositionRejected("invalid_clock")
        self._path = path
        self._monotonic = monotonic
        self._attempted = False
        self._close_attempted = False
        self._acquisition_count = 0
        self._acquisition_complete = False
        self._no_connection_proven = False
        self._close_verified = False
        self._ownership_uncertain = False
        self._cursor_acquisition_count = 0
        self._cursor_close_verified = False
        self._physical = None
        self._connection = None
        self._deadline = None
        self._events = []

    @property
    def acquisition_count(self) -> int:
        return self._acquisition_count

    @property
    def acquisition_complete(self) -> bool:
        return self._acquisition_complete

    @property
    def no_connection_proven(self) -> bool:
        return self._no_connection_proven

    @property
    def close_verified(self) -> bool:
        return self._close_verified

    @property
    def connection(self):
        return self._connection

    @property
    def cursor_acquisition_count(self) -> int:
        return self._cursor_acquisition_count

    @property
    def cursor_close_verified(self) -> bool:
        return self._cursor_close_verified

    @property
    def observation(self) -> ConnectionObservation:
        return ConnectionObservation(
            self._acquisition_count,
            self._no_connection_proven,
            self._acquisition_complete,
            self._cursor_acquisition_count,
            self._cursor_close_verified,
            self._close_verified,
            tuple(self._events),
        )

    def _before_source_operation(self) -> None:
        if self._close_attempted or self._deadline is None:
            raise CompositionRejected("connection_not_available")
        _raise_if_late(monotonic=self._monotonic, deadline=self._deadline)

    def _after_source_operation(self) -> None:
        _raise_if_late(monotonic=self._monotonic, deadline=self._deadline)

    def _register(self, physical: object) -> None:
        if self._acquisition_count != 0 or physical is None:
            self._ownership_uncertain = True
            raise CompositionRejected("connection_acquisition_failed")
        self._physical = physical
        self._connection = _OwnedConnection(self, physical)
        self._acquisition_count = 1
        self._no_connection_proven = False
        self._events.append("physical_connection_received")

    def acquire(self, deadline: float) -> None:
        if self._attempted or not _valid_deadline(deadline):
            raise CompositionRejected("connection_adapter_reused")
        self._attempted = True
        self._deadline = deadline
        _raise_if_late(monotonic=self._monotonic, deadline=deadline)
        try:
            physical = self._path.acquire_until(
                deadline=deadline, monotonic=self._monotonic,
            )
        except Exception:
            physical = self._path.take_owned_after_failure()
            if physical is not None:
                self._register(physical)
            self._no_connection_proven = self._path.no_connection_proven
            self._ownership_uncertain = (
                self._ownership_uncertain or self._path.ownership_uncertain
            )
            raise CompositionRejected("connection_acquisition_failed") from None
        self._register(physical)
        _raise_if_late(monotonic=self._monotonic, deadline=deadline)
        self._acquisition_complete = True
        self._events.append("connection_acquisition_complete")

    def close_owned(self, deadline: float) -> None:
        if self._close_attempted:
            raise CompositionRejected("connection_close_reused")
        self._close_attempted = True
        if self._physical is None:
            return
        self._events.append("physical_close_started")
        completed, value = _bounded_call(
            action=self._physical.close,
            deadline=deadline,
            monotonic=self._monotonic,
        )
        closed = getattr(self._physical, "closed", None)
        verified = (
            completed and value is not _FAILED
            and type(closed) is int and closed > 0
        )
        self._close_verified = verified and not self._ownership_uncertain
        if not self._close_verified:
            raise CompositionRejected("physical_close_unverified")
        self._events.append("physical_close_verified")
        self._physical = None
        self._connection = None


class AtomicNoOverwriteMemorySink(_Redacted):
    """Atomic, no-overwrite, volatile sink for the disabled composition."""

    __slots__ = ("_created_final", "_existing_final", "_final", "_temporary")

    def __init__(self, *, existing_final: bytes | None = None):
        if existing_final is not None and type(existing_final) is not bytes:
            raise CompositionRejected("invalid_existing_artifact")
        self._existing_final = existing_final is not None
        self._created_final = False
        self._final = existing_final
        self._temporary = None

    @property
    def final_bytes(self) -> bytes | None:
        return self._final

    def final_exists(self) -> bool:
        return self._final is not None

    def create_new_no_overwrite(self) -> None:
        if self._temporary is not None or self._final is not None:
            raise CompositionRejected("artifact_exists")
        self._temporary = b""

    def write(self, artifact: bytes) -> None:
        if self._temporary is None or type(artifact) is not bytes:
            raise CompositionRejected("artifact_write_failed")
        if len(artifact) > capture.MAX_ARTIFACT_BYTES:
            raise CompositionRejected("artifact_write_failed")
        self._temporary = artifact

    def publish_no_overwrite(self) -> None:
        if self._temporary is None or self._final is not None:
            raise CompositionRejected("artifact_exists")
        self._final = self._temporary
        self._temporary = None
        self._created_final = True

    def discard_all(self) -> None:
        self._temporary = None
        if self._created_final and not self._existing_final:
            self._final = None
            self._created_final = False


class DisabledOrdersEvidenceComposition(_Redacted):
    """Single-use, configuration-free composition; never runtime activated."""

    __slots__ = (
        "_attempted", "_connection_owner", "_lease", "_monotonic", "_sink",
        "_statement_items",
    )

    def __init__(
        self, path: Psycopg2SingleConnectionPath, *,
        monotonic=time.monotonic,
    ):
        self._statement_items = _load_frozen_statements()
        self._monotonic = monotonic
        self._lease = build_disabled_orders_evidence_lease(monotonic=monotonic)
        self._connection_owner = ResourceOwningConnectionAdapter(
            path, monotonic=monotonic,
        )
        self._sink = AtomicNoOverwriteMemorySink()
        self._attempted = False

    @property
    def connection_observation(self) -> ConnectionObservation:
        return self._connection_owner.observation

    @property
    def final_artifact(self) -> bytes | None:
        return self._sink.final_bytes

    @property
    def statement_digests(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (statement_id, capture.sha256(value).hexdigest())
            for statement_id, value in self._statement_items
        )

    def execute_once(
        self, *, identity: executor.IdentityPathAttestation,
        approval: executor.ExecutorApproval, window: executor.ExecutionWindow,
        runtime_commit: str, evidence_date: date, now: datetime,
    ) -> capture.CaptureOutcome:
        if self._attempted:
            raise CompositionRejected("composition_reused")
        self._attempted = True
        return executor.execute_reviewed_package_once(
            identity=identity,
            approval=approval,
            window=window,
            runtime_commit=runtime_commit,
            evidence_date=evidence_date,
            now=now,
            statement_bytes=dict(self._statement_items),
            monotonic=self._monotonic,
            serialized_lease=self._lease,
            connection_owner=self._connection_owner,
            sink=self._sink,
        )


def build_disabled_orders_evidence_composition(
    *, path: Psycopg2SingleConnectionPath,
    monotonic=time.monotonic,
) -> DisabledOrdersEvidenceComposition:
    """Construct the disabled composition without acquiring any resource."""

    return DisabledOrdersEvidenceComposition(path, monotonic=monotonic)
