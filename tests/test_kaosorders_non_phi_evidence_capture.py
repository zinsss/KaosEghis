import ast
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pytest

from KaosEghis.core import kaosorders_non_phi_evidence_capture as capture


CANARY = "SYNTHETIC-SECRET-PATIENT-CANARY"
STATEMENTS_DOC = (
    Path(__file__).parents[1]
    / "docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md"
)


def statement_bytes():
    lines = STATEMENTS_DOC.read_text(encoding="utf-8").splitlines(keepends=True)
    result = {}
    for spec in capture.STATEMENT_SPECS:
        begin = f"-- BEGIN {spec.statement_id}\n"
        end = f"-- END {spec.statement_id}\n"
        start = lines.index(begin)
        finish = lines.index(end, start) + 1
        result[spec.statement_id] = "".join(lines[start:finish]).encode("utf-8")
    return result


def p00_row(**changes):
    row = {name: True for name in capture.P00_COLUMNS}
    row.update(changes)
    return row


def m10_rows():
    return tuple(
        {
            "relation_id": relation_id,
            "column_id": column_id,
            "column_present": True,
            "data_type": "text",
            "nullable": False,
            "generated": False,
            "identity": False,
        }
        for relation_id, column_id in capture.M10_IDENTITIES
    )


def k20_rows():
    return tuple(
        {
            "relation_id": relation_id,
            "key_id": key_id,
            "matching_index_count": 1,
            "any_unique": True,
            "any_primary": False,
            "all_valid": True,
            "all_ready": True,
            "single_index_method": "btree",
        }
        for relation_id, key_id in capture.K20_IDENTITIES
    )


def default_results():
    return {
        "EKO-C00": capture.InjectedResult(()),
        "EKO-C01": capture.InjectedResult(()),
        "EKO-C02": capture.InjectedResult(()),
        "EKO-C03": capture.InjectedResult(()),
        "EKO-P00": capture.InjectedResult((p00_row(),)),
        "EKO-V01": capture.InjectedResult(({"source_version_class": "150000"},)),
        "EKO-M10": capture.InjectedResult(m10_rows()),
        "EKO-K20": capture.InjectedResult(k20_rows()),
        "EKO-C99": capture.InjectedResult(()),
    }


class FakePort:
    def __init__(self, *, results=None, fail_at=None, false_at=None, increments=None, events=None):
        self.results = results or default_results()
        self.fail_at = fail_at
        self.false_at = set(false_at or ())
        self.increments = increments or {}
        self.events = events if events is not None else []
        self.now = 0.0

    def monotonic(self):
        return self.now

    def _call(self, name):
        self.events.append(name)
        self.now += self.increments.get(name, 0.0)
        if self.fail_at == name:
            raise RuntimeError(CANARY)
        return name not in self.false_at

    def acquire_lease(self, _deadline):
        return self._call("acquire_lease")

    def connect(self, _deadline):
        return self._call("connect")

    def execute(self, statement_id, _statement_bytes, _deadline):
        self._call(f"execute:{statement_id}")
        return self.results[statement_id]

    def cancel(self, _deadline):
        return self._call("cancel")

    def rollback(self, _deadline):
        return self._call("rollback")

    def close_cursors(self, _deadline):
        return self._call("close_cursors")

    def close_connection(self, _deadline):
        return self._call("close_connection")

    def release_lease(self, _deadline):
        return self._call("release_lease")


class FakeSink:
    def __init__(self, *, fail_at=None, events=None):
        self.fail_at = fail_at
        self.events = events if events is not None else []
        self.temp = None
        self.final = None

    def _call(self, name):
        self.events.append(name)
        if self.fail_at == name:
            raise RuntimeError(CANARY)

    def create_new(self):
        self._call("sink:create_new")
        if self.temp is not None or self.final is not None:
            raise RuntimeError(CANARY)
        self.temp = b""

    def write(self, payload):
        self._call("sink:write")
        if self.temp is None or type(payload) is not bytes:
            raise RuntimeError(CANARY)
        self.temp = payload

    def publish(self):
        self._call("sink:publish")
        if self.temp is None or self.final is not None:
            raise RuntimeError(CANARY)
        self.final = self.temp
        self.temp = None

    def discard(self):
        self.events.append("sink:discard")
        self.temp = None


def run(*, port=None, sink=None, statements=None, evidence_date=date(2026, 10, 9)):
    port = port or FakePort()
    sink = sink or FakeSink()
    outcome = capture.run_injected_capture(
        port=port,
        sink=sink,
        statement_bytes=statements or statement_bytes(),
        evidence_date=evidence_date,
    )
    return outcome, port, sink


def decoded(outcome):
    assert outcome.artifact is not None
    return json.loads(outcome.artifact.decode("ascii"))


def test_literal_contract_and_closed_k20_shape():
    assert capture.CONTRACT_ID == "kaoseghis.non-phi-source-evidence"
    assert capture.CONTRACT_VERSION == 1
    assert capture.PACKAGE_ID == "eghis-kaosorders-non-phi-evidence-run-v1"
    assert capture.PACKAGE_REVISION == "review-candidate-3"
    assert capture.CENTRAL_COMMIT == "e3417375984acc2a58392315e26035e14c253219"
    assert capture.ENVIRONMENT_CLASS == "production-read-only"
    assert capture.SOURCE_VERSION_MIN == 120000
    assert capture.SOURCE_VERSION_MAX == 179999
    assert capture.GLOBAL_DEADLINE_SECONDS == 10.0
    assert capture.K20_COLUMNS == (
        "relation_id", "key_id", "matching_index_count", "any_unique",
        "any_primary", "all_valid", "all_ready", "single_index_method",
    )
    assert len(capture.K20_COLUMNS) == 8
    assert {item.value for item in capture.RunStatus} == {"complete", "blocked"}
    assert {item.value for item in capture.CriterionStatus} == {
        "proven", "unproven", "not_applicable"
    }
    assert repr(capture.CaptureOutcome(capture.RunStatus.BLOCKED, capture.FixedReason.TIMEOUT, None)) == (
        "<CaptureOutcome: redacted>"
    )


def test_all_nine_statement_digests_match_documented_exact_bytes():
    statements = statement_bytes()
    assert tuple(statements) == tuple(spec.statement_id for spec in capture.STATEMENT_SPECS)
    assert len(statements) == 9
    for spec in capture.STATEMENT_SPECS:
        assert sha256(statements[spec.statement_id]).hexdigest() == spec.sha256_hex


def test_success_closes_envelope_provenance_results_and_crosswalk():
    events = []
    outcome, port, sink = run(port=FakePort(events=events), sink=FakeSink(events=events))
    assert outcome.status is capture.RunStatus.COMPLETE
    assert outcome.fixed_reason is capture.FixedReason.NONE
    assert sink.final == outcome.artifact and sink.temp is None
    assert events[-4:] == ["release_lease", "sink:create_new", "sink:write", "sink:publish"]
    body = decoded(outcome)
    assert tuple(body) == (
        "central_commit", "contract_id", "contract_version", "criteria",
        "environment_class", "evidence_date", "fixed_reason", "package_id",
        "package_revision", "provenance", "results", "run_status",
    )
    assert body["contract_id"] == "kaoseghis.non-phi-source-evidence"
    assert body["contract_version"] == 1
    assert body["run_status"] == "complete" and body["fixed_reason"] == "none"
    assert body["evidence_date"] == "2026-10-09"
    assert body["environment_class"] == "production-read-only"
    assert tuple(body["results"]) == ("k20", "m10", "p00", "v01")
    assert tuple(body["results"]["p00"]) == tuple(sorted(capture.P00_COLUMNS))
    assert len(body["results"]["m10"]) == 19
    assert len(body["results"]["k20"]) == 3
    provenance = body["provenance"]
    assert provenance == {
        "accepted_version_range": "120000-179999",
        "applicable_source_database_version": "150000",
        "artifact_path": "evidence/eghis-kaosorders-non-phi-evidence-v1.json",
        "authority_role": "clinical-product-owner",
        "expires_on": "2026-11-08",
        "revalidation_triggers": list(capture.EXPIRY_TRIGGERS),
        "reviewer_role": "independent-integration-review",
        "safe_content_sha256": provenance["safe_content_sha256"],
    }
    expected_digest = sha256(
        capture._canonical({"results": body["results"], "criteria": body["criteria"]})
    ).hexdigest()
    assert provenance["safe_content_sha256"] == expected_digest
    criteria = {item["criterion_id"]: item for item in body["criteria"]}
    assert tuple(criteria) == capture.CRITERION_IDS
    assert criteria["preflight.transaction_read_only"]["status"] == "proven"
    assert criteria["parent_field.encounter_id"]["status"] == "unproven"
    assert criteria["policy.age.leap_day_rule_a"]["status"] == "not_applicable"
    assert criteria["failure.timeout"]["status"] == "not_applicable"


def test_missing_required_candidate_column_blocks_before_k20_and_stays_unproven():
    results = default_results()
    rows = list(m10_rows())
    rows[0] = {
        "relation_id": rows[0]["relation_id"],
        "column_id": rows[0]["column_id"],
        "column_present": False,
        "data_type": None,
        "nullable": None,
        "generated": None,
        "identity": None,
    }
    results["EKO-M10"] = capture.InjectedResult(tuple(rows))
    outcome, port, sink = run(port=FakePort(results=results))
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.fixed_reason is capture.FixedReason.INVENTORY_MISMATCH
    assert "execute:EKO-K20" not in port.events
    assert sink.final == outcome.artifact and sink.temp is None
    body = decoded(outcome)
    assert body["run_status"] == "blocked"
    assert body["results"] == {
        "k20": None,
        "m10": None,
        "p00": None,
        "v01": {"source_version_class": "150000"},
    }
    criteria = {item["criterion_id"]: item for item in body["criteria"]}
    assert criteria["metadata.closed_candidate_columns"] == {
        "criterion_id": "metadata.closed_candidate_columns",
        "status": "unproven",
        "source_statement_id": None,
        "fixed_reason": "inventory_mismatch",
    }


def test_absent_matching_index_retains_exact_k20_null_behavior():
    results = default_results()
    indexes = list(k20_rows())
    indexes[0] = {
        "relation_id": indexes[0]["relation_id"],
        "key_id": indexes[0]["key_id"],
        "matching_index_count": 0,
        "any_unique": False,
        "any_primary": False,
        "all_valid": False,
        "all_ready": False,
        "single_index_method": None,
    }
    results["EKO-K20"] = capture.InjectedResult(tuple(indexes))
    outcome, _, _ = run(port=FakePort(results=results))
    body = decoded(outcome)
    assert outcome.status is capture.RunStatus.COMPLETE
    assert body["results"]["k20"][0]["matching_index_count"] == 0


@pytest.mark.parametrize(
    "statement_id,mutate",
    [
        ("EKO-M10", lambda rows: ({**rows[0], "data_type": "text"},) + rows[1:]),
        ("EKO-K20", lambda rows: ({**rows[0], "index_method": "btree"},) + rows[1:]),
        ("EKO-K20", lambda rows: ({**rows[0], "matching_index_count": True},) + rows[1:]),
    ],
)
def test_malformed_or_old_output_shape_is_blocked_without_raw_echo(statement_id, mutate):
    results = default_results()
    if statement_id == "EKO-M10":
        base = list(m10_rows())
        base[0] = {**base[0], "column_present": False, "nullable": None, "generated": None, "identity": None}
        rows = tuple(base)
    else:
        rows = k20_rows()
    results[statement_id] = capture.InjectedResult(mutate(rows))
    outcome, port, sink = run(port=FakePort(results=results))
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.fixed_reason is capture.FixedReason.UNEXPECTED_SHAPE
    body = decoded(outcome)
    assert body["run_status"] == "blocked"
    assert body["results"] == {"k20": None, "m10": None, "p00": None, "v01": {"source_version_class": "150000"}}
    assert CANARY not in outcome.artifact.decode("ascii")
    assert "cancel" in port.events and "rollback" in port.events
    assert sink.temp is None and sink.final == outcome.artifact


@pytest.mark.parametrize("version", ["120000", "179999"])
def test_version_range_boundaries_are_accepted(version):
    results = default_results()
    results["EKO-V01"] = capture.InjectedResult(({"source_version_class": version},))
    outcome, _, _ = run(port=FakePort(results=results))
    assert outcome.status is capture.RunStatus.COMPLETE
    assert decoded(outcome)["provenance"]["applicable_source_database_version"] == version


def test_p00_false_blocks_before_version_and_does_not_claim_full_least_privilege():
    results = default_results()
    results["EKO-P00"] = capture.InjectedResult((p00_row(all_select=False),))
    outcome, port, _ = run(port=FakePort(results=results))
    assert outcome.fixed_reason is capture.FixedReason.PREFLIGHT_FAILED
    assert "execute:EKO-V01" not in port.events
    body = decoded(outcome)
    criteria = {item["criterion_id"]: item for item in body["criteria"]}
    assert criteria["preflight.all_select"] == {
        "criterion_id": "preflight.all_select",
        "status": "unproven",
        "source_statement_id": None,
        "fixed_reason": "preflight_failed",
    }
    assert all(not item["criterion_id"].startswith("least_privilege") for item in body["criteria"])


@pytest.mark.parametrize("version", ["119999", "180000", "15000", "15.0", 150000, True])
def test_version_mismatch_stops_before_metadata(version):
    results = default_results()
    results["EKO-V01"] = capture.InjectedResult(({"source_version_class": version},))
    outcome, port, _ = run(port=FakePort(results=results))
    assert outcome.fixed_reason is capture.FixedReason.VERSION_MISMATCH
    assert "execute:EKO-M10" not in port.events
    body = decoded(outcome)
    assert body["run_status"] == "blocked"
    assert body["provenance"]["applicable_source_database_version"] is None


def test_digest_or_statement_order_mismatch_never_acquires_lease():
    statements = statement_bytes()
    statements["EKO-M10"] += b" "
    port_events = []
    sink_events = []
    outcome, port, sink = run(
        port=FakePort(events=port_events), sink=FakeSink(events=sink_events), statements=statements
    )
    assert outcome.fixed_reason is capture.FixedReason.INVENTORY_MISMATCH
    assert port.events == []
    assert sink_events == ["sink:create_new", "sink:write", "sink:publish"]
    assert decoded(outcome)["results"] == {
        "k20": None, "m10": None, "p00": None, "v01": {"source_version_class": None}
    }


@pytest.mark.parametrize("surface", ["notices", "stdout", "stderr", "exception"])
def test_non_echo_canaries_are_suppressed(surface):
    results = default_results()
    if surface == "exception":
        port = FakePort(results=results, fail_at="execute:EKO-M10")
    else:
        result = results["EKO-M10"]
        results["EKO-M10"] = capture.InjectedResult(
            result.rows,
            notices=(CANARY,) if surface == "notices" else (),
            stdout=CANARY if surface == "stdout" else "",
            stderr=CANARY if surface == "stderr" else "",
        )
        port = FakePort(results=results)
    outcome, _, _ = run(port=port)
    assert outcome.fixed_reason is capture.FixedReason.CAPTURE_FAILED
    assert outcome.artifact is not None
    assert CANARY.encode() not in outcome.artifact
    assert CANARY not in repr(outcome)


@pytest.mark.parametrize("fail_at", ["sink:create_new", "sink:write", "sink:publish"])
def test_atomic_sink_failure_leaves_no_partial_or_final_artifact(fail_at):
    sink = FakeSink(fail_at=fail_at)
    outcome, _, sink = run(sink=sink)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.fixed_reason is capture.FixedReason.CAPTURE_FAILED
    assert outcome.artifact is None
    assert sink.temp is None and sink.final is None
    assert "sink:discard" in sink.events


@pytest.mark.parametrize(
    "false_at,expected",
    [
        ({"cancel"}, capture.FixedReason.CANCEL_FAILED),
        ({"rollback"}, capture.FixedReason.CLEANUP_UNCERTAIN),
        ({"close_cursors"}, capture.FixedReason.CLEANUP_UNCERTAIN),
        ({"close_connection"}, capture.FixedReason.CLEANUP_UNCERTAIN),
        ({"release_lease"}, capture.FixedReason.CLEANUP_UNCERTAIN),
    ],
)
def test_failure_cleanup_checks_cancel_rollback_all_closes_and_lease(false_at, expected):
    port = FakePort(fail_at="execute:EKO-M10", false_at=false_at)
    outcome, port, sink = run(port=port)
    assert outcome.fixed_reason is expected
    assert outcome.artifact is None
    assert sink.final is None and sink.temp is None
    for call in ("cancel", "rollback", "close_cursors", "close_connection", "release_lease"):
        assert call in port.events
    assert port.events.index("cancel") < port.events.index("rollback")
    assert port.events.index("rollback") < port.events.index("close_cursors")
    assert port.events.index("close_cursors") < port.events.index("close_connection")
    assert port.events.index("close_connection") < port.events.index("release_lease")


def test_global_deadline_exact_edge_includes_lease_release_and_publication_is_later():
    events = []
    port = FakePort(increments={"release_lease": 10.0}, events=events)
    sink = FakeSink(events=events)
    outcome, _, _ = run(port=port, sink=sink)
    assert outcome.status is capture.RunStatus.COMPLETE
    assert events.index("release_lease") < events.index("sink:create_new")


def test_global_deadline_overrun_after_lease_release_blocks_without_artifact():
    port = FakePort(increments={"release_lease": 10.000001})
    outcome, _, sink = run(port=port)
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert outcome.artifact is None
    assert sink.final is None and sink.temp is None


def test_global_deadline_starts_before_fifo_lease_admission():
    port = FakePort(increments={"acquire_lease": 10.000001})
    outcome, port, _ = run(port=port)
    assert outcome.fixed_reason is capture.FixedReason.TIMEOUT
    assert "connect" not in port.events
    assert "release_lease" in port.events


def test_clock_failure_before_deadline_creation_is_closed_and_non_echoing():
    port = FakePort()

    def fail_clock():
        raise RuntimeError(CANARY)

    port.monotonic = fail_clock
    outcome, _, sink = run(port=port)
    assert outcome.status is capture.RunStatus.BLOCKED
    assert outcome.fixed_reason is capture.FixedReason.CAPTURE_FAILED
    assert outcome.artifact is not None
    assert CANARY.encode() not in outcome.artifact
    assert sink.temp is None and sink.final == outcome.artifact


def test_leap_day_rule_a_and_ordinary_birthdays():
    birth = date(2000, 2, 29)
    assert capture.completed_years_rule_a(birth, date(2024, 2, 28)) == 23
    assert capture.completed_years_rule_a(birth, date(2024, 2, 29)) == 24
    assert capture.completed_years_rule_a(birth, date(2025, 2, 27)) == 24
    assert capture.completed_years_rule_a(birth, date(2025, 2, 28)) == 25
    assert capture.completed_years_rule_a(date(2000, 3, 1), date(2025, 2, 28)) == 24
    assert capture.completed_years_rule_a(date(2000, 3, 1), date(2025, 3, 1)) == 25


def test_fixed_crosswalk_covers_every_required_orders_boundary():
    ids = set(capture.CRITERION_IDS)
    expected = {
        *(f"parent_field.{name}" for name in (
            "encounter_id", "chart_number", "patient_name", "sex", "age", "state", "hold_yn"
        )),
        *(f"child_field.{name}" for name in (
            "encounter_id", "order_date", "order_number", "order_sequence",
            "catalog_code", "catalog_name", "user_code", "user_name", "order_type",
            "department_code", "state", "dc_yn", "act_yn"
        )),
        "parent_state.waiting", "parent_state.in_progress", "parent_state.on_hold",
        "parent_state.consultation_completed", "parent_state.payment_completed",
        "parent_lifecycle.cancellation", "parent_lifecycle.restoration",
        "child_semantics.active", "child_semantics.cancelled",
        "child_semantics.dc_yn", "child_semantics.act_yn",
        "relation.parent", "relation.child", "relation.patient_exact_one",
        "category.fee", "category.non_billing", "category.medication",
        "category.procedure", "category.unclassified",
        "completeness.clinic_day", "completeness.all_parents",
        "completeness.no_order_parents", "completeness.all_children",
        "reconciliation.parent_counts", "reconciliation.child_counts",
        "reconciliation.duplicates", "reconciliation.orphans", "reconciliation.off_day",
        "reconciliation.verified_empty", "reconciliation.save_completion_fence",
        "reconciliation.single_snapshot", "cap.parents_and_sentinel",
        "cap.children_and_sentinel", "cap.source_and_result_bytes",
        "cap.atomic_peak_memory", "cap.global_deadline",
    }
    assert expected <= ids
    assert set(capture.FAILURE_CRITERIA) <= ids
    assert len(ids) == len(capture.CRITERION_IDS)


def test_pure_module_static_boundary_and_fixed_rejections():
    module_path = Path(capture.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports <= {"dataclasses", "datetime", "enum", "hashlib", "json"}
    source = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "socket", "requests", "urllib", "psycopg", "sqlite", "subprocess",
        "pathlib", "open(", "print(", "PySide6",
    ):
        assert forbidden not in source
    assert {str(capture.CaptureRejected(reason)) for reason in (
        "unexpected_shape", "inventory_mismatch", "timeout"
    )} == {"unexpected_shape", "inventory_mismatch", "timeout"}
