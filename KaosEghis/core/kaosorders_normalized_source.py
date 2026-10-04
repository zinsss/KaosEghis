"""Pure synthetic serializer for KaosOrders' disabled normalized-source contract.

Reference: zinsss/KaosOrders 7c9275fb74680f46e4d459c821c7d501758c6b1c.
No reader, runtime hook, production ordering, endpoint, persistence or delivery.
Returned JSON contains source identifiers and must never be logged.
"""

from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
import hashlib
import json
from uuid import UUID

from KaosEghis.core.emr_source import (
    MAX_ENCOUNTERS, MAX_ORDERS, EncounterFacts, OrderFacts, OrderKey,
    OrderQualifiers, OrderState, ReceptionQualifiers, ReceptionState,
    SnapshotRejected, SourceSnapshot, _PrivateModel, _decimal_value,
    _source_flag, _text, _timestamp,
)


CONTRACT_ID = "kaosorders.normalized-source"
CONTRACT_VERSION = 1
MAX_SEQUENCE_VALUE = 2**63 - 1


@dataclass(frozen=True, repr=False)
class SyntheticDeliveryMetadata(_PrivateModel):
    clinic_id: str
    batch_id: str
    source_epoch: int
    revision: int


def _model(value, kind):
    # Frozen dataclasses alone do not validate direct construction or extra fields.
    if type(value) is not kind or set(vars(value)) != {field.name for field in fields(kind)}:
        raise SnapshotRejected("invalid_snapshot")


def _wire_text(value, *, allow_empty=False):
    if type(value) is not str or value != value.strip():
        raise SnapshotRejected("invalid_text")
    if allow_empty and value == "":
        return value
    return _text(value)


def _sequence(value):
    if type(value) is not int or not 1 <= value <= MAX_SEQUENCE_VALUE:
        raise SnapshotRejected("invalid_sequence")
    return value


def _decimal_text(value):
    if value is None:
        return None
    if type(value) is not Decimal:
        raise SnapshotRejected("invalid_number")
    _decimal_value(value)
    if value.is_zero():
        return "0"
    # Fixed formatting preserves exactness without Decimal context rounding.
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if len(text) > 32:
        raise SnapshotRejected("invalid_number")
    return text


def _encounter(item):
    _model(item, EncounterFacts)
    _model(item.qualifiers, ReceptionQualifiers)
    if item.sex == "":
        raise SnapshotRejected("unverified_sex")
    if (item.sex is not None and (type(item.sex) is not str or item.sex not in ("M", "F", "O"))
            or (item.age is not None and (type(item.age) is not int or not 0 <= item.age <= 130))):
        raise SnapshotRejected("invalid_demographics")
    if type(item.state) is not ReceptionState:
        raise SnapshotRejected("unknown_reception_state")
    return {
        "encounter_id": _wire_text(item.encounter_id),
        "chart_number": _wire_text(item.chart_no),
        "patient_name": _wire_text(item.patient_name),
        "sex": item.sex,
        "age": item.age,
        "source_state_code": _wire_text(item.source_state_code),
        "state": item.state.value,
        "qualifiers": {
            "hold_yn": _source_flag(item.qualifiers.hold_yn),
            "hold_opd": _source_flag(item.qualifiers.hold_opd),
        },
    }


def _order(item):
    _model(item, OrderFacts)
    _model(item.key, OrderKey)
    _model(item.qualifiers, OrderQualifiers)
    if type(item.key.order_date) is not date:
        raise SnapshotRejected("invalid_order_date")
    if type(item.state) is not OrderState:
        raise SnapshotRejected("unknown_order_state")
    return {
        "key": {
            "encounter_id": _wire_text(item.key.encounter_id),
            "order_date": item.key.order_date.isoformat(),
            "order_number": _wire_text(item.key.order_number),
            "order_sequence": _wire_text(item.key.order_sequence),
        },
        "order_code": _wire_text(item.order_code),
        "order_type": _wire_text(item.order_type),
        "department_code": _wire_text(item.department_code, allow_empty=True),
        "source_state_code": _wire_text(item.source_state_code),
        "state": item.state.value,
        "qualifiers": {
            "dc_yn": _source_flag(item.qualifiers.dc_yn),
            "act_yn": _source_flag(item.qualifiers.act_yn),
        },
        "quantity": _decimal_text(item.quantity),
        "days": _decimal_text(item.days),
        "frequency": _decimal_text(item.frequency),
    }


def calculate_content_sha256(payload: dict) -> str:
    """Digest parsed JSON only, not source validity or delivery authorization."""
    if type(payload) is not dict:
        raise SnapshotRejected("invalid_payload")
    content = dict(payload)
    content.pop("content_sha256", None)
    try:
        encoded = json.dumps(content, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        raise SnapshotRejected("invalid_payload") from None
    return hashlib.sha256(encoded).hexdigest()


def serialize_normalized_source(
    snapshot: SourceSnapshot, metadata: SyntheticDeliveryMetadata, *, synthetic_fixture=False,
) -> dict:
    """Serialize a validated detached snapshot with explicit synthetic metadata.

    The fixture flag is an explicit caller assertion, not proof of synthetic data.
    No production epoch/revision allocator or retry store is supplied here.
    """
    if synthetic_fixture is not True:
        raise SnapshotRejected("synthetic_fixture_required")
    _model(snapshot, SourceSnapshot)
    _model(metadata, SyntheticDeliveryMetadata)
    if type(snapshot.clinic_day) is not date:
        raise SnapshotRejected("invalid_day")
    if (type(snapshot.encounters) is not tuple or type(snapshot.orders) is not tuple
            or len(snapshot.encounters) > MAX_ENCOUNTERS or len(snapshot.orders) > MAX_ORDERS):
        raise SnapshotRejected("invalid_row_bound")
    try:
        batch_id = _wire_text(metadata.batch_id)
        if str(UUID(batch_id)) != batch_id:
            raise ValueError
    except (SnapshotRejected, ValueError, TypeError, AttributeError):
        raise SnapshotRejected("invalid_batch_id") from None

    encounters = [_encounter(item) for item in snapshot.encounters]
    orders = [_order(item) for item in snapshot.orders]
    encounter_ids = [item["encounter_id"] for item in encounters]
    keys = [tuple(item["key"][name] for name in
                  ("encounter_id", "order_date", "order_number", "order_sequence")) for item in orders]
    if len(set(encounter_ids)) != len(encounter_ids):
        raise SnapshotRejected("duplicate_encounter")
    if len(set(keys)) != len(keys):
        raise SnapshotRejected("duplicate_order")
    parents = set(encounter_ids)
    if any(key[0] not in parents for key in keys):
        raise SnapshotRejected("orphan_order")

    payload = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "batch_id": batch_id,
        "source_epoch": _sequence(metadata.source_epoch),
        "revision": _sequence(metadata.revision),
        "scope": {
            "clinic_id": _wire_text(metadata.clinic_id),
            "source_id": _wire_text(snapshot.source_id),
            "projection_id": _wire_text(snapshot.projection_id),
            "clinic_day": snapshot.clinic_day.isoformat(),
            "mapping_revision": _wire_text(snapshot.mapping_revision),
        },
        "observed_at": _timestamp(snapshot.observed_at).isoformat(),
        "snapshot_kind": "FULL",
        "complete": True,
        "encounters": sorted(encounters, key=lambda item: item["encounter_id"]),
        "orders": [item for _key, item in sorted(zip(keys, orders), key=lambda pair: pair[0])],
    }
    payload["content_sha256"] = calculate_content_sha256(payload)
    return payload
