from pathlib import Path
from PySide6.QtCore import Signal
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.db.database import connect, describe_database_path, initialize_database
from KaosEghis.db.repositories import DEFAULT_SETTINGS, get_settings, set_settings
from KaosEghis.core.kaospacs_client import check_kaospacs_health


class SettingsTab(QWidget):
    general_settings_saved = Signal()

    TOP_PAGES = ["General", "PACS"]
    PACS_DEFAULTS = {
        "eghis_db_connection_string": DEFAULT_SETTINGS["eghis_db_connection_string"],
        "eghis_db_image_study_query": DEFAULT_SETTINGS["eghis_db_image_study_query"],
        "eghis_db_weekly_age_report_query": DEFAULT_SETTINGS["eghis_db_weekly_age_report_query"],
        "kaospacs_api_base_url": DEFAULT_SETTINGS["kaospacs_api_base_url"],
        "kaospacs_gateway_url": DEFAULT_SETTINGS["kaospacs_gateway_url"],
        "kaospacs_web_admin_url": DEFAULT_SETTINGS["kaospacs_web_admin_url"],
        "kaospacs_gateway_api_token": DEFAULT_SETTINGS["kaospacs_gateway_api_token"],
        "kaospacs_patient_context_bind_host": DEFAULT_SETTINGS["kaospacs_patient_context_bind_host"],
        "kaospacs_patient_context_port": DEFAULT_SETTINGS["kaospacs_patient_context_port"],
        "kaospacs_integration_token": DEFAULT_SETTINGS["kaospacs_integration_token"],
        "kaospacs_api_timeout_seconds": DEFAULT_SETTINGS["kaospacs_api_timeout_seconds"],
        "pacs_auto_poll_enabled": DEFAULT_SETTINGS["pacs_auto_poll_enabled"],
        "pacs_poll_interval_seconds": DEFAULT_SETTINGS["pacs_poll_interval_seconds"],
        "pacs_dry_run": DEFAULT_SETTINGS["pacs_dry_run"],
    }

    def __init__(
        self,
        db_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.process_name = QLineEdit()
        self.window_title = QLineEdit()
        self.patient_alert_enabled = QCheckBox("Enable *** patient-note alert")
        self.patient_alert_chart_scope_automation_id = QLineEdit()
        self.patient_alert_chart_automation_id = QLineEdit()
        self.patient_alert_chart_name = QLineEdit()
        self.patient_alert_memo_scope_automation_id = QLineEdit()
        self.patient_alert_memo_automation_id = QLineEdit()
        self.patient_alert_memo_name = QLineEdit()
        self.patient_alert_memo_ancestor_path = QPlainTextEdit()
        self.patient_alert_memo_ancestor_path.setPlaceholderText(
            "Paste the Ancestors section from Inspect.exe here."
        )
        self.patient_alert_memo_ancestor_path.setMaximumHeight(110)
        self.kaosgdd_url = QLineEdit()
        self.memos_url = QLineEdit()
        self.paperless_url = QLineEdit()
        self.stirling_pdf_url = QLineEdit()
        self.rhwp_url = QLineEdit()
        self.wikijs_url = QLineEdit()
        self.sftpgo_url = QLineEdit()
        self.credential_ref = QLineEdit()
        self.eghis_db_connection_string = QLineEdit()
        self.eghis_db_connection_string.setEchoMode(QLineEdit.EchoMode.Password)
        self.eghis_db_image_study_query = QPlainTextEdit()
        self.eghis_db_weekly_age_report_query = QPlainTextEdit()
        self.kaospacs_api_base_url = QLineEdit()
        self.kaospacs_gateway_url = QLineEdit()
        self.kaospacs_web_admin_url = QLineEdit()
        self.kaospacs_gateway_api_token = QLineEdit()
        self.kaospacs_gateway_api_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.kaospacs_patient_context_bind_host = QLineEdit()
        self.kaospacs_patient_context_port = QLineEdit()
        self.kaospacs_integration_token = QLineEdit()
        self.kaospacs_integration_token.setEchoMode(QLineEdit.EchoMode.Password)
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
            "KaosPACS Web admin access. "
            "Sync remains manual unless auto-poll is enabled; auto-poll only polls "
            "Eghis into local SQLite and never syncs to KaosPACS. "
            "PACS dry run keeps polling live but simulates sync and reconcile. "
            "Patient-context API host/port are for KaosPACS fallback demographic lookup."
        )
        self.toggle_connection_string_button = QPushButton("Show")
        self.toggle_connection_string_button.clicked.connect(
            self.toggle_connection_string_visibility
        )
        self.save_general_button = QPushButton("Save Settings")
        self.save_general_button.clicked.connect(self.save_general_settings)

        self.reload_general_button = QPushButton("Reload Settings")
        self.reload_general_button.clicked.connect(self.load_settings)

        general_buttons = QHBoxLayout()
        general_buttons.addWidget(self.save_general_button)
        general_buttons.addWidget(self.reload_general_button)
        general_buttons.addStretch()

        form = QFormLayout()
        form.addRow("Eghis process name", self.process_name)
        form.addRow("Eghis window title contains", self.window_title)
        form.addRow(self.patient_alert_enabled)
        form.addRow(
            "Chart No scope Automation ID",
            self.patient_alert_chart_scope_automation_id,
        )
        form.addRow(
            "Chart No Automation ID", self.patient_alert_chart_automation_id
        )
        form.addRow("Chart No UIA name", self.patient_alert_chart_name)
        form.addRow(
            "Patient memo scope Automation ID",
            self.patient_alert_memo_scope_automation_id,
        )
        form.addRow(
            "Patient memo textbox Automation ID",
            self.patient_alert_memo_automation_id,
        )
        form.addRow("Patient memo textbox UIA name", self.patient_alert_memo_name)
        form.addRow(
            "Patient memo ancestor path",
            self.patient_alert_memo_ancestor_path,
        )
        form.addRow("KaosGDD URL", self.kaosgdd_url)
        form.addRow("Memos URL", self.memos_url)
        form.addRow("Paperless URL", self.paperless_url)
        form.addRow("Stirling-PDF URL", self.stirling_pdf_url)
        form.addRow("rHWP URL", self.rhwp_url)
        form.addRow("Wiki.js URL", self.wikijs_url)
        form.addRow("SFTPGo URL", self.sftpgo_url)
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
        pacs_form.addRow("KaosPACS Web admin URL", self.kaospacs_web_admin_url)
        pacs_form.addRow("KaosPACS Gateway API token", self.kaospacs_gateway_api_token)
        pacs_form.addRow("Patient-context bind host", self.kaospacs_patient_context_bind_host)
        pacs_form.addRow("Patient-context port", self.kaospacs_patient_context_port)
        pacs_form.addRow("Patient-context integration token", self.kaospacs_integration_token)
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

        self.general_page = QWidget()
        general_layout = QVBoxLayout(self.general_page)
        general_layout.addLayout(form)
        general_layout.addLayout(general_buttons)
        general_layout.addWidget(self.sqlite_path_label)
        general_layout.addWidget(self.general_status)
        general_layout.addStretch()

        self.pacs_page = QWidget()
        pacs_layout = QVBoxLayout(self.pacs_page)
        pacs_layout.addWidget(QLabel("PACS Settings"))
        pacs_layout.addWidget(self.pacs_info)
        pacs_layout.addLayout(pacs_form)
        pacs_layout.addLayout(pacs_buttons)
        pacs_layout.addWidget(self.pacs_status)
        pacs_layout.addStretch()

        for page in (self.general_page, self.pacs_page):
            self.stacked_widget.addWidget(page)

        for index, name in enumerate(self.TOP_PAGES):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_page(page_index)
            )
            self.nav_buttons[name] = button
            self.top_nav_row.addWidget(button)
        self.top_nav_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(self.top_nav_row)
        layout.addWidget(self.stacked_widget, 1)

        self.show_page(0)
        self.load_settings()

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

    def load_settings(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        self.sqlite_path_label.setText(
            f"Active SQLite path: {describe_database_path(self._db_path)}"
        )
        self.process_name.setText(settings["eghis_process_name"])
        self.window_title.setText(settings["eghis_window_title_contains"])
        self.patient_alert_enabled.setChecked(
            settings["eghis_patient_alert_enabled"].strip().lower() == "true"
        )
        self.patient_alert_chart_scope_automation_id.setText(
            settings["eghis_patient_alert_chart_scope_automation_id"]
        )
        self.patient_alert_chart_automation_id.setText(
            settings["eghis_patient_alert_chart_automation_id"]
        )
        self.patient_alert_chart_name.setText(
            settings["eghis_patient_alert_chart_name"]
        )
        self.patient_alert_memo_scope_automation_id.setText(
            settings["eghis_patient_alert_memo_scope_automation_id"]
        )
        self.patient_alert_memo_automation_id.setText(
            settings["eghis_patient_alert_memo_automation_id"]
        )
        self.patient_alert_memo_name.setText(
            settings["eghis_patient_alert_memo_name"]
        )
        self.patient_alert_memo_ancestor_path.setPlainText(
            settings["eghis_patient_alert_memo_ancestor_path"]
        )
        self.kaosgdd_url.setText(settings["kaosgdd_url"])
        self.memos_url.setText(settings["memos_url"])
        self.paperless_url.setText(settings["paperless_url"])
        self.stirling_pdf_url.setText(settings["stirling_pdf_url"])
        self.rhwp_url.setText(settings["rhwp_url"])
        self.wikijs_url.setText(settings["wikijs_url"])
        self.sftpgo_url.setText(settings["sftpgo_url"])
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
        self.kaospacs_web_admin_url.setText(settings["kaospacs_web_admin_url"])
        self.kaospacs_gateway_api_token.setText(settings["kaospacs_gateway_api_token"])
        self.kaospacs_patient_context_bind_host.setText(settings["kaospacs_patient_context_bind_host"])
        self.kaospacs_patient_context_port.setText(settings["kaospacs_patient_context_port"])
        self.kaospacs_integration_token.setText(settings["kaospacs_integration_token"])
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
            "eghis_patient_alert_enabled": (
                "true" if self.patient_alert_enabled.isChecked() else "false"
            ),
            "eghis_patient_alert_chart_scope_automation_id": (
                self.patient_alert_chart_scope_automation_id.text().strip()
            ),
            "eghis_patient_alert_chart_automation_id": (
                self.patient_alert_chart_automation_id.text().strip()
            ),
            "eghis_patient_alert_chart_name": (
                self.patient_alert_chart_name.text().strip()
            ),
            "eghis_patient_alert_memo_scope_automation_id": (
                self.patient_alert_memo_scope_automation_id.text().strip()
            ),
            "eghis_patient_alert_memo_automation_id": (
                self.patient_alert_memo_automation_id.text().strip()
            ),
            "eghis_patient_alert_memo_name": (
                self.patient_alert_memo_name.text().strip()
            ),
            "eghis_patient_alert_memo_ancestor_path": (
                self.patient_alert_memo_ancestor_path.toPlainText().strip()
            ),
            "kaosgdd_url": self.kaosgdd_url.text().strip(),
            "memos_url": self.memos_url.text().strip(),
            "paperless_url": self.paperless_url.text().strip(),
            "stirling_pdf_url": self.stirling_pdf_url.text().strip(),
            "rhwp_url": self.rhwp_url.text().strip(),
            "wikijs_url": self.wikijs_url.text().strip(),
            "sftpgo_url": self.sftpgo_url.text().strip(),
            "credential_reference_name": self.credential_ref.text().strip(),
        }
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(connection, values)
        self.general_status.setText("Settings saved.")
        self.general_settings_saved.emit()

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
        self.kaospacs_web_admin_url.setText(self.PACS_DEFAULTS["kaospacs_web_admin_url"])
        self.kaospacs_gateway_api_token.setText(self.PACS_DEFAULTS["kaospacs_gateway_api_token"])
        self.kaospacs_patient_context_bind_host.setText(self.PACS_DEFAULTS["kaospacs_patient_context_bind_host"])
        self.kaospacs_patient_context_port.setText(self.PACS_DEFAULTS["kaospacs_patient_context_port"])
        self.kaospacs_integration_token.setText(self.PACS_DEFAULTS["kaospacs_integration_token"])
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
            "kaospacs_web_admin_url": self.kaospacs_web_admin_url.text().strip(),
            "kaospacs_gateway_api_token": self.kaospacs_gateway_api_token.text().strip(),
            "kaospacs_patient_context_bind_host": self.kaospacs_patient_context_bind_host.text().strip(),
            "kaospacs_patient_context_port": self.kaospacs_patient_context_port.text().strip(),
            "kaospacs_integration_token": self.kaospacs_integration_token.text().strip(),
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

        web_admin_url = self.kaospacs_web_admin_url.text().strip()
        if not web_admin_url or not (
            web_admin_url.startswith("http://") or web_admin_url.startswith("https://")
        ):
            return "KaosPACS Web admin URL must start with http:// or https://."

        bind_host = self.kaospacs_patient_context_bind_host.text().strip()
        if not bind_host:
            return "Patient-context bind host is required."

        port_text = self.kaospacs_patient_context_port.text().strip()
        try:
            port_value = int(port_text)
        except ValueError:
            return "Patient-context port must be an integer between 1 and 65535."
        if port_value <= 0 or port_value > 65535:
            return "Patient-context port must be an integer between 1 and 65535."

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
