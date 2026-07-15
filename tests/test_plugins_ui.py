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


def test_pacs_panel_default_page_is_admin(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    class FakeWebView(QWidget):
        def __init__(self):
            super().__init__()
            self.loaded_url = None

        def setUrl(self, url):
            self.loaded_url = url.toString()

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", FakeWebView)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.page_stack.currentWidget() is panel.admin_page
    assert panel.page_buttons["admin"].isChecked() is True
    assert panel.admin_status_label.text() == "KaosPACS Admin: embedded web view"
    assert panel.admin_web_view.loaded_url == "http://192.168.0.200:8070/imaging/worklist"


def test_pacs_panel_navigation_buttons_are_exact(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert list(panel.page_buttons.keys()) == ["admin", "operator_mode", "settings"]
    assert [button.text() for button in panel.page_buttons.values()] == [
        "KaosPACS Admin",
        "Operator Mode",
        "Settings",
    ]


def test_pacs_panel_internal_navigation_switches_pages(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    panel.page_buttons["operator_mode"].click()
    assert panel.page_stack.currentWidget() is panel.operator_mode_page

    panel.page_buttons["settings"].click()
    assert panel.page_stack.currentWidget() is panel.settings_page


def test_pacs_panel_embedded_admin_fallback_without_webengine(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.admin_web_view is None
    assert panel.admin_status_label.text() == "KaosPACS Admin: embedded browser unavailable"


def test_reload_admin_page_uses_configured_url(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    class FakeWebView(QWidget):
        def __init__(self):
            super().__init__()
            self.loaded_url = None

        def setUrl(self, url):
            self.loaded_url = url.toString()

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"kaospacs_web_admin_url": "http://example:8070/imaging/worklist"})

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", FakeWebView)
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.reload_admin_page()

    assert panel.admin_url_label.text() == "http://example:8070/imaging/worklist"
    assert panel.admin_web_view.loaded_url == "http://example:8070/imaging/worklist"


def test_open_external_browser_uses_configured_url(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"kaospacs_web_admin_url": "http://example:8070/imaging/worklist"})

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    opened = []
    monkeypatch.setattr(pacs_panel_module.webbrowser, "open", lambda url: opened.append(url) or True)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.open_admin_page_externally()

    assert opened == ["http://example:8070/imaging/worklist"]
    assert panel.admin_url_label.text() == "http://example:8070/imaging/worklist"


def test_no_mark_done_button_or_completion_method_remains(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.core.kaospacs_client as kaospacs_client
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert hasattr(panel, "mark_selected_imaging_row_done") is False
    assert hasattr(panel, "imaging_mark_done_button") is False
    assert hasattr(kaospacs_client, "complete_kaospacs_order") is False


def test_default_settings_include_kaospacs_web_admin_url() -> None:
    from KaosEghis.db.repositories import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["kaospacs_web_admin_url"] == "http://192.168.0.200:8070/imaging/worklist"


def test_operator_mode_contains_local_orders_controls(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
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

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()

    assert panel.refresh_audit_button.text() == "Refresh log"
    assert panel.clear_audit_button.text() == "Clear log"
    assert panel.copy_audit_button.text() == "Copy log summary"


def test_pacs_panel_has_no_separate_log_page(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
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
                "kaospacs_web_admin_url": "http://192.168.0.200:8070/imaging/worklist",
                "kaospacs_gateway_api_token": "super-secret-token",
            },
        )

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel.page_buttons["settings"].click()

    all_text = " ".join(label.text() for label in panel.findChildren(type(panel.diagnostics_sqlite_label)))
    assert "super-secret-token" not in all_text
    assert "http://127.0.0.1:8060" in panel.diagnostics_gateway_url_label.text()
    assert "http://192.168.0.200:8070/imaging/worklist" in panel.diagnostics_web_admin_url_label.text()


def test_pacs_panel_default_auto_poll_setting_is_false(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
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


def test_pacs_panel_checks_kaospacs_health_on_init(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "check_kaospacs_health",
        lambda settings: calls.append(settings) or True,
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert len(calls) == 1
    assert panel.pacs_server_status.text() == "KaosPACS server: healthy"


def test_pacs_panel_startup_checks_health_but_does_not_poll_sync_or_reconcile(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    calls = {"health": 0, "poll": 0, "sync": 0, "reconcile": 0, "db": 0}
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
    monkeypatch.setattr(
        pacs_panel_module,
        "run_readonly_query",
        lambda *_args, **_kwargs: calls.__setitem__("db", calls["db"] + 1) or (["?column?"], [(1,)]),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert calls == {"health": 1, "poll": 0, "sync": 0, "reconcile": 0, "db": 0}
    assert panel.polling_status.text().startswith("Startup readiness: sqlite=ok, settings=ok")


def test_pacs_panel_startup_checks_eghis_db_connectivity(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"eghis_db_connection_string": "dbname=test"})

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "run_readonly_query",
        lambda connection_string, query: calls.append((connection_string, query)) or (["?column?"], [(1,)]),
    )

    panel = pacs_panel_module.PacsPanel(db_path=db_path)

    assert calls == [("dbname=test", "SELECT 1")]
    assert panel.eghis_db_status.text() == "Eghis DB: healthy"


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
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()
    panel.refresh_button.click()

    assert calls == {"health": 1, "poll": 0, "sync": 0}


def test_pacs_panel_apply_settings_persists_values(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    db_path = tmp_path / "KaosEghis.sqlite"
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
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
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
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
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1)
        or KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel.page_buttons["operator_mode"].click()
    panel.poll_button.click()

    assert calls == {"health": 2, "poll": 1, "sync": 1}
    assert (
        panel.polling_status.text()
        == "Polling status: inserted=1, updated=0, skipped=0 | KaosPACS sync: sent=1, cancelled=0, errors=0, skipped=0"
    )


def test_pacs_panel_manual_poll_schedules_deferred_admin_reload(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
    from KaosEghis.core.pacs_polling import PollResult

    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_admin_reload", lambda: scheduled.append(True))

    panel.poll_now()

    assert scheduled == [True]


def test_pacs_panel_auto_poll_schedules_deferred_admin_reload(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
    from KaosEghis.core.pacs_polling import PollResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"eghis_db_connection_string": "dbname=test"})

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_admin_reload", lambda: scheduled.append(True))

    panel._handle_poll_timer_tick()

    assert scheduled == [True]


def test_pacs_panel_auto_poll_hits_sync(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
    from KaosEghis.core.pacs_polling import PollResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"eghis_db_connection_string": "dbname=test"})

    calls = {"poll": 0, "sync": 0}
    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda settings, db_path, selected_date=None: calls.__setitem__("poll", calls["poll"] + 1)
        or PollResult(inserted=1, updated=0, skipped=0),
    )
    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: calls.__setitem__("sync", calls["sync"] + 1)
        or KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel._handle_poll_timer_tick()

    assert calls == {"poll": 1, "sync": 1}


def test_pacs_panel_auto_poll_stops_when_kaospacs_unavailable(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: False)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    panel._poll_timer.start(60000)
    poll_calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda *args, **kwargs: poll_calls.append(True),
    )

    panel._handle_poll_timer_tick()

    assert poll_calls == []
    assert panel._poll_timer.isActive() is False
    assert panel.polling_status.text() == "Auto poll stopped: KaosPACS unavailable"


def test_pacs_panel_auto_poll_stops_when_eghis_db_unavailable(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {"eghis_db_connection_string": "dbname=test"})

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(
        pacs_panel_module,
        "run_readonly_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=db_path)
    panel._poll_timer.start(60000)
    poll_calls = []
    monkeypatch.setattr(
        pacs_panel_module,
        "poll_eghis_image_orders_into_local_worklist",
        lambda *args, **kwargs: poll_calls.append(True),
    )

    panel._handle_poll_timer_tick()

    assert poll_calls == []
    assert panel._poll_timer.isActive() is False
    assert panel.polling_status.text() == "Auto poll stopped: Eghis DB unavailable"


def test_pacs_panel_sync_schedules_deferred_admin_reload(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module
    from KaosEghis.core.kaospacs_client import KaosPacsSyncResult

    monkeypatch.setattr(
        pacs_panel_module,
        "sync_local_worklist_to_kaospacs",
        lambda settings, db_path: KaosPacsSyncResult(sent=1, cancelled=0, errors=0, skipped=0),
    )
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_admin_reload", lambda: scheduled.append(True))

    panel.sync_to_kaospacs()

    assert scheduled == [True]


def test_pacs_panel_reconcile_schedules_deferred_admin_reload(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)

    panel = pacs_panel_module.PacsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    scheduled = []
    monkeypatch.setattr(panel, "_schedule_admin_reload", lambda: scheduled.append(True))

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

    monkeypatch.setattr(pacs_panel_module, "QWebEngineView", None)
    panel = pacs_panel_module.PacsPanel(db_path=db_path)

    assert panel.worklist_table.rowCount() == 0
    panel.page_buttons["operator_mode"].click()
    assert panel.worklist_table.rowCount() == 1
    assert panel.worklist_table.item(0, 6).text() == "ACC-1"
