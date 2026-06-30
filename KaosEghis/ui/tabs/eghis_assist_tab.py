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

from KaosEghis.core.eghis_key_paste_test import (
    paste_to_eghis_field_by_function_key_for_test,
)
from KaosEghis.core.paste_test import paste_text_to_target_for_test
from KaosEghis.core.uia_inspector import inspect_target_readonly
from KaosEghis.core.wait_engine import WaitCondition, wait_for_target_condition
from KaosEghis.core.write_test import (
    set_edit_text_to_target_for_test,
    set_value_to_target_for_test,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    ALLOWED_MACRO_ACTIONS,
    build_macro_dry_run_preview,
    EmrUiTargetRecord,
    ItemRecord,
    MacroStepRecord,
    UiTargetRecord,
    create_item,
    create_macro_step,
    create_ui_target,
    delete_item,
    delete_macro_step,
    delete_macro_steps_for_item,
    delete_ui_target,
    get_item,
    get_default_emr_target_profile,
    get_emr_target_profile,
    get_settings,
    get_ui_target,
    list_emr_target_profiles,
    list_emr_ui_targets,
    list_ui_targets,
    list_items,
    list_macro_steps,
    reorder_macro_steps,
    resolve_macro_emr_target_profile,
    update_item,
    update_macro_step,
    update_ui_target,
    validate_macro_dry_run,
)


TARGET_BASED_ACTIONS = {
    "click",
    "mouse_click",
    "paste_text",
    "preset_text",
    "read_text_uia",
    "set_text_uia",
    "type_text",
    "type_text_clipboard",
    "type_text_keyboard",
    "wait_for_target",
}


class MacrosTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Macros")
        title.setObjectName("pageTitle")

        targets_title = QLabel("UI Targets")
        self.targets_table = QTableWidget(0, 7)
        self.targets_table.setHorizontalHeaderLabels(
            [
                "target_id",
                "parent_target_id",
                "parent_automation_id",
                "automation_id",
                "name",
                "control_type",
                "class_name",
            ]
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

        self.wait_condition = QComboBox()
        self.wait_condition.addItems([condition.value for condition in WaitCondition])

        self.wait_timeout_ms = QSpinBox()
        self.wait_timeout_ms.setRange(0, 60000)
        self.wait_timeout_ms.setValue(5000)
        self.wait_timeout_ms.setSuffix(" ms")

        self.wait_poll_ms = QSpinBox()
        self.wait_poll_ms.setRange(1, 5000)
        self.wait_poll_ms.setValue(200)
        self.wait_poll_ms.setSuffix(" ms")

        wait_test_button = QPushButton("Wait Test")
        wait_test_button.clicked.connect(self.wait_test_target)

        target_controls = QHBoxLayout()
        target_controls.addWidget(add_target_button)
        target_controls.addWidget(edit_target_button)
        target_controls.addWidget(delete_target_button)
        target_controls.addWidget(refresh_targets_button)
        target_controls.addWidget(test_target_button)
        target_controls.addWidget(QLabel("Condition"))
        target_controls.addWidget(self.wait_condition)
        target_controls.addWidget(QLabel("Timeout"))
        target_controls.addWidget(self.wait_timeout_ms)
        target_controls.addWidget(QLabel("Poll"))
        target_controls.addWidget(self.wait_poll_ms)
        target_controls.addWidget(wait_test_button)
        target_controls.addStretch()

        paste_test_label = QLabel("Paste Test")
        self.paste_test_text = QPlainTextEdit()
        self.paste_test_text.setPlaceholderText(
            "Enter harmless test text for an explicit Ctrl+V paste test."
        )
        self.paste_test_text.setMaximumBlockCount(20)

        paste_warning = QLabel(
            "Manual test only. Use dummy/test patient or harmless empty field."
        )

        paste_test_button = QPushButton("Paste Test")
        paste_test_button.clicked.connect(self.paste_test_target)

        set_value_button = QPushButton("SetValue Test")
        set_value_button.clicked.connect(self.set_value_test_target)

        set_edit_text_button = QPushButton("Set Edit Text Test")
        set_edit_text_button.clicked.connect(self.set_edit_text_test_target)

        paste_controls = QHBoxLayout()
        paste_controls.addWidget(paste_test_button)
        paste_controls.addWidget(set_value_button)
        paste_controls.addWidget(set_edit_text_button)
        paste_controls.addStretch()

        function_key_controls = QHBoxLayout()
        for function_key, destination in [
            ("F1", "Symptom"),
            ("F2", "Diagnosis"),
            ("F3", "Orders"),
            ("F4", "Patient Notes"),
        ]:
            button = QPushButton(f"{function_key} {destination} Paste Test")
            button.clicked.connect(
                lambda _checked=False, dest=destination, key=function_key: (
                    self.function_key_paste_test(dest, key)
                )
            )
            function_key_controls.addWidget(button)
        function_key_controls.addStretch()

        macros_title = QLabel("Macros")
        self.macros_table = QTableWidget(0, 4)
        self.macros_table.setHorizontalHeaderLabels(
            ["id", "name", "EMR profile", "enabled"]
        )
        self.macros_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.macros_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.macros_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        add_macro_button = QPushButton("Add Macro")
        add_macro_button.clicked.connect(self.add_macro)

        edit_macro_button = QPushButton("Edit Macro")
        edit_macro_button.clicked.connect(self.edit_macro)

        delete_macro_button = QPushButton("Delete Macro")
        delete_macro_button.clicked.connect(self.delete_macro)

        refresh_macros_button = QPushButton("Refresh Macros")
        refresh_macros_button.clicked.connect(self.refresh_macros)

        dry_run_button = QPushButton("Dry Run")
        dry_run_button.clicked.connect(self.dry_run_macro)

        macro_controls = QHBoxLayout()
        macro_controls.addWidget(add_macro_button)
        macro_controls.addWidget(edit_macro_button)
        macro_controls.addWidget(delete_macro_button)
        macro_controls.addWidget(refresh_macros_button)
        macro_controls.addWidget(dry_run_button)
        macro_controls.addStretch()

        log = QPlainTextEdit()
        self.log = log
        log.setReadOnly(True)
        log.setPlaceholderText("Status and safety messages will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(targets_title)
        layout.addWidget(self.targets_table)
        layout.addLayout(target_controls)
        layout.addWidget(paste_test_label)
        layout.addWidget(self.paste_test_text)
        layout.addWidget(paste_warning)
        layout.addLayout(paste_controls)
        layout.addLayout(function_key_controls)
        layout.addWidget(macros_title)
        layout.addWidget(self.macros_table)
        layout.addLayout(macro_controls)
        layout.addWidget(log)

        self.refresh_targets()
        self.refresh_macros()

    def refresh_targets(self) -> None:
        initialize_database()
        with connect() as connection:
            targets = list_ui_targets(connection)

        self.targets_table.setRowCount(len(targets))
        for row_index, target in enumerate(targets):
            self.targets_table.setItem(row_index, 0, QTableWidgetItem(target.target_id))
            self.targets_table.setItem(
                row_index, 1, QTableWidgetItem(target.parent_target_id or "")
            )
            self.targets_table.setItem(
                row_index, 2, QTableWidgetItem(target.parent_automation_id or "")
            )
            self.targets_table.setItem(row_index, 3, QTableWidgetItem(target.automation_id or ""))
            self.targets_table.setItem(row_index, 4, QTableWidgetItem(target.name or ""))
            self.targets_table.setItem(row_index, 5, QTableWidgetItem(target.control_type or ""))
            self.targets_table.setItem(row_index, 6, QTableWidgetItem(target.class_name or ""))
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
                target_id=target_id,
                parent_target_id=values["parent_target_id"],
                parent_automation_id=values["parent_automation_id"],
                automation_id=values["automation_id"],
                name=values["name"],
                control_type=values["control_type"],
                class_name=values["class_name"],
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
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target to test.")
            return

        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
            target = _get_required_target(connection, target_id)

        result = inspect_target_readonly(settings, target)
        lines = [
            f"Found: {_yes_no(result.found)}",
            f"target_id: {result.target_id}",
            f"configured parent_target_id: {_value_or_empty(result.parent_target_id)}",
            f"configured parent_automation_id: {_value_or_empty(result.parent_automation_id)}",
            f"parent found: {_optional_yes_no(result.parent_found)}",
            f"automation_id: {_value_or_empty(result.automation_id)}",
            f"configured name: {_value_or_empty(result.name)}",
            f"configured control_type: {_value_or_empty(result.control_type)}",
            f"configured class_name: {_value_or_empty(result.class_name)}",
            f"found_name: {_value_or_empty(result.found_name)}",
            f"found_control_type: {_value_or_empty(result.found_control_type)}",
            f"found_class_name: {_value_or_empty(result.found_class_name)}",
            f"enabled: {_optional_yes_no(result.is_enabled)}",
            f"visible: {_optional_yes_no(result.is_visible)}",
        ]
        if result.text_value:
            lines.append(f"text_value: {result.text_value}")
        lines.append(f"message: {result.message}")
        self.log.setPlainText("\n".join(lines))

    def wait_test_target(self) -> None:
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target to wait for.")
            return

        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
            target = _get_required_target(connection, target_id)

        result = wait_for_target_condition(
            settings,
            target,
            self.wait_condition.currentText(),
            timeout_ms=self.wait_timeout_ms.value(),
            poll_ms=self.wait_poll_ms.value(),
        )
        self.log.setPlainText(
            "\n".join(
                [
                    f"target_id: {result.target_id}",
                    f"condition: {result.condition}",
                    f"success: {_yes_no(result.success)}",
                    f"elapsed_ms: {result.elapsed_ms}",
                    f"attempts: {result.attempts}",
                    f"message: {result.message}",
                ]
            )
        )

    def paste_test_target(self) -> None:
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target for Paste Test.")
            return

        text = self.paste_test_text.toPlainText()
        if not text.strip():
            self.log.setPlainText("Paste test text is empty.")
            return

        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
            target = _get_required_target(connection, target_id)

        result = paste_text_to_target_for_test(settings, target, text)
        self.log.setPlainText(
            "\n".join(
                [
                    f"selected target_id: {target_id}",
                    f"text length: {len(text)}",
                    (
                        "resolved target found: yes"
                        if result.success or result.focused is not None
                        else "resolved target found: no"
                    ),
                    (
                        "focus/click attempted: yes"
                        if result.focused is not None
                        else "focus/click attempted: no"
                    ),
                    f"clipboard restored: {_yes_no(result.clipboard_restored)}",
                    f"final result: {_yes_no(result.success)}",
                    f"message: {result.message}",
                ]
            )
        )

    def set_value_test_target(self) -> None:
        self._run_manual_write_test("set_value")

    def set_edit_text_test_target(self) -> None:
        self._run_manual_write_test("set_edit_text")

    def function_key_paste_test(self, destination: str, function_key: str) -> None:
        text = self.paste_test_text.toPlainText()
        if not text.strip():
            self.log.setPlainText("Paste test text is empty.")
            return

        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)

        result = paste_to_eghis_field_by_function_key_for_test(
            settings,
            destination,
            function_key,
            text,
        )
        self.log.setPlainText(
            "\n".join(
                [
                    f"destination: {result.destination}",
                    f"function key: {result.function_key}",
                    f"text length: {result.text_length}",
                    f"Eghis active: {_yes_no(result.eghis_active)}",
                    f"popup check passed: {_popup_check_text(result.popup_check_passed)}",
                    f"function key sent: {_yes_no(result.key_sent)}",
                    f"Ctrl+V sent: {_yes_no(result.paste_sent)}",
                    f"clipboard restored: {_yes_no(result.clipboard_restored)}",
                    f"final result: {_yes_no(result.success)}",
                    f"message: {result.message}",
                ]
            )
        )

    def _run_manual_write_test(self, method: str) -> None:
        target_id = self._selected_target_id()
        if target_id is None:
            self.log.setPlainText("Select a target for the write test.")
            return

        text = self.paste_test_text.toPlainText()
        if not text.strip():
            self.log.setPlainText("Write test text is empty.")
            return

        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
            target = _get_required_target(connection, target_id)

        if method == "set_value":
            result = set_value_to_target_for_test(settings, target, text)
        else:
            result = set_edit_text_to_target_for_test(settings, target, text)

        self.log.setPlainText(
            "\n".join(
                [
                    f"selected target_id: {target_id}",
                    f"method: {result.method}",
                    f"text length: {len(text)}",
                    (
                        "resolved target: yes"
                        if result.success or result.focused is not None
                        or "not found" not in result.message.casefold()
                        else "resolved target: no"
                    ),
                    (
                        f"focus attempted: {_optional_yes_no(result.focused)}"
                        if result.focused is not None
                        else "focus attempted: "
                    ),
                    f"final result: {_yes_no(result.success)}",
                    f"message: {result.message}",
                ]
            )
        )

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
            profile = resolve_macro_emr_target_profile(connection, macro)
            self.macros_table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
            self.macros_table.setItem(row_index, 1, QTableWidgetItem(macro.name))
            self.macros_table.setItem(
                row_index, 2, QTableWidgetItem(profile.name if profile is not None else "")
            )
            self.macros_table.setItem(row_index, 3, QTableWidgetItem(_yes_no(macro.is_enabled)))
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
            item = create_item(
                connection,
                values["name"],
                "macro",
                values["is_enabled"],
                values["emr_target_profile_id"],
            )
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
            update_item(
                connection,
                item_id,
                values["name"],
                "macro",
                values["is_enabled"],
                values["emr_target_profile_id"],
            )
            delete_macro_steps_for_item(connection, item_id)
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
            profile = resolve_macro_emr_target_profile(connection, item)
            preview = build_macro_dry_run_preview(connection, item_id)

        lines = [f"Dry run: {item.name}"]
        lines.append(
            f"Profile: {profile.name if profile is not None else '(No EMR profile)'}"
        )
        for warning in preview.warnings:
            lines.append(f"Warning: {warning}")
        for step in preview.steps:
            lines.extend(_dry_run_preview_lines(step))
        if preview.warnings or any(step.warnings for step in preview.steps):
            lines.append("")
            lines.append("Result: Review warnings before real execution.")
        else:
            if not preview.steps:
                lines.append("No steps defined.")
            lines.append("")
            lines.append("Result: OK - dry run only, no actions executed.")
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


def _optional_yes_no(value: bool | None) -> str:
    if value is None:
        return ""
    return _yes_no(value)


def _popup_check_text(value: bool | None) -> str:
    if value is None:
        return "not checked"
    return _yes_no(value)


def _value_or_empty(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _dry_run_step_line(step: MacroStepRecord) -> str:
    target = f" target_id={step.target_id}" if step.target_id else ""
    value = f" value={step.value}" if step.value else ""
    if step.action == "wait_for_target":
        return (
            f"{step.step_order}. wait_for_target{target} "
            f"timeout={step.timeout_seconds} retries={step.retries} (dry run only)"
        )
    if step.action == "wait_ms":
        duration = step.value or ""
        duration_text = f" duration_ms={duration}" if duration else ""
        return f"{step.step_order}. wait_ms{duration_text} (dry run only)"
    return (
        f"{step.step_order}. {step.action}{target}{value} "
        f"timeout={step.timeout_seconds} retries={step.retries}"
    )


def _dry_run_preview_lines(step_preview) -> list[str]:
    target = f" target_key={step_preview.target_key}" if step_preview.target_key else ""
    label = f" label={step_preview.resolved_label}" if step_preview.resolved_label else ""
    line = f"{step_preview.step_order}. action={step_preview.action}{target}{label}"
    detail_parts = []
    if step_preview.automation_id:
        detail_parts.append(f"automation_id={step_preview.automation_id}")
    if step_preview.control_type:
        detail_parts.append(f"control_type={step_preview.control_type}")
    if step_preview.name_match:
        detail_parts.append(f"name_match={step_preview.name_match}")
    if step_preview.class_name:
        detail_parts.append(f"class_name={step_preview.class_name}")
    if step_preview.parent_target_key:
        detail_parts.append(f"parent_key={step_preview.parent_target_key}")
    if step_preview.value_summary:
        detail_parts.append(step_preview.value_summary)
    lines = [line]
    if detail_parts:
        lines.append(f"   preview: {'; '.join(detail_parts)}")
    for warning in step_preview.warnings:
        lines.append(f"   warning: {warning}")
    return lines


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


def _missing_target_from_error(error: str) -> str | None:
    marker = "target_id '"
    if marker not in error:
        return None
    start = error.index(marker) + len(marker)
    end = error.find("'", start)
    if end == -1:
        return None
    return error[start:end]


class UiTargetDialog(QDialog):
    def __init__(self, parent: QWidget, target: UiTargetRecord | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("UI Target")

        self.target_id = QLineEdit(target.target_id if target else "")
        self.parent_target_id = QLineEdit(
            target.parent_target_id if target and target.parent_target_id else ""
        )
        self.parent_automation_id = QLineEdit(
            target.parent_automation_id if target and target.parent_automation_id else ""
        )
        self.automation_id = QLineEdit(target.automation_id if target and target.automation_id else "")
        self.name = QLineEdit(target.name if target and target.name else "")
        self.control_type = QLineEdit(target.control_type if target and target.control_type else "")
        self.class_name = QLineEdit(target.class_name if target and target.class_name else "")
        self.target_id.setEnabled(target is None)

        form = QFormLayout()
        form.addRow("target_id", self.target_id)
        form.addRow("parent_target_id", self.parent_target_id)
        form.addRow("parent_automation_id", self.parent_automation_id)
        form.addRow("automation_id", self.automation_id)
        form.addRow("name", self.name)
        form.addRow("control_type", self.control_type)
        form.addRow("class_name", self.class_name)

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
            "parent_target_id": self.parent_target_id.text().strip(),
            "parent_automation_id": self.parent_automation_id.text().strip(),
            "automation_id": self.automation_id.text().strip(),
            "name": self.name.text().strip(),
            "control_type": self.control_type.text().strip(),
            "class_name": self.class_name.text().strip(),
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
        initialize_database()
        with connect() as connection:
            self._profiles = list_emr_target_profiles(connection)
            default_profile = get_default_emr_target_profile(connection)

        self._default_profile_id = default_profile.id if default_profile is not None else None
        self._profile_target_keys: list[str] = []

        self.name = QLineEdit(item.name if item else "")
        self.enabled = QCheckBox()
        self.enabled.setChecked(item.is_enabled if item else True)
        self.emr_profile = QComboBox()
        self.emr_profile.addItem(
            self._default_profile_label(default_profile.name if default_profile else None),
            None,
        )
        for profile in self._profiles:
            self.emr_profile.addItem(profile.name, profile.id)

        profile_index = self.emr_profile.findData(item.emr_target_profile_id if item else None)
        if profile_index >= 0:
            self.emr_profile.setCurrentIndex(profile_index)
        self.emr_profile.currentIndexChanged.connect(self._on_profile_changed)

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
        form.addRow("EMR profile", self.emr_profile)

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
        self._refresh_profile_target_keys()

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "is_enabled": self.enabled.isChecked(),
            "emr_target_profile_id": self.current_profile_id(),
            "steps": self._steps(),
        }

    def add_step(self) -> None:
        dialog = MacroStepDialog(
            self,
            next_order=self.steps_table.rowCount() + 1,
            profile_id=self.effective_profile_id(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._append_step(dialog.values())

    def edit_step(self) -> None:
        row = self._selected_step_row()
        if row is None:
            return
        dialog = MacroStepDialog(
            self,
            self._step_at_row(row),
            profile_id=self.effective_profile_id(),
        )
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

    def current_profile_id(self) -> int | None:
        value = self.emr_profile.currentData()
        return value if isinstance(value, int) else None

    def effective_profile_id(self) -> int | None:
        return self.current_profile_id() or self._default_profile_id

    def available_target_keys(self) -> list[str]:
        return list(self._profile_target_keys)

    def _default_profile_label(self, default_profile_name: str | None) -> str:
        if default_profile_name:
            return f"(Default profile) {default_profile_name}"
        return "(Default profile)"

    def _on_profile_changed(self) -> None:
        self._refresh_profile_target_keys()

    def _refresh_profile_target_keys(self) -> None:
        profile_id = self.effective_profile_id()
        if profile_id is None:
            self._profile_target_keys = []
            return
        initialize_database()
        with connect() as connection:
            self._profile_target_keys = [
                target.target_key for target in list_emr_ui_targets(connection, profile_id)
            ]


class MacroStepDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        step: dict | None = None,
        next_order: int = 1,
        profile_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")
        self._profile_id = profile_id

        self.step_order = QSpinBox()
        self.step_order.setMinimum(1)
        self.step_order.setMaximum(9999)
        self.step_order.setValue(step["step_order"] if step else next_order)

        self.action = QComboBox()
        self.action.addItems(sorted(ALLOWED_MACRO_ACTIONS))
        if step:
            self.action.setCurrentText(step["action"])
        self.action.currentTextChanged.connect(self._update_target_field_state)

        self.target_id = QComboBox()
        self.target_id.setEditable(True)
        self._load_target_options()
        if step and step.get("target_id", ""):
            self.target_id.setCurrentText(step.get("target_id", ""))
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
        self._update_target_field_state(self.action.currentText())

    def values(self) -> dict:
        return {
            "step_order": self.step_order.value(),
            "action": self.action.currentText(),
            "target_id": self.target_id.currentText().strip(),
            "value": self.value.text().strip(),
            "timeout_seconds": self.timeout_seconds.value(),
            "retries": self.retries.value(),
        }

    def _load_target_options(self) -> None:
        self.target_id.clear()
        self.target_id.addItem("")
        if self._profile_id is None:
            return
        initialize_database()
        with connect() as connection:
            targets = list_emr_ui_targets(connection, self._profile_id)
        for target in targets:
            self.target_id.addItem(target.target_key)

    def _update_target_field_state(self, action: str) -> None:
        uses_target = action in TARGET_BASED_ACTIONS
        self.target_id.setEnabled(uses_target)
        if not uses_target:
            self.target_id.setCurrentText("")


EghisAssistTab = MacrosTab
