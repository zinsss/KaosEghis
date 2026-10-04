import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

import pytest

from KaosEghis.core.emr_source import (
    MAX_ENCOUNTERS, MAX_ORDERS, EmrDayRead, OrderQualifiers, OrderState,
    ReadStatus, ReceptionQualifiers, ReceptionState, SnapshotRejected,
    SourcePolicy, normalize_source_day,
)
from KaosEghis.core.emr_source_shadow import SourceLedger
from KaosEghis.core.kaosorders_normalized_source import (
    MAX_SEQUENCE_VALUE, SyntheticDeliveryMetadata, calculate_content_sha256,
    serialize_normalized_source,
)
from tests.test_emr_source import fake_db


FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_COMMIT = "7c9275fb74680f46e4d459c821c7d501758c6b1c"


def expected(name="full"):
    return json.loads((FIXTURES / f"normalized_source_v1_{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def source_policy():
    return SourcePolicy(
        "synthetic-v1",
        tuple((f"TEST_{state.value}", state) for state in ReceptionState),
        tuple((f"TEST_{state.value}", state) for state in OrderState),
    )


@pytest.fixture
def source_read():
    # Deliberately independent source aliases, not a round trip of the expected JSON.
    encounters = tuple(
        {"encounter_id": f"fixture-{identifier}", "chart_no": f"TEST-000{index}",
         "patient_name": f"Synthetic {name}", "sex": sex, "age": age,
         "state_code": f"TEST_{state}", "qualifiers": {"hold_yn": hold, "hold_opd": hold}}
        for index, (identifier, name, sex, age, state, hold) in enumerate([
            ("cancelled", "Alpha", "F", 53, "CANCELLED", "N"),
            ("consultation-completed", "Beta", "M", 47, "CONSULTATION_COMPLETED", "N"),
            ("hold", "Gamma", "F", 38, "ON_HOLD", "N"),
            ("in-progress", "Delta", None, None, "IN_PROGRESS", "Y"),
            ("no-orders", "Epsilon", "O", 29, "REGISTERED", "N"),
            ("payment-completed", "Zeta", "M", 61, "PAYMENT_COMPLETED", "N"),
        ], start=1)
    )
    orders = tuple(
        {"encounter_id": f"fixture-{encounter}", "order_date": date(2026, 10, 1),
         "order_number": number, "order_sequence": "1", "order_code": code,
         "order_type": kind, "department_code": department, "state_code": f"TEST_{state}",
         "qualifiers": {"dc_yn": dc, "act_yn": act},
         **({"quantity": "1.000", "days": 1, "frequency": Decimal("1.00")} if number == "1" and encounter == "hold" else {})}
        for encounter, number, code, kind, department, state, dc, act in [
            ("cancelled", "1", "TEST_CANCELLED_CHILD", "TEST_OTHER", "", "ACTIVE", "N", "N"),
            ("consultation-completed", "1", "TEST_FEE", "TEST_FEE", "", "ACTIVE", "N", "Y"),
            ("hold", "1", "TEST_LAB", "TEST_LAB_TYPE", "TEST_LAB", "ACTIVE", "N", "N"),
            ("hold", "2", "TEST_CANCELLED_ORDER", "TEST_OTHER", "TEST_DEPARTMENT", "CANCELLED", "Y", "N"),
        ]
    )
    return EmrDayRead(
        "fixture-eghis", "fixture-all-orders-v1", date(2026, 10, 1),
        datetime.fromisoformat("2026-10-01T09:00:00+09:00"), ReadStatus.COMPLETE,
        encounters, orders, keys_verified=True, states_verified=True, whole_day=True,
        untruncated=True, consistent_snapshot=True, connection_closed=True,
        structured_fields_verified=True,
    )


@pytest.fixture
def metadata():
    return SyntheticDeliveryMetadata("fixture-clinic", "11111111-1111-4111-8111-111111111111", 1, 1)


@pytest.fixture
def snapshot(source_read, source_policy):
    return normalize_source_day(source_read, source_policy)


def serialize(snapshot, metadata):
    return serialize_normalized_source(snapshot, metadata, synthetic_fixture=True)


def changed_read(read, *, encounter=None, order=None, **changes):
    read = deepcopy(read)
    if encounter:
        read.encounters[0].update(encounter)
    if order:
        read.orders[0].update(order)
    return replace(read, observed_at=read.observed_at + timedelta(seconds=30), **changes)


def independent_digest(payload):
    content = {key: value for key, value in payload.items() if key != "content_sha256"}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def test_exact_full_fixture_parity(snapshot, metadata):
    payload = serialize(snapshot, metadata)
    assert payload == expected()
    assert payload["content_sha256"] == "4173c829519b0884a9cca0a7ee216ee8d6bfa05147427de1a16f638bf2c93030"
    assert independent_digest(payload) == payload["content_sha256"]


def test_exact_verified_empty_day_parity(source_read, source_policy, metadata):
    source_read = replace(source_read, encounters=(), orders=(), clinic_day=date(2026, 10, 2),
                          observed_at=datetime.fromisoformat("2026-10-02T09:00:00+09:00"))
    metadata = replace(metadata, batch_id="22222222-2222-4222-8222-222222222222")
    payload = serialize(normalize_source_day(source_read, source_policy), metadata)
    assert payload == expected("empty")
    assert payload["content_sha256"] == "d286948d18b2e7b66f86f1a1b6c7931f58cd1753e8572e1338df85f1f37fecef"
    assert independent_digest(payload) == payload["content_sha256"]


@pytest.mark.parametrize("state", list(ReceptionState))
def test_all_six_states_preserved_with_no_inferred_child_state(snapshot, metadata, state):
    payload = serialize(snapshot, metadata)
    assert state.value in {row["state"] for row in payload["encounters"]}
    by_id = {row["encounter_id"]: row["state"] for row in payload["encounters"]}
    assert by_id["fixture-consultation-completed"] == "CONSULTATION_COMPLETED"
    assert by_id["fixture-payment-completed"] == "PAYMENT_COMPLETED"
    assert payload["encounters"][0]["state"] == "CANCELLED"
    assert payload["orders"][0]["state"] == "ACTIVE"
    assert payload["orders"][1]["order_code"] == "TEST_FEE"
    assert any(row["encounter_id"] == "fixture-no-orders" for row in payload["encounters"])
    assert not any(row["key"]["encounter_id"] == "fixture-no-orders" for row in payload["orders"])


def test_same_key_edits_and_key_reuse_replace_facts_without_filtering(source_read, source_policy, metadata):
    ledger = SourceLedger()
    first = ledger.observe(source_read, source_policy)
    edited = changed_read(source_read, order={"quantity": "2.2500", "days": 5, "frequency": "3"})
    change = ledger.observe(edited, source_policy)
    assert len(change.order_upserts) == 1 and not change.missing_order_keys
    payload = serialize(change.snapshot, replace(metadata, revision=2))
    assert payload["orders"][0]["quantity"] == "2.25"
    assert payload["orders"][0]["days"] == "5" and payload["orders"][0]["frequency"] == "3"
    removed = ledger.observe(changed_read(edited, orders=edited.orders[1:]), source_policy)
    replacement = changed_read(edited, order={"order_code": "TEST_UNCLASSIFIED", "order_type": "TEST_NEW",
                                            "department_code": "", "quantity": None, "days": None, "frequency": None})
    replacement = replace(replacement, observed_at=removed.snapshot.observed_at + timedelta(seconds=30))
    restored = ledger.observe(replacement, source_policy)
    assert restored.order_upserts[0].key == removed.missing_order_keys[0] == first.snapshot.orders[0].key
    row = serialize(restored.snapshot, replace(metadata, revision=4))["orders"][0]
    assert row["order_code"] == "TEST_UNCLASSIFIED" and row["quantity"] is None
    assert row["order_type"] == "TEST_NEW" and row["department_code"] == ""


def test_explicit_cancellation_is_not_disappearance(source_read, source_policy, metadata):
    ledger = SourceLedger()
    ledger.observe(source_read, source_policy)
    cancelled = changed_read(source_read, order={"state_code": "TEST_CANCELLED",
                                               "qualifiers": {"dc_yn": "Y", "act_yn": "N"}})
    change = ledger.observe(cancelled, source_policy)
    assert len(change.order_upserts) == 1 and not change.missing_order_keys
    assert serialize(change.snapshot, replace(metadata, revision=2))["orders"][0]["state"] == "CANCELLED"
    removal = ledger.observe(changed_read(cancelled, orders=cancelled.orders[1:]), source_policy)
    assert len(removal.missing_order_keys) == 1 and not removal.order_upserts
    payload = serialize(removal.snapshot, replace(metadata, revision=3))
    assert len(payload["orders"]) == 3 and payload["snapshot_kind"] == "FULL"
    assert "withdrawals" not in payload


@pytest.mark.parametrize("row_type,names", [("encounters", ("hold_yn", "hold_opd")), ("orders", ("dc_yn", "act_yn"))])
@pytest.mark.parametrize("values", [("Y", "Y"), ("Y", "N"), ("N", "Y"), ("N", "N")])
def test_raw_qualifiers_are_detached_fixed_facts_not_state_rules(source_read, source_policy, metadata, row_type, names, values):
    read = deepcopy(source_read)
    qualifiers = dict(zip(names, values))
    getattr(read, row_type)[0]["qualifiers"] = qualifiers
    snapshot = normalize_source_day(read, source_policy)
    payload = serialize(snapshot, metadata)
    assert payload[row_type][0]["qualifiers"] == qualifiers
    assert payload["encounters"][0]["state"] == "CANCELLED"
    assert payload["orders"][0]["state"] == "ACTIVE"
    qualifiers[names[0]] = "PRIVATE_MUTATION"
    assert serialize(snapshot, metadata) == payload
    with pytest.raises(FrozenInstanceError):
        setattr(getattr(snapshot, row_type)[0].qualifiers, names[0], "N")


@pytest.mark.parametrize("row_type,field", [("encounters", "hold_yn"), ("encounters", "hold_opd"),
                                           ("orders", "dc_yn"), ("orders", "act_yn")])
@pytest.mark.parametrize("bad", [None, True, 1, "", "n", " Y", "Y ", "UNKNOWN", "PRIVATE_TEST_MARKER"])
def test_unknown_qualifiers_are_not_defaulted(source_read, source_policy, row_type, field, bad):
    getattr(source_read, row_type)[0]["qualifiers"][field] = bad
    with pytest.raises(SnapshotRejected) as error:
        normalize_source_day(source_read, source_policy)
    assert str(error.value) == "invalid_qualifier"
    assert "PRIVATE_TEST_MARKER" not in repr(error.value)


@pytest.mark.parametrize("row_type", ["encounters", "orders"])
@pytest.mark.parametrize("change", ["missing_container", "missing_field", "extra", "none"])
def test_qualifier_shape_is_closed(source_read, source_policy, row_type, change):
    row = getattr(source_read, row_type)[0]
    if change == "missing_container":
        del row["qualifiers"]
    elif change == "missing_field":
        row["qualifiers"].pop(next(iter(row["qualifiers"])))
    elif change == "extra":
        row["qualifiers"]["clinical_meaning"] = "PRIVATE_TEST_MARKER"
    else:
        row["qualifiers"] = None
    with pytest.raises(SnapshotRejected, match="^invalid_fields$"):
        normalize_source_day(source_read, source_policy)


@pytest.mark.parametrize("row_type,field", [("encounter", "hold_yn"), ("encounter", "hold_opd"),
                                           ("order", "dc_yn"), ("order", "act_yn")])
def test_qualifier_only_changes_are_source_edits(source_read, source_policy, row_type, field):
    ledger = SourceLedger()
    ledger.observe(source_read, source_policy)
    source_rows = source_read.encounters if row_type == "encounter" else source_read.orders
    qualifiers = dict(source_rows[0]["qualifiers"], **{field: "Y"})
    result = ledger.observe(changed_read(source_read, **{row_type: {"qualifiers": qualifiers}}), source_policy)
    assert len(result.encounter_upserts if row_type == "encounter" else result.order_upserts) == 1
    assert not result.missing_order_keys and not result.missing_encounter_ids


def test_four_part_key_and_canonical_order_are_preserved(snapshot, metadata):
    original = snapshot.orders[2]
    extra = tuple(replace(original, key=replace(original.key, **changes)) for changes in [
        {"encounter_id": "fixture-no-orders"}, {"order_date": date(2026, 9, 30)},
        {"order_number": "10"}, {"order_sequence": "2"},
    ])
    full = replace(snapshot, orders=snapshot.orders + extra)
    payload = serialize(full, metadata)
    keys = [tuple(row["key"][name] for name in ("encounter_id", "order_date", "order_number", "order_sequence"))
            for row in payload["orders"]]
    assert keys == sorted(keys) and len(set(keys)) == 8
    reverse = replace(full, encounters=tuple(reversed(full.encounters)), orders=tuple(reversed(full.orders)))
    assert serialize(reverse, metadata) == payload


@pytest.mark.parametrize("field", ["quantity", "days", "frequency"])
@pytest.mark.parametrize("raw,canonical", [("2.2500", "2.25"), ("1000.00", "1000"), ("-0.000", "0"),
                                          ("-0E+12", "0"), ("1E-12", "0.000000000001"),
                                          ("1E+9", "1000000000"), ("-12.3400", "-12.34")])
def test_exact_decimal_formatting_is_independent_of_context(snapshot, metadata, field, raw, canonical):
    row = replace(snapshot.orders[0], **{field: Decimal(raw)})
    with localcontext() as context:
        context.prec = 2
        payload = serialize(replace(snapshot, orders=(row,) + snapshot.orders[1:]), metadata)
    assert payload["orders"][0][field] == canonical
    assert independent_digest(payload) == payload["content_sha256"]


@pytest.mark.parametrize("bad", [True, 1.5, float("nan"), float("inf"), "PRIVATE_TEST_MARKER",
                                 Decimal("NaN"), Decimal("Infinity"), Decimal("1E+100"), Decimal("1E-100")])
def test_invalid_decimal_facts_are_rejected_not_coerced(snapshot, metadata, bad):
    order = replace(snapshot.orders[0], quantity=bad)
    with pytest.raises(SnapshotRejected) as error:
        serialize(replace(snapshot, orders=(order,) + snapshot.orders[1:]), metadata)
    assert str(error.value) == "invalid_number"
    assert "PRIVATE_TEST_MARKER" not in repr(error.value)


def test_explicit_null_is_not_a_guessed_blank_sex_conversion(source_read, source_policy, metadata):
    source_read.encounters[0]["sex"] = None
    assert serialize(normalize_source_day(source_read, source_policy), metadata)["encounters"][0]["sex"] is None
    source_read.encounters[0]["sex"] = ""
    snapshot = normalize_source_day(source_read, source_policy)
    assert snapshot.encounters[0].sex == ""
    with pytest.raises(SnapshotRejected, match="^unverified_sex$"):
        serialize(snapshot, metadata)


@pytest.mark.parametrize("code", ["10", "30", "40"])
def test_no_production_code_mapping_is_invented(source_read, source_policy, code):
    source_read.encounters[0]["state_code"] = code
    with pytest.raises(SnapshotRejected, match="^unknown_reception_state$"):
        normalize_source_day(source_read, source_policy)


def test_unicode_digest_tamper_detection_and_no_input_mutation(source_read, source_policy, metadata):
    source_read.encounters[0]["patient_name"] = "\ud569\uc131 \ud658\uc790"
    snapshot = normalize_source_day(source_read, source_policy)
    before = deepcopy(snapshot)
    payload = serialize(snapshot, metadata)
    assert snapshot == before
    assert payload["content_sha256"] == independent_digest(payload)
    tampered = deepcopy(payload)
    tampered["orders"][0]["order_code"] = "TEST_CHANGED"
    assert calculate_content_sha256(tampered) != tampered["content_sha256"]
    assert serialize(snapshot, metadata) == payload  # No generated UUID/cursor/time.


@pytest.mark.parametrize("bad", [None, [], {"bad": float("nan")}, {"bad": float("inf")}, {"bad": object()}, {"bad": "\ud800"}])
def test_digest_failures_are_fixed_and_redacted(bad):
    with pytest.raises(SnapshotRejected, match="^invalid_payload$"):
        calculate_content_sha256(bad)


@pytest.mark.parametrize("field,value,reason", [
    ("batch_id", "PRIVATE_TEST_MARKER", "invalid_batch_id"),
    ("batch_id", None, "invalid_batch_id"),
    ("clinic_id", " PRIVATE_TEST_MARKER", "invalid_text"),
    ("clinic_id", "x" * 129, "invalid_text"),
    ("source_epoch", 0, "invalid_sequence"), ("revision", True, "invalid_sequence"),
    ("source_epoch", "1", "invalid_sequence"), ("revision", MAX_SEQUENCE_VALUE + 1, "invalid_sequence"),
])
def test_metadata_is_explicit_strict_and_not_allocated(snapshot, metadata, field, value, reason):
    with pytest.raises(SnapshotRejected) as error:
        serialize(snapshot, replace(metadata, **{field: value}))
    assert str(error.value) == reason and "PRIVATE_TEST_MARKER" not in repr(error.value)


@pytest.mark.parametrize("flag", [False, None, 1, "true"])
def test_synthetic_gate_requires_explicit_true(snapshot, metadata, flag):
    with pytest.raises(SnapshotRejected, match="^synthetic_fixture_required$"):
        serialize_normalized_source(snapshot, metadata, synthetic_fixture=flag)


@pytest.mark.parametrize("state", [value for value in ReadStatus if value is not ReadStatus.COMPLETE])
def test_failed_empty_read_cannot_reach_serializer(source_read, source_policy, metadata, state):
    with pytest.raises(SnapshotRejected, match="^incomplete_source$"):
        snapshot = normalize_source_day(replace(source_read, status=state, encounters=(), orders=()), source_policy)
        serialize(snapshot, metadata)
        pytest.fail("Non-authoritative read reached serializer")


@pytest.mark.parametrize("field,limit", [("encounters", MAX_ENCOUNTERS), ("orders", MAX_ORDERS)])
def test_overflow_rejected_before_rows_are_inspected(snapshot, metadata, field, limit):
    with pytest.raises(SnapshotRejected, match="^invalid_row_bound$"):
        serialize(replace(snapshot, **{field: (None,) * (limit + 1)}), metadata)


@pytest.mark.parametrize("location", ["snapshot", "metadata", "encounter", "order", "key", "reception_qualifiers", "order_qualifiers"])
def test_forged_extra_fields_are_not_silently_dropped(snapshot, metadata, location):
    target = {"snapshot": snapshot, "metadata": metadata, "encounter": snapshot.encounters[0],
              "order": snapshot.orders[0], "key": snapshot.orders[0].key,
              "reception_qualifiers": snapshot.encounters[0].qualifiers,
              "order_qualifiers": snapshot.orders[0].qualifiers}[location]
    object.__setattr__(target, "raw_payload", "PRIVATE_TEST_MARKER")
    with pytest.raises(SnapshotRejected) as error:
        serialize(snapshot, metadata)
    assert str(error.value) == "invalid_snapshot" and "PRIVATE_TEST_MARKER" not in repr(error.value)


FORBIDDEN_FIELDS = [
    "resident_id", "dob", "phone", "address", "diagnosis", "notes", "insurance",
    "credentials", "sql", "raw_rows", "raw_payload", "category", "korean_pill",
    "display_text", "visibility", "pacs", "dicom", "mwl", "orthanc", "accession",
    "modality", "station", "schedule", "units", "edited_at", "cancelled_at", "paid_at",
]


@pytest.mark.parametrize("field", FORBIDDEN_FIELDS)
@pytest.mark.parametrize("location", ["encounters", "orders"])
def test_prohibited_fields_cannot_enter_validated_source(source_read, source_policy, field, location):
    getattr(source_read, location)[0][field] = "PRIVATE_TEST_MARKER"
    with pytest.raises(SnapshotRejected) as error:
        normalize_source_day(source_read, source_policy)
    assert str(error.value) == "invalid_fields" and "PRIVATE_TEST_MARKER" not in repr(error.value)


def test_output_has_no_prohibited_fields_or_event_times(snapshot, metadata):
    payload = serialize(snapshot, metadata)
    def check(value):
        if isinstance(value, dict):
            assert not set(value) & set(FORBIDDEN_FIELDS)
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(payload)
    assert payload["observed_at"] == snapshot.observed_at.isoformat()


@pytest.mark.parametrize("change,reason", [("duplicate_encounter", "duplicate_encounter"),
                                          ("duplicate_order", "duplicate_order"), ("orphan", "orphan_order")])
def test_forged_graph_cannot_be_serialized(snapshot, metadata, change, reason):
    if change == "duplicate_encounter":
        snapshot = replace(snapshot, encounters=snapshot.encounters + snapshot.encounters[:1])
    elif change == "duplicate_order":
        snapshot = replace(snapshot, orders=snapshot.orders + snapshot.orders[:1])
    else:
        row = replace(snapshot.orders[0], key=replace(snapshot.orders[0].key, encounter_id="TEST_MISSING"))
        snapshot = replace(snapshot, orders=(row,))
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        serialize(snapshot, metadata)


def test_redacted_models_and_reasons(snapshot, metadata):
    for value in (snapshot, metadata, *snapshot.encounters, *snapshot.orders,
                  snapshot.orders[0].key, snapshot.orders[0].qualifiers, snapshot.encounters[0].qualifiers):
        assert str(value) == repr(value) == f"<{type(value).__name__}: redacted>"
    with pytest.raises(SnapshotRejected) as error:
        encounter = replace(snapshot.encounters[0], patient_name=" PRIVATE_TEST_MARKER")
        serialize(replace(snapshot, encounters=(encounter,) + snapshot.encounters[1:]), metadata)
    assert str(error.value) == "invalid_text" and "PRIVATE_TEST_MARKER" not in repr(error.value)


@pytest.mark.parametrize("kind", [ReceptionQualifiers, OrderQualifiers])
def test_qualifier_models_reject_invalid_direct_construction(kind):
    with pytest.raises(SnapshotRejected, match="^invalid_qualifier$"):
        kind("Y", "UNKNOWN")


def test_serialization_occurs_after_physical_cleanup(snapshot, metadata, fake_db):
    from KaosEghis.core.eghis_db import run_readonly_query
    run_readonly_query("mock", "SELECT 'synthetic-only'")
    assert fake_db.live == 0 and fake_db.events[-2:] == ["cursor_closed", "connection_closed"]
    before = list(fake_db.events)
    assert serialize(snapshot, metadata) == expected()
    assert fake_db.events == before


def test_serializer_is_pure_and_not_imported_by_runtime():
    import KaosEghis.core.kaosorders_normalized_source as module
    path = Path(module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed = {"dataclasses", "datetime", "decimal", "hashlib", "json", "uuid", "KaosEghis.core.emr_source"}
    for node in ast.walk(tree):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) else [])
        assert set(names) <= allowed
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "print", "exec", "eval", "__import__", "getattr"}
    for candidate in path.parents[1].rglob("*.py"):
        if candidate != path:
            assert "kaosorders_normalized_source" not in candidate.read_text(encoding="utf-8-sig")
    assert "uuid4" not in path.read_text(encoding="utf-8")


def test_fixture_provenance_pins_exact_reference():
    provenance = (FIXTURES / "normalized_source_v1_provenance.md").read_text(encoding="utf-8")
    assert REFERENCE_COMMIT in provenance
    assert "794a11b1faa8e91282e9acd4f509f3c6a6aff1ce" in provenance
    assert "12d3b9937bc9b9b2213830335a29f582083d6ac0" in provenance
