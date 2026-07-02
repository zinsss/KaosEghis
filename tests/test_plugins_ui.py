import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_plugin_ui_modules_import() -> None:
    import KaosEghis.core.kaospacs_gateway_client
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


def test_pacs_panel_default_page_is_imaging_worklist(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.page_stack.currentWidget() is panel.imaging_page
    assert panel.page_buttons["imaging"].isChecked() is True
    assert panel.imaging_filter_buttons["active"].isChecked() is True
    assert "inactive" in panel.imaging_filter_buttons
    assert panel.imaging_status_label.text() == "Not loaded yet."


def test_pacs_panel_navigation_buttons_are_exact(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    assert list(panel.page_buttons.keys()) == ["imaging", "operator_mode", "settings"]
    assert [button.text() for button in panel.page_buttons.values()] == [
        "Imaging Worklist",
        "Operator Mode",
        "Settings",
    ]


def test_pacs_panel_internal_navigation_switches_pages(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()
    assert panel.page_stack.currentWidget() is panel.operator_mode_page

    panel.page_buttons["settings"].click()
    assert panel.page_stack.currentWidget() is panel.settings_page


def test_imaging_worklist_calls_gateway(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "get_imaging_worklist",
        lambda settings: calls.append(settings) or [],
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == []
    panel.refresh_imaging_worklist()

    assert len(calls) == 1


def test_imaging_worklist_does_not_query_local_sources(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    monkeypatch.setattr(
        pacs_panel_module,
        "list_pacs_worklist_items",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("local worklist queried")),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("eghis poll queried")),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_imaging_worklist()


def test_imaging_worklist_korean_text_and_filters(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    rows = [
        {
            "state": "inactive",
            "AccessionNumber": "ACC-0",
            "PatientID": "P-0",
            "PatientName": "Dormant",
            "Modality": "CT",
            "Description": "Inactive row",
        },
        {
            "state": "active",
            "AccessionNumber": "ACC-1",
            "PatientID": "P-1",
            "PatientName": "홍길동",
            "Modality": "BMD",
            "ScheduledAt": "2026-07-01T09:00:00",
            "Description": "골밀도 검사",
        },
        {
            "state": "completed",
            "AccessionNumber": "ACC-2",
            "PatientID": "P-2",
            "PatientName": "Alice",
            "Modality": "CR",
            "CompletedAt": "2026-07-01T10:00:00",
            "Description": "Chest",
        },
        {
            "state": "expired",
            "AccessionNumber": "ACC-3",
            "PatientID": "P-3",
            "PatientName": "Bob",
            "Modality": "MR",
            "ExpiredAt": "2026-07-01T11:00:00",
            "Description": "Brain",
        },
        {
            "state": "cancelled",
            "AccessionNumber": "ACC-4",
            "PatientID": "P-4",
            "PatientName": "Carol",
            "Modality": "US",
            "CancelledAt": "2026-07-01T12:00:00",
            "Description": "Abdomen",
        },
    ]
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: rows)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_imaging_worklist()

    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 3).text() == "홍길동"
    assert panel.imaging_table.item(0, 9).text() == "골밀도 검사"

    panel.imaging_filter_buttons["completed"].click()
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 1).text() == "ACC-2"

    panel.imaging_filter_buttons["inactive"].click()
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 1).text() == "ACC-0"

    panel.imaging_filter_buttons["expired"].click()
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 1).text() == "ACC-3"

    panel.imaging_filter_buttons["cancelled"].click()
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 1).text() == "ACC-4"

    panel.imaging_filter_buttons["all"].click()
    assert panel.imaging_table.rowCount() == 5


def test_imaging_worklist_search_filters_rows(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(
        pacs_panel_module,
        "get_imaging_worklist",
        lambda settings: [
            {
                "state": "active",
                "AccessionNumber": "ACC-1",
                "PatientID": "P-1",
                "PatientName": "홍길동",
                "Modality": "BMD",
                "Description": "골밀도 검사",
            },
            {
                "state": "active",
                "AccessionNumber": "ACC-2",
                "PatientID": "P-2",
                "PatientName": "Alice",
                "Modality": "CR",
                "Description": "Chest",
            },
        ],
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_imaging_worklist()
    panel.imaging_search_input.setText("홍길동")
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 3).text() == "홍길동"


def test_gateway_unavailable_shows_safe_error(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(
        pacs_panel_module,
        "get_imaging_worklist",
        lambda settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_imaging_worklist()

    assert panel.imaging_status_label.text() == "KaosPACS Gateway unavailable"
    assert panel.imaging_table.rowCount() == 0


def test_inactive_imaging_rows_are_not_shown_under_active_filter(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(
        pacs_panel_module,
        "get_imaging_worklist",
        lambda settings: [
            {
                "state": "inactive",
                "AccessionNumber": "ACC-INACTIVE",
                "PatientID": "P-1",
                "PatientName": "홍길동",
                "Modality": "BMD",
                "Description": "골밀도 검사",
            }
        ],
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.refresh_imaging_worklist()

    assert panel.imaging_filter_buttons["active"].isChecked() is True
    assert panel.imaging_table.rowCount() == 0
    panel.imaging_filter_buttons["inactive"].click()
    assert panel.imaging_table.rowCount() == 1
    assert panel.imaging_table.item(0, 0).text() == "inactive"
    assert panel.imaging_table.item(0, 1).text() == "ACC-INACTIVE"


def test_pacs_panel_does_not_call_gateway_on_init(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "get_imaging_worklist",
        lambda settings: calls.append(settings) or [],
    )

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == []
    assert panel.imaging_status_label.text() == "Not loaded yet."


def test_operator_mode_contains_local_orders_controls(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()

    assert panel.refresh_button.text() == "Load from KaosEghis"
    assert panel.poll_button.text() == "Load from eGHIS"
    assert panel.sync_button.text() == "Sync to KaosPACS"
    assert panel.reconcile_button.text() == "Sync from KaosPACS"
    assert panel.manual_insert_button.text() == "Manual insert"
    assert panel.edit_button.text() == "Edit selected"
    assert panel.delete_button.text() == "Delete / Cancel selected"

def test_operator_mode_contains_pacs_log_controls(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()

    assert panel.refresh_audit_button.text() == "Refresh log"
    assert panel.clear_audit_button.text() == "Clear log"
    assert panel.copy_audit_button.text() == "Copy log summary"


def test_pacs_panel_has_no_separate_log_page(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert "log" not in panel.page_buttons
    assert panel.page_stack.count() == 3


def test_settings_diagnostics_hide_gateway_token(monkeypatch, tmp_path) -> None:
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
                "kaospacs_gateway_url": "http://127.0.0.1:8060",
                "kaospacs_gateway_api_token": "super-secret-token",
            },
        )

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.page_buttons["settings"].click()

    all_text = " ".join(label.text() for label in panel.findChildren(type(panel.diagnostics_sqlite_label)))
    assert "super-secret-token" not in all_text
    assert "http://127.0.0.1:8060" in panel.diagnostics_gateway_url_label.text()


def test_pacs_panel_default_auto_poll_setting_is_false(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.auto_poll_checkbox.isChecked() is False
    assert panel.interval_spinbox.value() == 60
    assert panel._poll_timer.isActive() is False


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
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

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
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == {"health": 0, "poll": 0, "sync": 0, "reconcile": 0}
    assert panel.polling_status.text().startswith("Startup readiness: sqlite=ok, settings=ok")


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
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()
    panel.refresh_button.click()

    assert calls == {"health": 0, "poll": 0, "sync": 0}


def test_pacs_panel_apply_settings_persists_values(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    db_path = tmp_path / "KaosEghis.sqlite"
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.page_buttons["operator_mode"].click()
    panel.auto_poll_checkbox.setChecked(True)
    panel.interval_spinbox.setValue(45)
    panel.apply_polling_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)

    assert settings["pacs_auto_poll_enabled"] == "true"
    assert settings["pacs_poll_interval_seconds"] == "45"


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
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1)
        or PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1),
    )
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()
    panel.poll_button.click()

    assert calls == {"health": 0, "poll": 1, "sync": 0}
    assert panel.polling_status.text() == "Polling status: inserted=1, updated=0, skipped=0"


def test_pacs_panel_manual_poll_schedules_deferred_imaging_refresh(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult

    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_imaging_refresh", lambda: scheduled.append(True))

    panel.poll_now()

    assert scheduled == [True]


def test_pacs_panel_auto_poll_schedules_deferred_imaging_refresh(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.pacs_polling import PollResult

    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_imaging_refresh", lambda: scheduled.append(True))

    panel._handle_poll_timer_tick()

    assert scheduled == [True]


def test_pacs_panel_sync_schedules_deferred_imaging_refresh(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult

    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_imaging_refresh", lambda: scheduled.append(True))

    panel.sync_to_kaospacs()

    assert scheduled == [True]


def test_pacs_panel_reconcile_schedules_deferred_imaging_refresh(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsReconcileResult

    monkeypatch.setattr(
        pacs_panel_module,
        "reconcile_kaospacs_worklist_to_local",
        lambda settings, db_path: KaosPacsReconcileResult(
            completed=1,
            expired=0,
            skipped=0,
            errors=0,
        ),
    )
    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_imaging_refresh", lambda: scheduled.append(True))

    panel.reconcile_from_kaospacs()

    assert scheduled == [True]


def test_operator_mode_loads_local_rows_when_opened(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_pacs_worklist_item
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            study="Chest",
            modality="CR",
            requested_at=date.today().strftime("%Y-%m-%d 09:30:00"),
            accession_or_order_id="ACC-1",
        )

    monkeypatch.setattr(pacs_panel_module, "get_imaging_worklist", lambda settings: [])
    panel = pacs_panel_module.PacsPanel(db_path=db_path)

    assert panel.worklist_table.rowCount() == 0
    panel.page_buttons["operator_mode"].click()
    assert panel.worklist_table.rowCount() == 1
    assert panel.worklist_table.item(0, 6).text() == "ACC-1"
