"""Pure injected model for the disabled non-PHI evidence capture gate.

This module has no source, filesystem, network, credential, logging, runtime, or
deployment integration.  It validates synthetic injected statement results and
models fail-closed cleanup plus atomic publication through injected test doubles.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from hashlib import sha256
import json


CONTRACT_ID = "kaoseghis.non-phi-source-evidence"
CONTRACT_VERSION = 1
PACKAGE_ID = "eghis-kaosorders-non-phi-evidence-run-v1"
PACKAGE_REVISION = "review-candidate-3"
CENTRAL_COMMIT = "e3417375984acc2a58392315e26035e14c253219"
ENVIRONMENT_CLASS = "production-read-only"
ARTIFACT_PATH = "evidence/eghis-kaosorders-non-phi-evidence-v1.json"
REVIEWER_ROLE = "independent-integration-review"
AUTHORITY_ROLE = "clinical-product-owner"
SOURCE_VERSION_MIN = 120000
SOURCE_VERSION_MAX = 179999
EVIDENCE_VALID_DAYS = 30
GLOBAL_DEADLINE_SECONDS = 10.0
MAX_ARTIFACT_BYTES = 65_536
MAX_METADATA_TEXT_BYTES = 128
MAX_MATCHING_INDEX_COUNT = 64


class CaptureRejected(ValueError):
    """A fixed non-sensitive capture rejection."""


class RunStatus(StrEnum):
    COMPLETE = "complete"
    BLOCKED = "blocked"


class CriterionStatus(StrEnum):
    PROVEN = "proven"
    UNPROVEN = "unproven"
    NOT_APPLICABLE = "not_applicable"


class FixedReason(StrEnum):
    NONE = "none"
    PREFLIGHT_FAILED = "preflight_failed"
    INVENTORY_MISMATCH = "inventory_mismatch"
    UNEXPECTED_SHAPE = "unexpected_shape"
    PRIVACY_BOUNDARY = "privacy_boundary"
    ROW_LIMIT = "row_limit"
    BYTE_LIMIT = "byte_limit"
    TIMEOUT = "timeout"
    CANCEL_FAILED = "cancel_failed"
    CLEANUP_UNCERTAIN = "cleanup_uncertain"
    VERSION_MISMATCH = "version_mismatch"
    CAPTURE_FAILED = "capture_failed"


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


@dataclass(frozen=True, slots=True, repr=False)
class StatementSpec(_Redacted):
    statement_id: str
    sha256_hex: str
    columns: tuple[str, ...]
    maximum_rows: int


@dataclass(frozen=True, slots=True, repr=False)
class InjectedResult(_Redacted):
    rows: tuple[dict[str, object], ...]
    notices: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True, repr=False)
class CaptureOutcome(_Redacted):
    status: RunStatus
    fixed_reason: FixedReason
    artifact: bytes | None


P00_COLUMNS = (
    "transaction_read_only",
    "all_relations_present",
    "all_select",
    "no_insert",
    "no_update",
    "no_delete",
    "no_truncate",
    "no_references",
    "no_trigger",
    "no_database_create",
    "no_database_temp",
    "no_public_schema_create",
    "no_non_system_function_execute",
    "no_non_system_relation_write",
    "no_non_system_schema_create",
)
M10_COLUMNS = (
    "relation_id",
    "column_id",
    "column_present",
    "data_type",
    "nullable",
    "generated",
    "identity",
)
K20_COLUMNS = (
    "relation_id",
    "key_id",
    "matching_index_count",
    "any_unique",
    "any_primary",
    "all_valid",
    "all_ready",
    "single_index_method",
)

STATEMENT_SPECS = (
    StatementSpec("EKO-C00", "8e8fe700469cae8bd58eb7c36c0e9f7af5eb7c31abd2fd4aa1ac2bbc294a1605", (), 0),
    StatementSpec("EKO-C01", "5b4365b0e536dcaf636f0d4a87d9ce36f786fe570c4320172a9a6a352b34fd2e", (), 0),
    StatementSpec("EKO-C02", "45ab9545d6195a0772ec432ff05d89e6d6f6e5e8efcbac9e5f486a9697960a1f", (), 0),
    StatementSpec("EKO-C03", "98abef6980f6444c65a59fe0c434990d73d43af8c8cbf7bb603b831d06b1c306", (), 0),
    StatementSpec("EKO-P00", "6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6", P00_COLUMNS, 1),
    StatementSpec("EKO-V01", "3155dd719026df1163a083a69503aef73ffa7279cd0d0b5dde4c4178b0b99b57", ("source_version_class",), 1),
    StatementSpec("EKO-M10", "16f87d77183f5f2173d63513e6e527bbc9b6be865d86fd89e89a8970e1abf543", M10_COLUMNS, 19),
    StatementSpec("EKO-K20", "2e8e2160000f566de2b8c4ccda1f9e90b3992d9b66842e07616c6d5ab9a11462", K20_COLUMNS, 3),
    StatementSpec("EKO-C99", "0b45ae2ca7baf6547c3d61d85a8f616b64a5efca3637b4bf88008e64d8be29aa", (), 0),
)

M10_IDENTITIES = (
    ("CHILD", "activity_flag"),
    ("CHILD", "cancel_flag"),
    ("CHILD", "catalog_code"),
    ("CHILD", "catalog_name"),
    ("CHILD", "department_code"),
    ("CHILD", "encounter_key"),
    ("CHILD", "order_day"),
    ("CHILD", "order_number"),
    ("CHILD", "order_sequence"),
    ("CHILD", "order_type"),
    ("CHILD", "user_code"),
    ("CHILD", "user_name"),
    ("PARENT", "clinic_day"),
    ("PARENT", "encounter_key"),
    ("PARENT", "hold_flag"),
    ("PARENT", "patient_join_key"),
    ("PARENT", "raw_state"),
    ("PATIENT", "patient_join_key"),
    ("PATIENT", "patient_name_candidate"),
)
K20_IDENTITIES = (
    ("CHILD", "four_part_key"),
    ("PARENT", "encounter_key"),
    ("PATIENT", "patient_join_key"),
)

P00_CRITERIA = tuple(f"preflight.{name}" for name in P00_COLUMNS)
LOGICAL_CRITERIA = (
    "parent_field.encounter_id", "parent_field.chart_number", "parent_field.patient_name",
    "parent_field.sex", "parent_field.age", "parent_field.state", "parent_field.hold_yn",
    "child_field.encounter_id", "child_field.order_date", "child_field.order_number",
    "child_field.order_sequence", "child_field.catalog_code", "child_field.catalog_name",
    "child_field.user_code", "child_field.user_name", "child_field.order_type",
    "child_field.department_code", "child_field.state", "child_field.dc_yn",
    "child_field.act_yn",
    "parent_state.waiting", "parent_state.in_progress", "parent_state.on_hold",
    "parent_state.consultation_completed", "parent_state.payment_completed",
    "parent_lifecycle.cancellation", "parent_lifecycle.restoration",
    "child_semantics.active", "child_semantics.cancelled",
    "child_semantics.dc_yn", "child_semantics.act_yn",
    "relation.parent", "relation.child", "relation.patient_exact_one",
    "category.fee", "category.non_billing", "category.medication",
    "category.procedure", "category.unclassified",
    "completeness.clinic_day", "completeness.all_parents", "completeness.no_order_parents",
    "completeness.all_children", "reconciliation.parent_counts", "reconciliation.child_counts",
    "reconciliation.duplicates", "reconciliation.orphans", "reconciliation.off_day",
    "reconciliation.verified_empty", "reconciliation.save_completion_fence",
    "reconciliation.single_snapshot",
    "cap.parents_and_sentinel", "cap.children_and_sentinel", "cap.source_and_result_bytes",
    "cap.atomic_peak_memory", "cap.global_deadline",
)
FAILURE_CRITERIA = (
    "failure.preflight", "failure.inventory_mismatch", "failure.unexpected_shape",
    "failure.privacy_boundary", "failure.row_limit", "failure.byte_limit",
    "failure.timeout", "failure.cancel", "failure.rollback", "failure.cleanup",
    "failure.version_mismatch", "failure.capture_failed", "failure.contradiction",
    "failure.no_retry_no_broadening",
)
SCOPED_METADATA_CRITERIA = (
    "metadata.source_version_class",
    "metadata.closed_candidate_columns",
    "metadata.index.parent_encounter_key",
    "metadata.index.child_four_part_key",
    "metadata.index.patient_join_key",
)
POLICY_CRITERIA = ("policy.age.leap_day_rule_a",)
CRITERION_IDS = (
    P00_CRITERIA
    + SCOPED_METADATA_CRITERIA
    + LOGICAL_CRITERIA
    + POLICY_CRITERIA
    + FAILURE_CRITERIA
)

EXPIRY_TRIGGERS = (
    "source_database_version_change",
    "schema_relation_column_key_or_index_change",
    "privilege_or_identity_change",
    "statement_or_digest_change",
    "package_or_protocol_change",
    "environment_class_change",
    "contradictory_or_unverifiable_evidence",
    "review_expiry",
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def _ascii(value: object, *, maximum: int = MAX_METADATA_TEXT_BYTES) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value.encode("ascii", "ignore")) <= maximum
        or not value.isascii()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise CaptureRejected("unexpected_shape")
    return value


def _exact_keys(row: object, keys: tuple[str, ...]) -> dict[str, object]:
    if type(row) is not dict or tuple(row.keys()) != keys:
        raise CaptureRejected("unexpected_shape")
    return row


def _validate_control(result: InjectedResult) -> None:
    if type(result) is not InjectedResult or result.rows:
        raise CaptureRejected("unexpected_shape")
    if result.notices or result.stdout or result.stderr:
        raise CaptureRejected("capture_failed")


def _validate_p00(result: InjectedResult) -> dict[str, bool]:
    if len(result.rows) != 1:
        raise CaptureRejected("preflight_failed")
    row = _exact_keys(result.rows[0], P00_COLUMNS)
    if any(type(row[name]) is not bool for name in P00_COLUMNS):
        raise CaptureRejected("unexpected_shape")
    if not all(row[name] for name in P00_COLUMNS):
        raise CaptureRejected("preflight_failed")
    return {name: True for name in P00_COLUMNS}


def _validate_version(result: InjectedResult) -> str:
    if len(result.rows) != 1:
        raise CaptureRejected("version_mismatch")
    row = _exact_keys(result.rows[0], ("source_version_class",))
    value = row["source_version_class"]
    if type(value) is not str or len(value) != 6 or not value.isascii() or not value.isdigit():
        raise CaptureRejected("version_mismatch")
    number = int(value)
    if not SOURCE_VERSION_MIN <= number <= SOURCE_VERSION_MAX:
        raise CaptureRejected("version_mismatch")
    return value


def _validate_m10(result: InjectedResult) -> list[dict[str, object]]:
    if len(result.rows) != len(M10_IDENTITIES):
        raise CaptureRejected("row_limit")
    validated: list[dict[str, object]] = []
    identities: list[tuple[str, str]] = []
    for candidate in result.rows:
        row = _exact_keys(candidate, M10_COLUMNS)
        relation_id = _ascii(row["relation_id"])
        column_id = _ascii(row["column_id"])
        identities.append((relation_id, column_id))
        present = row["column_present"]
        if type(present) is not bool:
            raise CaptureRejected("unexpected_shape")
        optional = (row["data_type"], row["nullable"], row["generated"], row["identity"])
        if not present:
            if optional != (None, None, None, None):
                raise CaptureRejected("unexpected_shape")
            raise CaptureRejected("inventory_mismatch")
        else:
            _ascii(row["data_type"])
            if any(type(value) is not bool for value in optional[1:]):
                raise CaptureRejected("unexpected_shape")
        validated.append(dict(row))
    if tuple(identities) != M10_IDENTITIES:
        raise CaptureRejected("inventory_mismatch")
    return validated


def _validate_k20(result: InjectedResult) -> list[dict[str, object]]:
    if len(result.rows) != len(K20_IDENTITIES):
        raise CaptureRejected("row_limit")
    validated: list[dict[str, object]] = []
    identities: list[tuple[str, str]] = []
    for candidate in result.rows:
        row = _exact_keys(candidate, K20_COLUMNS)
        relation_id = _ascii(row["relation_id"])
        key_id = _ascii(row["key_id"])
        identities.append((relation_id, key_id))
        count = row["matching_index_count"]
        if type(count) is not int or not 0 <= count <= MAX_MATCHING_INDEX_COUNT:
            raise CaptureRejected("unexpected_shape")
        for name in ("any_unique", "any_primary", "all_valid", "all_ready"):
            if type(row[name]) is not bool:
                raise CaptureRejected("unexpected_shape")
        method = row["single_index_method"]
        if count == 0:
            if any(row[name] for name in ("any_unique", "any_primary", "all_valid", "all_ready")):
                raise CaptureRejected("unexpected_shape")
            if method is not None:
                raise CaptureRejected("unexpected_shape")
        elif method is not None:
            _ascii(method)
        validated.append(dict(row))
    if tuple(identities) != K20_IDENTITIES:
        raise CaptureRejected("inventory_mismatch")
    return validated


def completed_years_rule_a(birth_date: date, clinic_day: date) -> int:
    """Apply the accepted 29-February/28-February KST clinic-day rule."""

    if type(birth_date) is not date or type(clinic_day) is not date or clinic_day < birth_date:
        raise CaptureRejected("unexpected_shape")
    leap = clinic_day.year % 4 == 0 and (
        clinic_day.year % 100 != 0 or clinic_day.year % 400 == 0
    )
    month = birth_date.month
    day = birth_date.day
    if month == 2 and day == 29 and not leap:
        day = 28
    anniversary = date(clinic_day.year, month, day)
    return clinic_day.year - birth_date.year - (clinic_day < anniversary)


def _criteria(*, complete: bool, fixed_reason: FixedReason) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for name in P00_COLUMNS:
        items.append({
            "criterion_id": f"preflight.{name}",
            "status": (
                CriterionStatus.PROVEN.value if complete else CriterionStatus.UNPROVEN.value
            ),
            "source_statement_id": "EKO-P00" if complete else None,
            "fixed_reason": None if complete else fixed_reason.value,
        })
    for criterion_id, statement_id in (
        ("metadata.source_version_class", "EKO-V01"),
        ("metadata.closed_candidate_columns", "EKO-M10"),
        ("metadata.index.parent_encounter_key", "EKO-K20"),
        ("metadata.index.child_four_part_key", "EKO-K20"),
        ("metadata.index.patient_join_key", "EKO-K20"),
    ):
        items.append({
            "criterion_id": criterion_id,
            "status": (
                CriterionStatus.PROVEN.value if complete else CriterionStatus.UNPROVEN.value
            ),
            "source_statement_id": statement_id if complete else None,
            "fixed_reason": None if complete else fixed_reason.value,
        })
    for criterion_id in LOGICAL_CRITERIA:
        items.append({
            "criterion_id": criterion_id,
            "status": CriterionStatus.UNPROVEN.value,
            "source_statement_id": None,
            "fixed_reason": "metadata_only",
        })
    items.append({
        "criterion_id": "policy.age.leap_day_rule_a",
        "status": CriterionStatus.NOT_APPLICABLE.value,
        "source_statement_id": None,
        "fixed_reason": "owner_decision_not_source_evidence",
    })
    for criterion_id in FAILURE_CRITERIA:
        active = (
            not complete
            and criterion_id
            == {
                FixedReason.PREFLIGHT_FAILED: "failure.preflight",
                FixedReason.INVENTORY_MISMATCH: "failure.inventory_mismatch",
                FixedReason.UNEXPECTED_SHAPE: "failure.unexpected_shape",
                FixedReason.PRIVACY_BOUNDARY: "failure.privacy_boundary",
                FixedReason.ROW_LIMIT: "failure.row_limit",
                FixedReason.BYTE_LIMIT: "failure.byte_limit",
                FixedReason.TIMEOUT: "failure.timeout",
                FixedReason.CANCEL_FAILED: "failure.cancel",
                FixedReason.CLEANUP_UNCERTAIN: "failure.cleanup",
                FixedReason.VERSION_MISMATCH: "failure.version_mismatch",
                FixedReason.CAPTURE_FAILED: "failure.capture_failed",
            }.get(fixed_reason)
        )
        items.append({
            "criterion_id": criterion_id,
            "status": (
                CriterionStatus.PROVEN.value if active else CriterionStatus.NOT_APPLICABLE.value
            ),
            "source_statement_id": None,
            "fixed_reason": fixed_reason.value if active else "synthetic_harness_only",
        })
    if tuple(item["criterion_id"] for item in items) != CRITERION_IDS:
        raise CaptureRejected("capture_failed")
    return items


def _build_artifact(
    *, evidence_date: date, run_status: RunStatus, fixed_reason: FixedReason,
    version: str | None, p00: dict[str, bool] | None,
    m10: list[dict[str, object]] | None, k20: list[dict[str, object]] | None,
) -> bytes:
    complete = run_status is RunStatus.COMPLETE
    if complete and (fixed_reason is not FixedReason.NONE or None in (version, p00, m10, k20)):
        raise CaptureRejected("capture_failed")
    if not complete and fixed_reason is FixedReason.NONE:
        raise CaptureRejected("capture_failed")
    results = {"p00": p00, "v01": {"source_version_class": version}, "m10": m10, "k20": k20}
    criteria = _criteria(complete=complete, fixed_reason=fixed_reason)
    safe_content_sha256 = sha256(_canonical({"results": results, "criteria": criteria})).hexdigest()
    artifact = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "package_id": PACKAGE_ID,
        "package_revision": PACKAGE_REVISION,
        "central_commit": CENTRAL_COMMIT,
        "run_status": run_status.value,
        "fixed_reason": fixed_reason.value,
        "evidence_date": evidence_date.isoformat(),
        "environment_class": ENVIRONMENT_CLASS,
        "provenance": {
            "artifact_path": ARTIFACT_PATH,
            "safe_content_sha256": safe_content_sha256,
            "reviewer_role": REVIEWER_ROLE,
            "authority_role": AUTHORITY_ROLE,
            "applicable_source_database_version": version,
            "accepted_version_range": f"{SOURCE_VERSION_MIN}-{SOURCE_VERSION_MAX}",
            "expires_on": (evidence_date + timedelta(days=EVIDENCE_VALID_DAYS)).isoformat(),
            "revalidation_triggers": list(EXPIRY_TRIGGERS),
        },
        "results": results,
        "criteria": criteria,
    }
    payload = _canonical(artifact)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise CaptureRejected("byte_limit")
    return payload


def _publish(
    *, sink: object, evidence_date: date, run_status: RunStatus,
    fixed_reason: FixedReason, version: str | None = None,
    p00: dict[str, bool] | None = None, m10: list[dict[str, object]] | None = None,
    k20: list[dict[str, object]] | None = None,
) -> CaptureOutcome:
    try:
        artifact = _build_artifact(
            evidence_date=evidence_date,
            run_status=run_status,
            fixed_reason=fixed_reason,
            version=version,
            p00=p00,
            m10=m10,
            k20=k20,
        )
        sink.create_new()
        sink.write(artifact)
        sink.publish()
    except Exception:
        try:
            sink.discard()
        except Exception:
            pass
        return CaptureOutcome(RunStatus.BLOCKED, FixedReason.CAPTURE_FAILED, None)
    return CaptureOutcome(run_status, fixed_reason, artifact)


def _reason(error: Exception) -> FixedReason:
    value = str(error)
    return {
        "preflight_failed": FixedReason.PREFLIGHT_FAILED,
        "inventory_mismatch": FixedReason.INVENTORY_MISMATCH,
        "unexpected_shape": FixedReason.UNEXPECTED_SHAPE,
        "privacy_boundary": FixedReason.PRIVACY_BOUNDARY,
        "row_limit": FixedReason.ROW_LIMIT,
        "byte_limit": FixedReason.BYTE_LIMIT,
        "timeout": FixedReason.TIMEOUT,
        "version_mismatch": FixedReason.VERSION_MISMATCH,
        "capture_failed": FixedReason.CAPTURE_FAILED,
    }.get(value, FixedReason.CAPTURE_FAILED)


def run_injected_capture(
    *, port: object, sink: object, statement_bytes: dict[str, bytes], evidence_date: date,
) -> CaptureOutcome:
    """Run the pure injected gate; production adapters are deliberately absent."""

    if type(evidence_date) is not date:
        return CaptureOutcome(RunStatus.BLOCKED, FixedReason.CAPTURE_FAILED, None)
    expected_ids = tuple(spec.statement_id for spec in STATEMENT_SPECS)
    if type(statement_bytes) is not dict or tuple(statement_bytes.keys()) != expected_ids:
        return _publish(
            sink=sink, evidence_date=evidence_date, run_status=RunStatus.BLOCKED,
            fixed_reason=FixedReason.INVENTORY_MISMATCH,
        )
    for spec in STATEMENT_SPECS:
        value = statement_bytes[spec.statement_id]
        if type(value) is not bytes or sha256(value).hexdigest() != spec.sha256_hex:
            return _publish(
                sink=sink, evidence_date=evidence_date, run_status=RunStatus.BLOCKED,
                fixed_reason=FixedReason.INVENTORY_MISMATCH,
            )

    connected = False
    leased = False
    deadline: float | None = None
    failure: FixedReason | None = None
    p00: dict[str, bool] | None = None
    version: str | None = None
    m10: list[dict[str, object]] | None = None
    k20: list[dict[str, object]] | None = None
    try:
        started = port.monotonic()
        deadline = started + GLOBAL_DEADLINE_SECONDS
        if port.monotonic() > deadline or not port.acquire_lease(deadline):
            raise CaptureRejected("timeout")
        leased = True
        if port.monotonic() > deadline or not port.connect(deadline):
            raise CaptureRejected("timeout")
        connected = True
        for spec in STATEMENT_SPECS[:-1]:
            if port.monotonic() > deadline:
                raise CaptureRejected("timeout")
            result = port.execute(spec.statement_id, statement_bytes[spec.statement_id], deadline)
            if type(result) is not InjectedResult:
                raise CaptureRejected("unexpected_shape")
            if result.notices or result.stdout or result.stderr:
                raise CaptureRejected("capture_failed")
            if spec.statement_id.startswith("EKO-C"):
                _validate_control(result)
            elif spec.statement_id == "EKO-P00":
                p00 = _validate_p00(result)
            elif spec.statement_id == "EKO-V01":
                version = _validate_version(result)
            elif spec.statement_id == "EKO-M10":
                m10 = _validate_m10(result)
            elif spec.statement_id == "EKO-K20":
                k20 = _validate_k20(result)
            if port.monotonic() > deadline:
                raise CaptureRejected("timeout")
        result = port.execute("EKO-C99", statement_bytes["EKO-C99"], deadline)
        _validate_control(result)
    except Exception as error:
        failure = _reason(error)
        if connected and deadline is not None:
            try:
                if not port.cancel(deadline):
                    failure = FixedReason.CANCEL_FAILED
            except Exception:
                failure = FixedReason.CANCEL_FAILED
            try:
                if not port.rollback(deadline):
                    failure = FixedReason.CLEANUP_UNCERTAIN
            except Exception:
                failure = FixedReason.CLEANUP_UNCERTAIN
    finally:
        cleanup_ok = True
        if connected:
            try:
                cleanup_ok = bool(port.close_cursors(deadline)) and cleanup_ok
            except Exception:
                cleanup_ok = False
            try:
                cleanup_ok = bool(port.close_connection(deadline)) and cleanup_ok
            except Exception:
                cleanup_ok = False
        if leased and deadline is not None:
            try:
                cleanup_ok = bool(port.release_lease(deadline)) and cleanup_ok
            except Exception:
                cleanup_ok = False
        try:
            within_deadline = deadline is not None and port.monotonic() <= deadline
        except Exception:
            within_deadline = False
        if not cleanup_ok:
            failure = FixedReason.CLEANUP_UNCERTAIN
        elif not within_deadline:
            failure = failure or FixedReason.TIMEOUT

    if failure is not None:
        if failure in {
            FixedReason.TIMEOUT,
            FixedReason.CANCEL_FAILED,
            FixedReason.CLEANUP_UNCERTAIN,
        }:
            try:
                sink.discard()
            except Exception:
                pass
            return CaptureOutcome(RunStatus.BLOCKED, failure, None)
        return _publish(
            sink=sink,
            evidence_date=evidence_date,
            run_status=RunStatus.BLOCKED,
            fixed_reason=failure,
            version=version,
        )
    if p00 is None or version is None or m10 is None or k20 is None:
        try:
            sink.discard()
        except Exception:
            pass
        return CaptureOutcome(RunStatus.BLOCKED, FixedReason.CAPTURE_FAILED, None)
    return _publish(
        sink=sink,
        evidence_date=evidence_date,
        run_status=RunStatus.COMPLETE,
        fixed_reason=FixedReason.NONE,
        version=version,
        p00=p00,
        m10=m10,
        k20=k20,
    )
