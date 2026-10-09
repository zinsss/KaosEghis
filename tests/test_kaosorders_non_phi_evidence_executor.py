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


class Sink:
    def __init__(self, events):
        self.events = events
        self.temp = self.final = None

    def create_new(self):
        self.events.append("publish:create")
        self.temp = b""

    def write(self, value):
        self.events.append("publish:write")
        self.temp = value

    def publish(self):
        self.events.append("publish:commit")
        self.final, self.temp = self.temp, None

    def discard(self):
        self.events.append("publish:discard")
        self.temp = None


class Cursor:
    def __init__(self, events, *, missing_m10=False, close_ok=True):
        self.events = events
        self.missing_m10 = missing_m10
        self.close_ok = close_ok
        self.current = None
        self.closed = False
        self.description = None

    def execute(self, sql):
        statement_id = sql.splitlines()[0].split()[-1]
        self.current = statement_id
        self.events.append(f"execute:{statement_id}")
        spec = next(item for item in capture.STATEMENT_SPECS if item.statement_id == statement_id)
        self.description = None if not spec.columns else tuple((name,) for name in spec.columns)

    def fetchmany(self, _limit):
        if self.current == "EKO-P00":
            return [p00_row()]
        if self.current == "EKO-V01":
            return [("150000",)]
        if self.current == "EKO-M10":
            rows = m10_rows()
            if self.missing_m10:
                first = list(rows[0]); first[2:] = [False, None, None, None, None]; rows[0] = tuple(first)
            return rows
        if self.current == "EKO-K20":
            return k20_rows()
        raise AssertionError("unexpected fetch")

    def close(self):
        self.events.append("cursor:close")
        self.closed = self.close_ok


class Connection:
    notices = ()

    def __init__(self, events, **cursor_options):
        self.events = events
        self.cursor_value = Cursor(events, **cursor_options)
        self.closed = 0

    def cursor(self):
        self.events.append("cursor:create")
        return self.cursor_value

    def cancel(self):
        self.events.append("connection:cancel")

    def close(self):
        self.events.append("connection:close")
        self.closed = 1


def run(*, identity=None, approval=None, window=None, connection_options=None,
        serialized=None, clock=None):
    events = []
    identity0, approval0, window0 = prerequisites()
    clock = clock or Clock()
    sink = Sink(events)

    def connection_factory(_deadline):
        events.append("connection:create")
        return Connection(events, **(connection_options or {}))

    def serialized_default(operation, _deadline):
        events.append("lease:acquired")
        try:
            return operation()
        finally:
            events.append("lease:released")

    outcome = executor.execute_reviewed_package_once(
        identity=identity if identity is not None else identity0,
        approval=approval if approval is not None else approval0,
        window=window if window is not None else window0,
        runtime_commit=COMMIT, evidence_date=DAY, now=NOW,
        statement_bytes=statement_bytes(), monotonic=clock,
        serialized_read_until=serialized or serialized_default,
        connection_factory=connection_factory, sink=sink,
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


def test_queue_time_is_inside_global_deadline_and_prevents_connection():
    clock = Clock()

    def delayed(operation, deadline):
        clock.value = deadline + 0.001
        return operation()

    outcome, events, _ = run(serialized=delayed, clock=clock)
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert "connection:create" not in events


def test_statement_digest_change_stops_before_serialization():
    identity, approval, window = prerequisites()
    events = []
    sink = Sink(events)
    statements = statement_bytes(); statements["EKO-M10"] += b" "
    outcome = executor.execute_reviewed_package_once(
        identity=identity, approval=approval, window=window, runtime_commit=COMMIT,
        evidence_date=DAY, now=NOW, statement_bytes=statements, monotonic=Clock(),
        serialized_read_until=lambda *_a: pytest.fail("serialized"),
        connection_factory=lambda *_a: pytest.fail("connected"), sink=sink,
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
