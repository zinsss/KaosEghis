from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.emr_detector import (
    check_process_running,
    find_window_by_title_contains,
    get_active_window_title,
    is_target_window_active,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


class EghisAssistTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Eghis Assist")
        title.setObjectName("pageTitle")

        search = QLineEdit()
        search.setPlaceholderText("Search automation, clipboard presets, workflows...")

        self.process_name = QLabel()
        self.window_title = QLabel()
        self.process_running = QLabel()
        self.window_found = QLabel()
        self.active_window = QLabel()
        self.target_active = QLabel()

        status_form = QFormLayout()
        status_form.addRow("Configured process name", self.process_name)
        status_form.addRow("Configured window title fragment", self.window_title)
        status_form.addRow("Process running", self.process_running)
        status_form.addRow("Window found", self.window_found)
        status_form.addRow("Active window title", self.active_window)
        status_form.addRow("Target active", self.target_active)

        refresh_button = QPushButton("Refresh Status")
        refresh_button.clicked.connect(self.refresh_status)

        self.clipboard_text = QTextEdit()
        self.clipboard_text.setPlaceholderText("Enter harmless text to copy for clipboard testing.")

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self.copy_to_clipboard)

        clipboard_controls = QHBoxLayout()
        clipboard_controls.addWidget(copy_button)
        clipboard_controls.addStretch()

        log = QPlainTextEdit()
        self.log = log
        log.setReadOnly(True)
        log.setPlaceholderText("Status and safety messages will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(search)
        layout.addLayout(status_form)
        layout.addWidget(refresh_button)
        layout.addWidget(self.clipboard_text)
        layout.addLayout(clipboard_controls)
        layout.addWidget(log)

        self.refresh_status()

    def refresh_status(self) -> None:
        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)

        process_name = settings["eghis_process_name"]
        title_fragment = settings["eghis_window_title_contains"]
        active_title = get_active_window_title()

        self.process_name.setText(process_name)
        self.window_title.setText(title_fragment)
        self.process_running.setText(_yes_no(check_process_running(process_name)))
        self.window_found.setText(_yes_no(find_window_by_title_contains(title_fragment)))
        self.active_window.setText(active_title or "(none)")
        self.target_active.setText(_yes_no(is_target_window_active(title_fragment)))
        self.log.setPlainText("Status refreshed.")

    def copy_to_clipboard(self) -> None:
        copy_text(self.clipboard_text.toPlainText())
        self.log.setPlainText("Copied")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
