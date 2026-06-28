from pathlib import Path

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_pacs_worklist_item,
    delete_pacs_worklist_item,
    get_pacs_worklist_item,
    list_pacs_worklist_items,
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
    assert "chart_no" in columns
    assert "study" in columns
    assert "modality" in columns
    assert "requested_at" in columns
    assert "accession_or_order_id" in columns
    assert "source" in columns
    assert "error_message" in columns


def test_pacs_worklist_repository_crud(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        created = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
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

        listed = list_pacs_worklist_items(connection)
        assert len(listed) == 1
        assert listed[0].id == created.id

        loaded = get_pacs_worklist_item(connection, created.id)
        assert loaded is not None
        assert loaded.chart_no == "C001"

        updated = update_pacs_worklist_status(connection, created.id, "done")
        assert updated is True
        assert get_pacs_worklist_item(connection, created.id) is not None
        assert get_pacs_worklist_item(connection, created.id).status == "done"

        assert delete_pacs_worklist_item(connection, created.id) is True
        assert get_pacs_worklist_item(connection, created.id) is None


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


def test_pacs_worklist_list_filter(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        create_pacs_worklist_item(connection, status="active", patient_name="A")
        create_pacs_worklist_item(connection, status="done", patient_name="B")
        create_pacs_worklist_item(connection, status="cancelled", patient_name="C")
        create_pacs_worklist_item(connection, status="error", patient_name="D")

        assert len(list_pacs_worklist_items(connection)) == 4
        assert [i.status for i in list_pacs_worklist_items(connection, "active")] == [
            "active",
        ]
        assert [i.status for i in list_pacs_worklist_items(connection, "done")] == ["done"]
        assert [i.status for i in list_pacs_worklist_items(connection, "cancelled")] == [
            "cancelled"
        ]
        assert [i.status for i in list_pacs_worklist_items(connection, "error")] == ["error"]


def test_pacs_panel_instantiates_with_local_sqlite(tmp_path) -> None:
    import os

    from PySide6.QtWidgets import QApplication

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])

    db_path = Path(tmp_path / "KaosEghis.sqlite")
    panel = PacsPanel(db_path=db_path)
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
        lambda _settings, _db_path: PollResult(inserted=0, updated=1, skipped=2),
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
        lambda _settings, _db_path: PollResult(
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
