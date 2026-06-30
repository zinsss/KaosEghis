import os
from datetime import date, timedelta

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


def test_plugins_tab_can_be_instantiated_without_backends(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

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
    assert any(button.text() == "Reconcile from KaosPACS" for button in panel.findChildren(type(panel.refresh_button)))
    assert any(button.text() == "Refresh audit" for button in panel.findChildren(type(panel.refresh_button)))


def test_pacs_panel_default_auto_poll_setting_is_false(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.auto_poll_checkbox.isChecked() is False
    assert panel.interval_spinbox.value() == 60
    assert panel._poll_timer.isActive() is False
    assert panel.date_selector.date().toPython() == panel._selected_date


def test_pacs_panel_previous_next_today_buttons_change_selected_date(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    original = panel._selected_date

    panel.previous_day_button.click()
    assert panel._selected_date == original - timedelta(days=1)

    panel.next_day_button.click()
    assert panel._selected_date == original

    panel.previous_day_button.click()
    panel.today_button.click()
    assert panel._selected_date == date.today()


def test_pacs_panel_invalid_interval_falls_back_to_60() -> None:
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    assert PacsPanel._normalize_poll_interval("invalid") == 60
    assert PacsPanel._normalize_poll_interval(None) == 60


def test_pacs_panel_interval_below_15_is_clamped_to_15() -> None:
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    assert PacsPanel._normalize_poll_interval("1") == 15
    assert PacsPanel._normalize_poll_interval(14) == 15


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


def test_pacs_panel_startup_does_not_call_poll_sync_or_health(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = {"health": 0, "poll": 0, "sync": 0, "reconcile": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "reconcile_kaospacs_worklist_to_local",
        lambda settings, db_path: calls.__setitem__("reconcile", calls["reconcile"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == {"health": 0, "poll": 0, "sync": 0, "reconcile": 0}
    assert panel.polling_status.text().startswith("Startup readiness: sqlite=ok, settings=ok")


def test_pacs_panel_startup_readiness_shows_active_sqlite_path(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = PacsPanel(db_path=db_path)

    assert f"db={db_path.resolve()}" in panel.polling_status.text()


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
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_button.click()

    assert calls == {"health": 0, "poll": 0, "sync": 0}


def test_pacs_panel_refresh_shows_selected_date_only(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_worklist_item
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 09:30:00",
            accession_or_order_id="ACC-1",
        )
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Bob",
            study="Spine",
            modality="MR",
            requested_at="2026-07-01 09:30:00",
            accession_or_order_id="ACC-2",
        )

    panel = PacsPanel(db_path=db_path)
    panel._set_selected_date(date(2026, 6, 30))

    assert panel.worklist_table.rowCount() == 1
    assert panel.worklist_table.item(0, 6).text() == "ACC-1"


def test_pacs_panel_apply_settings_persists_values(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = PacsPanel(db_path=db_path)
    panel.auto_poll_checkbox.setChecked(True)
    panel.interval_spinbox.setValue(45)
    panel.apply_polling_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)

    assert settings["pacs_auto_poll_enabled"] == "true"
    assert settings["pacs_poll_interval_seconds"] == "45"


def test_pacs_panel_timer_starts_only_when_enabled(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.auto_poll_checkbox.setChecked(True)
    panel.interval_spinbox.setValue(45)
    panel.apply_polling_settings()

    assert panel._poll_timer.isActive() is True
    assert panel._poll_timer.interval() == 45000


def test_pacs_panel_timer_stops_when_disabled(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.auto_poll_checkbox.setChecked(True)
    panel.interval_spinbox.setValue(45)
    panel.apply_polling_settings()
    panel.auto_poll_checkbox.setChecked(False)
    panel.apply_polling_settings()

    assert panel._poll_timer.isActive() is False


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
    selected_dates: list[date] = []
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1)
        or selected_dates.append(selected_date)
        or PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel._set_selected_date(date(2026, 6, 30))
    panel.poll_button.click()

    assert calls == {"health": 0, "poll": 1, "sync": 0}
    assert selected_dates == [date(2026, 6, 30)]
    assert panel.polling_status.text() == "Polling status: inserted=1, updated=0, skipped=0"
    assert panel.last_poll_time_label.text() != "Last poll time: never"
    assert panel.last_poll_result_label.text() == "Last poll result: inserted=1, updated=0, skipped=0"


def test_pacs_panel_timer_tick_calls_poll_not_sync(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult

    calls = {"poll": 0, "sync": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1)
        or PollResult(inserted=0, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel._handle_poll_timer_tick()

    assert calls == {"poll": 1, "sync": 0}


def test_pacs_panel_reconcile_button_calls_reconcile_not_poll_or_sync(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsReconcileResult

    calls = {"poll": 0, "sync": 0, "reconcile": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "reconcile_kaospacs_worklist_to_local",
        lambda settings, db_path: calls.__setitem__("reconcile", calls["reconcile"] + 1)
        or KaosPacsReconcileResult(done=1, cancelled=2, skipped=3, errors=0),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.reconcile_button.click()

    assert calls == {"poll": 0, "sync": 0, "reconcile": 1}
    assert (
        panel.polling_status.text()
        == "KaosPACS reconcile: done=1, cancelled=2, skipped=3, errors=0"
    )


def test_pacs_panel_overlapping_poll_is_skipped(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = {"poll": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel._poll_in_progress = True
    panel._handle_poll_timer_tick()

    assert calls["poll"] == 0
    assert panel.last_poll_result_label.text() == "Last poll result: skipped overlap"
    assert panel.polling_status.text() == "Polling status: skipped overlap"


def test_pacs_panel_saved_auto_poll_true_starts_timer_without_polling(
    tmp_path, monkeypatch
) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "pacs_auto_poll_enabled": "true",
                "pacs_poll_interval_seconds": "45",
            },
        )

    calls = {"poll": 0, "sync": 0, "health": 0}
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)

    assert panel._poll_timer.isActive() is True
    assert panel._poll_timer.interval() == 45000
    assert calls == {"poll": 0, "sync": 0, "health": 0}


def test_pacs_panel_saved_invalid_interval_falls_back_to_60_on_startup(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "pacs_auto_poll_enabled": "true",
                "pacs_poll_interval_seconds": "abc",
            },
        )

    panel = PacsPanel(db_path=db_path)

    assert panel.interval_spinbox.value() == 60
    assert panel._poll_timer.isActive() is True
    assert panel._poll_timer.interval() == 60000


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
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1)
        or KaosPacsSyncResult(sent=1, cancelled=1, errors=0, skipped=0),
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.sync_button.click()

    assert calls == {"health": 0, "poll": 0, "sync": 1}
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
    from KaosEghis.db.repositories import list_pacs_audit_events, list_pacs_worklist_items

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
        audit_rows = list_pacs_audit_events(connection)

    assert len(rows) == 1
    assert rows[0].patient_name == "Alice"
    assert rows[0].source == "manual"
    assert rows[0].kaospacs_mwl_status == "not_sent"
    assert audit_rows[0].event_type == "manual_insert"
    assert "Alice" not in audit_rows[0].summary


def test_pacs_panel_edit_selected_updates_local_row(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_pacs_worklist_item,
        get_pacs_worklist_item,
        list_pacs_audit_events,
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
    panel._set_selected_date(date(2026, 6, 28))
    panel.worklist_table.selectRow(0)
    panel.edit_selected()

    with connect(db_path) as connection:
        updated = get_pacs_worklist_item(connection, created.id)
        audit_rows = list_pacs_audit_events(connection)

    assert updated is not None
    assert updated.patient_name == "Bob"
    assert updated.chart_no == "C002"
    assert updated.study == "Spine"
    assert updated.modality == "MR"
    assert updated.status == "done"
    assert audit_rows[0].event_type == "manual_edit"
    assert "Bob" not in audit_rows[0].summary


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
    panel._set_selected_date(date(2026, 6, 28))
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


def test_pacs_panel_cancel_selected_creates_audit_event(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_pacs_worklist_item,
        list_pacs_audit_events,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            accession_or_order_id="ACC-100",
            study="Chest",
            modality="CR",
            requested_at="2026-06-28 09:30:00",
        )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel._set_selected_date(date(2026, 6, 28))
    panel.worklist_table.selectRow(0)
    panel.delete_selected()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "cancel_selected"
    assert audit_rows[0].status_before == "active"
    assert audit_rows[0].status_after == "cancelled"


def test_pacs_panel_poll_creates_aggregate_audit_only(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_pacs_audit_events

    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda _settings, _db_path, selected_date=None: PollResult(inserted=1, updated=2, skipped=3),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.poll_now()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "poll"
    assert audit_rows[0].summary == "inserted=1, updated=2, skipped=3"
    assert "patient" not in audit_rows[0].summary.lower()


def test_pacs_panel_removed_active_row_moves_from_active_to_cancelled(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_audit_event, create_pacs_worklist_item
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="cancelled",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 09:30:00",
            accession_or_order_id="ACC-1",
            error_message="order removed from eGHIS MWL",
        )
        create_pacs_audit_event(
            connection,
            event_type="poll",
            status_before="active",
            status_after="cancelled",
            summary="active order removed from eGHIS MWL -> marked cancelled",
        )

    panel = PacsPanel(db_path=db_path)
    panel._set_selected_date(date(2026, 6, 30))
    panel._active_filter = "active"
    panel.refresh_rows()
    assert panel.worklist_table.rowCount() == 0

    panel._active_filter = "cancelled"
    panel.refresh_rows()
    assert panel.worklist_table.rowCount() == 1
    assert panel.worklist_table.item(0, 0).text() == "cancelled"


def test_pacs_panel_sync_creates_aggregate_audit_only(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_worklist_item, list_pacs_audit_events
    from PySide6.QtWidgets import QMessageBox

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

    monkeypatch.setattr(
        pacs_panel_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: True,
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.sync_button.click()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "sync"
    assert audit_rows[0].summary == "sent=1, cancelled=0, errors=0, skipped=0"


def test_pacs_panel_reconcile_creates_aggregate_audit_only(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsReconcileResult
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_pacs_audit_events

    monkeypatch.setattr(
        pacs_panel_module,
        "reconcile_kaospacs_worklist_to_local",
        lambda settings, db_path: KaosPacsReconcileResult(done=1, cancelled=2, skipped=3, errors=0),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.reconcile_button.click()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "reconcile"
    assert audit_rows[0].summary == "done=1, cancelled=2, skipped=3, errors=0"


def test_pacs_panel_audit_error_is_sanitized_before_storage(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsReconcileResult
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_pacs_audit_events

    monkeypatch.setattr(
        pacs_panel_module,
        "reconcile_kaospacs_worklist_to_local",
        lambda settings, db_path: KaosPacsReconcileResult(
            done=0,
            cancelled=0,
            skipped=0,
            errors=1,
            message="Connection refused for patient Alice during payload parse failure",
        ),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.reconcile_button.click()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "error"
    assert audit_rows[0].summary == "connection failed"
    assert audit_rows[0].error_message == "connection failed"
    assert "Alice" not in audit_rows[0].error_message


def test_pacs_panel_poll_message_is_sanitized_before_storage(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_pacs_audit_events

    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda _settings, _db_path, selected_date=None: PollResult(
            inserted=0,
            updated=0,
            skipped=0,
            message="Query rejected after payload parse error for Sample Patient",
        ),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.poll_now()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)

    assert audit_rows[0].event_type == "poll"
    assert audit_rows[0].summary == "invalid payload"
    assert "Sample Patient" not in audit_rows[0].summary


def test_pacs_panel_copy_audit_summary_excludes_patient_name(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_audit_event

    copied = {}
    monkeypatch.setattr(
        pacs_panel_module,
        "copy_text",
        lambda text: copied.setdefault("text", text),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_audit_event(
            connection,
            event_type="poll",
            accession_or_order_id="ACC-1",
            summary="inserted=1, updated=0, skipped=0",
        )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.copy_audit_summary()

    assert "Alice" not in copied["text"]
    assert "ACC-1" in copied["text"]


def test_pacs_panel_copy_audit_summary_uses_sanitized_error_text(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database

    copied = {}
    monkeypatch.setattr(
        pacs_panel_module,
        "copy_text",
        lambda text: copied.setdefault("text", text),
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel._log_audit_error(
        summary="Connection refused for patient Alice",
        error_message="Timeout while connecting to Alice endpoint",
    )
    panel.refresh_audit()
    panel.copy_audit_summary()

    assert "Alice" not in copied["text"]
    assert "timeout" in copied["text"]


def test_pacs_panel_clear_audit_does_not_delete_worklist_items(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_pacs_audit_event,
        create_pacs_worklist_item,
        list_pacs_audit_events,
        list_pacs_worklist_items,
    )
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        pacs_panel_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

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

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.clear_audit()

    with connect(db_path) as connection:
        audit_rows = list_pacs_audit_events(connection)
        worklist_rows = list_pacs_worklist_items(connection)

    assert audit_rows == []
    assert len(worklist_rows) == 1


def test_flu_panel_can_load_week_without_backend(tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel(db_path=tmp_path / "KaosEghis.sqlite")
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


def test_plugins_tab_groups_weekly_panel_under_kaoseghis_flu(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()
    labels = [label.text() for label in tab.findChildren(QLabel)]

    assert "Weekly - Influenza Report" in labels
    assert "PACS Worklist" in labels
