import ast
from copy import deepcopy
from dataclasses import fields, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

import pytest

from KaosEghis.core.emr_source import (
    MAX_ENCOUNTERS, MAX_ORDERS, EghisSourceDayReader, OrderState, ReadStatus,
    ReceptionQualifiers, ReceptionState, SnapshotRejected, SourcePolicy,
)
from KaosEghis.core.emr_source_v2 import (
    PROJECTION_ID, EmrDayReadV2, ReceptionQualifiersV2, normalize_source_day_v2,
)
from KaosEghis.core.kaosorders_normalized_source_v2 import (
    MAX_SEQUENCE_VALUE, SyntheticDeliveryMetadataV2, calculate_content_sha256_v2,
    serialize_normalized_source_v2,
)
from tests.test_emr_source import fake_db
from tests.test_kaosorders_normalized_source import FORBIDDEN_FIELDS


FIXTURES = Path(__file__).parent / "fixtures"
DIGESTS = {
    "full": "a6b7e348c734c7af4c1f7467e0f66ec84dfaa4904fe53d53a1a389ddc9b17c2d",
    "empty": "f03a8a244b8c3d324d6011d0c15f49c49ce2567872665ba1e4e1efb8413daf16",
}


@pytest.fixture
def policy():
    return SourcePolicy("synthetic-v2",
                        tuple((f"TEST_{state.value}", state) for state in ReceptionState),
                        tuple((f"TEST_{state.value}", state) for state in OrderState))


@pytest.fixture
def read():
    # Independent input aliases; never built by converting a v1 snapshot/payload.
    encounters = tuple({
        "encounter_id": f"fixture-{identifier}", "chart_no": f"TEST-000{index}",
        "patient_name": f"Synthetic {name}", "sex": sex, "age": age,
        "state_code": f"TEST_{state}", "qualifiers": {"hold_yn": hold},
    } for index, (identifier, name, sex, age, state, hold) in enumerate([
        ("cancelled", "Alpha", "F", 53, "CANCELLED", "N"),
        ("consultation-completed", "Beta", "M", 47, "CONSULTATION_COMPLETED", "N"),
        ("hold", "Gamma", "F", 38, "ON_HOLD", "N"),
        ("in-progress", "Delta", None, None, "IN_PROGRESS", "Y"),
        ("no-orders", "Epsilon", "O", 29, "REGISTERED", "N"),
        ("payment-completed", "Zeta", "M", 61, "PAYMENT_COMPLETED", "N"),
    ], start=1))
    orders = tuple({
        "encounter_id": f"fixture-{encounter}", "order_date": date(2026, 10, 1),
        "order_number": number, "order_sequence": "1", "order_code": code,
        "order_type": kind, "department_code": department, "state_code": f"TEST_{state}",
        "qualifiers": {"dc_yn": dc, "act_yn": act},
    } for encounter, number, code, kind, department, state, dc, act in [
        ("cancelled", "1", "TEST_CANCELLED_CHILD", "TEST_OTHER", "", "ACTIVE", "N", "N"),
        ("consultation-completed", "1", "TEST_FEE", "TEST_FEE", "", "ACTIVE", "N", "Y"),
        ("hold", "1", "TEST_LAB", "TEST_LAB_TYPE", "TEST_LAB", "ACTIVE", "N", "N"),
        ("hold", "2", "TEST_CANCELLED_ORDER", "TEST_OTHER", "TEST_DEPARTMENT", "CANCELLED", "Y", "N"),
        ("payment-completed", "1", "TEST_UNCLASSIFIED", "TEST_NEW_TYPE", "", "ACTIVE", "N", "N"),
    ])
    orders[2].update(quantity="1.000", days=1, frequency=Decimal("1.00"))
    orders[4].update(quantity="0.1250", frequency="2.500")
    return EmrDayReadV2("fixture-eghis", PROJECTION_ID, date(2026, 10, 1),
                        datetime.fromisoformat("2026-10-01T09:00:00+09:00"), ReadStatus.COMPLETE,
                        encounters, orders, True, True, True, True, True, True, True)


@pytest.fixture
def metadata():
    return SyntheticDeliveryMetadataV2("fixture-clinic", "33333333-3333-4333-8333-333333333333", 1, 1)


def normalize(read, policy):
    return normalize_source_day_v2(read, policy, synthetic_fixture=True)


@pytest.fixture
def snapshot(read, policy):
    return normalize(read, policy)


def serialize(snapshot, metadata):
    return serialize_normalized_source_v2(snapshot, metadata, synthetic_fixture=True)


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def independent_digest(payload):
    return hashlib.sha256(canonical({k: v for k, v in payload.items() if k != "content_sha256"}).encode()).hexdigest()


@pytest.mark.parametrize("kind", ["full", "empty"])
def test_exact_canonical_fixture_bytes_and_independent_digest(read, policy, metadata, kind):
    if kind == "empty":
        read = replace(read, encounters=(), orders=(), clinic_day=date(2026, 10, 2),
                       observed_at=datetime.fromisoformat("2026-10-02T09:00:00+09:00"))
        metadata = replace(metadata, batch_id="44444444-4444-4444-8444-444444444444")
    payload = serialize(normalize(read, policy), metadata)
    golden = (FIXTURES / f"normalized_source_v2_{kind}.json").read_bytes()
    assert payload == json.loads(golden)
    assert (canonical(payload) + "\n").encode("utf-8") == golden
    assert independent_digest(payload) == payload["content_sha256"] == DIGESTS[kind]


def test_all_states_and_rows_are_kept_without_clinical_inference(snapshot, metadata):
    p = serialize(snapshot, metadata)
    assert {e["state"] for e in p["encounters"]} == {s.value for s in ReceptionState}
    assert len(p["encounters"]) == 6 and len(p["orders"]) == 5
    assert p["encounters"][0]["state"] == "CANCELLED" and p["orders"][0]["state"] == "ACTIVE"
    assert {o["state"] for o in p["orders"]} == {"ACTIVE", "CANCELLED"}
    assert {o["order_code"] for o in p["orders"]} >= {"TEST_FEE", "TEST_UNCLASSIFIED"}
    assert not any(o["key"]["encounter_id"] == "fixture-no-orders" for o in p["orders"])
    assert p["encounters"][3]["sex"] is None and p["encounters"][3]["age"] is None


@pytest.mark.parametrize("bad", ["Y", "N", None, 1, "12345678", "UNKNOWN", "a" * 64,
                                 "ASCII_DIGITS", "UNREVIEWED", "PRIVATE_TEST_MARKER"])
def test_excluded_field_is_rejected_never_stripped(read, policy, snapshot, bad):
    read.encounters[0]["qualifiers"]["hold_opd"] = bad
    with pytest.raises(SnapshotRejected, match="^invalid_fields$"):
        normalize(read, policy)
    with pytest.raises(TypeError):
        ReceptionQualifiersV2(hold_yn="N", hold_opd=bad)
    with pytest.raises(AttributeError):
        object.__setattr__(snapshot.encounters[0].qualifiers, "hold_opd", bad)
    assert [f.name for f in fields(ReceptionQualifiersV2)] == ["hold_yn"]


@pytest.mark.parametrize("row_type,field", [("encounters", "hold_yn"), ("orders", "dc_yn"), ("orders", "act_yn")])
@pytest.mark.parametrize("bad", [None, True, 1, "", "n", " Y", "Y ", "UNKNOWN", "0", "ASCII_DIGITS"])
def test_retained_flags_fail_closed(read, policy, row_type, field, bad):
    getattr(read, row_type)[0]["qualifiers"][field] = bad
    with pytest.raises(SnapshotRejected, match="^invalid_qualifier$"):
        normalize(read, policy)


@pytest.mark.parametrize("row_type", ["encounters", "orders"])
@pytest.mark.parametrize("change", ["missing_container", "missing_field", "extra", "none"])
def test_closed_qualifier_shapes(read, policy, row_type, change):
    row = getattr(read, row_type)[0]
    if change == "missing_container":
        del row["qualifiers"]
    elif change == "missing_field":
        row["qualifiers"].pop(next(iter(row["qualifiers"])))
    elif change == "extra":
        row["qualifiers"]["extra"] = "PRIVATE_TEST_MARKER"
    else:
        row["qualifiers"] = None
    with pytest.raises(SnapshotRejected, match="^invalid_fields$"):
        normalize(read, policy)


@pytest.mark.parametrize("dc,act", [("N", "N"), ("N", "Y"), ("Y", "N"), ("Y", "Y")])
@pytest.mark.parametrize("hold", ["N", "Y"])
def test_qualifiers_are_facts_not_implicit_state_rules(read, policy, metadata, dc, act, hold):
    read.encounters[0]["qualifiers"]["hold_yn"] = hold
    read.orders[0]["qualifiers"] = {"dc_yn": dc, "act_yn": act}
    p = serialize(normalize(read, policy), metadata)
    assert p["encounters"][0]["qualifiers"] == {"hold_yn": hold}
    assert p["orders"][0]["qualifiers"] == {"dc_yn": dc, "act_yn": act}
    assert p["encounters"][0]["state"] == "CANCELLED" and p["orders"][0]["state"] == "ACTIVE"


def test_edits_reuse_cancellation_and_disappearance_are_distinct_facts(read, policy, metadata):
    first = normalize(read, policy)
    edited = deepcopy(read)
    edited.orders[0].update(quantity="2.2500")
    second = normalize(edited, policy)
    assert second.orders[0].key == first.orders[0].key and second.orders[0] != first.orders[0]
    assert serialize(second, replace(metadata, revision=2))["orders"][0]["quantity"] == "2.25"
    edited.orders[0].update(state_code="TEST_CANCELLED", qualifiers={"dc_yn": "Y", "act_yn": "N"})
    cancelled = normalize(edited, policy)
    assert cancelled.orders[0].state is OrderState.CANCELLED
    removed = normalize(replace(edited, orders=edited.orders[1:]), policy)
    assert cancelled.orders[0].key not in {o.key for o in removed.orders}
    edited.orders[0].update(order_code="TEST_REUSED", state_code="TEST_ACTIVE",
                            qualifiers={"dc_yn": "N", "act_yn": "N"})
    reused = normalize(edited, policy)
    assert reused.orders[0].key == first.orders[0].key and reused.orders[0] != first.orders[0]
    assert len(serialize(reused, replace(metadata, revision=4))["orders"]) == 5
    assert "withdrawals" not in serialize(removed, replace(metadata, revision=3))


@pytest.mark.parametrize("change", ["hold", "state", "dc", "act"])
def test_retained_only_edits_are_detectable(read, policy, metadata, change):
    first = normalize(read, policy)
    if change == "hold":
        read.encounters[0]["qualifiers"]["hold_yn"] = "Y"
    elif change == "state":
        read.encounters[0]["state_code"] = "TEST_ON_HOLD"
    else:
        read.orders[0]["qualifiers"][f"{change}_yn"] = "Y"
    second = normalize(read, policy)
    assert second != first
    assert serialize(second, metadata)["content_sha256"] != serialize(first, metadata)["content_sha256"]
    assert second.encounters != first.encounters if change in ("hold", "state") else second.orders != first.orders


def test_four_part_keys_and_canonical_sorting(snapshot, metadata):
    original = snapshot.orders[2]
    extra = tuple(replace(original, key=replace(original.key, **change)) for change in [
        {"encounter_id": "fixture-no-orders"}, {"order_date": date(2026, 9, 30)},
        {"order_number": "10"}, {"order_sequence": "2"},
    ])
    full = replace(snapshot, orders=snapshot.orders + extra)
    p = serialize(full, metadata)
    keys = [tuple(o["key"][n] for n in ("encounter_id", "order_date", "order_number", "order_sequence")) for o in p["orders"]]
    assert len(set(keys)) == 9 and keys == sorted(keys)
    assert serialize(replace(full, encounters=tuple(reversed(full.encounters)), orders=tuple(reversed(full.orders))), metadata) == p


def test_scope_isolation_and_observation_time_is_not_a_fact_edit(snapshot, metadata):
    later = replace(snapshot, observed_at=snapshot.observed_at + timedelta(seconds=30))
    assert later.encounters == snapshot.encounters and later.orders == snapshot.orders
    assert serialize(later, metadata)["content_sha256"] != serialize(snapshot, metadata)["content_sha256"]
    other_day = replace(snapshot, clinic_day=date(2026, 10, 2), encounters=(), orders=())
    assert other_day.scope != snapshot.scope
    assert serialize(other_day, metadata)["scope"]["clinic_day"] == "2026-10-02"
    assert len(serialize(snapshot, metadata)["orders"]) == 5


@pytest.mark.parametrize("field", ["quantity", "days", "frequency"])
@pytest.mark.parametrize("raw,text", [("2.2500", "2.25"), ("1000.00", "1000"), ("-0.000", "0"),
                                     ("1E-12", "0.000000000001"), ("1E+9", "1000000000"), ("-12.3400", "-12.34")])
def test_decimal_canonicalization_ignores_context(snapshot, metadata, field, raw, text):
    order = replace(snapshot.orders[0], **{field: Decimal(raw)})
    with localcontext() as context:
        context.prec = 2
        p = serialize(replace(snapshot, orders=(order,) + snapshot.orders[1:]), metadata)
    assert p["orders"][0][field] == text and p["content_sha256"] == independent_digest(p)


@pytest.mark.parametrize("bad", [True, 1.5, float("nan"), float("inf"), "1", 1,
                                 Decimal("NaN"), Decimal("Infinity"), Decimal("1E10"), Decimal("1E-13")])
def test_bad_direct_decimal_constructions_reject(snapshot, metadata, bad):
    order = replace(snapshot.orders[0], quantity=bad)
    with pytest.raises(SnapshotRejected, match="^invalid_number$"):
        serialize(replace(snapshot, orders=(order,) + snapshot.orders[1:]), metadata)


@pytest.mark.parametrize("field", FORBIDDEN_FIELDS + ["hold_opd", "hold_opd_shape", "contract_version"])
@pytest.mark.parametrize("location", ["encounters", "orders"])
def test_forbidden_input_fields_reject_without_echo(read, policy, field, location):
    getattr(read, location)[0][field] = "PRIVATE_TEST_MARKER"
    with pytest.raises(SnapshotRejected) as error:
        normalize(read, policy)
    assert str(error.value) == "invalid_fields" and "PRIVATE_TEST_MARKER" not in repr(error.value)


def test_output_redaction_unicode_and_tamper_detection(read, policy, metadata):
    read.encounters[0]["patient_name"] = "\ud569\uc131 \ud658\uc790"
    snapshot = normalize(read, policy)
    before = deepcopy(snapshot)
    p = serialize(snapshot, metadata)
    def check(value):
        if isinstance(value, dict):
            assert not set(value) & set(FORBIDDEN_FIELDS + ["hold_opd"])
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(p)
    assert p["content_sha256"] == independent_digest(p)
    tampered = deepcopy(p)
    tampered["orders"][0]["quantity"] = "7"
    assert calculate_content_sha256_v2(tampered) != tampered["content_sha256"]
    assert snapshot == before and serialize(snapshot, metadata) == p
    for item in (read, snapshot, metadata, *snapshot.encounters, *snapshot.orders,
                 snapshot.encounters[0].qualifiers, snapshot.orders[0].key, snapshot.orders[0].qualifiers):
        assert repr(item) == str(item) == f"<{type(item).__name__}: redacted>"


@pytest.mark.parametrize("bad", [None, [], {"bad": float("nan")}, {"bad": float("inf")}, {"bad": object()}, {"bad": "\ud800"}])
def test_digest_errors_are_redacted(bad):
    with pytest.raises(SnapshotRejected, match="^invalid_payload$"):
        calculate_content_sha256_v2(bad)


@pytest.mark.parametrize("location", ["root", "scope", "encounter", "encounter_flags",
                                      "order", "order_key", "order_flags", "nested_list", "nested_tuple"])
@pytest.mark.parametrize("bad", ["Y", "N", None, 1, True, "12345678", "PRIVATE_TEST_MARKER",
                                 "a" * 64, "ASCII_DIGITS", "UNREVIEWED"])
def test_digest_helper_rejects_excluded_field_before_encoding(
    snapshot, metadata, monkeypatch, capsys, caplog, location, bad,
):
    from KaosEghis.core import kaosorders_normalized_source_v2 as module

    payload = serialize(snapshot, metadata)
    targets = {
        "root": payload, "scope": payload["scope"], "encounter": payload["encounters"][0],
        "encounter_flags": payload["encounters"][0]["qualifiers"], "order": payload["orders"][0],
        "order_key": payload["orders"][0]["key"], "order_flags": payload["orders"][0]["qualifiers"],
    }
    if location in ("nested_list", "nested_tuple"):
        nested = {"hold_opd": bad}
        payload["unexpected"] = [nested] if location == "nested_list" else (nested,)
    else:
        targets[location]["hold_opd"] = bad

    def prohibited(*_args, **_kwargs):
        pytest.fail("Excluded input reached JSON encoding or hashing")

    monkeypatch.setattr(module.json, "dumps", prohibited)
    monkeypatch.setattr(module.hashlib, "sha256", prohibited)
    with pytest.raises(SnapshotRejected) as error:
        calculate_content_sha256_v2(payload)
    assert str(error.value) == "invalid_payload"
    assert repr(error.value) == "SnapshotRejected('invalid_payload')"
    assert not caplog.records
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("shape", ["cyclic_dict", "cyclic_list", "non_text_key"])
def test_digest_guard_failures_do_not_leak_input(shape):
    payload = {}
    if shape == "cyclic_dict":
        payload["loop"] = payload
    elif shape == "cyclic_list":
        rows = []
        rows.append(rows)
        payload["loop"] = rows
    else:
        payload["nested"] = {1: "PRIVATE_TEST_MARKER"}
    with pytest.raises(SnapshotRejected, match="^invalid_payload$"):
        calculate_content_sha256_v2(payload)


@pytest.mark.parametrize("flag", [False, None, 1, "true"])
def test_explicit_synthetic_gate(read, policy, snapshot, metadata, flag):
    with pytest.raises(SnapshotRejected, match="^synthetic_fixture_required$"):
        normalize_source_day_v2(read, policy, synthetic_fixture=flag)
    with pytest.raises(SnapshotRejected, match="^synthetic_fixture_required$"):
        serialize_normalized_source_v2(snapshot, metadata, synthetic_fixture=flag)


@pytest.mark.parametrize("status", [s for s in ReadStatus if s is not ReadStatus.COMPLETE])
def test_failed_empty_is_never_authoritative(read, policy, status):
    with pytest.raises(SnapshotRejected, match="^incomplete_source$"):
        normalize(replace(read, encounters=(), orders=(), status=status), policy)


@pytest.mark.parametrize("flag", ["keys_verified", "states_verified", "whole_day", "untruncated", "consistent_snapshot", "connection_closed"])
@pytest.mark.parametrize("bad", [False, None, 1])
def test_empty_requires_every_completeness_assertion(read, policy, flag, bad):
    with pytest.raises(SnapshotRejected, match="^incomplete_source$"):
        normalize(replace(read, encounters=(), orders=(), **{flag: bad}), policy)


def test_unverified_structured_values_reject(read, policy):
    with pytest.raises(SnapshotRejected, match="^unverified_structured_fields$"):
        normalize(replace(read, structured_fields_verified=False), policy)


@pytest.mark.parametrize("field,limit", [("encounters", MAX_ENCOUNTERS), ("orders", MAX_ORDERS)])
def test_overflow_and_non_tuple_rows_fail_before_processing(read, policy, snapshot, metadata, field, limit):
    for value in ((None,) * (limit + 1), []):
        with pytest.raises(SnapshotRejected, match="^invalid_row_bound$"):
            normalize(replace(read, **{field: value}), policy)
        with pytest.raises(SnapshotRejected, match="^invalid_row_bound$"):
            serialize(replace(snapshot, **{field: value}), metadata)


@pytest.mark.parametrize("change,reason", [("duplicate_encounter", "duplicate_encounter"),
                                          ("duplicate_order", "duplicate_order"), ("orphan", "orphan_order")])
def test_graph_validation(snapshot, metadata, change, reason):
    if change == "duplicate_encounter":
        snapshot = replace(snapshot, encounters=snapshot.encounters + snapshot.encounters[:1])
    elif change == "duplicate_order":
        snapshot = replace(snapshot, orders=snapshot.orders + snapshot.orders[:1])
    else:
        snapshot = replace(snapshot, orders=(replace(snapshot.orders[0], key=replace(snapshot.orders[0].key, encounter_id="TEST_ABSENT")),))
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        serialize(snapshot, metadata)


@pytest.mark.parametrize("field,bad,reason", [
    ("batch_id", "PRIVATE_TEST_MARKER", "invalid_batch_id"), ("batch_id", None, "invalid_batch_id"),
    ("clinic_id", " PRIVATE_TEST_MARKER", "invalid_text"), ("clinic_id", "x" * 129, "invalid_text"),
    ("source_epoch", 0, "invalid_sequence"), ("source_epoch", "1", "invalid_sequence"),
    ("revision", True, "invalid_sequence"), ("revision", MAX_SEQUENCE_VALUE + 1, "invalid_sequence"),
])
def test_metadata_is_strict_not_generated(snapshot, metadata, field, bad, reason):
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        serialize(snapshot, replace(metadata, **{field: bad}))


@pytest.mark.parametrize("field,bad", [("projection_id", "fixture-all-orders-v1"), ("projection_id", None),
                                      ("mapping_revision", "synthetic-v1"), ("mapping_revision", "production")])
def test_only_agreed_synthetic_identity_is_accepted(snapshot, metadata, field, bad):
    with pytest.raises(SnapshotRejected, match="^unsupported_projection$"):
        serialize(replace(snapshot, **{field: bad}), metadata)


@pytest.mark.parametrize("field,bad,reason", [("sex", "", "unverified_sex"), ("sex", " ", "invalid_demographics"),
    ("sex", "UNKNOWN", "invalid_demographics"), ("age", True, "invalid_demographics"),
    ("age", 131, "invalid_demographics"), ("state_code", "10", "unknown_reception_state")])
def test_no_guessed_source_mapping(read, policy, field, bad, reason):
    read.encounters[0][field] = bad
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        normalize(read, policy)


def test_versions_cannot_reinterpret_each_other(snapshot, metadata, read, policy):
    from KaosEghis.core.emr_source import EmrDayRead, SourceSnapshot, normalize_source_day
    from KaosEghis.core.kaosorders_normalized_source import SyntheticDeliveryMetadata, serialize_normalized_source
    v1_metadata = SyntheticDeliveryMetadata(metadata.clinic_id, metadata.batch_id, 1, 1)
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize_normalized_source(snapshot, v1_metadata, synthetic_fixture=True)
    v1 = SourceSnapshot(snapshot.source_id, snapshot.projection_id, snapshot.clinic_day,
                        snapshot.observed_at, snapshot.mapping_revision, (), ())
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize(v1, metadata)
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize(snapshot, v1_metadata)
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize(EmrDayRead(read.source_id, read.projection_id, read.clinic_day, read.observed_at, ReadStatus.COMPLETE), policy)
    with pytest.raises(SnapshotRejected, match="^invalid_fields$"):
        normalize_source_day(read, policy)
    encounter = replace(snapshot.encounters[0], qualifiers=ReceptionQualifiers("N", "N"))
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize(replace(snapshot, encounters=(encounter,) + snapshot.encounters[1:]), metadata)


def test_direct_tampering_is_revalidated(snapshot, metadata):
    object.__setattr__(snapshot.encounters[0].qualifiers, "hold_yn", "PRIVATE_TEST_MARKER")
    with pytest.raises(SnapshotRejected, match="^invalid_qualifier$"):
        serialize(snapshot, metadata)
    object.__setattr__(snapshot.encounters[0].qualifiers, "hold_yn", "N")
    object.__setattr__(snapshot.orders[0], "raw_payload", "PRIVATE_TEST_MARKER")
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize(snapshot, metadata)


@pytest.mark.parametrize("kind,blob", [
    ("full", "794a11b1faa8e91282e9acd4f509f3c6a6aff1ce"),
    ("empty", "12d3b9937bc9b9b2213830335a29f582083d6ac0"),
])
def test_v1_committed_fixture_bytes_stay_unchanged(kind, blob):
    # V1's existing Git text conversion is not changed by the v2 LF-only rule.
    body = (FIXTURES / f"normalized_source_v1_{kind}.json").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == blob


@pytest.mark.parametrize("name,blob", [
    ("emr_source.py", "bc94159d6d5b48b4caaae3d794c55f3a6e8a1c35"),
    ("kaosorders_normalized_source.py", "fc75780553faac8e5e3ccef81edb626f9a03c26d"),
    ("kaosorders_outbox_shadow.py", "9e1212a6cef434a4df75aece0f4367dbaaba35aa"),
])
def test_v1_model_serializer_outbox_match_starting_commit_bytes(name, blob):
    path = Path(__file__).parents[1] / "KaosEghis" / "core" / name
    body = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == blob


def test_provenance_pins_sender_and_receiver_and_hashes():
    text = (FIXTURES / "normalized_source_v2_provenance.md").read_text(encoding="utf-8")
    assert "6837845fc4c691075bab41c6e07ef69e8562580b" in text
    assert "51d7601327ab4db58155960b8e0be75ea029e43f" in text
    for kind, digest in DIGESTS.items():
        assert digest in text
        assert hashlib.sha256((FIXTURES / f"normalized_source_v2_{kind}.json").read_bytes()).hexdigest() in text


@pytest.mark.parametrize("change,reason", [
    ({"clinic_day": "2026-10-01"}, "invalid_day"),
    ({"observed_at": datetime(2026, 10, 1)}, "unverified_time"),
    ({"source_id": " PRIVATE_TEST_MARKER"}, "invalid_text"),
])
def test_scope_and_time_errors_are_fixed(snapshot, metadata, change, reason):
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        serialize(replace(snapshot, **change), metadata)


@pytest.mark.parametrize("field,bad,reason", [
    ("state", "ACTIVE", "unknown_order_state"),
    ("department_code", None, "invalid_text"),
    ("order_code", " PRIVATE_TEST_MARKER", "invalid_text"),
])
def test_order_facts_are_not_coerced(snapshot, metadata, field, bad, reason):
    order = replace(snapshot.orders[0], **{field: bad})
    with pytest.raises(SnapshotRejected, match=f"^{reason}$"):
        serialize(replace(snapshot, orders=(order,)), metadata)


def test_missing_model_slot_is_rejected_without_value_disclosure(snapshot, metadata):
    object.__delattr__(snapshot.encounters[0], "patient_name")
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize(snapshot, metadata)


def test_reader_stays_unavailable_and_serialization_is_after_mock_cleanup(snapshot, metadata, fake_db):
    from KaosEghis.core.eghis_db import run_readonly_query
    assert EghisSourceDayReader().read_day(snapshot.clinic_day, snapshot.observed_at).status is ReadStatus.UNAVAILABLE
    run_readonly_query("mock", "SELECT 'synthetic-only'")
    assert fake_db.live == 0 and fake_db.events[-2:] == ["cursor_closed", "connection_closed"]
    before = list(fake_db.events)
    serialize(snapshot, metadata)
    assert fake_db.events == before


def test_pure_modules_have_no_runtime_importers_or_io():
    from KaosEghis.core import emr_source_v2, kaosorders_normalized_source_v2
    allowed = {"dataclasses", "datetime", "decimal", "typing", "hashlib", "json", "uuid",
               "KaosEghis.core.emr_source", "KaosEghis.core.emr_source_v2"}
    modules = (emr_source_v2, kaosorders_normalized_source_v2)
    paths = {Path(m.__file__) for m in modules}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            assert set(names) <= allowed
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "print", "exec", "eval", "__import__"}
        assert "uuid4" not in path.read_text(encoding="utf-8")
    for path in Path(emr_source_v2.__file__).parents[1].rglob("*.py"):
        if path not in paths:
            text = path.read_text(encoding="utf-8-sig")
            assert "emr_source_v2" not in text and "kaosorders_normalized_source_v2" not in text
