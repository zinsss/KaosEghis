from pathlib import Path
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.db.database import connect, describe_database_path, initialize_database
from KaosEghis.db.repositories import DEFAULT_SETTINGS, get_settings, set_settings
from KaosEghis.core.kaospacs_client import check_kaospacs_health


class SettingsTab(QWidget):
    PACS_DEFAULTS = {
        "eghis_db_connection_string": DEFAULT_SETTINGS["eghis_db_connection_string"],
        "eghis_db_image_study_query": DEFAULT_SETTINGS["eghis_db_image_study_query"],
        "eghis_db_weekly_age_report_query": DEFAULT_SETTINGS["eghis_db_weekly_age_report_query"],
        "kaospacs_api_base_url": DEFAULT_SETTINGS["kaospacs_api_base_url"],
        "kaospacs_gateway_url": DEFAULT_SETTINGS["kaospacs_gateway_url"],
        "kaospacs_gateway_api_token": DEFAULT_SETTINGS["kaospacs_gateway_api_token"],
        "kaospacs_api_timeout_seconds": DEFAULT_SETTINGS["kaospacs_api_timeout_seconds"],
        "pacs_auto_poll_enabled": DEFAULT_SETTINGS["pacs_auto_poll_enabled"],
        "pacs_poll_interval_seconds": DEFAULT_SETTINGS["pacs_poll_interval_seconds"],
        "pacs_dry_run": DEFAULT_SETTINGS["pacs_dry_run"],
    }

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        self.process_name = QLineEdit()
        self.window_title = QLineEdit()
        self.kaosgdd_url = QLineEdit()
        self.credential_ref = QLineEdit()
        self.eghis_db_connection_string = QLineEdit()
        self.eghis_db_connection_string.setEchoMode(QLineEdit.EchoMode.Password)
        self.eghis_db_image_study_query = QPlainTextEdit()
        self.eghis_db_weekly_age_report_query = QPlainTextEdit()
        self.kaospacs_api_base_url = QLineEdit()
        self.kaospacs_gateway_url = QLineEdit()
        self.kaospacs_gateway_api_token = QLineEdit()
        self.kaospacs_gateway_api_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.kaospacs_api_timeout_seconds = QLineEdit()
        self.pacs_auto_poll_enabled = QCheckBox("Enable PACS auto poll")
        self.pacs_dry_run = QCheckBox("Enable PACS dry run")
        self.pacs_poll_interval_seconds = QSpinBox()
        self.pacs_poll_interval_seconds.setMinimum(15)
        self.pacs_poll_interval_seconds.setMaximum(86400)
        self.general_status = QLabel()
        self.pacs_status = QLabel()
        self.sqlite_path_label = QLabel()
        self.pacs_info = QLabel(
            "PACS settings control Eghis DB polling, KaosPACS API access, and "
            "KaosPACS Gateway imaging worklist access. "
            "Sync remains manual unless auto-poll is enabled; auto-poll only polls "
            "Eghis into local SQLite and never syncs to KaosPACS. "
            "PACS dry run keeps polling live but simulates sync and reconcile."
        )
        self.toggle_connection_string_button = QPushButton("Show")
        self.toggle_connection_string_button.clicked.connect(
            self.toggle_connection_string_visibility
        )

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_general_settings)

        reload_button = QPushButton("Reload Settings")
        reload_button.clicked.connect(self.load_settings)

        buttons = QHBoxLayout()
        buttons.addWidget(save_button)
        buttons.addWidget(reload_button)
        buttons.addStretch()

        form = QFormLayout()
        form.addRow("Eghis process name", self.process_name)
        form.addRow("Eghis window title contains", self.window_title)
        form.addRow("KaosGDD URL", self.kaosgdd_url)
        form.addRow("Credential reference name", self.credential_ref)

        connection_string_widget = QWidget()
        connection_string_row = QHBoxLayout(connection_string_widget)
        connection_string_row.setContentsMargins(0, 0, 0, 0)
        connection_string_row.addWidget(self.eghis_db_connection_string)
        connection_string_row.addWidget(self.toggle_connection_string_button)

        pacs_form = QFormLayout()
        pacs_form.addRow("Eghis DB connection string", connection_string_widget)
        pacs_form.addRow("Eghis image study query", self.eghis_db_image_study_query)
        pacs_form.addRow("Flu weekly report query", self.eghis_db_weekly_age_report_query)
        pacs_form.addRow("KaosPACS API base URL", self.kaospacs_api_base_url)
        pacs_form.addRow("KaosPACS Gateway URL", self.kaospacs_gateway_url)
        pacs_form.addRow("KaosPACS Gateway API token", self.kaospacs_gateway_api_token)
        pacs_form.addRow("KaosPACS API timeout seconds", self.kaospacs_api_timeout_seconds)
        pacs_form.addRow(self.pacs_auto_poll_enabled)
        pacs_form.addRow(self.pacs_dry_run)
        pacs_form.addRow("PACS poll interval seconds", self.pacs_poll_interval_seconds)

        self.save_pacs_button = QPushButton("Save PACS settings")
        self.save_pacs_button.clicked.connect(self.save_pacs_settings)
        self.reset_pacs_button = QPushButton("Reset PACS settings to defaults")
        self.reset_pacs_button.clicked.connect(self.reset_pacs_settings_to_defaults)
        self.test_kaospacs_button = QPushButton("Test KaosPACS connection")
        self.test_kaospacs_button.clicked.connect(self.test_kaospacs_connection)

        pacs_buttons = QGridLayout()
        pacs_buttons.addWidget(self.save_pacs_button, 0, 0)
        pacs_buttons.addWidget(self.reset_pacs_button, 0, 1)
        pacs_buttons.addWidget(self.test_kaospacs_button, 1, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.sqlite_path_label)
        layout.addWidget(self.general_status)
        layout.addSpacing(12)
        layout.addWidget(QLabel("PACS Settings"))
        layout.addWidget(self.pacs_info)
        layout.addLayout(pacs_form)
        layout.addLayout(pacs_buttons)
        layout.addWidget(self.pacs_status)
        layout.addStretch()

        self.load_settings()

    def load_settings(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        self.sqlite_path_label.setText(
            f"Active SQLite path: {describe_database_path(self._db_path)}"
        )
        self.process_name.setText(settings["eghis_process_name"])
        self.window_title.setText(settings["eghis_window_title_contains"])
        self.kaosgdd_url.setText(settings["kaosgdd_url"])
        self.credential_ref.setText(settings["credential_reference_name"])
        self.eghis_db_connection_string.setText(
            settings["eghis_db_connection_string"]
        )
        self.eghis_db_image_study_query.setPlainText(
            settings["eghis_db_image_study_query"]
        )
        self.eghis_db_weekly_age_report_query.setPlainText(
            settings["eghis_db_weekly_age_report_query"]
        )
        self.kaospacs_api_base_url.setText(settings["kaospacs_api_base_url"])
        self.kaospacs_gateway_url.setText(settings["kaospacs_gateway_url"])
        self.kaospacs_gateway_api_token.setText(settings["kaospacs_gateway_api_token"])
        self.kaospacs_api_timeout_seconds.setText(
            settings["kaospacs_api_timeout_seconds"]
        )
        self.pacs_auto_poll_enabled.setChecked(
            settings["pacs_auto_poll_enabled"].strip().lower() == "true"
        )
        self.pacs_dry_run.setChecked(
            settings["pacs_dry_run"].strip().lower() == "true"
        )
        self.pacs_poll_interval_seconds.setValue(
            self._normalize_poll_interval(settings["pacs_poll_interval_seconds"])
        )
        self.general_status.setText("Settings loaded.")
        self.pacs_status.setText("PACS settings loaded.")

    def save_general_settings(self) -> None:
        values = {
            "eghis_process_name": self.process_name.text().strip(),
            "eghis_window_title_contains": self.window_title.text().strip(),
            "kaosgdd_url": self.kaosgdd_url.text().strip(),
            "credential_reference_name": self.credential_ref.text().strip(),
        }
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(connection, values)
        self.general_status.setText("Settings saved.")

    def save_pacs_settings(self) -> None:
        validation_error = self._validate_pacs_settings()
        if validation_error is not None:
            self.pacs_status.setText(validation_error)
            return

        values = self._current_pacs_settings()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(connection, values)
        self.pacs_status.setText("PACS settings saved.")

    def reset_pacs_settings_to_defaults(self) -> None:
        self.eghis_db_connection_string.setText(
            self.PACS_DEFAULTS["eghis_db_connection_string"]
        )
        self.eghis_db_image_study_query.setPlainText(
            self.PACS_DEFAULTS["eghis_db_image_study_query"]
        )
        self.eghis_db_weekly_age_report_query.setPlainText(
            self.PACS_DEFAULTS["eghis_db_weekly_age_report_query"]
        )
        self.kaospacs_api_base_url.setText(self.PACS_DEFAULTS["kaospacs_api_base_url"])
        self.kaospacs_gateway_url.setText(self.PACS_DEFAULTS["kaospacs_gateway_url"])
        self.kaospacs_gateway_api_token.setText(self.PACS_DEFAULTS["kaospacs_gateway_api_token"])
        self.kaospacs_api_timeout_seconds.setText(
            self.PACS_DEFAULTS["kaospacs_api_timeout_seconds"]
        )
        self.pacs_auto_poll_enabled.setChecked(False)
        self.pacs_dry_run.setChecked(False)
        self.pacs_poll_interval_seconds.setValue(
            self._normalize_poll_interval(
                self.PACS_DEFAULTS["pacs_poll_interval_seconds"]
            )
        )
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(connection, self._current_pacs_settings())
        self.pacs_status.setText("PACS settings reset to defaults.")

    def test_kaospacs_connection(self) -> None:
        validation_error = self._validate_pacs_settings()
        if validation_error is not None:
            self.pacs_status.setText(validation_error)
            return

        try:
            healthy = check_kaospacs_health(self._current_pacs_settings())
        except RuntimeError:
            healthy = False
        if healthy:
            self.pacs_status.setText("KaosPACS connection OK.")
        else:
            self.pacs_status.setText("KaosPACS connection failed.")

    def toggle_connection_string_visibility(self) -> None:
        if self.eghis_db_connection_string.echoMode() == QLineEdit.EchoMode.Password:
            self.eghis_db_connection_string.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_connection_string_button.setText("Hide")
        else:
            self.eghis_db_connection_string.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_connection_string_button.setText("Show")

    def _current_pacs_settings(self) -> dict[str, str]:
        timeout_text = self.kaospacs_api_timeout_seconds.text().strip()
        normalized_timeout = self._normalize_timeout_text(timeout_text)
        return {
            "eghis_db_connection_string": self.eghis_db_connection_string.text().strip(),
            "eghis_db_image_study_query": self.eghis_db_image_study_query.toPlainText().strip(),
            "eghis_db_weekly_age_report_query": self.eghis_db_weekly_age_report_query.toPlainText().strip(),
            "kaospacs_api_base_url": self.kaospacs_api_base_url.text().strip(),
            "kaospacs_gateway_url": self.kaospacs_gateway_url.text().strip(),
            "kaospacs_gateway_api_token": self.kaospacs_gateway_api_token.text().strip(),
            "kaospacs_api_timeout_seconds": normalized_timeout,
            "pacs_auto_poll_enabled": "true" if self.pacs_auto_poll_enabled.isChecked() else "false",
            "pacs_dry_run": "true" if self.pacs_dry_run.isChecked() else "false",
            "pacs_poll_interval_seconds": str(
                self._normalize_poll_interval(self.pacs_poll_interval_seconds.value())
            ),
        }

    def _validate_pacs_settings(self) -> str | None:
        base_url = self.kaospacs_api_base_url.text().strip()
        if not base_url or not (
            base_url.startswith("http://") or base_url.startswith("https://")
        ):
            return "KaosPACS API base URL must start with http:// or https://."

        gateway_url = self.kaospacs_gateway_url.text().strip()
        if not gateway_url or not (
            gateway_url.startswith("http://") or gateway_url.startswith("https://")
        ):
            return "KaosPACS Gateway URL must start with http:// or https://."

        timeout_text = self.kaospacs_api_timeout_seconds.text().strip()
        try:
            timeout_value = float(timeout_text)
        except ValueError:
            return "KaosPACS API timeout seconds must be numeric and greater than 0."
        if timeout_value <= 0:
            return "KaosPACS API timeout seconds must be numeric and greater than 0."

        interval = self._normalize_poll_interval(self.pacs_poll_interval_seconds.value())
        self.pacs_poll_interval_seconds.setValue(interval)
        return None

    @staticmethod
    def _normalize_poll_interval(value: str | int) -> int:
        try:
            interval = int(value)
        except (TypeError, ValueError):
            return 60
        return max(15, interval)

    @staticmethod
    def _normalize_timeout_text(value: str) -> str:
        if not value:
            return ""
        timeout_value = float(value)
        if timeout_value.is_integer():
            return str(int(timeout_value))
        return str(timeout_value)
