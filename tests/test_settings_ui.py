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
    assert tab.eghis_db_connection_string.echoMode() == tab.eghis_db_connection_string.EchoMode.Password
    assert tab.kaospacs_gateway_api_token.echoMode() == tab.kaospacs_gateway_api_token.EchoMode.Password


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
    tab.kaospacs_gateway_api_token.setText("secret-token")
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
    assert settings["kaospacs_gateway_api_token"] == "secret-token"
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
    tab.kaospacs_gateway_api_token.setText("secret-token")
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
    assert settings["kaospacs_gateway_api_token"] == ""
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
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "must start with http:// or https://" in tab.pacs_status.text()


def test_invalid_gateway_url_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("ftp://bad")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert "Gateway URL must start with http:// or https://" in tab.pacs_status.text()


def test_invalid_timeout_rejected(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.settings_tab import SettingsTab

    tab = SettingsTab(db_path=tmp_path / "KaosEghis.sqlite")
    tab.kaospacs_api_base_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_gateway_url.setText("http://127.0.0.1:8060")
    tab.kaospacs_api_timeout_seconds.setText("nope")
    tab.save_pacs_settings()

    assert "must be numeric and greater than 0" in tab.pacs_status.text()


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
    tab.kaospacs_gateway_api_token.setText("gateway-secret")
    tab.kaospacs_api_timeout_seconds.setText("5")
    tab.save_pacs_settings()

    assert secret not in tab.general_status.text()
    assert secret not in tab.pacs_status.text()
    assert "gateway-secret" not in tab.general_status.text()
    assert "gateway-secret" not in tab.pacs_status.text()
