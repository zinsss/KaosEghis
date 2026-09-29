from dataclasses import asdict
from types import SimpleNamespace

import pytest

from KaosEghis.core import kaospacs_client as client
from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_pacs_worklist_item, get_pacs_worklist_item,
    update_pacs_worklist_item, update_pacs_worklist_sync_state,
)


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite"
    initialize_database(path)
    values = dict(status="active", patient_name="Test Patient", patient_birth_date="20000101",
                  patient_sex="F", chart_no="TEST-001", study="Chest", modality="CR",
                  requested_at="2026-09-29T09:00:00", accession_or_order_id="TEST-ORDER", source="eghis-db")
    with connect(path) as connection:
        item = create_pacs_worklist_item(connection, **values)
    pushes, cancels = [], []
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda settings, items: pushes.extend(items) or {})
    monkeypatch.setattr(client, "cancel_kaospacs_order", lambda settings, accession: cancels.append(accession) or {})
    return SimpleNamespace(path=path, values=values, item=item, pushes=pushes, cancels=cancels,
                           settings={"kaospacs_api_base_url": "http://test.invalid:8060"})


def sync(delivery, **kwargs):
    return client.sync_local_worklist_to_kaospacs(delivery.settings, delivery.path, **kwargs)


def load(delivery):
    with connect(delivery.path) as connection:
        return get_pacs_worklist_item(connection, delivery.item.id)


def edit(delivery, **changes):
    values = {key: value for key, value in asdict(load(delivery)).items() if key in delivery.values}
    values.update(changes)
    with connect(delivery.path) as connection:
        return update_pacs_worklist_item(connection, delivery.item.id, **values)


def test_successful_payload_is_persisted_and_skipped_after_reinitialization(delivery):
    assert sync(delivery).sent == 1
    acknowledged = load(delivery)
    assert len(acknowledged.kaospacs_mwl_fingerprint) == 64
    initialize_database(delivery.path)
    result = sync(delivery)
    assert result.sent == 0 and result.unchanged == 1 and result.skipped == 1
    assert len(delivery.pushes) == 1
    assert load(delivery) == acknowledged


@pytest.mark.parametrize("field,value", [
    ("patient_name", "Changed Test"), ("patient_birth_date", "20010101"),
    ("patient_sex", "M"), ("chart_no", "TEST-002"), ("study", "Knee"),
    ("modality", "BMD"), ("requested_at", "2026-09-29T10:00:00"),
    ("accession_or_order_id", "TEST-OTHER-ORDER"),
])
def test_each_transmitted_field_change_sends_again(delivery, field, value):
    sync(delivery)
    fingerprint = load(delivery).kaospacs_mwl_fingerprint
    edit(delivery, **{field: value})
    assert sync(delivery).sent == 1
    assert load(delivery).kaospacs_mwl_fingerprint != fingerprint
    assert sync(delivery).unchanged == 1


def test_source_and_timestamp_only_changes_do_not_send_again(delivery):
    sync(delivery)
    edit(delivery, source="manual")
    with connect(delivery.path) as connection:
        connection.execute("UPDATE pacs_worklist_items SET updated_at='later' WHERE id=?", (delivery.item.id,))
        connection.commit()
    assert sync(delivery).unchanged == 1
    assert len(delivery.pushes) == 1


def test_unchanged_source_poll_does_not_resend_even_when_local_upsert_runs(delivery):
    sync(delivery)
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "mock"}, delivery.path, poller=lambda _: [delivery.values])
    assert result.updated == 1
    assert sync(delivery).unchanged == 1
    assert len(delivery.pushes) == 1


def test_legacy_sent_row_without_fingerprint_is_sent_once(delivery):
    with connect(delivery.path) as connection:
        update_pacs_worklist_sync_state(connection, delivery.item.id, kaospacs_mwl_status="sent")
    assert sync(delivery).sent == 1
    assert sync(delivery).unchanged == 1


def test_destination_change_resends_but_token_rotation_and_trailing_slash_do_not(delivery):
    sync(delivery)
    delivery.settings["kaospacs_gateway_api_token"] = "test-token"
    delivery.settings["kaospacs_api_base_url"] += "/"
    assert sync(delivery).unchanged == 1
    delivery.settings["kaospacs_api_base_url"] = "http://different.invalid:8060"
    assert sync(delivery).sent == 1


def test_failed_delivery_remains_retryable_until_acknowledged(delivery, monkeypatch):
    def fail(*args):
        raise RuntimeError("simulated network failure")
    monkeypatch.setattr(client, "push_kaospacs_worklist", fail)
    assert sync(delivery).errors == 1
    assert load(delivery).kaospacs_mwl_fingerprint is None
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda *args: {})
    assert sync(delivery).sent == 1
    assert sync(delivery).unchanged == 1


def test_failed_edit_does_not_retain_old_acknowledgement(delivery, monkeypatch):
    sync(delivery)
    edit(delivery, study="Knee")
    monkeypatch.setattr(client, "push_kaospacs_worklist",
                        lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))
    assert sync(delivery).errors == 1
    assert load(delivery).kaospacs_mwl_fingerprint is None
    edit(delivery, study="Chest")
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda *args: {})
    assert sync(delivery).sent == 1  # The failed edit may have reached the server.


def test_cancel_acknowledged_once_then_reactivation_sends_again(delivery):
    sync(delivery)
    edit(delivery, status="cancelled")
    assert sync(delivery).cancelled == 1
    assert sync(delivery).unchanged == 1
    assert delivery.cancels == ["TEST-ORDER"]
    edit(delivery, status="active")
    assert sync(delivery).sent == 1
    assert len(delivery.pushes) == 2


def test_dry_run_never_acknowledges_changed_payload(delivery):
    sync(delivery)
    edit(delivery, study="Knee")
    before = load(delivery)
    delivery.settings["pacs_dry_run"] = "true"
    assert sync(delivery).sent == 1
    assert load(delivery) == before
    assert len(delivery.pushes) == 1
    delivery.settings["pacs_dry_run"] = "false"
    assert sync(delivery).sent == 1


def test_explicit_force_resends_unchanged_and_dry_run_force_does_not_write(delivery):
    sync(delivery)
    assert sync(delivery, force=True).sent == 1
    before = load(delivery)
    delivery.settings["pacs_dry_run"] = "true"
    assert sync(delivery, force=True).sent == 1
    assert load(delivery) == before
    assert len(delivery.pushes) == 2


def test_invalid_rows_remain_visible_without_network_or_repeated_writes(delivery):
    edit(delivery, study=None, requested_at=None)
    first = sync(delivery)
    before = load(delivery)
    second = sync(delivery)
    assert first.errors == second.errors == first.invalid == second.invalid == 1
    assert before.kaospacs_mwl_error == "missing required fields: ScheduledAt, Description"
    assert load(delivery) == before
    assert not delivery.pushes
    edit(delivery, study="Chest", requested_at="2026-09-29T09:00:00")
    assert sync(delivery).sent == 1


@pytest.mark.parametrize("change", [{"study": "Knee"}, {"status": "cancelled"}])
def test_edit_during_http_does_not_acknowledge_new_payload(delivery, monkeypatch, change):
    def push(settings, items):
        edit(delivery, **change)
        return {}
    monkeypatch.setattr(client, "push_kaospacs_worklist", push)
    assert sync(delivery).sent == 1
    assert not client._delivery_is_current(delivery.settings, load(delivery))
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda *args: {})
    result = sync(delivery)
    assert result.sent + result.cancelled == 1


def test_row_cancelled_while_another_item_sends_is_not_upserted(delivery, monkeypatch):
    with connect(delivery.path) as connection:
        create_pacs_worklist_item(connection, **{**delivery.values, "accession_or_order_id": "NEWER"})
    def push(settings, items):
        delivery.pushes.extend(items)
        edit(delivery, status="cancelled")
        return {}
    monkeypatch.setattr(client, "push_kaospacs_worklist", push)
    result = sync(delivery)
    assert result.sent == 1 and result.skipped == 1
    assert [item.accession_or_order_id for item in delivery.pushes] == ["NEWER"]


@pytest.mark.parametrize("status", ["completed", "expired", "error"])
def test_inactive_records_are_not_upserted_even_with_force(delivery, status):
    edit(delivery, status=status)
    assert sync(delivery, force=True).skipped == 1
    assert not delivery.pushes


def test_migration_of_pre_fingerprint_database_preserves_existing_row(tmp_path):
    from pathlib import Path
    from KaosEghis.db import database
    path = tmp_path / "old.sqlite"
    schema = Path(database.__file__).with_name("schema.sql").read_text(encoding="utf-8")
    schema = schema.replace("    kaospacs_mwl_fingerprint TEXT,\n", "")
    with connect(path) as connection:
        connection.executescript(schema)
        connection.execute("INSERT INTO pacs_worklist_items (status, chart_no, kaospacs_mwl_status) VALUES ('active', 'TEST', 'sent')")
        connection.commit()
    initialize_database(path)
    initialize_database(path)
    with connect(path) as connection:
        row = connection.execute("SELECT chart_no, kaospacs_mwl_status, kaospacs_mwl_fingerprint FROM pacs_worklist_items").fetchall()
    assert row == [("TEST", "sent", None)]


@pytest.mark.parametrize("response", [{"ok": False}, {"error": "rejected"}, [], None])
def test_explicit_api_rejection_cannot_be_acknowledged(delivery, monkeypatch, response):
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda *args: response)
    assert sync(delivery).errors == 1
    assert load(delivery).kaospacs_mwl_fingerprint is None


def test_invalid_json_on_forced_resend_invalidates_old_receipt(delivery, monkeypatch):
    sync(delivery)
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b"<html>unexpected gateway response</html>"
    monkeypatch.setattr(client.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda settings, items: client._push_kaospacs_item(settings, items[0]))
    assert sync(delivery, force=True).errors == 1
    assert load(delivery).kaospacs_mwl_fingerprint is None


def test_many_unchanged_rows_and_invalid_rows_make_no_second_delivery(delivery):
    with connect(delivery.path) as connection:
        for index in range(52):
            create_pacs_worklist_item(connection, **{**delivery.values, "accession_or_order_id": f"TEST-{index}"})
        for index in range(3):
            create_pacs_worklist_item(connection, **{**delivery.values, "accession_or_order_id": f"INVALID-{index}",
                                                    "study": None, "requested_at": None})
    assert sync(delivery).sent == 53
    result = sync(delivery)
    assert (result.sent, result.unchanged, result.invalid, result.errors) == (0, 53, 3, 3)
    assert len(delivery.pushes) == 53
