import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_settings_panel_instantiates(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")

    assert tab is not None
    assert tab.TOP_PAGES == ["General", "PACS"]
    assert tab.stacked_widget.count() == 2
    assert tab.eghis_db_connection_string.echoMode() == tab.eghis_db_connection_string.EchoMode.Password
    assert tab.kaospacs_gateway_api_token.echoMode() == tab.kaospacs_gateway_api_token.EchoMode.Password
    assert tab.kaospacs_integration_token.echoMode() == tab.kaospacs_integration_token.EchoMode.Password
    assert tab.patient_alert_enabled.isChecked() is True
    assert tab.patient_alert_chart_automation_id.text() == "792028"
    assert tab.patient_alert_memo_scope_automation_id.text() == ""
    assert tab.patient_alert_memo_automation_id.text() == "TreatmentPtntMemo"
    assert tab.patient_alert_memo_name.text() == ""
    assert tab.patient_alert_memo_ancestor_path.toPlainText() == ""


def test_save_general_settings_persists_patient_alert_targets(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    db_path = tmp_path / "KaosEghis.sqlite"
    tab = SettingsTab(db_path=db_path)
    tab.patient_alert_enabled.setChecked(True)
    tab.patient_alert_chart_scope_automation_id.setText("PatientHeader")
    tab.patient_alert_chart_automation_id.setText("ChartId")
    tab.patient_alert_chart_name.setText("Chart No")
    tab.patient_alert_memo_scope_automation_id.setText("MemoArea")
    tab.patient_alert_memo_automation_id.setText("MemoText")
    tab.patient_alert_memo_name.setText("Patient memo")
    tab.patient_alert_memo_ancestor_path.setPlainText(
        'Ancestors:\n"Patient memo" pane\n"진료실" window'
    )
    tab.save_general_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)

    assert settings["eghis_patient_alert_enabled"] == "true"
    assert settings["eghis_patient_alert_chart_scope_automation_id"] == "PatientHeader"
    assert settings["eghis_patient_alert_chart_automation_id"] == "ChartId"
    assert settings["eghis_patient_alert_chart_name"] == "Chart No"
    assert settings["eghis_patient_alert_memo_scope_automation_id"] == "MemoArea"
    assert settings["eghis_patient_alert_memo_automation_id"] == "MemoText"
    assert settings["eghis_patient_alert_memo_name"] == "Patient memo"
    assert settings["eghis_patient_alert_memo_ancestor_path"] == (
        'Ancestors:\n"Patient memo" pane\n"진료실" window'
    )


def test_previous_patient_alert_defaults_upgrade_to_verified_targets(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "eghis_patient_alert_chart_automation_id": "lblChartNo",
                "eghis_patient_alert_memo_scope_automation_id": (
                    "TreatmentPtntMemoDoctor"
                ),
                "eghis_patient_alert_memo_automation_id": "eghisRichTextBox",
                "eghis_patient_alert_memo_name": "eghisRichTexbox",
            },
        )
        settings = get_settings(connection)

    assert settings["eghis_patient_alert_chart_automation_id"] == "792028"
    assert settings["eghis_patient_alert_memo_scope_automation_id"] == ""
    assert settings["eghis_patient_alert_memo_automation_id"] == "TreatmentPtntMemo"
    assert settings["eghis_patient_alert_memo_name"] == ""


def test_settings_internal_pages_are_reachable(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")

    tab.show_page(1)
    assert tab.stacked_widget.currentWidget() is tab.pacs_page
    tab.show_page(0)
    assert tab.stacked_widget.currentWidget() is tab.general_page


def test_save_pacs_settings_persists_values(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    db_path = tmp_path / "KaosEghis.sqlite"
    tab = SettingsTab(db_path=db_path)
    tab.eghis_db_connection_string.setText("Host=x;Password=secret")
    tab.eghis_db_image_study_query.setPlainText("SELECT 1")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_gateway_api_token.setText("secret-token")
    tab.kaospacs_patient_context_bind_host.setText("192.168.0.100")
    tab.kaospacs_patient_context_port.setText("8877")
    tab.kaospacs_integration_token.setText("integration-secret")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.pacs_auto_poll_enabled.setChecked(True)
    tab.pacs_dry_run.setChecked(True)
    tab.pacs_poll_interval_seconds.setValue(45)
    tab.save_pacs_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)

    assert settings["eghis_db_connection_string"] == "Host=x;Password=secret"
    assert settings["eghis_db_image_study_query"] == "SELECT 1"
    assert settings["kaospacs_api_base_url"] == "http://127.0.0.1:8060"
    assert settings["kaospacs_gateway_url"] == "http://127.0.0.1:8060"
    assert settings["kaospacs_web_admin_url"] == "http://192.168.0.200:8070/imaging/worklist"
    assert settings["kaospacs_gateway_api_token"] == "secret-token"
    assert settings["kaospacs_patient_context_bind_host"] == "192.168.0.100"
    assert settings["kaospacs_patient_context_port"] == "8877"
    assert settings["kaospacs_integration_token"] == "integration-secret"
    assert settings["kaospacs_api_timeout_seconds"] == "5"
    assert settings["pacs_auto_poll_enabled"] == "true"
    assert settings["pacs_dry_run"] == "true"
    assert settings["pacs_poll_interval_seconds"] == "45"


def test_reset_pacs_settings_restores_defaults(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    db_path = tmp_path / "KaosEghis.sqlite"
    tab = SettingsTab(db_path=db_path)
    tab.eghis_db_connection_string.setText("Host=x;Password=secret")
    tab.eghis_db_image_study_query.setPlainText("SELECT 1")
    tab.kaospacs_api_base_url.setText("https://gateway-api.example")
    tab.kaospacs_gateway_url.setText("https://gateway")
    tab.kaospacs_web_admin_url.setText("https://admin")
    tab.kaospacs_gateway_api_token.setText("secret-token")
    tab.kaospacs_patient_context_bind_host.setText("192.168.0.100")
    tab.kaospacs_patient_context_port.setText("8877")
    tab.kaospacs_integration_token.setText("integration-secret")
    tab.kaospacs_api_timeout_seconds.setText("9")
    tab.pacs_auto_poll_enabled.setChecked(True)
    tab.pacs_dry_run.setChecked(True)
    tab.pacs_poll_interval_seconds.setValue(45)
    tab.reset_pacs_settings_to_defaults()

    with connect(db_path) as connection:
        settings = get_settings(connection)

    assert settings["eghis_db_connection_string"] == ""
    assert settings["eghis_db_image_study_query"] == ""
    assert settings["kaospacs_api_base_url"] == "http://127.0.0.1:8060"
    assert settings["kaospacs_gateway_url"] == "http://127.0.0.1:8060"
    assert settings["kaospacs_web_admin_url"] == "http://192.168.0.200:8070/imaging/worklist"
    assert settings["kaospacs_gateway_api_token"] == ""
    assert settings["kaospacs_patient_context_bind_host"] == "127.0.0.1"
    assert settings["kaospacs_patient_context_port"] == "8765"
    assert settings["kaospacs_integration_token"] == ""
    assert settings["kaospacs_api_timeout_seconds"] == "5"
    assert settings["pacs_auto_poll_enabled"] == "false"
    assert settings["pacs_dry_run"] == "false"
    assert settings["pacs_poll_interval_seconds"] == "60"


def test_invalid_url_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("ftp://bad")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "must start with http:// or https://" in tab.pacs_status.text()


def test_invalid_gateway_url_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("ftp://bad")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "Gateway URL must start with http:// or https://" in tab.pacs_status.text()


def test_invalid_web_admin_url_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("ftp://bad")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "Web admin URL must start with http:// or https://" in tab.pacs_status.text()


def test_invalid_timeout_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_api_timeout_seconds.setText("nope")
    tab.save_pacs_settings()

    assert "must be numeric and greater than 0" in tab.pacs_status.text()


def test_invalid_patient_context_port_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_patient_context_bind_host.setText("192.168.0.100")
    tab.kaospacs_patient_context_port.setText("70000")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "Patient-context port must be an integer between 1 and 65535." in tab.pacs_status.text()


def test_interval_below_15_is_clamped(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.pacs_poll_interval_seconds.setValue(15)
    tab.save_pacs_settings()

    assert tab.pacs_poll_interval_seconds.value() == 15


def test_test_kaospacs_calls_health_only(monkeypatch, tmp_path) -> None:
    _app()

    import KaosEghis.ui.tabs.settings_tab as settings_tab_module

    calls = {"health": 0}
    monkeypatch.setattr(
        settings_tab_module,
        "check_kaospacs_health",
        lambda settings: calls.__setitem__("health", calls["health"] + 1) or True,
    )

    tab = settings_tab_module.SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.test_kaospacs_connection()

    assert calls == {"health": 1}
    assert tab.pacs_status.text() == "KaosPACS connection OK."


def test_connection_string_not_displayed_in_status_labels(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    secret = "Host=x;Password=topsecret"
    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.eghis_db_connection_string.setText(secret)
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_web_admin_url.setText("http://192.168.0.200:8070/imaging/worklist")
    tab.kaospacs_gateway_api_token.setText("gateway-secret")
    tab.kaospacs_integration_token.setText("integration-secret")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert secret not in tab.general_status.text()
    assert secret not in tab.pacs_status.text()
    assert "gateway-secret" not in tab.general_status.text()
    assert "gateway-secret" not in tab.pacs_status.text()
    assert "integration-secret" not in tab.general_status.text()
    assert "integration-secret" not in tab.pacs_status.text()
