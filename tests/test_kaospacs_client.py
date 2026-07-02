import json
from urllib import error

from KaosEghis.core.kaospacs_client import (
    _build_kaospacs_entry,
    KaosPacsRequestError,
    cancel_kaospacs_order,
    check_kaospacs_health,
    reconcile_kaospacs_worklist_to_local,
    push_kaospacs_worklist,
    sync_local_worklist_to_kaospacs,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import PacsWorklistItemRecord, create_pacs_worklist_item, get_pacs_worklist_item


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _sample_item(
    accession: str = "ACC-1",
    *,
    patient_name: str = "Alice",
    patient_birth_date: str = "19900101",
    patient_sex: str = "F",
    chart_no: str = "C001",
    study: str = "Chest",
    modality: str = "CR",
    requested_at: str = "2026-06-28T09:30:00",
) -> PacsWorklistItemRecord:
    return PacsWorklistItemRecord(
        id=1,
        status="active",
        patient_name=patient_name,
        patient_birth_date=patient_birth_date,
        patient_sex=patient_sex,
        chart_no=chart_no,
        study=study,
        modality=modality,
        requested_at=requested_at,
        accession_or_order_id=accession,
        source="eghis-db",
        error_message=None,
        kaospacs_mwl_status="not_sent",
        kaospacs_mwl_last_synced_at=None,
        kaospacs_mwl_error=None,
        created_at="now",
        updated_at="now",
    )


def test_kaospacs_health_success(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: _FakeResponse({"status": "ok"}),
    )

    assert check_kaospacs_health({"kaospacs_api_base_url": "http://127.0.0.1:8060"}) is True


def test_kaospacs_health_failure(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(error.URLError("down")),
    )

    try:
        check_kaospacs_health({"kaospacs_api_base_url": "http://127.0.0.1:8060"})
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

    assert "down" in message


def test_active_rows_become_worklist_payload_and_exclude_sensitive_fields() -> None:
    item = _sample_item()

    payload = _build_kaospacs_entry(item)

    assert payload["PatientName"] == "Alice"
    assert payload["ChartNo"] == "C001"
    assert payload["PatientBirthDate"] == "19900101"
    assert payload["PatientSex"] == "F"
    assert payload["AccessionNumber"] == "ACC-1"
    assert payload["StudyType"] == "CR"
    assert payload["Description"] == "Chest"
    assert payload["StationAET"] == "INNOVISION"
    assert payload["ScheduledAt"] == "2026-06-28T09:30:00"
    assert payload["Modality"] == "CR"
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
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    push_kaospacs_worklist(
        {
            "kaospacs_api_base_url": "http://127.0.0.1:8060",
            "kaospacs_gateway_api_token": "token-123",
        },
        [_sample_item()],
    )

    assert captured["url"].endswith("/orders/upsert")
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Bearer token-123"
    assert captured["body"] == {
        "ChartNo": "C001",
        "PatientName": "Alice",
        "PatientBirthDate": "19900101",
        "PatientSex": "F",
        "AccessionNumber": "ACC-1",
        "StudyType": "CR",
        "Modality": "CR",
        "StationAET": "INNOVISION",
        "ScheduledAt": "2026-06-28T09:30:00",
        "Description": "Chest",
        "PatientID": "C001",
    }


def test_push_kaospacs_worklist_falls_back_to_legacy_put_worklist_on_404(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append((req.get_method(), req.full_url, json.loads(req.data.decode("utf-8"))))
        if req.full_url.endswith("/orders/upsert"):
            raise error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)
        return _FakeResponse({"entries": []})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    response = push_kaospacs_worklist(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        [_sample_item()],
    )

    assert response == {"entries": []}
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:8060/orders/upsert",
            {
                "ChartNo": "C001",
                "PatientName": "Alice",
                "PatientBirthDate": "19900101",
                "PatientSex": "F",
                "AccessionNumber": "ACC-1",
                "StudyType": "CR",
                "Modality": "CR",
                "StationAET": "INNOVISION",
                "ScheduledAt": "2026-06-28T09:30:00",
                "Description": "Chest",
                "PatientID": "C001",
            },
        ),
        (
            "PUT",
            "http://127.0.0.1:8060/worklist",
            {
                "entries": [
                    {
                        "PatientName": "Alice",
                        "PatientBirthDate": "19900101",
                        "PatientSex": "F",
                        "PatientID": "C001",
                        "AccessionNumber": "ACC-1",
                        "RequestedProcedureID": "ACC-1",
                        "ScheduledProcedureStepID": "ACC-1",
                        "RequestedProcedureDescription": "Chest",
                        "ScheduledProcedureStepDescription": "Chest",
                        "Modality": "CR",
                        "ScheduledStationAETitle": "INNOVISION",
                        "ScheduledProcedureStepStartDate": "20260628",
                        "ScheduledProcedureStepStartTime": "093000",
                    }
                ]
            },
        ),
    ]


def test_push_kaospacs_worklist_does_not_fall_back_on_500(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        raise error.HTTPError(req.full_url, 500, "Server Error", hdrs=None, fp=None)

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    try:
        push_kaospacs_worklist(
            {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
            [_sample_item()],
        )
    except KaosPacsRequestError as exc:
        assert exc.status_code == 500
    else:
        raise AssertionError("Expected KaosPacsRequestError")

    assert calls == ["http://127.0.0.1:8060/orders/upsert"]


def test_push_kaospacs_worklist_does_not_fall_back_on_network_error(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        raise error.URLError("down")

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    try:
        push_kaospacs_worklist(
            {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
            [_sample_item()],
        )
    except KaosPacsRequestError as exc:
        assert exc.status_code is None
    else:
        raise AssertionError("Expected KaosPacsRequestError")

    assert calls == ["http://127.0.0.1:8060/orders/upsert"]


def test_push_kaospacs_worklist_matches_kaospacs_contract(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    push_kaospacs_worklist(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        [
            _sample_item("ACC-1"),
            _sample_item("ACC-2", patient_name="Bob", chart_no="C002", study="Spine", modality="MR", requested_at="2026-06-28T10:00:00"),
        ],
    )

    assert isinstance(captured["body"], dict)
    assert list(captured["body"].keys()) == [
        "ChartNo",
        "PatientName",
        "PatientBirthDate",
        "PatientSex",
        "AccessionNumber",
        "StudyType",
        "Modality",
        "StationAET",
        "ScheduledAt",
        "Description",
        "PatientID",
    ]
    assert captured["body"] == {
        "ChartNo": "C002",
        "PatientName": "Bob",
        "PatientBirthDate": "19900101",
        "PatientSex": "F",
        "AccessionNumber": "ACC-2",
        "StudyType": "MR",
        "Modality": "MR",
        "StationAET": "INNOVISION",
        "ScheduledAt": "2026-06-28T10:00:00",
        "Description": "Spine",
        "PatientID": "C002",
    }


def test_cancel_kaospacs_order_falls_back_to_legacy_worklist_cancel_on_404(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    calls = []

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data.decode("utf-8"))
        calls.append((req.get_method(), req.full_url, body))
        if req.full_url.endswith("/orders/cancel"):
            raise error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    response = cancel_kaospacs_order(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        "ACC-1",
    )

    assert response == {"ok": True}
    assert calls == [
        ("POST", "http://127.0.0.1:8060/orders/cancel", {"AccessionNumber": "ACC-1"}),
        ("POST", "http://127.0.0.1:8060/worklist/cancel", {"AccessionNumber": "ACC-1"}),
    ]


def test_cancel_kaospacs_order_does_not_fall_back_on_500(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_client as client

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        raise error.HTTPError(req.full_url, 500, "Server Error", hdrs=None, fp=None)

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    try:
        cancel_kaospacs_order(
            {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
            "ACC-1",
        )
    except KaosPacsRequestError as exc:
        assert exc.status_code == 500
    else:
        raise AssertionError("Expected KaosPacsRequestError")

    assert calls == ["http://127.0.0.1:8060/orders/cancel"]


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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.errors == 1
    assert loaded is not None
    assert loaded.kaospacs_mwl_status == "error"
    assert loaded.kaospacs_mwl_error == "api failure"


def test_sync_skips_invalid_local_rows_and_still_sends_valid_entries(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    captured = {}

    with connect(db_path) as connection:
        valid_item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-VALID",
            source="eghis-db",
        )
        invalid_item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Bob",
            chart_no="C002",
            study="",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
            accession_or_order_id="ACC-INVALID",
            source="eghis-db",
        )

    def fake_push(settings, entries):
        captured["entries"] = entries
        return {"ok": True}

    monkeypatch.setattr(client, "push_kaospacs_worklist", fake_push)
    monkeypatch.setattr(client, "cancel_kaospacs_order", lambda settings, accession_number: {"ok": True})

    result = sync_local_worklist_to_kaospacs(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_valid = get_pacs_worklist_item(connection, valid_item.id)
        loaded_invalid = get_pacs_worklist_item(connection, invalid_item.id)

    assert result.sent == 1
    assert result.errors == 1
    assert captured["entries"] == [valid_item]
    assert loaded_valid is not None
    assert loaded_invalid is not None
    assert loaded_valid.kaospacs_mwl_status == "sent"
    assert loaded_invalid.kaospacs_mwl_status == "error"
    assert loaded_invalid.kaospacs_mwl_error == "missing required fields: Description"


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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
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
            chart_no="C001",
            accession_or_order_id="ACC-DRY-1",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28T09:30:00",
        )
        cancelled_item = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Bob",
            chart_no="C002",
            accession_or_order_id="ACC-DRY-2",
            study="Spine",
            modality="MR",
            requested_at="2026-06-28T10:00:00",
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
            "kaospacs_api_base_url": "http://127.0.0.1:8060",
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


def test_reconcile_completed_kaospacs_row_marks_local_completed(tmp_path, monkeypatch) -> None:
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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.completed == 1
    assert result.expired == 0
    assert loaded is not None
    assert loaded.status == "completed"


def test_reconcile_uses_gateway_imaging_worklist_when_configured(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    calls = {"gateway": 0, "api": 0}

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-GW-1",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "get_imaging_worklist",
        lambda settings: calls.__setitem__("gateway", calls["gateway"] + 1) or [
            {"AccessionNumber": "ACC-GW-1", "state": "completed"}
        ],
    )
    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: calls.__setitem__("api", calls["api"] + 1) or {"entries": []},
    )

    result = reconcile_kaospacs_worklist_to_local(
        {
            "kaospacs_gateway_url": "http://pacs.example:8060",
            "kaospacs_api_base_url": "http://pacs.example:8060",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert calls == {"gateway": 1, "api": 0}
    assert result.completed == 1
    assert loaded is not None
    assert loaded.status == "completed"


def test_reconcile_expired_kaospacs_row_marks_local_expired(tmp_path, monkeypatch) -> None:
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
        lambda settings: {"entries": [{"RequestedProcedureID": "ACC-1001", "ExpiredAt": "2026-06-29T12:00:00Z"}]},
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.completed == 0
    assert result.expired == 1
    assert loaded is not None
    assert loaded.status == "expired"


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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM pacs_worklist_items").fetchone()[0]

    assert result.skipped == 1
    assert result.completed == 0
    assert result.expired == 0
    assert rows == 0


def test_reconcile_local_completed_or_cancelled_is_not_reverted(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        completed_item = create_pacs_worklist_item(
            connection,
            status="completed",
            patient_name="Completed",
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
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_completed = get_pacs_worklist_item(connection, completed_item.id)
        loaded_cancelled = get_pacs_worklist_item(connection, cancelled_item.id)

    assert result.skipped == 2
    assert loaded_completed is not None
    assert loaded_cancelled is not None
    assert loaded_completed.status == "completed"
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
                {"RequestedProcedureID": "ACC-NEW-2", "ExpiredAt": "2026-06-29T12:00:00Z"},
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
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
        completed_candidate = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-DRY-R1",
            study="Chest",
            modality="CR",
        )
        expired_candidate = create_pacs_worklist_item(
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
                {"RequestedProcedureID": "ACC-DRY-R2", "ExpiredAt": "2026-06-29T12:10:00Z"},
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {
            "kaospacs_api_base_url": "http://127.0.0.1:8060",
            "pacs_dry_run": "true",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded_completed_candidate = get_pacs_worklist_item(connection, completed_candidate.id)
        loaded_expired_candidate = get_pacs_worklist_item(connection, expired_candidate.id)

    assert result.dry_run is True
    assert result.completed == 1
    assert result.expired == 1
    assert loaded_completed_candidate is not None
    assert loaded_expired_candidate is not None
    assert loaded_completed_candidate.status == "active"
    assert loaded_expired_candidate.status == "active"


def test_reconcile_cancelled_kaospacs_row_does_not_infer_local_cancelled(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-CANCEL-REMOTE",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {
            "entries": [
                {"RequestedProcedureID": "ACC-CANCEL-REMOTE", "CancelledAt": "2026-06-29T12:00:00Z"}
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.completed == 0
    assert result.expired == 0
    assert result.skipped == 1
    assert loaded is not None
    assert loaded.status == "active"


def test_reconcile_falls_back_to_api_worklist_without_gateway_url(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    calls = {"gateway": 0, "api": 0}

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-API-1",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "get_imaging_worklist",
        lambda settings: calls.__setitem__("gateway", calls["gateway"] + 1) or [],
    )
    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: calls.__setitem__("api", calls["api"] + 1) or {
            "entries": [{"AccessionNumber": "ACC-API-1", "CompletedAt": "2026-06-29T12:00:00Z"}]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://pacs.example:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert calls == {"gateway": 0, "api": 1}
    assert result.completed == 1
    assert loaded is not None
    assert loaded.status == "completed"


def test_reconcile_active_false_does_not_infer_local_completed(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    import KaosEghis.core.kaospacs_client as client

    with connect(db_path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-ACTIVE-FALSE",
            study="Chest",
            modality="CR",
        )

    monkeypatch.setattr(
        client,
        "fetch_kaospacs_worklist",
        lambda settings: {
            "entries": [
                {"RequestedProcedureID": "ACC-ACTIVE-FALSE", "Active": False}
            ]
        },
    )

    result = reconcile_kaospacs_worklist_to_local(
        {"kaospacs_api_base_url": "http://127.0.0.1:8060"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        loaded = get_pacs_worklist_item(connection, item.id)

    assert result.completed == 0
    assert result.expired == 0
    assert result.skipped == 1
    assert loaded is not None
    assert loaded.status == "active"
