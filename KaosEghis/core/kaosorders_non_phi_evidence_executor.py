"""Disabled, injected executor candidate for the frozen Orders evidence package.

There is no credential lookup, source discovery, runtime binding, or connection
factory here.  Every external capability is injected after prerequisite review.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
import re

from KaosEghis.core import kaosorders_non_phi_evidence_capture as capture


ATTESTATION_CONTRACT = "kaoseghis.orders-evidence-read-path-attestation.v1"
EXECUTOR_APPROVAL_CONTRACT = "kaoseghis.orders-evidence-executor-approval.v1"
WINDOW_CONTRACT = "kaoseghis.orders-evidence-window.v1"
IDENTITY_CLASS = "dedicated-least-privilege-read-only"
PATH_CLASS = "existing-serialized-read-single-connection"
AUTHORITY_ROLE = "database-security-authority"
REVIEWER_ROLE = "independent-integration-review"
MAX_WINDOW_SECONDS = 1800
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class ExecutorReason(StrEnum):
    PREREQUISITE_UNPROVEN = "prerequisite_unproven"
    INVENTORY_MISMATCH = "inventory_mismatch"
    TIMEOUT = "timeout"
    OBSERVATION_REJECTED = "observation_rejected"
    CLEANUP_UNCERTAIN = "cleanup_uncertain"
    PUBLICATION_FAILED = "publication_failed"


class ExecutorRejected(RuntimeError):
    """Fixed non-sensitive executor rejection."""


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


@dataclass(frozen=True, slots=True, repr=False)
class IdentityPathAttestation(_Redacted):
    contract_id: str
    decision: str
    attestation_sha256: str
    identity_class: str
    path_class: str
    p00_statement_sha256: str
    authority_role: str
    valid_from: date
    expires_on: date


@dataclass(frozen=True, slots=True, repr=False)
class ExecutorApproval(_Redacted):
    contract_id: str
    decision: str
    review_sha256: str
    executor_commit: str
    reviewer_role: str
    package_revision: str


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionWindow(_Redacted):
    contract_id: str
    decision: str
    approval_sha256: str
    starts_at: datetime
    ends_at: datetime
    operator_reference: str
    cancellation_owner_reference: str


@dataclass(frozen=True, slots=True, repr=False)
class _Observation(_Redacted):
    version: str
    p00: dict[str, bool]
    m10: list[dict[str, object]]
    k20: list[dict[str, object]]


class SerializedReadLease(_Redacted):
    """Single-use reviewed wrapper around one concrete FIFO/mutex backend."""

    __slots__ = (
        "_backend", "_acquisition_count", "_release_count",
        "_acquisition_verified", "_release_verified", "_no_lease_proven",
    )

    def __init__(self, backend: object):
        self._backend = backend
        self._acquisition_count = 0
        self._release_count = 0
        self._acquisition_verified = False
        self._release_verified = False
        self._no_lease_proven = False

    @property
    def acquisition_count(self) -> int:
        return self._acquisition_count

    @property
    def release_count(self) -> int:
        return self._release_count

    @property
    def acquisition_verified(self) -> bool:
        return self._acquisition_verified

    @property
    def release_verified(self) -> bool:
        return self._release_verified

    @property
    def no_lease_proven(self) -> bool:
        return self._no_lease_proven

    @property
    def held(self) -> bool:
        return self._backend.held_by_caller() is True

    def acquire(self, deadline: float) -> None:
        if self._acquisition_count != 0 or self._release_count != 0:
            raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        acquired = self._backend.acquire_until(deadline)
        held = self._backend.held_by_caller()
        if acquired is True and held is True:
            self._acquisition_count = 1
            self._acquisition_verified = True
            self._no_lease_proven = False
        elif acquired is False and held is False:
            self._no_lease_proven = True
        else:
            raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)

    def release_owned(self, deadline: float) -> None:
        held = self._backend.held_by_caller()
        if held is True:
            self._release_count += 1
            released = self._backend.release_owned(deadline)
            self._release_verified = (
                released is True and self._backend.held_by_caller() is False
            )
            self._no_lease_proven = False
        elif held is False:
            self._no_lease_proven = self._acquisition_count == 0
        else:
            self._no_lease_proven = False


def _raise_if_late(*, monotonic: object, deadline: float) -> None:
    if monotonic() > deadline:
        raise ExecutorRejected(ExecutorReason.TIMEOUT.value)


def _fixed_reason(error: Exception) -> capture.FixedReason:
    allowed = {
        item.value: item for item in capture.FixedReason
        if item is not capture.FixedReason.NONE
    }
    return allowed.get(str(error), capture.FixedReason.PREFLIGHT_FAILED)


def _discard_and_classify(
    *, sink: object, sink_clean: bool, error: Exception,
    monotonic: object, deadline: float,
    default_reason: capture.FixedReason = capture.FixedReason.PREFLIGHT_FAILED,
) -> capture.FixedReason:
    try:
        if sink_clean:
            sink.discard_all()
        absent = sink.final_exists() is False
    except Exception:
        absent = False
    if not absent:
        return capture.FixedReason.CLEANUP_UNCERTAIN
    fixed = _fixed_reason(error)
    if fixed is capture.FixedReason.PREFLIGHT_FAILED:
        fixed = default_reason
    if fixed is capture.FixedReason.CLEANUP_UNCERTAIN:
        return fixed
    if monotonic() > deadline:
        return capture.FixedReason.TIMEOUT
    return fixed


def _approved_prerequisites(
    *, identity: IdentityPathAttestation, approval: ExecutorApproval,
    window: ExecutionWindow, runtime_commit: str, evidence_date: date,
    now: datetime,
) -> None:
    p00_digest = next(
        item.sha256_hex for item in capture.STATEMENT_SPECS if item.statement_id == "EKO-P00"
    )
    if (
        type(identity) is not IdentityPathAttestation
        or identity.contract_id != ATTESTATION_CONTRACT
        or identity.decision != "approved"
        or not _HEX.fullmatch(identity.attestation_sha256)
        or identity.identity_class != IDENTITY_CLASS
        or identity.path_class != PATH_CLASS
        or identity.p00_statement_sha256 != p00_digest
        or identity.authority_role != AUTHORITY_ROLE
        or type(identity.valid_from) is not date
        or type(identity.expires_on) is not date
        or not identity.valid_from <= evidence_date <= identity.expires_on
    ):
        raise ExecutorRejected(ExecutorReason.PREREQUISITE_UNPROVEN.value)
    if (
        type(approval) is not ExecutorApproval
        or approval.contract_id != EXECUTOR_APPROVAL_CONTRACT
        or approval.decision != "approved"
        or not _HEX.fullmatch(approval.review_sha256)
        or not _COMMIT.fullmatch(approval.executor_commit)
        or approval.executor_commit != runtime_commit
        or approval.reviewer_role != REVIEWER_ROLE
        or approval.package_revision != capture.PACKAGE_REVISION
    ):
        raise ExecutorRejected(ExecutorReason.PREREQUISITE_UNPROVEN.value)
    if (
        type(window) is not ExecutionWindow
        or window.contract_id != WINDOW_CONTRACT
        or window.decision != "approved"
        or not _HEX.fullmatch(window.approval_sha256)
        or type(window.starts_at) is not datetime
        or type(window.ends_at) is not datetime
        or type(now) is not datetime
        or any(value.utcoffset() != timedelta(hours=9) for value in (window.starts_at, window.ends_at, now))
        or not window.starts_at <= now <= window.ends_at
        or not (
            evidence_date
            == now.date()
            == window.starts_at.date()
            == window.ends_at.date()
        )
        or not timedelta(0) < window.ends_at - window.starts_at <= timedelta(seconds=MAX_WINDOW_SECONDS)
        or not _REFERENCE.fullmatch(window.operator_reference)
        or not _REFERENCE.fullmatch(window.cancellation_owner_reference)
    ):
        raise ExecutorRejected(ExecutorReason.PREREQUISITE_UNPROVEN.value)


def _verified_statements(statement_bytes: object) -> dict[str, bytes]:
    expected = tuple(item.statement_id for item in capture.STATEMENT_SPECS)
    if type(statement_bytes) is not dict or tuple(statement_bytes) != expected:
        raise ExecutorRejected(ExecutorReason.INVENTORY_MISMATCH.value)
    for spec in capture.STATEMENT_SPECS:
        value = statement_bytes[spec.statement_id]
        if type(value) is not bytes or capture.sha256(value).hexdigest() != spec.sha256_hex:
            raise ExecutorRejected(ExecutorReason.INVENTORY_MISMATCH.value)
    return statement_bytes


def _rows(
    cursor: object, spec: capture.StatementSpec, *,
    monotonic: object, deadline: float,
) -> capture.InjectedResult:
    columns = tuple(item[0] for item in (cursor.description or ()))
    if columns != spec.columns:
        raise ExecutorRejected(capture.FixedReason.UNEXPECTED_SHAPE.value)
    fetched = cursor.fetchmany(spec.maximum_rows + 1)
    _raise_if_late(monotonic=monotonic, deadline=deadline)
    if type(fetched) not in (list, tuple):
        raise ExecutorRejected(capture.FixedReason.UNEXPECTED_SHAPE.value)
    if len(fetched) > spec.maximum_rows:
        raise ExecutorRejected(capture.FixedReason.ROW_LIMIT.value)
    rows = []
    for values in fetched:
        if type(values) not in (list, tuple) or len(values) != len(columns):
            raise ExecutorRejected(capture.FixedReason.UNEXPECTED_SHAPE.value)
        rows.append(dict(zip(columns, values, strict=True)))
    return capture.InjectedResult(tuple(rows))


def _observe_and_close(*, connection_owner: object, statement_bytes: dict[str, bytes],
                       deadline: float, monotonic: object) -> _Observation:
    connection = cursor = None
    c99_done = False
    p00 = version = m10 = k20 = None
    failure: Exception | None = None
    try:
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        connection_owner.acquire(deadline)
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        if (connection_owner.acquisition_count != 1
                or connection_owner.acquisition_complete is not True
                or connection_owner.connection is None):
            raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        connection = connection_owner.connection
        cursor = connection.cursor()
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        for spec in capture.STATEMENT_SPECS:
            _raise_if_late(monotonic=monotonic, deadline=deadline)
            if spec.statement_id == "EKO-C99":
                c99_done = True
            cursor.execute(statement_bytes[spec.statement_id].decode("ascii"))
            _raise_if_late(monotonic=monotonic, deadline=deadline)
            if getattr(connection, "notices", ()):
                raise ExecutorRejected(ExecutorReason.OBSERVATION_REJECTED.value)
            if spec.maximum_rows == 0:
                if cursor.description is not None:
                    raise ExecutorRejected(ExecutorReason.OBSERVATION_REJECTED.value)
                result = capture.InjectedResult(())
                capture._validate_control(result)
            else:
                result = _rows(
                    cursor, spec, monotonic=monotonic, deadline=deadline,
                )
                if spec.statement_id == "EKO-P00":
                    p00 = capture._validate_p00(result)
                elif spec.statement_id == "EKO-V01":
                    version = capture._validate_version(result)
                elif spec.statement_id == "EKO-M10":
                    m10 = capture._validate_m10(result)
                elif spec.statement_id == "EKO-K20":
                    k20 = capture._validate_k20(result)
            _raise_if_late(monotonic=monotonic, deadline=deadline)
    except Exception as error:
        failure = (
            ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
            if c99_done else error
        )
        if connection is not None:
            try:
                connection.cancel()
            except Exception:
                failure = ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        if cursor is not None and not c99_done:
            try:
                c99_done = True
                cursor.execute(statement_bytes["EKO-C99"].decode("ascii"))
            except Exception:
                failure = ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
    finally:
        cleanup_ok = True
        if cursor is not None:
            try:
                cursor.close()
                cleanup_ok = getattr(cursor, "closed", None) is True and cleanup_ok
            except Exception:
                cleanup_ok = False
        try:
            connection_owner.close_owned(deadline)
            if connection_owner.acquisition_count == 0:
                cleanup_ok = connection_owner.no_connection_proven is True and cleanup_ok
            else:
                cleanup_ok = connection_owner.close_verified is True and cleanup_ok
        except Exception:
            cleanup_ok = False
        if not cleanup_ok:
            failure = ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        elif monotonic() > deadline:
            failure = ExecutorRejected(ExecutorReason.TIMEOUT.value)
    if failure is not None:
        if isinstance(failure, ExecutorRejected):
            raise failure
        if isinstance(failure, capture.CaptureRejected):
            raise ExecutorRejected(str(failure)) from None
        raise ExecutorRejected(ExecutorReason.OBSERVATION_REJECTED.value) from None
    if type(version) is not str or p00 is None or m10 is None or k20 is None:
        raise ExecutorRejected(ExecutorReason.OBSERVATION_REJECTED.value)
    return _Observation(version, p00, m10, k20)


def _observe_with_owned_lease(
    *, serialized_lease: object, connection_owner: object,
    statement_bytes: dict[str, bytes], deadline: float, monotonic: object,
) -> _Observation:
    observation = None
    failure: Exception | None = None
    try:
        if type(serialized_lease) is not SerializedReadLease:
            raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        serialized_lease.acquire(deadline)
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        if (
            type(serialized_lease.acquisition_count) is not int
            or serialized_lease.acquisition_count != 1
            or serialized_lease.acquisition_verified is not True
            or serialized_lease.held is not True
        ):
            raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        observation = _observe_and_close(
            connection_owner=connection_owner,
            statement_bytes=statement_bytes,
            deadline=deadline,
            monotonic=monotonic,
        )
    except Exception as error:
        failure = error
    finally:
        cleanup_ok = True
        try:
            serialized_lease.release_owned(deadline)
            if serialized_lease.release_count == 1:
                cleanup_ok = (
                    serialized_lease.release_verified is True
                    and serialized_lease.held is False
                )
            elif serialized_lease.acquisition_count == 0:
                cleanup_ok = (
                    serialized_lease.no_lease_proven is True
                    and serialized_lease.held is False
                )
            else:
                cleanup_ok = False
        except Exception:
            cleanup_ok = False
        if not cleanup_ok:
            failure = ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
        elif monotonic() > deadline:
            failure = ExecutorRejected(ExecutorReason.TIMEOUT.value)
    if failure is not None:
        if isinstance(failure, ExecutorRejected):
            raise failure
        if isinstance(failure, capture.CaptureRejected):
            raise ExecutorRejected(str(failure)) from None
        raise ExecutorRejected(ExecutorReason.OBSERVATION_REJECTED.value) from None
    if type(observation) is not _Observation:
        raise ExecutorRejected(ExecutorReason.CLEANUP_UNCERTAIN.value)
    return observation


def execute_reviewed_package_once(
    *, identity: IdentityPathAttestation, approval: ExecutorApproval,
    window: ExecutionWindow, runtime_commit: str, evidence_date: date,
    now: datetime, statement_bytes: dict[str, bytes], monotonic: object,
    serialized_lease: object, connection_owner: object, sink: object,
) -> capture.CaptureOutcome:
    """Execute only after all injected prerequisites are independently approved."""

    started = monotonic()
    deadline = started + capture.GLOBAL_DEADLINE_SECONDS
    sink_clean = False
    try:
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        _approved_prerequisites(
            identity=identity, approval=approval, window=window,
            runtime_commit=runtime_commit, evidence_date=evidence_date, now=now,
        )
        statements = _verified_statements(statement_bytes)
        if sink.final_exists() is not False:
            raise ExecutorRejected(ExecutorReason.PUBLICATION_FAILED.value)
        sink_clean = True
        _raise_if_late(monotonic=monotonic, deadline=deadline)

        observation = _observe_with_owned_lease(
            serialized_lease=serialized_lease,
            connection_owner=connection_owner,
            statement_bytes=statements,
            deadline=deadline,
            monotonic=monotonic,
        )
        _raise_if_late(monotonic=monotonic, deadline=deadline)
    except Exception as error:
        fixed = _discard_and_classify(
            sink=sink, sink_clean=sink_clean, error=error,
            monotonic=monotonic, deadline=deadline,
        )
        return capture.CaptureOutcome(capture.RunStatus.BLOCKED, fixed, None)
    try:
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        if sink.final_exists() is not False:
            raise ExecutorRejected(ExecutorReason.PUBLICATION_FAILED.value)
        artifact = capture._build_artifact(
            evidence_date=evidence_date, run_status=capture.RunStatus.COMPLETE,
            fixed_reason=capture.FixedReason.NONE, version=observation.version,
            p00=observation.p00, m10=observation.m10, k20=observation.k20,
        )
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        sink.create_new_no_overwrite()
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        sink.write(artifact)
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        sink.publish_no_overwrite()
        if sink.final_exists() is not True:
            raise ExecutorRejected(ExecutorReason.PUBLICATION_FAILED.value)
        _raise_if_late(monotonic=monotonic, deadline=deadline)
        return capture.CaptureOutcome(capture.RunStatus.COMPLETE, capture.FixedReason.NONE, artifact)
    except Exception as error:
        fixed = _discard_and_classify(
            sink=sink, sink_clean=True, error=error,
            monotonic=monotonic, deadline=deadline,
            default_reason=capture.FixedReason.CAPTURE_FAILED,
        )
        return capture.CaptureOutcome(
            capture.RunStatus.BLOCKED, fixed, None,
        )
