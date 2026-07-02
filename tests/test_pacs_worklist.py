from pathlib import Path

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    clear_pacs_audit_events,
    create_pacs_audit_event,
    create_pacs_worklist_item,
    delete_pacs_worklist_item,
    get_pacs_worklist_item,
    list_pacs_audit_events,
    list_pacs_worklist_items,
    update_pacs_worklist_item,
    update_pacs_worklist_sync_state,
    update_pacs_worklist_status,
)


def test_database_migration_creates_pacs_worklist_table(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(pacs_worklist_items)")
        }

    assert "status" in columns
    assert "patient_name" in columns
    assert "patient_birth_date" in columns
    assert "patient_sex" in columns
    assert "chart_no" in columns
    assert "study" in columns
    assert "modality" in columns
    assert "requested_at" in columns
    assert "accession_or_order_id" in columns
    assert "source" in columns
    assert "error_message" in columns
    assert "kaospacs_mwl_status" in columns
    assert "kaospacs_mwl_last_synced_at" in columns
    assert "kaospacs_mwl_error" in columns


def test_database_migration_creates_pacs_audit_table(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(pacs_audit_events)")
        }

    assert "event_type" in columns
    assert "worklist_item_id" in columns
    assert "accession_or_order_id" in columns
    assert "status_before" in columns
    assert "status_after" in columns
    assert "summary" in columns
    assert "error_message" in columns
    assert "created_at" in columns


def test_pacs_worklist_repository_crud(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        created = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            patient_birth_date="19900101",
            patient_sex="F",
            chart_no="C001",
            study="CT",
            modality="CT",
            requested_at="2026-06-01",
            accession_or_order_id="A001",
            source="manual",
        )
        assert created.id > 0
        assert created.status == "active"
        assert created.patient_name == "Alice"
        assert created.patient_birth_date == "19900101"
        assert created.patient_sex == "F"
        assert created.kaospacs_mwl_status == "not_sent"

        listed = list_pacs_worklist_items(connection)
        assert len(listed) == 1
        assert listed[0].id == created.id

        loaded = get_pacs_worklist_item(connection, created.id)
        assert loaded is not None
        assert loaded.patient_birth_date == "19900101"
        assert loaded.patient_sex == "F"
        assert loaded.chart_no == "C001"

        updated = update_pacs_worklist_status(connection, created.id, "completed")
        assert updated is True
        assert get_pacs_worklist_item(connection, created.id) is not None
        assert get_pacs_worklist_item(connection, created.id).status == "completed"

        assert delete_pacs_worklist_item(connection, created.id) is True
        assert get_pacs_worklist_item(connection, created.id) is None


def test_pacs_worklist_update_preserves_sync_state(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        created = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            patient_birth_date="19900101",
            patient_sex="F",
            chart_no="C001",
            study="CT",
            modality="CT",
            requested_at="2026-06-01",
            accession_or_order_id="A001",
            source="manual",
        )
        update_pacs_worklist_sync_state(
            connection,
            created.id,
            kaospacs_mwl_status="sent",
            kaospacs_mwl_last_synced_at="2026-06-28T12:00:00+00:00",
        )

        updated = update_pacs_worklist_item(
            connection,
            created.id,
            status="completed",
            patient_name="Alice Updated",
            patient_birth_date="19920202",
            patient_sex="F",
            chart_no="C009",
            study="MR",
            modality="MR",
            requested_at="2026-06-02",
            accession_or_order_id="A009",
            source="manual",
        )

    assert updated is not None
    assert updated.patient_name == "Alice Updated"
    assert updated.patient_birth_date == "19920202"
    assert updated.patient_sex == "F"
    assert updated.kaospacs_mwl_status == "sent"
    assert updated.kaospacs_mwl_last_synced_at == "2026-06-28T12:00:00+00:00"


def test_pacs_worklist_status_validation(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        created = create_pacs_worklist_item(connection, status="active")
        try:
            update_pacs_worklist_status(connection, created.id, "unknown")
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("Expected ValueError")

    assert "Unsupported PACS worklist status" in message


def test_pacs_audit_repository_create_list_filter_and_clear(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        create_pacs_audit_event(
            connection,
            event_type="poll",
            accession_or_order_id="ACC-1",
            summary="inserted=1, updated=0, skipped=0",
        )
        create_pacs_audit_event(
            connection,
            event_type="sync",
            accession_or_order_id="ACC-2",
            status_before="active",
            status_after="completed",
            summary="sent=1, cancelled=0, errors=0, skipped=0",
        )

        listed = list_pacs_audit_events(connection)
        filtered = list_pacs_audit_events(connection, event_type="poll")
        cleared = clear_pacs_audit_events(connection)

    assert len(listed) == 2
    assert listed[0].summary
    assert [event.event_type for event in filtered] == ["poll"]
    assert cleared == 2


def test_clear_audit_does_not_delete_worklist_items(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            accession_or_order_id="ACC-1",
            study="Chest",
            modality="CR",
        )
        create_pacs_audit_event(
            connection,
            event_type="poll",
            accession_or_order_id="ACC-1",
            summary="inserted=1, updated=0, skipped=0",
        )
        clear_pacs_audit_events(connection)
        rows = list_pacs_worklist_items(connection)

    assert len(rows) == 1


def test_pacs_worklist_list_filter(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        create_pacs_worklist_item(connection, status="active", patient_name="A")
        create_pacs_worklist_item(connection, status="completed", patient_name="B")
        create_pacs_worklist_item(connection, status="expired", patient_name="C")
        create_pacs_worklist_item(connection, status="cancelled", patient_name="D")
        create_pacs_worklist_item(connection, status="error", patient_name="E")

        assert len(list_pacs_worklist_items(connection)) == 5
        assert [i.status for i in list_pacs_worklist_items(connection, "active")] == [
            "active",
        ]
        assert [i.status for i in list_pacs_worklist_items(connection, "completed")] == ["completed"]
        assert [i.status for i in list_pacs_worklist_items(connection, "expired")] == ["expired"]
        assert [i.status for i in list_pacs_worklist_items(connection, "cancelled")] == [
            "cancelled"
        ]
        assert [i.status for i in list_pacs_worklist_items(connection, "error")] == ["error"]


def test_database_migration_rebuilds_legacy_done_statuses(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE pacs_worklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL CHECK (status IN ('active', 'done', 'cancelled', 'error')),
                patient_name TEXT,
                chart_no TEXT,
                study TEXT,
                modality TEXT,
                requested_at TEXT,
                accession_or_order_id TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                error_message TEXT,
                kaospacs_mwl_status TEXT NOT NULL DEFAULT 'not_sent',
                kaospacs_mwl_last_synced_at TEXT,
                kaospacs_mwl_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pacs_worklist_items
                (status, patient_name, accession_or_order_id, study, modality)
            VALUES ('done', 'Legacy', 'LEGACY-1', 'Chest', 'CR')
            """
        )
        connection.commit()

    initialize_database(db_path)

    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT status FROM pacs_worklist_items WHERE accession_or_order_id = 'LEGACY-1'"
        ).fetchone()
        create_pacs_worklist_item(
            connection,
            status="expired",
            accession_or_order_id="EXP-1",
            study="Chest",
            modality="CR",
        )

    assert row is not None
    assert row[0] == "completed"


def test_pacs_panel_instantiates_with_local_sqlite(tmp_path, monkeypatch) -> None:
    import os

    from PySide6.QtWidgets import QApplication

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])

    payload = {
        "patient_name": "Smoke Test",
        "chart_no": "SM-1",
        "study": "XR",
        "modality": "CR",
        "requested_at": "2026-06-28 10:00",
        "accession_or_order_id": "ACC-SMOKE",
        "status": "active",
    }

    class FakeDialog:
        DialogCode = pacs_panel.PacsWorklistDialog.DialogCode

        def __init__(self, parent=None, item=None):
            self.item = item

        def exec(self):
            return self.DialogCode.Accepted

        def get_form_data(self):
            return payload

    monkeypatch.setattr(pacs_panel, "PacsWorklistDialog", FakeDialog)

    db_path = Path(tmp_path / "KaosEghis.sqlite")
    panel = pacs_panel.PacsPanel(db_path=db_path)
    panel.refresh_rows()
    panel.manual_insert_row()
    panel.refresh_rows()
    panel.delete_selected()

    assert panel is not None


def test_pacs_panel_poll_status_remains_visible_after_poll_now(
    tmp_path, monkeypatch
) -> None:
    import os

    from PySide6.QtWidgets import QApplication

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel
    from KaosEghis.core.pacs_polling import PollResult

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        pacs_panel,
        "poll_eghis_image_orders_into_local_worklist",
        lambda _settings, _db_path, selected_date=None: PollResult(inserted=0, updated=1, skipped=2),
    )

    db_path = Path(tmp_path / "KaosEghis.sqlite")
    panel = pacs_panel.PacsPanel(db_path=db_path)
    panel.poll_now()

    assert panel.polling_status.text() == "Polling status: inserted=0, updated=1, skipped=2"


def test_pacs_panel_poll_now_handles_adapter_unavailable(
    tmp_path, monkeypatch
) -> None:
    import os

    from PySide6.QtWidgets import QApplication

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel
    from KaosEghis.core.pacs_polling import PollResult

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        pacs_panel,
        "poll_eghis_image_orders_into_local_worklist",
        lambda _settings, _db_path, selected_date=None: PollResult(
            inserted=0,
            updated=0,
            skipped=0,
            message="unavailable",
        ),
    )

    db_path = Path(tmp_path / "KaosEghis.sqlite")
    panel = pacs_panel.PacsPanel(db_path=db_path)
    panel.poll_now()

    assert panel.polling_status.text() == "Polling status: unavailable"
