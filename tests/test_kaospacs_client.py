import json
from urllib import error

from KaosEghis.core.kaospacs_client import (
    _build_kaospacs_entry,
    cancel_kaospacs_order,
    check_kaospacs_health,
    reconcile_kaospacs_worklist_to_local,
    push_kaospacs_worklist,
    sync_local_worklist_to_kaospacs,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import create_pacs_worklist_item, get_pacs_worklist_item


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_kaospacs_health_success(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: _FakeResponse({"status": "ok"}),
    )

    assert check_kaospacs_health({"kaospacs_api_base_url": "http://127.0.0.1:8055"}) is True


def test_kaospacs_health_failure(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(error.URLError("down")),
    )

    try:
        check_kaospacs_health({"kaospacs_api_base_url": "http://127.0.0.1:8055"})
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

    assert "down" in message


def test_active_rows_become_worklist_payload_and_exclude_sensitive_fields() -> None:
    from KaosEghis.db.repositories import PacsWorklistItemRecord

    item = PacsWorklistItemRecord(
        id=1,
        status="active",
        patient_name="Alice",
        chart_no="C001",
        study="Chest",
        modality="CR",
        requested_at="2026-06-28T09:30:00",
        accession_or_order_id="ACC-1",
        source="eghis-db",
        error_message=None,
        kaospacs_mwl_status="not_sent",
        kaospacs_mwl_last_synced_at=None,
        kaospacs_mwl_error=None,
        created_at="now",
        updated_at="now",
    )

    payload = _build_kaospacs_entry(item)

    assert payload["PatientName"] == "Alice"
    assert payload["PatientID"] == "C001"
    assert payload["AccessionNumber"] == "ACC-1"
    assert payload["RequestedProcedureDescription"] == "Chest"
    assert payload["Modality"] == "CR"
    assert "patient_birth_date" not in payload
    assert "patient_sex" not in payload
    assert "resident_id" not in payload
    assert "phone" not in payload
    assert "address" not in payload
    assert "diagnosis" not in payload
    assert "error_message" not in payload


def test_push_kaospacs_worklist_sends_entries(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    push_kaospacs_worklist(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        [{"AccessionNumber": "ACC-1"}],
    )

    assert captured["url"].endswith("/worklist")
    assert captured["method"] == "PUT"
    assert captured["body"] == {"entries": [{"AccessionNumber": "ACC-1"}]}


def test_push_kaospacs_worklist_matches_kaospacs_contract(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    push_kaospacs_worklist(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        [{"AccessionNumber": "ACC-1"}, {"AccessionNumber": "ACC-2"}],
    )

    assert isinstance(captured["body"], dict)
    assert list(captured["body"].keys()) == ["entries"]
    assert captured["body"]["entries"] == [
        {"AccessionNumber": "ACC-1"},
        {"AccessionNumber": "ACC-2"},
    ]


def test_successful_sync_marks_sent(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-2",
            source="eghis-db",
        )

    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda settings, entries: {"ok": True})
    monkeypatch.setattr(client, "cancel_kaospacs_order", lambda settings, accession_number: {"ok": True})

    result = sync_local_worklist_to_kaospacs(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.sent == 1
    assert loaded is not None
    assert loaded.kaospacs_mwl_status == "sent"
    assert loaded.kaospacs_mwl_error is None


def test_failed_sync_marks_error(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-3",
            source="eghis-db",
        )

    monkeypatch.setattr(
        client,
        "push_kaospacs_worklist",
        lambda settings, entries: (_ for _ in ()).throw(RuntimeError("api failure")),
    )

    result = sync_local_worklist_to_kaospacs(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.errors == 1
    assert loaded is not None
    assert loaded.kaospacs_mwl_status == "error"
    assert loaded.kaospacs_mwl_error == "api failure"


def test_cancelled_previously_sent_row_calls_cancel(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client
    from KaosEghis.db.repositories import update_pacs_worklist_sync_state

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-4",
            source="eghis-db",
        )
        update_pacs_worklist_sync_state(
            connection,
            item.id,
            kaospacs_mwl_status="sent",
        )

    calls = []
    monkeypatch.setattr(client, "push_kaospacs_worklist", lambda settings, entries: {"ok": True})
    monkeypatch.setattr(
        client,
        "cancel_kaospacs_order",
        lambda settings, accession_number: calls.append(accession_number) or {"ok": True},
    )

    result = sync_local_worklist_to_kaospacs(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.cancelled == 1
    assert calls == ["ACC-4"]
    assert loaded is not None
    assert loaded.kaospacs_mwl_status == "cancelled"


def test_cancelled_never_sent_row_is_not_sent(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-5",
            source="eghis-db",
        )

    push_calls = []
    cancel_calls = []
    monkeypatch.setattr(
        client,
        "push_kaospacs_worklist",
        lambda settings, entries: push_calls.append(entries) or {"ok": True},
    )
    monkeypatch.setattr(
        client,
        "cancel_kaospacs_order",
        lambda settings, accession_number: cancel_calls.append(accession_number) or {"ok": True},
    )

    result = sync_local_worklist_to_kaospacs(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.sent == 0
    assert result.cancelled == 0
    assert result.skipped >= 1
    assert push_calls == []
    assert cancel_calls == []
    assert loaded is not None
    assert loaded.kaospacs_mwl_status == "not_sent"


def test_dry_run_sync_makes_no_api_changes(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client
    from KaosEghis.db.repositories import update_pacs_worklist_sync_state

    with connect(db_path) as connection:
        active_item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-DRY-1",
            study="Chest",
            modality="CR",
        )
        cancelled_item = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Bob",
            accession_or_order_id="ACC-DRY-2",
            study="Spine",
            modality="MR",
        )
        update_pacs_worklist_sync_state(
            connection,
            cancelled_item.id,
            kaospacs_mwl_status="sent",
        )

    calls = {"push": 0, "cancel": 0}
    monkeypatch.setattr(
        client,
        "push_kaospacs_worklist",
        lambda settings, entries: calls.__setitem__("push", calls["push"] + 1),
    )
    monkeypatch.setattr(
        client,
        "cancel_kaospacs_order",
        lambda settings, accession_number: calls.__setitem__("cancel", calls["cancel"] + 1),
    )

    result = sync_local_worklist_to_kaospacs(
        {
            "kaospacs_api_base_url": "http://127.0.0.1:8055",
            "pacs_dry_run": "true",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_active = get_pacs_worklist_item(connection, active_item.id)
        loaded_cancelled = get_pacs_worklist_item(connection, cancelled_item.id)

    assert result.dry_run is True
    assert result.sent == 1
    assert result.cancelled == 1
    assert calls == {"push": 0, "cancel": 0}
    assert loaded_active is not None
    assert loaded_cancelled is not None
    assert loaded_active.kaospacs_mwl_status == "not_sent"
    assert loaded_cancelled.kaospacs_mwl_status == "sent"


def test_reconcile_completed_kaospacs_row_marks_local_done(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-1000",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {"entries": [{"AccessionNumber": "ACC-1000", "CompletedAt": "2026-06-29T12:00:00Z"}]},
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.done == 1
    assert result.cancelled == 0
    assert loaded is not None
    assert loaded.status == "done"


def test_reconcile_cancelled_kaospacs_row_marks_local_cancelled(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-1001",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {"entries": [{"RequestedProcedureID": "ACC-1001", "CancelledAt": "2026-06-29T12:00:00Z"}]},
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.done == 0
    assert result.cancelled == 1
    assert loaded is not None
    assert loaded.status == "cancelled"


def test_reconcile_unmatched_kaospacs_row_is_skipped(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {"entries": [{"AccessionNumber": "ACC-NOT-FOUND", "CompletedAt": "2026-06-29T12:00:00Z"}]},
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM pacs_worklist_items").fetchone()[0]

    assert result.skipped == 1
    assert result.done == 0
    assert result.cancelled == 0
    assert rows == 0


def test_reconcile_local_done_or_cancelled_is_not_reverted(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        done_item = create_pacs_worklist_item(
            connection,
            status="done",
            patient_name="Done",
            accession_or_order_id="ACC-1002",
            study="Chest",
            modality="CR",
        )
        cancelled_item = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Cancelled",
            accession_or_order_id="ACC-1003",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {
            "entries": [
                {"AccessionNumber": "ACC-1002", "Active": True},
                {"ScheduledProcedureStepID": "ACC-1003", "Active": True},
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_done = get_pacs_worklist_item(connection, done_item.id)
        loaded_cancelled = get_pacs_worklist_item(connection, cancelled_item.id)

    assert result.skipped == 2
    assert loaded_done is not None
    assert loaded_cancelled is not None
    assert loaded_done.status == "done"
    assert loaded_cancelled.status == "cancelled"


def test_reconcile_does_not_create_new_local_rows_from_kaospacs(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {
            "entries": [
                {"AccessionNumber": "ACC-NEW-1", "CompletedAt": "2026-06-29T12:00:00Z"},
                {"RequestedProcedureID": "ACC-NEW-2", "CancelledAt": "2026-06-29T12:00:00Z"},
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8055"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM pacs_worklist_items").fetchone()[0]

    assert result.skipped == 2
    assert rows == 0


def test_dry_run_reconcile_makes_no_status_changes(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        done_candidate = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-DRY-R1",
            study="Chest",
            modality="CR",
        )
        cancelled_candidate = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Bob",
            accession_or_order_id="ACC-DRY-R2",
            study="Spine",
            modality="MR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {
            "entries": [
                {"AccessionNumber": "ACC-DRY-R1", "CompletedAt": "2026-06-29T12:00:00Z"},
                {"RequestedProcedureID": "ACC-DRY-R2", "CancelledAt": "2026-06-29T12:10:00Z"},
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {
            "kaospacs_api_base_url": "http://127.0.0.1:8055",
            "pacs_dry_run": "true",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_done_candidate = get_pacs_worklist_item(connection, done_candidate.id)
        loaded_cancelled_candidate = get_pacs_worklist_item(connection, cancelled_candidate.id)

    assert result.dry_run is True
    assert result.done == 1
    assert result.cancelled == 1
    assert loaded_done_candidate is not None
    assert loaded_cancelled_candidate is not None
    assert loaded_done_candidate.status == "active"
    assert loaded_cancelled_candidate.status == "active"
