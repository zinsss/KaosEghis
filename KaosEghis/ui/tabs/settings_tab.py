from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings, set_settings


class SettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.process_name = QLineEdit()
        self.window_title = QLineEdit()
        self.kaosgdd_url = QLineEdit()
        self.credential_ref = QLineEdit()
        self.eghis_db_connection_string = QLineEdit()
        self.eghis_db_image_study_query = QLineEdit()
        self.kaospacs_api_base_url = QLineEdit()
        self.kaospacs_api_timeout_seconds = QLineEdit()
        self.pacs_auto_poll_enabled = QLineEdit()
        self.pacs_poll_interval_seconds = QLineEdit()
        self.status = QLabel()

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)

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
        form.addRow("Eghis DB connection string", self.eghis_db_connection_string)
        form.addRow("Eghis image study query (placeholder)", self.eghis_db_image_study_query)
        form.addRow("KaosPACS API base URL", self.kaospacs_api_base_url)
        form.addRow("KaosPACS API timeout seconds", self.kaospacs_api_timeout_seconds)
        form.addRow("PACS auto poll enabled", self.pacs_auto_poll_enabled)
        form.addRow("PACS poll interval seconds", self.pacs_poll_interval_seconds)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        layout.addStretch()

        self.load_settings()

    def load_settings(self) -> None:
        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
        self.process_name.setText(settings["eghis_process_name"])
        self.window_title.setText(settings["eghis_window_title_contains"])
        self.kaosgdd_url.setText(settings["kaosgdd_url"])
        self.credential_ref.setText(settings["credential_reference_name"])
        self.eghis_db_connection_string.setText(
            settings["eghis_db_connection_string"]
        )
        self.eghis_db_image_study_query.setText(
            settings["eghis_db_image_study_query"]
        )
        self.kaospacs_api_base_url.setText(settings["kaospacs_api_base_url"])
        self.kaospacs_api_timeout_seconds.setText(
            settings["kaospacs_api_timeout_seconds"]
        )
        self.pacs_auto_poll_enabled.setText(settings["pacs_auto_poll_enabled"])
        self.pacs_poll_interval_seconds.setText(settings["pacs_poll_interval_seconds"])
        self.status.setText("Settings loaded.")

    def save_settings(self) -> None:
        values = {
            "eghis_process_name": self.process_name.text().strip(),
            "eghis_window_title_contains": self.window_title.text().strip(),
            "kaosgdd_url": self.kaosgdd_url.text().strip(),
            "credential_reference_name": self.credential_ref.text().strip(),
            "eghis_db_connection_string": self.eghis_db_connection_string.text().strip(),
            "eghis_db_image_study_query": self.eghis_db_image_study_query.text().strip(),
            "kaospacs_api_base_url": self.kaospacs_api_base_url.text().strip(),
            "kaospacs_api_timeout_seconds": self.kaospacs_api_timeout_seconds.text().strip(),
            "pacs_auto_poll_enabled": self.pacs_auto_poll_enabled.text().strip(),
            "pacs_poll_interval_seconds": self.pacs_poll_interval_seconds.text().strip(),
        }
        initialize_database()
        with connect() as connection:
            set_settings(connection, values)
        self.status.setText("Settings saved.")
