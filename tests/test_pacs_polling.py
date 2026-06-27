from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import list_pacs_worklist_items


def test_poll_service_no_db_config_is_noop(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    calls: list[dict[str, str | None]] = []

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        calls.append({})
        return [
            {
                "status": "active",
                "accession_or_order_id": "X-1",
                "patient_name": "Ghost",
                "chart_no": "000",
            }
        ]

    from KaosEghis.core import pacs_polling

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)

    result = poll_eghis_image_orders_into_local_worklist({}, db_path=db_path)
    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 0
    assert not calls
    assert len(rows) == 0


def test_poll_service_inserts_mock_order(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-001",
                "source": "eghis-poll-mock",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)

    settings = {"eghis_db_connection_string": "read-only-scaffold"}
    result = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert len(rows) == 1
    assert rows[0].accession_or_order_id == "AC-001"
    assert rows[0].patient_name == "Alice"


def test_poll_service_does_not_duplicate_orders(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-002",
                "source": "eghis-poll-mock",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)
    settings = {"eghis_db_connection_string": "read-only-scaffold"}

    first = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)
    second = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert first.inserted == 1
    assert first.updated == 0
    assert second.inserted == 0
    assert second.updated == 1
    assert len(rows) == 1
    assert rows[0].accession_or_order_id == "AC-002"
