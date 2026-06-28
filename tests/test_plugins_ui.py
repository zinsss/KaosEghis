import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_plugin_ui_modules_import() -> None:
    import KaosEghis.ui.plugins.flu_panel
    import KaosEghis.ui.plugins.pacs_panel
    import KaosEghis.ui.plugins.pacs_worklist_dialog
    import KaosEghis.ui.plugins.weekly_visits_panel
    import KaosEghis.ui.tabs.kaosclip_tab
    import KaosEghis.ui.tabs.plugins_tab


def test_plugins_tab_can_be_instantiated_without_backends() -> None:
    _app()

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()

    assert tab is not None


def test_pacs_panel_has_required_worklist_columns() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel()

    assert panel.WORKLIST_COLUMNS == [
        "Status",
        "Patient",
        "Chart No",
        "Study",
        "Modality",
        "Requested At",
        "Accession / Order ID",
        "KaosPACS Status",
        "Last Synced",
        "Sync Error",
    ]
    assert "PACS Worklist" in [label.text() for label in panel.findChildren(QLabel)]


def test_pacs_worklist_dialog_instantiates() -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog

    dialog = PacsWorklistDialog()

    assert dialog.status_combo.currentText() == "active"


def test_pacs_worklist_dialog_validation_rejects_missing_accession() -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog

    dialog = PacsWorklistDialog()
    dialog.study_edit.setText("Chest")
    dialog.modality_edit.setText("CR")

    assert dialog.validate_form() == "Accession / Order ID is required."


def test_pacs_worklist_dialog_validation_rejects_missing_study() -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog

    dialog = PacsWorklistDialog()
    dialog.accession_edit.setText("ACC-1")
    dialog.modality_edit.setText("CR")

    assert dialog.validate_form() == "Study is required."


def test_pacs_worklist_dialog_validation_rejects_missing_modality() -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog

    dialog = PacsWorklistDialog()
    dialog.accession_edit.setText("ACC-1")
    dialog.study_edit.setText("Chest")

    assert dialog.validate_form() == "Modality is required."


def test_pacs_panel_does_not_check_kaospacs_health_on_init(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.append(settings) or True,
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == []
    assert panel.pacs_server_status.text() == "KaosPACS server: not checked"


def test_pacs_panel_check_button_checks_kaospacs_health(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.append(settings) or True,
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.check_kaospacs_connection()

    assert len(calls) == 1
    assert panel.pacs_server_status.text() == "KaosPACS server: healthy"


def test_pacs_panel_refresh_stays_local_only(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = {"health": 0, "poll": 0, "sync": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_button.click()

    assert calls == {"health": 0, "poll": 0, "sync": 0}


def test_pacs_panel_poll_now_only_hits_polling(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult

    calls = {"health": 0, "poll": 0, "sync": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path: calls.__setitem__("poll", calls["poll"] + 1)
        or PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.poll_button.click()

    assert calls == {"health": 0, "poll": 1, "sync": 0}
    assert panel.polling_status.text() == "Polling status: inserted=1, updated=0, skipped=0"


def test_pacs_panel_sync_to_kaospacs_requires_confirmation_and_shows_summary(
    monkeypatch, tmp_path
) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_pacs_worklist_item,
        update_pacs_worklist_sync_state,
    )
    from PySide6.QtWidgets import QMessageBox

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-100",
        )
        cancelled_row = create_pacs_worklist_item(
            connection,
            status="cancelled",
            patient_name="Bob",
            accession_or_order_id="ACC-200",
        )
        update_pacs_worklist_sync_state(
            connection,
            cancelled_row.id,
            kaospacs_mwl_status="sent",
        )

    calls = {"health": 0, "poll": 0, "sync": 0}
    monkeypatch.setattr(
        pacs_panel_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1)
        or KaosPacsSyncResult(sent=1, cancelled=1, errors=0, skipped=0),
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.sync_button.click()

    assert calls == {"health": 1, "poll": 0, "sync": 1}
    assert (
        panel.polling_status.text()
        == "KaosPACS sync: active rows=1, cancelled pending rows=1, sent=1, cancelled=1, errors=0, skipped=0"
    )


def test_pacs_panel_sync_cancel_does_not_call_api(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_worklist_item
    from PySide6.QtWidgets import QMessageBox

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            accession_or_order_id="ACC-100",
        )

    calls = {"health": 0, "sync": 0}
    monkeypatch.setattr(
        pacs_panel_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.sync_button.click()

    assert calls == {"health": 0, "sync": 0}
    assert panel.polling_status.text() == "KaosPACS sync: canceled"


def test_pacs_panel_manual_insert_creates_local_row(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_pacs_worklist_items

    payload = {
        "patient_name": "Alice",
        "chart_no": "C001",
        "study": "Chest",
        "modality": "CR",
        "requested_at": "2026-06-28 09:30",
        "accession_or_order_id": "ACC-900",
        "status": "active",
    }

    class FakeDialog:
        DialogCode = pacs_panel_module.PacsWorklistDialog.DialogCode

        def __init__(self, parent=None, item=None):
            self.item = item

        def exec(self):
            return self.DialogCode.Accepted

        def get_form_data(self):
            return payload

    monkeypatch.setattr(pacs_panel_module, "PacsWorklistDialog", FakeDialog)

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.manual_insert_row()

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert len(rows) == 1
    assert rows[0].patient_name == "Alice"
    assert rows[0].source == "manual"
    assert rows[0].kaospacs_mwl_status == "not_sent"


def test_pacs_panel_edit_selected_updates_local_row(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_worklist_item, get_pacs_worklist_item

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        created = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28 09:30",
            accession_or_order_id="ACC-901",
            source="manual",
        )

    payload = {
        "patient_name": "Bob",
        "chart_no": "C002",
        "study": "Spine",
        "modality": "MR",
        "requested_at": "2026-06-29 10:00",
        "accession_or_order_id": "ACC-902",
        "status": "done",
    }

    class FakeDialog:
        DialogCode = pacs_panel_module.PacsWorklistDialog.DialogCode

        def __init__(self, parent=None, item=None):
            self.item = item

        def exec(self):
            return self.DialogCode.Accepted

        def get_form_data(self):
            return payload

    monkeypatch.setattr(pacs_panel_module, "PacsWorklistDialog", FakeDialog)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.worklist_table.selectRow(0)
    panel.edit_selected()

    with connect(db_path) as connection:
        updated = get_pacs_worklist_item(connection, created.id)

    assert updated is not None
    assert updated.patient_name == "Bob"
    assert updated.chart_no == "C002"
    assert updated.study == "Spine"
    assert updated.modality == "MR"
    assert updated.status == "done"


def test_pacs_panel_edit_sent_row_preserves_kaospacs_status(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_pacs_worklist_item,
        get_pacs_worklist_item,
        update_pacs_worklist_sync_state,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        created = create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            chart_no="C001",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28 09:30",
            accession_or_order_id="ACC-903",
            source="manual",
        )
        update_pacs_worklist_sync_state(
            connection,
            created.id,
            kaospacs_mwl_status="sent",
            kaospacs_mwl_last_synced_at="2026-06-28T12:00:00+00:00",
        )

    payload = {
        "patient_name": "Alice Updated",
        "chart_no": "C001",
        "study": "Chest Follow-up",
        "modality": "CR",
        "requested_at": "2026-06-28 09:30",
        "accession_or_order_id": "ACC-903",
        "status": "active",
    }

    class FakeDialog:
        DialogCode = pacs_panel_module.PacsWorklistDialog.DialogCode

        def __init__(self, parent=None, item=None):
            self.item = item

        def exec(self):
            return self.DialogCode.Accepted

        def get_form_data(self):
            return payload

    monkeypatch.setattr(pacs_panel_module, "PacsWorklistDialog", FakeDialog)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.worklist_table.selectRow(0)
    panel.edit_selected()

    with connect(db_path) as connection:
        updated = get_pacs_worklist_item(connection, created.id)

    assert updated is not None
    assert updated.study == "Chest Follow-up"
    assert updated.kaospacs_mwl_status == "sent"
    assert updated.kaospacs_mwl_last_synced_at == "2026-06-28T12:00:00+00:00"


def test_pacs_panel_edit_selected_with_no_row_does_not_crash(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.edit_selected()

    assert panel is not None


def test_flu_panel_can_load_week_without_backend() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel()
    panel.load_report()

    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert "Weekly - Influenza Report" in labels
    assert "Total Visits(Practice) Count: 0" in panel.report_output.toPlainText()


def test_weekly_visits_panel_can_load_without_backend(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel

    panel = WeeklyVisitsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.REPORT_COLUMNS == ["Age Group", "Visits", "Patients"]
    assert "unavailable" in panel.report_status.text()


def test_weekly_visits_panel_label_contains_kaoseghis_flu(tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel

    panel = WeeklyVisitsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    labels = [label.text() for label in panel.findChildren(QLabel)]

    assert "KaosEghis-flu weekly practice-count report" in labels


def test_plugins_tab_groups_weekly_panel_under_kaoseghis_flu() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()
    labels = [label.text() for label in tab.findChildren(QLabel)]

    assert "Weekly - Influenza Report" in labels
    assert "PACS Worklist" in labels
