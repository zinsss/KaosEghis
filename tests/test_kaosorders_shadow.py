import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from KaosEghis.core.kaosorders_source import (
    Category, CATEGORY_LABELS, EghisKaosOrdersDayReader, MappingPolicy, OrderState,
    ReadStatus, ReceptionState, SnapshotRejected, SourceDayRead, normalize_day,
)
from KaosEghis.core.kaosorders_shadow import ShadowLedger, proposed_v2_payload, read_shadow_day


@pytest.fixture
def policy():
    return MappingPolicy(
        reception_states=tuple((f"TEST_{code}", state) for code, state in (
            ("REGISTERED", ReceptionState.REGISTERED), ("CONSULT", ReceptionState.IN_PROGRESS),
            ("HOLD", ReceptionState.ON_HOLD), ("CLOSED", ReceptionState.CLOSED),
            ("CANCELLED", ReceptionState.CANCELLED),
        )),
        order_states=(("TEST_ACTIVE", OrderState.ACTIVE), ("TEST_WITHDRAWN", OrderState.WITHDRAWN)),
        categories=tuple((f"TEST_{category}", category) for category in Category) + (("TEST_UNRELATED", None),),
        details=tuple((category, "TEST_APPROVED", fields) for category, fields in (
            (Category.XRAY, (("exam", "\uac80\uc0ac \uc608\uc2dc"), ("view", "\ucd2c\uc601 \uc608\uc2dc"))),
            (Category.BLOOD, (("study", "\ucc44\ud608 \uc608\uc2dc"),)),
            (Category.URINE, (("study", "\uc18c\ubcc0 \uc608\uc2dc"),)),
            (Category.ECG, (("exam", "\uc2ec\uc804\ub3c4 \uc608\uc2dc"),)),
            (Category.BMD, (("exam", "\uace8\ubc00\ub3c4 \uc608\uc2dc"), ("site", "\ubd80\uc704 \uc608\uc2dc"))),
            (Category.INJECTION, (("medication", "\uc57d\ubb3c \uc608\uc2dc"), ("dose", "\uc6a9\ub7c9 \uc608\uc2dc"), ("route", "\uacbd\ub85c \uc608\uc2dc"))),
        )),
    )


@pytest.fixture
def source():
    data = json.loads((Path(__file__).parent / "fixtures/kaosorders_synthetic_day.json").read_text(encoding="utf-8"))
    return SourceDayRead(date.fromisoformat(data["clinic_day"]), datetime.fromisoformat(data["observed_at"]),
                         ReadStatus.COMPLETE, tuple(data["encounters"]), tuple(data["orders"]),
                         True, True, True, True, True)


def advance(source, *, encounter=None, orders=None, **kwargs):
    encounters = deepcopy(source.encounters)
    if encounter:
        encounters[0].update(encounter)
    return replace(source, observed_at=source.observed_at + timedelta(seconds=30),
                   encounters=encounters, orders=deepcopy(source.orders) if orders is None else tuple(orders), **kwargs)


def baseline(source, policy):
    ledger = ShadowLedger()
    change = ledger.prepare(source, policy)
    ledger.acknowledge(change.batch_id)
    return ledger


def test_six_categories_allowlisted_specs_and_multiple_same_category(source, policy):
    snapshot = normalize_day(source, policy)
    patient = snapshot.encounters[0]
    assert patient.sex_age == "\uc5ec/53" and patient.board_eligible
    assert set(order.category for order in patient.orders) == set(Category)
    assert len(patient.orders) == 7
    assert len([order for order in patient.orders if order.category == Category.XRAY]) == 2
    assert next(order for order in patient.orders if order.order_id == "fixture-xray-2").display_spec == ()
    assert set(CATEGORY_LABELS.values()) == {"\uc5d1\uc2a4\ub808\uc774", "\ucc44\ud608", "\uc18c\ubcc0\uac80\uc0ac", "\uc2ec\uc804\ub3c4", "\uace8\ubc00\ub3c4", "\uc8fc\uc0ac"}
    assert all(order.order_id != "fixture-unrelated-1" for order in patient.orders)


@pytest.mark.parametrize("state", ["TEST_REGISTERED", "TEST_CONSULT", "TEST_CLOSED", "TEST_CANCELLED"])
def test_only_confirmed_hold_is_visible(source, policy, state):
    assert not normalize_day(advance(source, encounter={"state_code": state}), policy).encounters[0].board_eligible


@pytest.mark.parametrize("category", list(Category))
def test_each_relevant_category_can_show_a_hold_patient(source, policy, category):
    rows = [row for row in source.orders if row["category_code"] == f"TEST_{category}"]
    assert normalize_day(advance(source, orders=rows), policy).encounters[0].board_eligible


def test_all_withdrawn_orders_hide_hold_patient(source, policy):
    rows = [dict(row, state_code="TEST_WITHDRAWN") for row in source.orders]
    assert not normalize_day(advance(source, orders=rows), policy).encounters[0].board_eligible


@pytest.mark.parametrize("status", [ReadStatus.PARTIAL, ReadStatus.FAILED, ReadStatus.TIMED_OUT, ReadStatus.UNAVAILABLE])
def test_failed_day_never_replaces_last_snapshot(source, policy, status):
    ledger = baseline(source, policy)
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        ledger.prepare(replace(source, status=status, encounters=(), orders=()), policy)
    assert ledger.pending is None
    change = ledger.prepare(advance(source), policy)
    assert not change.restart_reconciliation
    assert change.encounter_upserts == change.encounter_withdrawals == change.order_withdrawals == ()


@pytest.mark.parametrize("evidence", ["stable_keys_verified", "states_verified", "whole_day", "untruncated", "consistent_snapshot"])
def test_complete_flag_alone_cannot_authorize_removal(source, policy, evidence):
    ledger = baseline(source, policy)
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        ledger.prepare(replace(source, encounters=(), orders=(), **{evidence: False}), policy)
    assert ledger.pending is None


@pytest.mark.parametrize("flag", ["false", "true", 1, None])
def test_completeness_evidence_must_be_boolean_true(source, policy, flag):
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        normalize_day(replace(source, whole_day=flag), policy)


def test_empty_mapping_cannot_authorize_empty_day_withdrawals(source):
    with pytest.raises(SnapshotRejected, match="incomplete_mapping"):
        normalize_day(replace(source, encounters=(), orders=()), MappingPolicy())


@pytest.mark.parametrize("field,value", [("state_code", "UNKNOWN"), ("encounter_id", ""), ("chart_no", ""), ("age", True), ("age", -1)])
def test_bad_encounter_rejects_entire_day(source, policy, field, value):
    with pytest.raises(SnapshotRejected):
        normalize_day(advance(source, encounter={field: value}), policy)


@pytest.mark.parametrize("field,value", [("state_code", "DONE"), ("category_code", "UNREVIEWED"), ("order_id", ""), ("encounter_id", "missing")])
def test_bad_order_never_becomes_silent_omission(source, policy, field, value):
    rows = deepcopy(source.orders)
    rows[0][field] = value
    with pytest.raises(SnapshotRejected):
        normalize_day(advance(source, orders=rows), policy)


def test_duplicate_id_rejected_not_deduplicated(source, policy):
    with pytest.raises(SnapshotRejected, match="duplicate_encounter"):
        normalize_day(replace(source, encounters=source.encounters * 2), policy)
    with pytest.raises(SnapshotRejected, match="duplicate_order"):
        normalize_day(replace(source, orders=source.orders + (source.orders[0],)), policy)


def test_chart_number_does_not_merge_two_encounters(source, policy):
    second = dict(source.encounters[0], encounter_id="fixture-encounter-2")
    result = normalize_day(replace(source, encounters=source.encounters + (second,)), policy)
    assert len(result.encounters) == 2
    ledger = baseline(source, policy)
    with pytest.raises(SnapshotRejected, match="encounter_identity_changed"):
        ledger.prepare(advance(source, encounter={"chart_no": "TEST-OTHER"}), policy)


def test_same_id_edit_is_upsert_not_duplicate(source, policy):
    ledger = baseline(source, policy)
    rows = deepcopy(source.orders)
    rows[0]["detail_code"] = "TEST_UNMAPPED"
    change = ledger.prepare(advance(source, orders=rows), policy)
    assert len(change.encounter_upserts) == 1
    assert len(change.encounter_upserts[0].orders) == 7
    assert not change.order_withdrawals and not change.encounter_withdrawals


def test_individual_source_withdrawal(source, policy):
    ledger = baseline(source, policy)
    rows = deepcopy(source.orders)
    rows[0]["state_code"] = "TEST_WITHDRAWN"
    change = ledger.prepare(advance(source, orders=rows), policy)
    assert len(change.order_withdrawals) == 1
    assert change.order_withdrawals[0].order_id == rows[0]["order_id"]
    assert change.order_withdrawals[0].reason == "source_withdrawn"
    assert change.snapshot.encounters[0].board_eligible


def test_complete_all_order_deletion_hides_without_cancelling_encounter(source, policy):
    ledger = baseline(source, policy)
    change = ledger.prepare(advance(source, orders=[]), policy)
    assert len(change.order_withdrawals) == 7
    assert not change.encounter_withdrawals
    assert not change.snapshot.encounters[0].board_eligible
    assert change.snapshot.encounters[0].state == ReceptionState.ON_HOLD


def test_cancelled_encounter_withdraws_whole_encounter(source, policy):
    change = baseline(source, policy).prepare(advance(source, encounter={"state_code": "TEST_CANCELLED"}), policy)
    assert len(change.encounter_withdrawals) == 1
    assert change.encounter_withdrawals[0].reason == "source_cancelled"
    assert not change.encounter_upserts
    assert proposed_v2_payload(change, synthetic_fixture=True)["encounters"] == []


def test_complete_empty_day_can_withdraw_missing_encounter(source, policy):
    change = baseline(source, policy).prepare(replace(advance(source), encounters=(), orders=()), policy)
    assert len(change.encounter_withdrawals) == 1
    assert change.encounter_withdrawals[0].reason == "absent_from_complete_day"


def test_closed_does_not_complete_orders_and_can_reopen(source, policy):
    ledger = baseline(source, policy)
    closed = advance(source, encounter={"state_code": "TEST_CLOSED"})
    change = ledger.prepare(closed, policy)
    assert not change.order_withdrawals and not change.encounter_withdrawals
    assert not change.snapshot.encounters[0].board_eligible
    assert all(order.state == OrderState.ACTIVE for order in change.snapshot.encounters[0].orders)
    ledger.acknowledge(change.batch_id)
    reopened = ledger.prepare(advance(closed, encounter={"state_code": "TEST_HOLD"}), policy)
    assert reopened.snapshot.encounters[0].board_eligible
    assert not reopened.order_withdrawals and not reopened.encounter_withdrawals


def test_unknown_state_preserves_last_snapshot_and_retry(source, policy):
    ledger = baseline(source, policy)
    with pytest.raises(SnapshotRejected):
        ledger.prepare(advance(source, encounter={"state_code": "UNKNOWN"}), policy)
    good = ledger.prepare(advance(source), policy)
    assert good.encounter_upserts == good.order_withdrawals == good.encounter_withdrawals == ()


def test_retry_idempotency_ack_and_restart(source, policy):
    ledger = ShadowLedger()
    change = ledger.prepare(source, policy)
    assert change.restart_reconciliation
    assert ledger.prepare(source, policy) is change
    first = proposed_v2_payload(change, synthetic_fixture=True)
    assert first == proposed_v2_payload(ledger.pending, synthetic_fixture=True)
    with pytest.raises(SnapshotRejected, match="proposal_pending"):
        ledger.prepare(advance(source), policy)
    with pytest.raises(SnapshotRejected, match="acknowledgement_mismatch"):
        ledger.acknowledge("not-the-batch")
    assert ledger.pending is change
    ledger.acknowledge(change.batch_id)
    assert not ledger.prepare(advance(source), policy).restart_reconciliation
    assert ShadowLedger().prepare(source, policy).restart_reconciliation


def test_concurrent_retries_share_one_pending_proposal(source, policy):
    ledger = ShadowLedger()
    with ThreadPoolExecutor(4) as workers:
        results = list(workers.map(lambda _: ledger.prepare(source, policy), range(12)))
    assert all(result is results[0] for result in results)


def test_day_rollover_does_not_withdraw_previous_day(source, policy):
    ledger = baseline(source, policy)
    tomorrow = replace(source, clinic_day=source.clinic_day + timedelta(days=1),
                       observed_at=source.observed_at + timedelta(days=1), encounters=(), orders=())
    change = ledger.prepare(tomorrow, policy)
    assert change.restart_reconciliation and not change.encounter_withdrawals
    ledger.acknowledge(change.batch_id)
    old_follow_up = ledger.prepare(advance(source, orders=[]), policy)
    assert not old_follow_up.restart_reconciliation and len(old_follow_up.order_withdrawals) == 7


def test_stale_and_conflicting_observations_are_non_destructive(source, policy):
    ledger = baseline(source, policy)
    with pytest.raises(SnapshotRejected, match="stale_observation"):
        ledger.prepare(replace(source, observed_at=source.observed_at - timedelta(seconds=1)), policy)
    with pytest.raises(SnapshotRejected, match="conflicting_observation"):
        ledger.prepare(replace(source, orders=()), policy)
    assert ledger.pending is None


@pytest.mark.parametrize("field", ["resident_id", "dob", "phone", "address", "diagnosis", "notes", "insurance", "raw_text", "sql", "bearer_token", "connection_string"])
@pytest.mark.parametrize("target", ["encounter", "order"])
def test_forbidden_fields_rejected_without_value_disclosure(source, policy, field, target):
    rows = deepcopy(source.encounters if target == "encounter" else source.orders)
    rows[0][field] = "NEVER-DISCLOSE"
    bad = replace(source, **{("encounters" if target == "encounter" else "orders"): rows})
    with pytest.raises(SnapshotRejected, match="invalid_fields") as error:
        normalize_day(bad, policy)
    assert "NEVER-DISCLOSE" not in str(error.value)


def test_display_policy_cannot_include_arbitrary_fields(source, policy):
    bad = replace(policy, details=((Category.INJECTION, "TEST_APPROVED", (("diagnosis", "PRIVATE"),)),))
    with pytest.raises(SnapshotRejected, match="invalid_display_spec"):
        normalize_day(source, bad)


def test_timestamp_verification_required(source, policy):
    timed = advance(source, encounter={"received_at": source.observed_at})
    with pytest.raises(SnapshotRejected, match="unverified_time"):
        normalize_day(timed, policy)
    snapshot = normalize_day(replace(timed, timestamps_verified=True), policy)
    assert snapshot.encounters[0].received_at == source.observed_at
    with pytest.raises(SnapshotRejected, match="unverified_time"):
        normalize_day(replace(source, observed_at=datetime(2026, 10, 1)), policy)


def test_reprs_and_summary_are_private_and_nothing_is_logged(source, policy, capsys, caplog):
    change = ShadowLedger().prepare(source, policy)
    output = repr((source, policy, change, change.snapshot, change.encounter_upserts)) + json.dumps(change.summary())
    for secret in ("TEST-0001", "fixture-encounter-1", "fixture-xray-1", "\ud14c\uc2a4\ud2b8"):
        assert secret not in output
    assert capsys.readouterr() == ("", "") and not caplog.records
    with pytest.raises(SnapshotRejected, match="synthetic_export_only"):
        proposed_v2_payload(change)


def test_documented_synthetic_v2_example_matches_serializer(source, policy):
    change = ShadowLedger().prepare(source, policy)
    result = proposed_v2_payload(change, synthetic_fixture=True)
    example = json.loads((Path(__file__).resolve().parents[1] / "docs/kaosorders-v2-proposal.json").read_text(encoding="utf-8"))
    result["batch_id"] = example["batch_id"]
    assert result == example


def test_disabled_and_unapproved_reader_never_connects(source, monkeypatch):
    from KaosEghis.core import eghis_db
    from KaosEghis.db.repositories import DEFAULT_SETTINGS
    monkeypatch.setattr(eghis_db, "run_readonly_query", lambda *a, **k: pytest.fail("unapproved SQL"))
    assert DEFAULT_SETTINGS["kaosorders_shadow_enabled"] == "false"
    assert DEFAULT_SETTINGS["kaosorders_publish_enabled"] == "false"
    assert read_shadow_day({}, source.clinic_day, source.observed_at) is None
    blocked = read_shadow_day({"kaosorders_shadow_enabled": "true"}, source.clinic_day, source.observed_at)
    assert blocked.status == ReadStatus.UNAVAILABLE and not blocked.encounters
    with pytest.raises(SnapshotRejected, match="publishing_not_implemented"):
        read_shadow_day({"kaosorders_shadow_enabled": "true", "kaosorders_publish_enabled": "true"}, source.clinic_day, source.observed_at)
    assert EghisKaosOrdersDayReader().read_day(source.clinic_day, source.observed_at).status == ReadStatus.UNAVAILABLE


def test_no_database_network_persistence_or_runtime_imports_in_shadow_modules():
    import KaosEghis.core.kaosorders_source as source
    import KaosEghis.core.kaosorders_shadow as shadow
    forbidden = {"psycopg2", "sqlite3", "socket", "requests", "urllib", "httpx", "logging", "pathlib"}
    for module in (source, shadow):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any(name.split(".")[0] in forbidden for name in names)
    package = Path(source.__file__).parents[1]
    for path in package.rglob("*.py"):
        if path.name.startswith("kaosorders_"):
            continue
        assert "core.kaosorders_" not in path.read_text(encoding="utf-8-sig")


def test_fixture_reader_queues_behind_pacs_and_closes_before_mapping(source, policy, monkeypatch):
    from KaosEghis.core import eghis_db, emr_read_queue
    entered, release = threading.Event(), threading.Event()
    live, count, events = [0], [0], []

    class Cursor:
        description = [("fixture_value",)]
        def execute(self, query):
            if count[0] == 1 and query.startswith("SELECT"):
                entered.set()
                assert release.wait(3)
        def fetchall(self):
            return [(1,)]
        def close(self):
            events.append("cursor_closed")

    class Connection:
        closed = False
        def set_session(self, **options):
            assert options == {"readonly": True, "autocommit": True}
        def cursor(self):
            return Cursor()
        def close(self):
            live[0] -= 1
            self.closed = True
            events.append("connection_closed")

    def connect(*args, **kwargs):
        assert live[0] == 0
        live[0] += 1
        count[0] += 1
        return Connection()

    def fixture_reader():
        eghis_db.run_readonly_query("mock", "SELECT 'synthetic-fixture-only'")
        assert live[0] == 0 and events[-1] == "connection_closed"
        return normalize_day(source, policy)

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    with ThreadPoolExecutor(2) as callers:
        pacs = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 'mock-pacs'")
        try:
            assert entered.wait(2)
            orders = callers.submit(fixture_reader)
            deadline = time.monotonic() + 2
            while emr_read_queue._worker._work_queue.qsize() < 1:
                assert time.monotonic() < deadline
                time.sleep(0.005)
            assert count[0] == 1
        finally:
            release.set()
        pacs.result(3)
        assert orders.result(3).encounters[0].board_eligible
    assert live[0] == 0 and count[0] == 2


@pytest.fixture
def lifecycle_source(source):
    return replace(source, orders=tuple(
        row for row in source.orders if row["category_code"] == "TEST_INJECTION"
    ))


@pytest.fixture
def lifecycle_policy(policy):
    # Synthetic reviewed codes only; this does not approve live fee/dose mappings.
    return replace(policy, categories=policy.categories + tuple(
        (code, None) for code in (
            "TEST_ORAL_MEDICATION", "TEST_CONSULTATION_FEE",
            "TEST_ADMINISTRATION_FEE", "TEST_MEDICATION_MANAGEMENT_FEE",
        )
    ), details=policy.details + (
        (Category.INJECTION, "TEST_EDITED", (
            ("medication", "Test medication B"), ("dose", "Test dose B"),
            ("route", "Test route B"),
        )),
    ))


@pytest.fixture
def lifecycle_fees(lifecycle_source):
    return tuple({
        "encounter_id": lifecycle_source.encounters[0]["encounter_id"],
        "order_id": f"fixture-fee-{index}", "category_code": code,
        "state_code": "TEST_ACTIVE",
    } for index, code in enumerate((
        "TEST_CONSULTATION_FEE", "TEST_ADMINISTRATION_FEE",
        "TEST_MEDICATION_MANAGEMENT_FEE",
    )))


def test_same_key_approved_detail_edit_replaces_payload_and_retries_once(lifecycle_source, lifecycle_policy):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    edited = advance(lifecycle_source, orders=[dict(lifecycle_source.orders[0], detail_code="TEST_EDITED")])
    change = ledger.prepare(edited, lifecycle_policy)
    assert len(change.encounter_upserts) == 1
    assert change.order_withdrawals == change.encounter_withdrawals == ()
    payload = proposed_v2_payload(change, synthetic_fixture=True)
    orders = payload["encounters"][0]["orders"]
    assert len(orders) == 1 and orders[0]["order_id"] == lifecycle_source.orders[0]["order_id"]
    assert orders[0]["display_spec"] == {
        "medication": "Test medication B", "dose": "Test dose B", "route": "Test route B",
    }
    assert ledger.prepare(edited, lifecycle_policy) is change
    assert proposed_v2_payload(ledger.pending, synthetic_fixture=True) == payload
    ledger.acknowledge(change.batch_id)
    unchanged = ledger.prepare(advance(edited), lifecycle_policy)
    assert unchanged.encounter_upserts == unchanged.order_withdrawals == unchanged.encounter_withdrawals == ()


@pytest.mark.parametrize("field", ["qty", "days", "divide"])
def test_raw_dose_fields_still_require_an_approved_projection(lifecycle_source, lifecycle_policy, field):
    # Today's observed DB fields have no approved dynamic display mapping yet.
    rows = [dict(lifecycle_source.orders[0], **{field: "UNAPPROVED-TEST-VALUE"})]
    with pytest.raises(SnapshotRejected, match="invalid_fields") as error:
        normalize_day(advance(lifecycle_source, orders=rows), lifecycle_policy)
    assert "UNAPPROVED-TEST-VALUE" not in str(error.value)


@pytest.mark.parametrize("restored_category", [Category.INJECTION, Category.BLOOD])
def test_deleted_key_can_return_with_same_or_different_category(lifecycle_source, lifecycle_policy, restored_category):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    deleted = advance(lifecycle_source, orders=[])
    removal = ledger.prepare(deleted, lifecycle_policy)
    assert len(removal.order_withdrawals) == 1
    assert removal.order_withdrawals[0].order_id == lifecycle_source.orders[0]["order_id"]
    assert removal.order_withdrawals[0].reason == "absent_from_complete_day"
    assert not removal.encounter_withdrawals
    assert not removal.snapshot.encounters[0].board_eligible
    ledger.acknowledge(removal.batch_id)

    restored = advance(deleted, orders=[dict(lifecycle_source.orders[0], category_code=f"TEST_{restored_category}")])
    change = ledger.prepare(restored, lifecycle_policy)
    assert change.snapshot.encounters[0].board_eligible
    assert change.order_withdrawals == change.encounter_withdrawals == ()
    assert len(change.encounter_upserts) == 1
    order = change.encounter_upserts[0].orders[0]
    assert order.order_id == lifecycle_source.orders[0]["order_id"]
    assert order.category == restored_category and order.state == OrderState.ACTIVE
    ledger.acknowledge(change.batch_id)
    repeated = ledger.prepare(advance(restored), lifecycle_policy)
    assert repeated.encounter_upserts == repeated.order_withdrawals == repeated.encounter_withdrawals == ()


@pytest.mark.parametrize("old_category,new_category", [
    (Category.XRAY, Category.INJECTION), (Category.INJECTION, Category.BLOOD),
])
def test_key_reuse_without_observed_deletion_replaces_old_display_fields(
    lifecycle_source, lifecycle_policy, old_category, new_category,
):
    original = advance(lifecycle_source, orders=[dict(lifecycle_source.orders[0], category_code=f"TEST_{old_category}")])
    ledger = baseline(original, lifecycle_policy)
    replacement = advance(original, orders=[dict(original.orders[0], category_code=f"TEST_{new_category}")])
    change = ledger.prepare(replacement, lifecycle_policy)
    assert len(change.encounter_upserts) == 1
    assert change.order_withdrawals == change.encounter_withdrawals == ()
    emitted = proposed_v2_payload(change, synthetic_fixture=True)["encounters"][0]["orders"]
    expected = normalize_day(replacement, lifecycle_policy).encounters[0].orders[0]
    assert len(emitted) == 1 and emitted[0]["order_id"] == original.orders[0]["order_id"]
    assert emitted[0]["category"] == new_category.value
    assert emitted[0]["display_spec"] == dict(expected.display_spec)
    old_fields = dict(normalize_day(original, lifecycle_policy).encounters[0].orders[0].display_spec)
    assert not set(old_fields).intersection(emitted[0]["display_spec"])


def test_ignored_medication_key_can_become_visible_injection(lifecycle_source, lifecycle_policy):
    oral = advance(lifecycle_source, orders=[dict(lifecycle_source.orders[0], category_code="TEST_ORAL_MEDICATION")])
    ledger = baseline(oral, lifecycle_policy)
    assert not normalize_day(oral, lifecycle_policy).encounters[0].board_eligible
    injection = advance(oral, orders=lifecycle_source.orders)
    change = ledger.prepare(injection, lifecycle_policy)
    assert change.snapshot.encounters[0].board_eligible
    assert change.encounter_upserts[0].orders[0].order_id == oral.orders[0]["order_id"]
    assert change.order_withdrawals == change.encounter_withdrawals == ()


def test_relevant_key_replaced_by_ignored_fee_removes_old_board_item(lifecycle_source, lifecycle_policy):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    fee = advance(lifecycle_source, orders=[dict(lifecycle_source.orders[0], category_code="TEST_ADMINISTRATION_FEE")])
    change = ledger.prepare(fee, lifecycle_policy)
    assert not change.snapshot.encounters[0].board_eligible
    assert change.encounter_upserts[0].orders == ()
    assert len(change.order_withdrawals) == 1
    assert change.order_withdrawals[0].order_id == lifecycle_source.orders[0]["order_id"]
    assert not change.encounter_withdrawals
    payload = proposed_v2_payload(change, synthetic_fixture=True)
    assert payload["encounters"] == []
    assert payload["encounter_states"] == [{
        "encounter_id": lifecycle_source.encounters[0]["encounter_id"], "state": "ON_HOLD",
    }]


def test_completion_fee_row_replacement_does_not_duplicate_injection(lifecycle_source, lifecycle_policy, lifecycle_fees):
    consultation, administration, management = lifecycle_fees
    holding = advance(lifecycle_source, orders=lifecycle_source.orders + (consultation, administration))
    ledger = baseline(holding, lifecycle_policy)
    before = normalize_day(holding, lifecycle_policy).encounters[0].orders
    new_administration = dict(administration, order_id="fixture-fee-new-administration")
    completed = advance(holding, encounter={"state_code": "TEST_CLOSED"},
                        orders=lifecycle_source.orders + (consultation, new_administration, management))
    assert len(holding.orders) == 3 and len(completed.orders) == 4
    change = ledger.prepare(completed, lifecycle_policy)
    assert not change.snapshot.encounters[0].board_eligible
    assert change.snapshot.encounters[0].orders == before
    assert change.order_withdrawals == change.encounter_withdrawals == ()
    payload = proposed_v2_payload(change, synthetic_fixture=True)
    assert len(payload["encounters"][0]["orders"]) == 1
    assert "fixture-fee" not in json.dumps(payload)
    ledger.acknowledge(change.batch_id)
    reopened = ledger.prepare(advance(completed, encounter={"state_code": "TEST_HOLD"}), lifecycle_policy)
    assert reopened.summary()["visible_encounters"] == 1
    assert reopened.encounter_upserts[0].orders == before
    assert reopened.order_withdrawals == reopened.encounter_withdrawals == ()


def test_only_reviewed_fee_rows_never_show_a_hold_tile(lifecycle_source, lifecycle_policy, lifecycle_fees):
    fees_only = advance(lifecycle_source, orders=lifecycle_fees)
    change = ShadowLedger().prepare(fees_only, lifecycle_policy)
    assert change.summary()["visible_encounters"] == 0
    assert change.snapshot.encounters[0].orders == ()
    assert proposed_v2_payload(change, synthetic_fixture=True)["encounters"] == []


def test_unknown_fee_category_preserves_previous_snapshot(lifecycle_source, lifecycle_policy, lifecycle_fees):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    unknown = dict(lifecycle_fees[0], category_code="TEST_UNREVIEWED_FEE")
    with pytest.raises(SnapshotRejected, match="unknown_category"):
        ledger.prepare(advance(lifecycle_source, orders=lifecycle_source.orders + (unknown,)), lifecycle_policy)
    assert ledger.pending is None
    unchanged = ledger.prepare(advance(lifecycle_source), lifecycle_policy)
    assert unchanged.encounter_upserts == unchanged.order_withdrawals == unchanged.encounter_withdrawals == ()


def test_full_status_round_trip_reactivates_unchanged_orders(lifecycle_source, lifecycle_policy, lifecycle_fees):
    source = advance(lifecycle_source, orders=lifecycle_source.orders + lifecycle_fees)
    expected_orders = normalize_day(source, lifecycle_policy).encounters[0].orders
    ledger = ShadowLedger()
    sequence = ("TEST_HOLD", "TEST_CLOSED", "TEST_HOLD", "TEST_CANCELLED", "TEST_REGISTERED", "TEST_HOLD")
    for code in sequence:
        source = advance(source, encounter={"state_code": code})
        change = ledger.prepare(source, lifecycle_policy)
        encounter = change.snapshot.encounters[0]
        assert encounter.orders == expected_orders
        assert all(order.state == OrderState.ACTIVE for order in encounter.orders)
        assert encounter.board_eligible is (code == "TEST_HOLD")
        assert not change.order_withdrawals
        payload = proposed_v2_payload(change, synthetic_fixture=True)
        if code == "TEST_CANCELLED":
            assert len(change.encounter_withdrawals) == 1
            assert change.encounter_withdrawals[0].reason == "source_cancelled"
            assert change.encounter_upserts == () and payload["encounters"] == []
        else:
            assert not change.encounter_withdrawals
            assert change.encounter_upserts == (encounter,)
            assert len(payload["encounters"]) == 1
            assert len(payload["encounters"][0]["orders"]) == 1
        assert payload["encounter_states"][0]["state"] == encounter.state.value
        assert ledger.prepare(source, lifecycle_policy) is change
        ledger.acknowledge(change.batch_id)


def test_cancelled_active_orders_stay_hidden_on_repeat_and_restart(lifecycle_source, lifecycle_policy):
    cancelled = advance(lifecycle_source, encounter={"state_code": "TEST_CANCELLED"})
    ledger = baseline(cancelled, lifecycle_policy)
    repeated = ledger.prepare(advance(cancelled), lifecycle_policy)
    assert repeated.encounter_upserts == repeated.encounter_withdrawals == repeated.order_withdrawals == ()
    for change in (repeated, ShadowLedger().prepare(cancelled, lifecycle_policy)):
        assert not change.snapshot.encounters[0].board_eligible
        assert proposed_v2_payload(change, synthetic_fixture=True)["encounters"] == []


@pytest.mark.parametrize("failure", [
    {"status": ReadStatus.PARTIAL}, {"status": ReadStatus.FAILED},
    {"status": ReadStatus.TIMED_OUT}, {"status": ReadStatus.UNAVAILABLE},
    {"stable_keys_verified": False}, {"states_verified": False},
    {"whole_day": False}, {"untruncated": False}, {"consistent_snapshot": False},
])
def test_uncertain_fee_only_result_does_not_delete_active_injection(
    lifecycle_source, lifecycle_policy, lifecycle_fees, failure,
):
    source = advance(lifecycle_source, orders=lifecycle_source.orders + lifecycle_fees)
    ledger = baseline(source, lifecycle_policy)
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        ledger.prepare(advance(source, orders=lifecycle_fees, **failure), lifecycle_policy)
    assert ledger.pending is None
    recovery = ledger.prepare(advance(source), lifecycle_policy)
    assert recovery.snapshot.encounters[0].board_eligible
    assert recovery.encounter_upserts == recovery.encounter_withdrawals == recovery.order_withdrawals == ()
    ledger.acknowledge(recovery.batch_id)
    complete_removal = ledger.prepare(advance(advance(source), orders=lifecycle_fees), lifecycle_policy)
    assert len(complete_removal.order_withdrawals) == 1
    assert not complete_removal.encounter_withdrawals
    assert not complete_removal.snapshot.encounters[0].board_eligible


def test_failed_read_does_not_replace_pending_edit_or_its_retry(lifecycle_source, lifecycle_policy):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    edited = advance(lifecycle_source, orders=[dict(lifecycle_source.orders[0], detail_code="TEST_EDITED")])
    pending = ledger.prepare(edited, lifecycle_policy)
    payload = proposed_v2_payload(pending, synthetic_fixture=True)
    with pytest.raises(SnapshotRejected, match="incomplete_source"):
        ledger.prepare(advance(edited, orders=[], status=ReadStatus.TIMED_OUT), lifecycle_policy)
    assert ledger.pending is pending
    assert ledger.prepare(edited, lifecycle_policy) is pending
    assert proposed_v2_payload(ledger.pending, synthetic_fixture=True) == payload


@pytest.mark.parametrize("kinds", [("relevant", "fee"), ("fee", "relevant"), ("fee", "fee")])
def test_duplicate_keys_cannot_hide_behind_ignored_fees(lifecycle_source, lifecycle_policy, lifecycle_fees, kinds):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    relevant = lifecycle_source.orders[0]
    fee = dict(lifecycle_fees[0], order_id=relevant["order_id"])
    rows = [{"relevant": relevant, "fee": fee}[kind] for kind in kinds]
    with pytest.raises(SnapshotRejected, match="duplicate_order"):
        ledger.prepare(advance(lifecycle_source, orders=rows), lifecycle_policy)
    assert ledger.pending is None
    recovered = ledger.prepare(advance(lifecycle_source), lifecycle_policy)
    assert recovered.encounter_upserts == recovered.order_withdrawals == recovered.encounter_withdrawals == ()


@pytest.mark.parametrize("field,value,reason", [
    ("order_id", "", "invalid_text"),
    ("encounter_id", "fixture-missing-encounter", "orphan_order"),
])
def test_ignored_fee_still_requires_valid_source_identity(lifecycle_source, lifecycle_policy, lifecycle_fees, field, value, reason):
    ledger = baseline(lifecycle_source, lifecycle_policy)
    fee = dict(lifecycle_fees[0], **{field: value})
    with pytest.raises(SnapshotRejected, match=reason):
        ledger.prepare(advance(lifecycle_source, orders=lifecycle_source.orders + (fee,)), lifecycle_policy)
    assert ledger.pending is None
    recovered = ledger.prepare(advance(lifecycle_source), lifecycle_policy)
    assert recovered.encounter_upserts == recovered.order_withdrawals == recovered.encounter_withdrawals == ()


@pytest.mark.parametrize("category", ["TEST_INJECTION", "TEST_CONSULTATION_FEE"])
def test_order_key_uniqueness_remains_scoped_to_each_encounter(lifecycle_source, lifecycle_policy, category):
    second = dict(lifecycle_source.encounters[0], encounter_id="fixture-second-visit")
    reused = dict(lifecycle_source.orders[0], encounter_id=second["encounter_id"], category_code=category)
    source = replace(lifecycle_source, encounters=lifecycle_source.encounters + (second,),
                     orders=lifecycle_source.orders + (reused,))
    snapshot = normalize_day(source, lifecycle_policy)
    assert len(snapshot.encounters) == 2
    encounters = {item.encounter_id: item for item in snapshot.encounters}
    assert encounters[lifecycle_source.encounters[0]["encounter_id"]].board_eligible
    assert encounters[second["encounter_id"]].board_eligible is (category == "TEST_INJECTION")
