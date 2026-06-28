import json
from urllib import error

from KaosEghis.core.kaospacs_client import (
    _build_kaospacs_entry,
    cancel_kaospacs_order,
    check_kaospacs_health,
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
