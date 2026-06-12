from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QAbstractItemView,
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
    ALLOWED_MACRO_ACTIONS,
    ItemRecord,
    MacroStepRecord,
    UiTargetRecord,
    create_item,
    create_macro_step,
    create_ui_target,
    delete_item,
    delete_macro_step,
    delete_ui_target,
    get_item,
    get_settings,
    get_ui_target,
    list_ui_targets,
    list_items,
    list_macro_steps,
    reorder_macro_steps,
    update_item,
    update_macro_step,
    update_ui_target,
    validate_macro_dry_run,
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
        self.targets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

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

        macros_title = QLabel("Macros")
        self.macros_table = QTableWidget(0, 3)
        self.macros_table.setHorizontalHeaderLabels(["id", "name", "enabled"])
        self.macros_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.macros_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.macros_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        add_macro_button = QPushButton("Add Macro")
        add_macro_button.clicked.connect(self.add_macro)

        edit_macro_button = QPushButton("Edit Macro")
        edit_macro_button.clicked.connect(self.edit_macro)

        delete_macro_button = QPushButton("Delete Macro")
        delete_macro_button.clicked.connect(self.delete_macro)

        dry_run_button = QPushButton("Dry Run")
        dry_run_button.clicked.connect(self.dry_run_macro)

        macro_controls = QHBoxLayout()
        macro_controls.addWidget(add_macro_button)
        macro_controls.addWidget(edit_macro_button)
        macro_controls.addWidget(delete_macro_button)
        macro_controls.addWidget(dry_run_button)
        macro_controls.addStretch()

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
        layout.addWidget(macros_title)
        layout.addWidget(self.macros_table)
        layout.addLayout(macro_controls)
        layout.addWidget(log)

        self.refresh_status()
        self.refresh_targets()
        self.refresh_macros()

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
        if not _confirm(self, f"Delete UI target '{target_id}'?"):
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

    def refresh_macros(self) -> None:
        initialize_database()
        with connect() as connection:
            macros = list_items(connection, "macro")

        self.macros_table.setRowCount(len(macros))
        for row_index, macro in enumerate(macros):
            self.macros_table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
            self.macros_table.setItem(row_index, 1, QTableWidgetItem(macro.name))
            self.macros_table.setItem(row_index, 2, QTableWidgetItem(_yes_no(macro.is_enabled)))
        self.macros_table.resizeColumnsToContents()

    def add_macro(self) -> None:
        dialog = MacroEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            self.log.setPlainText("Macro name is required.")
            return
        initialize_database()
        with connect() as connection:
            item = create_item(connection, values["name"], "macro", values["is_enabled"])
            for step in values["steps"]:
                create_macro_step(connection, item.id, **step)
            reorder_macro_steps(connection, item.id)
        self.refresh_macros()
        self.log.setPlainText("Macro added.")

    def edit_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to edit.")
            return
        initialize_database()
        with connect() as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)

        dialog = MacroEditorDialog(self, item, steps)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database()
        with connect() as connection:
            update_item(connection, item_id, values["name"], "macro", values["is_enabled"])
            for step in list_macro_steps(connection, item_id):
                delete_macro_step(connection, step.id)
            for step in values["steps"]:
                create_macro_step(connection, item_id, **step)
            reorder_macro_steps(connection, item_id)
        self.refresh_macros()
        self.log.setPlainText("Macro updated.")

    def delete_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to delete.")
            return
        if not _confirm(self, "Delete selected macro?"):
            return
        initialize_database()
        with connect() as connection:
            deleted = delete_item(connection, item_id)
        self.refresh_macros()
        self.log.setPlainText("Macro deleted." if deleted else "Macro not found.")

    def dry_run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to dry run.")
            return

        initialize_database()
        with connect() as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)
            errors = validate_macro_dry_run(connection, item_id)

        lines = [f"Dry run only: {item.name}"]
        if errors:
            lines.append("Validation errors:")
            lines.extend(f"- {error}" for error in errors)
        else:
            lines.append("Planned steps:")
            if not steps:
                lines.append("- No steps defined.")
            for step in steps:
                target = f" target={step.target_id}" if step.target_id else ""
                value = f" value={step.value}" if step.value else ""
                lines.append(
                    f"- {step.step_order}: {step.action}{target}{value} "
                    f"timeout={step.timeout_seconds}s retries={step.retries}"
                )
        self.log.setPlainText("\n".join(lines))

    def _selected_macro_id(self) -> int | None:
        selected = self.macros_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.macros_table.item(row, 0)
        if item is None:
            return None
        return int(item.text())


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _get_required_target(connection, target_id: str) -> UiTargetRecord:
    target = get_ui_target(connection, target_id)
    if target is not None:
        return target
    raise RuntimeError("Target not found.")


def _get_required_item(connection, item_id: int) -> ItemRecord:
    item = get_item(connection, item_id)
    if item is not None:
        return item
    raise RuntimeError("Item not found.")


def _confirm(parent: QWidget, message: str) -> bool:
    return (
        QMessageBox.question(parent, "Confirm", message)
        == QMessageBox.StandardButton.Yes
    )


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


class MacroEditorDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        item: ItemRecord | None = None,
        steps: list[MacroStepRecord] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro")

        self.name = QLineEdit(item.name if item else "")
        self.enabled = QCheckBox()
        self.enabled.setChecked(item.is_enabled if item else True)

        self.steps_table = QTableWidget(0, 6)
        self.steps_table.setHorizontalHeaderLabels(
            ["step_order", "action", "target_id", "value", "timeout_seconds", "retries"]
        )
        self.steps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.steps_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.steps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        add_step_button = QPushButton("Add Step")
        add_step_button.clicked.connect(self.add_step)

        edit_step_button = QPushButton("Edit Step")
        edit_step_button.clicked.connect(self.edit_step)

        delete_step_button = QPushButton("Delete Step")
        delete_step_button.clicked.connect(self.delete_step)

        step_buttons = QHBoxLayout()
        step_buttons.addWidget(add_step_button)
        step_buttons.addWidget(edit_step_button)
        step_buttons.addWidget(delete_step_button)
        step_buttons.addStretch()

        form = QFormLayout()
        form.addRow("Macro name", self.name)
        form.addRow("Enabled", self.enabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.steps_table)
        layout.addLayout(step_buttons)
        layout.addWidget(buttons)
        self.resize(780, 520)

        for step in steps or []:
            self._append_step(
                {
                    "step_order": step.step_order,
                    "action": step.action,
                    "target_id": step.target_id or "",
                    "value": step.value or "",
                    "timeout_seconds": step.timeout_seconds,
                    "retries": step.retries,
                }
            )

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "is_enabled": self.enabled.isChecked(),
            "steps": self._steps(),
        }

    def add_step(self) -> None:
        dialog = MacroStepDialog(self, next_order=self.steps_table.rowCount() + 1)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._append_step(dialog.values())

    def edit_step(self) -> None:
        row = self._selected_step_row()
        if row is None:
            return
        dialog = MacroStepDialog(self, self._step_at_row(row))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._set_step(row, dialog.values())

    def delete_step(self) -> None:
        row = self._selected_step_row()
        if row is None:
            return
        self.steps_table.removeRow(row)
        self._renumber_steps()

    def _append_step(self, step: dict) -> None:
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)
        self._set_step(row, step)

    def _set_step(self, row: int, step: dict) -> None:
        values = [
            str(step["step_order"]),
            step["action"],
            step.get("target_id", ""),
            step.get("value", ""),
            str(step["timeout_seconds"]),
            str(step["retries"]),
        ]
        for column, value in enumerate(values):
            self.steps_table.setItem(row, column, QTableWidgetItem(value))
        self.steps_table.resizeColumnsToContents()

    def _selected_step_row(self) -> int | None:
        selected = self.steps_table.selectedItems()
        if not selected:
            return None
        return selected[0].row()

    def _step_at_row(self, row: int) -> dict:
        return {
            "step_order": int(self.steps_table.item(row, 0).text()),
            "action": self.steps_table.item(row, 1).text(),
            "target_id": self.steps_table.item(row, 2).text(),
            "value": self.steps_table.item(row, 3).text(),
            "timeout_seconds": float(self.steps_table.item(row, 4).text()),
            "retries": int(self.steps_table.item(row, 5).text()),
        }

    def _steps(self) -> list[dict]:
        return [self._step_at_row(row) for row in range(self.steps_table.rowCount())]

    def _renumber_steps(self) -> None:
        for row in range(self.steps_table.rowCount()):
            self.steps_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))


class MacroStepDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        step: dict | None = None,
        next_order: int = 1,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")

        self.step_order = QSpinBox()
        self.step_order.setMinimum(1)
        self.step_order.setMaximum(9999)
        self.step_order.setValue(step["step_order"] if step else next_order)

        self.action = QComboBox()
        self.action.addItems(sorted(ALLOWED_MACRO_ACTIONS))
        if step:
            self.action.setCurrentText(step["action"])

        self.target_id = QLineEdit(step.get("target_id", "") if step else "")
        self.value = QLineEdit(step.get("value", "") if step else "")

        self.timeout_seconds = QDoubleSpinBox()
        self.timeout_seconds.setMinimum(0.0)
        self.timeout_seconds.setMaximum(3600.0)
        self.timeout_seconds.setDecimals(2)
        self.timeout_seconds.setValue(float(step["timeout_seconds"]) if step else 5.0)

        self.retries = QSpinBox()
        self.retries.setMinimum(0)
        self.retries.setMaximum(100)
        self.retries.setValue(int(step["retries"]) if step else 0)

        form = QFormLayout()
        form.addRow("step_order", self.step_order)
        form.addRow("action", self.action)
        form.addRow("target_id", self.target_id)
        form.addRow("value", self.value)
        form.addRow("timeout_seconds", self.timeout_seconds)
        form.addRow("retries", self.retries)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "step_order": self.step_order.value(),
            "action": self.action.currentText(),
            "target_id": self.target_id.text().strip(),
            "value": self.value.text().strip(),
            "timeout_seconds": self.timeout_seconds.value(),
            "retries": self.retries.value(),
        }
