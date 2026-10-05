"""Pure synthetic v2 serialization; no v1 conversion, outbox or delivery.

Planning reference: KaosOrders 6837845fc4c691075bab41c6e07ef69e8562580b.
Output contains synthetic identities and must not be logged as a payload.
"""

from dataclasses import dataclass
import hashlib
import json
from uuid import UUID

from KaosEghis.core.emr_source import SnapshotRejected
from KaosEghis.core.emr_source_v2 import (
    SourceSnapshotV2, _PrivateV2, _require_model, _wire_text, decimal_text,
    validate_source_snapshot_v2,
)


CONTRACT_ID = "kaosorders.normalized-source"
CONTRACT_VERSION = 2
MAX_SEQUENCE_VALUE = 2**63 - 1


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticDeliveryMetadataV2(_PrivateV2):
    clinic_id: str
    batch_id: str
    source_epoch: int
    revision: int


def _sequence(value):
    if type(value) is not int or not 1 <= value <= MAX_SEQUENCE_VALUE:
        raise SnapshotRejected("invalid_sequence")
    return value


def _check_digest_input(value):
    # Also protect direct helper callers before JSON bytes or a digest are made.
    if isinstance(value, dict):
        if any(type(key) is not str or key == "hold_opd" for key in value):
            raise SnapshotRejected("invalid_payload")
        for child in value.values():
            _check_digest_input(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_digest_input(child)


def calculate_content_sha256_v2(payload: dict) -> str:
    """Privacy-checked content hash, not full schema validation or authorization."""
    if type(payload) is not dict:
        raise SnapshotRejected("invalid_payload")
    content = dict(payload)
    content.pop("content_sha256", None)
    try:
        _check_digest_input(content)
        encoded = json.dumps(content, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        raise SnapshotRejected("invalid_payload") from None
    return hashlib.sha256(encoded).hexdigest()


def serialize_normalized_source_v2(
    snapshot: SourceSnapshotV2, metadata: SyntheticDeliveryMetadataV2, *, synthetic_fixture=False,
) -> dict:
    """Explicit fixture metadata only. No generated or persisted ordering state."""
    if synthetic_fixture is not True:
        raise SnapshotRejected("synthetic_fixture_required")
    validate_source_snapshot_v2(snapshot)
    _require_model(metadata, SyntheticDeliveryMetadataV2)
    try:
        batch_id = _wire_text(metadata.batch_id)
        if str(UUID(batch_id)) != batch_id:
            raise ValueError
    except (SnapshotRejected, ValueError, TypeError, AttributeError):
        raise SnapshotRejected("invalid_batch_id") from None
    payload = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "batch_id": batch_id,
        "source_epoch": _sequence(metadata.source_epoch),
        "revision": _sequence(metadata.revision),
        "scope": {
            "clinic_id": _wire_text(metadata.clinic_id),
            "source_id": snapshot.source_id,
            "projection_id": snapshot.projection_id,
            "clinic_day": snapshot.clinic_day.isoformat(),
            "mapping_revision": snapshot.mapping_revision,
        },
        "observed_at": snapshot.observed_at.isoformat(),
        "snapshot_kind": "FULL",
        "complete": True,
        "encounters": [{
            "encounter_id": item.encounter_id, "chart_number": item.chart_no,
            "patient_name": item.patient_name, "sex": item.sex, "age": item.age,
            "source_state_code": item.source_state_code, "state": item.state.value,
            "qualifiers": {"hold_yn": item.qualifiers.hold_yn},
        } for item in sorted(snapshot.encounters, key=lambda item: item.encounter_id)],
        "orders": [{
            "key": {
                "encounter_id": item.key.encounter_id, "order_date": item.key.order_date.isoformat(),
                "order_number": item.key.order_number, "order_sequence": item.key.order_sequence,
            },
            "order_code": item.order_code, "order_type": item.order_type,
            "department_code": item.department_code, "source_state_code": item.source_state_code,
            "state": item.state.value,
            "qualifiers": {"dc_yn": item.qualifiers.dc_yn, "act_yn": item.qualifiers.act_yn},
            "quantity": decimal_text(item.quantity), "days": decimal_text(item.days),
            "frequency": decimal_text(item.frequency),
        } for item in sorted(snapshot.orders, key=lambda item: item.key)],
    }
    payload["content_sha256"] = calculate_content_sha256_v2(payload)
    return payload
