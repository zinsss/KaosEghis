import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from KaosEghis.core import kaosorders_non_phi_evidence_capture as capture
from KaosEghis.core import kaosorders_non_phi_evidence_executor as executor


KST = timezone(timedelta(hours=9), "KST")
DAY = date(2026, 10, 9)
NOW = datetime(2026, 10, 9, 20, 10, tzinfo=KST)
COMMIT = "a" * 40
HEX = "b" * 64
STATEMENTS_DOC = Path(__file__).parents[1] / "docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md"


def statement_bytes():
    lines = STATEMENTS_DOC.read_text(encoding="utf-8").splitlines(keepends=True)
    result = {}
    for spec in capture.STATEMENT_SPECS:
        start = lines.index(f"-- BEGIN {spec.statement_id}\n")
        finish = lines.index(f"-- END {spec.statement_id}\n", start) + 1
        result[spec.statement_id] = "".join(lines[start:finish]).encode()
    return result


def prerequisites():
    p00 = next(item for item in capture.STATEMENT_SPECS if item.statement_id == "EKO-P00")
    identity = executor.IdentityPathAttestation(
        executor.ATTESTATION_CONTRACT, "approved", HEX, executor.IDENTITY_CLASS,
        executor.PATH_CLASS, p00.sha256_hex, executor.AUTHORITY_ROLE,
        DAY, DAY + timedelta(days=1),
    )
    approval = executor.ExecutorApproval(
        executor.EXECUTOR_APPROVAL_CONTRACT, "approved", HEX, COMMIT,
        executor.REVIEWER_ROLE, capture.PACKAGE_REVISION,
    )
    window = executor.ExecutionWindow(
        executor.WINDOW_CONTRACT, "approved", HEX,
        NOW - timedelta(minutes=1), NOW + timedelta(minutes=1), "operator-1", "cancel-owner-1",
    )
    return identity, approval, window


def p00_row():
    return tuple(True for _ in capture.P00_COLUMNS)


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


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def expire(self):
        self.value = capture.GLOBAL_DEADLINE_SECONDS + 0.001


class Sink:
    def __init__(self, events, *, clock=None, publish_visible_raise=False,
                 initial_final=None, late_first_check=False, late_event=None):
        self.events = events
        self.clock = clock
        self.temp = None
        self.final = initial_final
        self.publish_visible_raise = publish_visible_raise
        self.late_first_check = late_first_check
        self.late_event = late_event
        self.check_count = 0

    def _record(self, event):
        self.events.append(event)
        if event == self.late_event:
            self.clock.expire()

    def create_new_no_overwrite(self):
        self._record("publish:create")
        if self.temp is not None or self.final is not None:
            raise RuntimeError("exists")
        self.temp = b""

    def write(self, value):
        self._record("publish:write")
        self.temp = value

    def publish_no_overwrite(self):
        self._record("publish:commit")
        if self.final is not None:
            raise RuntimeError("exists")
        self.final, self.temp = self.temp, None
        if self.publish_visible_raise:
            raise RuntimeError("synthetic")

    def discard_all(self):
        self._record("publish:discard")
        self.temp = self.final = None

    def final_exists(self):
        self.check_count += 1
        if self.late_first_check and self.check_count == 1:
            self.clock.expire()
        return self.final is not None


class Cursor:
    def __init__(self, events, *, clock=None, late_event=None, missing_m10=False,
                 close_ok=True, fail_c99=False, version="150000", p00_value=True,
                 extra_m10=False):
        self.events = events
        self.clock = clock
        self.late_event = late_event
        self.missing_m10 = missing_m10
        self.close_ok = close_ok
        self.fail_c99 = fail_c99
        self.version = version
        self.p00_value = p00_value
        self.extra_m10 = extra_m10
        self.current = None
        self.closed = False
        self.description = None

    def _record(self, event):
        self.events.append(event)
        if event == self.late_event:
            self.clock.expire()

    def execute(self, sql):
        statement_id = sql.splitlines()[0].split()[-1]
        self.current = statement_id
        self._record(f"execute:{statement_id}")
        if statement_id == "EKO-C99" and self.fail_c99:
            raise RuntimeError("synthetic")
        spec = next(item for item in capture.STATEMENT_SPECS if item.statement_id == statement_id)
        self.description = None if not spec.columns else tuple((name,) for name in spec.columns)

    def fetchmany(self, _limit):
        if self.current == "EKO-P00":
            return [tuple(self.p00_value for _ in capture.P00_COLUMNS)]
        if self.current == "EKO-V01":
            return [(self.version,)]
        if self.current == "EKO-M10":
            rows = m10_rows()
            if self.missing_m10:
                first = list(rows[0]); first[2:] = [False, None, None, None, None]; rows[0] = tuple(first)
            return rows + ([rows[0]] if self.extra_m10 else [])
        if self.current == "EKO-K20":
            return k20_rows()
        raise AssertionError("unexpected fetch")

    def close(self):
        self._record("cursor:close")
        self.closed = self.close_ok


class Connection:
    notices = ()

    def __init__(self, events, **cursor_options):
        self.events = events
        self.clock = cursor_options.get("clock")
        self.late_event = cursor_options.get("late_event")
        self.cursor_value = Cursor(events, **cursor_options)
        self.closed = 0

    def cursor(self):
        self.events.append("cursor:create")
        return self.cursor_value

    def cancel(self):
        self.events.append("connection:cancel")
        if self.late_event == "connection:cancel":
            self.clock.expire()

    def close(self):
        self.events.append("connection:close")
        if self.late_event == "connection:close":
            self.clock.expire()
        self.closed = 1


class ConnectionOwner:
    def __init__(self, events, *, raise_before_allocate=False, raise_after_allocate=False,
                 **connection_options):
        self.events = events
        self.raise_after_allocate = raise_after_allocate
        self.raise_before_allocate = raise_before_allocate
        self.connection_options = connection_options
        self.connection = None
        self.acquisition_count = 0
        self.acquisition_complete = False
        self.no_connection_proven = True
        self.close_verified = False

    def acquire(self, _deadline):
        if self.raise_before_allocate:
            raise RuntimeError("synthetic")
        self.connection = Connection(self.events, **self.connection_options)
        self.acquisition_count = 1
        self.no_connection_proven = False
        self.events.append("connection:create")
        if self.raise_after_allocate:
            raise RuntimeError("synthetic")
        self.acquisition_complete = True

    def close_owned(self, _deadline):
        if self.connection is None:
            self.no_connection_proven = True
            return
        self.connection.close()
        self.close_verified = self.connection.closed == 1


class LeaseBackend:
    def __init__(self, events, *, clock=None, no_lease=False, unreleased=False,
                 false_positive_acquire=False, raise_after_acquire=False,
                 late_acquire=False, late_release=False):
        self.events = events
        self.clock = clock
        self.no_lease = no_lease
        self.unreleased = unreleased
        self.false_positive_acquire = false_positive_acquire
        self.raise_after_acquire = raise_after_acquire
        self.late_acquire = late_acquire
        self.late_release = late_release
        self.held = False

    def acquire_until(self, _deadline):
        self.events.append("lease:acquire")
        if self.no_lease:
            return False
        if self.false_positive_acquire:
            return True
        self.held = True
        self.events.append("lease:acquired")
        if self.late_acquire:
            self.clock.expire()
        if self.raise_after_acquire:
            raise RuntimeError("synthetic")
        return True

    def held_by_caller(self):
        return self.held

    def release_owned(self, _deadline):
        self.events.append("lease:release")
        if not self.unreleased:
            self.held = False
            self.events.append("lease:released")
        if self.late_release:
            self.clock.expire()
        return True


def run(*, identity=None, approval=None, window=None, connection_options=None,
        owner_options=None, sink_options=None, lease_options=None, lease_backend=None,
        serialized_lease=None, clock=None, evidence_date=DAY, now=NOW):
    events = []
    identity0, approval0, window0 = prerequisites()
    clock = clock or Clock()
    sink = Sink(events, clock=clock, **(sink_options or {}))
    owner = ConnectionOwner(
        events, **(owner_options or {}), clock=clock, **(connection_options or {}),
    )
    lease_backend = lease_backend or LeaseBackend(
        events, clock=clock, **(lease_options or {}),
    )
    serialized_lease = serialized_lease or executor.SerializedReadLease(lease_backend)

    outcome = executor.execute_reviewed_package_once(
        identity=identity if identity is not None else identity0,
        approval=approval if approval is not None else approval0,
        window=window if window is not None else window0,
        runtime_commit=COMMIT, evidence_date=evidence_date, now=now,
        statement_bytes=statement_bytes(), monotonic=clock,
        serialized_lease=serialized_lease,
        connection_owner=owner, sink=sink,
    )
    return outcome, events, sink


def test_complete_observation_closes_and_releases_before_publication():
    outcome, events, sink = run()
    assert outcome.status is capture.RunStatus.COMPLETE
    assert sink.final == outcome.artifact
    assert events.index("cursor:close") < events.index("connection:close")
    assert events.index("connection:close") < events.index("lease:released")
    assert events.index("lease:released") < events.index("publish:create")
    assert [event for event in events if event.startswith("execute:")] == [
        f"execute:{item.statement_id}" for item in capture.STATEMENT_SPECS
    ]


def test_missing_identity_attestation_stops_before_serialization_or_connection():
    identity, _, _ = prerequisites()
    invalid = executor.IdentityPathAttestation(
        identity.contract_id, "pending", identity.attestation_sha256,
        identity.identity_class, identity.path_class, identity.p00_statement_sha256,
        identity.authority_role, identity.valid_from, identity.expires_on,
    )
    outcome, events, _ = run(identity=invalid)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.artifact is None
    assert not any(item.startswith(("lease:", "connection:", "execute:")) for item in events)


@pytest.mark.parametrize("which", ["approval", "window"])
def test_unapproved_executor_or_window_stops_before_connection(which):
    identity, approval, window = prerequisites()
    if which == "approval":
        approval = executor.ExecutorApproval(
            approval.contract_id, approval.decision, approval.review_sha256,
            "c" * 40, approval.reviewer_role, approval.package_revision,
        )
    else:
        window = executor.ExecutionWindow(
            window.contract_id, window.decision, window.approval_sha256,
            window.starts_at, window.ends_at, "", window.cancellation_owner_reference,
        )
    outcome, events, _ = run(identity=identity, approval=approval, window=window)
    assert outcome.artifact is None
    assert "connection:create" not in events


def test_missing_required_m10_column_rolls_back_closes_and_never_publishes():
    outcome, events, sink = run(connection_options={"missing_m10": True})
    assert outcome.status is capture.RunStatus.BLOCKED and outcome.artifact is None
    assert "execute:EKO-K20" not in events
    assert "connection:cancel" in events and events.count("execute:EKO-C99") == 1
    assert events.index("connection:close") < events.index("lease:released")
    assert sink.final is None and "publish:commit" not in events


def test_uncertain_cursor_close_blocks_without_artifact():
    outcome, events, sink = run(connection_options={"close_ok": False})
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None
    assert "connection:close" in events


def test_lease_acquisition_time_is_inside_global_deadline_and_prevents_connection():
    clock = Clock()
    outcome, events, _ = run(
        lease_options={"late_acquire": True}, clock=clock,
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert "connection:create" not in events


def test_no_actual_lease_acquisition_fails_closed_before_connection():
    outcome, events, sink = run(lease_options={"no_lease": True})
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None
    assert "connection:create" not in events and "publish:commit" not in events


def test_positive_acquire_without_independently_observed_ownership_fails_closed():
    outcome, events, sink = run(
        lease_options={"false_positive_acquire": True},
    )
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None
    assert "connection:create" not in events and "publish:commit" not in events


def test_forged_duck_typed_lease_state_is_rejected_before_connection():
    class ForgedLease:
        acquisition_count = 1
        acquisition_verified = True
        held = True
        release_count = 1
        release_verified = True
        no_lease_proven = False

        def acquire(self, _deadline):
            return None

        def release_owned(self, _deadline):
            return None

    outcome, events, sink = run(serialized_lease=ForgedLease())
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None
    assert "connection:create" not in events and "publish:commit" not in events


def test_unreleased_actual_lease_fails_closed_after_observation():
    outcome, events, sink = run(lease_options={"unreleased": True})
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None
    assert "connection:close" in events and "lease:released" not in events
    assert "publish:commit" not in events


def test_acquire_then_raise_still_releases_owned_lease_once():
    outcome, events, sink = run(lease_options={"raise_after_acquire": True})
    assert outcome.artifact is None and sink.final is None
    assert events.count("lease:acquire") == 1
    assert events.count("lease:release") == 1
    assert events.count("lease:released") == 1
    assert "connection:create" not in events


def test_validation_time_is_inside_global_deadline():
    clock = Clock()
    outcome, events, sink = run(
        clock=clock, sink_options={"late_first_check": True},
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None and sink.final is None
    assert "connection:create" not in events


@pytest.mark.parametrize(
    "late_event",
    ["connection:cancel", "execute:EKO-C99", "cursor:close", "connection:close"],
)
def test_late_cleanup_overrides_ordinary_failure_with_timeout(late_event):
    clock = Clock()
    outcome, _events, sink = run(
        clock=clock,
        connection_options={"missing_m10": True, "late_event": late_event},
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None and sink.final is None


def test_late_concrete_lease_release_blocks_publication():
    clock = Clock()
    outcome, events, sink = run(
        lease_options={"late_release": True}, clock=clock,
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None and sink.final is None
    assert "publish:commit" not in events


@pytest.mark.parametrize(
    "late_event", ["publish:create", "publish:write", "publish:commit"],
)
def test_late_publication_stage_is_removed_and_returns_timeout(late_event):
    clock = Clock()
    outcome, _events, sink = run(
        clock=clock, sink_options={"late_event": late_event},
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None and sink.final is None


def test_late_failure_artifact_cleanup_overrides_ordinary_rejection():
    clock = Clock()
    outcome, _events, sink = run(
        clock=clock,
        connection_options={"missing_m10": True},
        sink_options={"late_event": "publish:discard"},
    )
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None and sink.final is None


def test_allocate_then_raise_is_closed_by_resource_owner_and_never_published():
    outcome, events, sink = run(owner_options={"raise_after_allocate": True})
    assert outcome.artifact is None and sink.final is None
    assert events.count("connection:create") == 1
    assert events.count("connection:close") == 1


def test_raise_before_allocate_proves_no_connection_and_never_publishes():
    outcome, events, sink = run(owner_options={"raise_before_allocate": True})
    assert outcome.artifact is None and sink.final is None
    assert "connection:create" not in events and "connection:close" not in events


def test_publish_visible_then_raise_is_removed_and_verified_absent():
    outcome, events, sink = run(sink_options={"publish_visible_raise": True})
    assert outcome.status is capture.RunStatus.BLOCKED and outcome.artifact is None
    assert sink.final is None and events[-1] == "publish:discard"


def test_existing_final_is_never_overwritten_or_deleted():
    outcome, events, sink = run(sink_options={"initial_final": b"existing"})
    assert outcome.artifact is None and sink.final == b"existing"
    assert "connection:create" not in events and "publish:discard" not in events


def test_failed_c99_is_attempted_exactly_once_and_is_cleanup_uncertain():
    outcome, events, sink = run(connection_options={"fail_c99": True})
    assert events.count("execute:EKO-C99") == 1
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None


def test_failed_cleanup_c99_after_prior_rejection_is_never_retried():
    outcome, events, sink = run(
        connection_options={"missing_m10": True, "fail_c99": True},
    )
    assert events.count("execute:EKO-C99") == 1
    assert outcome.fixed_reason is capture.FixedReason.CLEANUP_UNCERTAIN
    assert outcome.artifact is None and sink.final is None


def test_evidence_date_mismatch_rejects_before_serialization_or_connection():
    outcome, events, _ = run(evidence_date=DAY - timedelta(days=1))
    assert outcome.fixed_reason is capture.FixedReason.PREFLIGHT_FAILED
    assert "connection:create" not in events and "lease:acquired" not in events


def test_window_crossing_kst_day_rejects_before_serialization_or_connection():
    identity, approval, window = prerequisites()
    crossing = executor.ExecutionWindow(
        window.contract_id, window.decision, window.approval_sha256,
        datetime(2026, 10, 8, 23, 59, tzinfo=KST),
        datetime(2026, 10, 9, 0, 1, tzinfo=KST),
        window.operator_reference, window.cancellation_owner_reference,
    )
    outcome, events, _ = run(
        identity=identity, approval=approval, window=crossing,
        now=datetime(2026, 10, 9, 0, 0, tzinfo=KST),
    )
    assert outcome.fixed_reason is capture.FixedReason.PREFLIGHT_FAILED
    assert "connection:create" not in events and "lease:acquired" not in events


@pytest.mark.parametrize(
    "connection_options,reason",
    [
        ({"version": "180000"}, capture.FixedReason.VERSION_MISMATCH),
        ({"p00_value": 1}, capture.FixedReason.UNEXPECTED_SHAPE),
        ({"extra_m10": True}, capture.FixedReason.ROW_LIMIT),
    ],
)
def test_allowlisted_capture_reasons_are_preserved_without_raw_error(connection_options, reason):
    outcome, _events, _sink = run(connection_options=connection_options)
    assert outcome.fixed_reason is reason
    assert outcome.artifact is None
    assert "synthetic" not in repr(outcome)


@pytest.mark.parametrize(
    "reason",
    [item for item in capture.FixedReason if item is not capture.FixedReason.NONE],
)
def test_every_allowlisted_capture_rejection_reason_is_preserved(monkeypatch, reason):
    monkeypatch.setattr(
        capture,
        "_validate_p00",
        lambda _result: (_ for _ in ()).throw(capture.CaptureRejected(reason.value)),
    )
    outcome, _events, sink = run()
    assert outcome.fixed_reason is reason
    assert outcome.artifact is None and sink.final is None


def test_artifact_byte_limit_reason_is_preserved_and_final_absent(monkeypatch):
    monkeypatch.setattr(
        capture, "_build_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(capture.CaptureRejected("byte_limit")),
    )
    outcome, _events, sink = run()
    assert outcome.fixed_reason is capture.FixedReason.BYTE_LIMIT
    assert outcome.artifact is None and sink.final is None


def test_statement_digest_change_stops_before_serialization():
    identity, approval, window = prerequisites()
    events = []
    sink = Sink(events)
    statements = statement_bytes(); statements["EKO-M10"] += b" "
    outcome = executor.execute_reviewed_package_once(
        identity=identity, approval=approval, window=window, runtime_commit=COMMIT,
        evidence_date=DAY, now=NOW, statement_bytes=statements, monotonic=Clock(),
        serialized_lease=executor.SerializedReadLease(
            LeaseBackend(events, clock=Clock()),
        ),
        connection_owner=ConnectionOwner(events), sink=sink,
    )
    assert outcome.fixed_reason is capture.FixedReason.INVENTORY_MISMATCH
    assert outcome.artifact is None


def test_static_boundary_has_no_driver_settings_credentials_or_runtime_activation():
    path = Path(executor.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports <= {"dataclasses", "datetime", "enum", "re", "KaosEghis"}
    source = path.read_text(encoding="utf-8")
    for forbidden in ("psycopg", "getenv", "settings", "connection_string", "socket", "logging", "print("):
        assert forbidden not in source
    assert repr(prerequisites()[0]) == "<IdentityPathAttestation: redacted>"
    assert repr(executor.SerializedReadLease(LeaseBackend([], clock=Clock()))) == (
        "<SerializedReadLease: redacted>"
    )
