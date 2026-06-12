from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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
from KaosEghis.db.repositories import (
    UiTargetRecord,
    create_ui_target,
    delete_ui_target,
    get_settings,
    get_ui_target,
    list_ui_targets,
    update_ui_target,
)


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

        targets_title = QLabel("UI Targets")
        self.targets_table = QTableWidget(0, 4)
        self.targets_table.setHorizontalHeaderLabels(
            ["target_id", "automation_id", "name", "control_type"]
        )
        self.targets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.targets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        add_target_button = QPushButton("Add Target")
        add_target_button.clicked.connect(self.add_target)

        edit_target_button = QPushButton("Edit Target")
        edit_target_button.clicked.connect(self.edit_target)

        delete_target_button = QPushButton("Delete Target")
        delete_target_button.clicked.connect(self.delete_target)

        refresh_targets_button = QPushButton("Refresh Targets")
        refresh_targets_button.clicked.connect(self.refresh_targets)

        test_target_button = QPushButton("Test Target")
        test_target_button.clicked.connect(self.test_target)

        target_controls = QHBoxLayout()
        target_controls.addWidget(add_target_button)
        target_controls.addWidget(edit_target_button)
        target_controls.addWidget(delete_target_button)
        target_controls.addWidget(refresh_targets_button)
        target_controls.addWidget(test_target_button)
        target_controls.addStretch()

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
        layout.addWidget(targets_title)
        layout.addWidget(self.targets_table)
        layout.addLayout(target_controls)
        layout.addWidget(log)

        self.refresh_status()
        self.refresh_targets()

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

    def refresh_targets(self) -> None:
        initialize_database()
        with connect() as connection:
            targets = list_ui_targets(connection)

        self.targets_table.setRowCount(len(targets))
        for row_index, target in enumerate(targets):
            self.targets_table.setItem(row_index, 0, QTableWidgetItem(target.target_id))
            self.targets_table.setItem(row_index, 1, QTableWidgetItem(target.automation_id or ""))
            self.targets_table.setItem(row_index, 2, QTableWidgetItem(target.name or ""))
            self.targets_table.setItem(row_index, 3, QTableWidgetItem(target.control_type or ""))
        self.targets_table.resizeColumnsToContents()

    def add_target(self) -> None:
        dialog = UiTargetDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["target_id"]:
            self.log.setPlainText("Target ID is required.")
            return
        initialize_database()
        try:
            with connect() as connection:
                create_ui_target(connection, **values)
        except Exception as error:
            self.log.setPlainText(f"Could not add target: {error}")
            return
        self.refresh_targets()
        self.log.setPlainText("Target added.")

    def edit_target(self) -> None:
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target to edit.")
            return

        initialize_database()
        with connect() as connection:
            target = _get_required_target(connection, target_id)

        dialog = UiTargetDialog(self, target)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database()
        with connect() as connection:
            update_ui_target(
                connection,
                target_id,
                values["automation_id"],
                values["name"],
                values["control_type"],
            )
        self.refresh_targets()
        self.log.setPlainText("Target updated.")

    def delete_target(self) -> None:
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target to delete.")
            return
        initialize_database()
        with connect() as connection:
            deleted = delete_ui_target(connection, target_id)
        self.refresh_targets()
        self.log.setPlainText("Target deleted." if deleted else "Target not found.")

    def test_target(self) -> None:
        self.log.setPlainText("UIA target testing not implemented.")

    def _selected_target_id(self) -> str | None:
        selected = self.targets_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.targets_table.item(row, 0)
        if item is None:
            return None
        return item.text()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _get_required_target(connection, target_id: str) -> UiTargetRecord:
    target = get_ui_target(connection, target_id)
    if target is not None:
        return target
    raise RuntimeError("Target not found.")


class UiTargetDialog(QDialog):
    def __init__(self, parent: QWidget, target: UiTargetRecord | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("UI Target")

        self.target_id = QLineEdit(target.target_id if target else "")
        self.automation_id = QLineEdit(target.automation_id if target and target.automation_id else "")
        self.name = QLineEdit(target.name if target and target.name else "")
        self.control_type = QLineEdit(target.control_type if target and target.control_type else "")
        self.target_id.setEnabled(target is None)

        form = QFormLayout()
        form.addRow("target_id", self.target_id)
        form.addRow("automation_id", self.automation_id)
        form.addRow("name", self.name)
        form.addRow("control_type", self.control_type)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "target_id": self.target_id.text().strip(),
            "automation_id": self.automation_id.text().strip(),
            "name": self.name.text().strip(),
            "control_type": self.control_type.text().strip(),
        }
