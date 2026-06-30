from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.macro_runner import MacroRunner
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_item,
    create_macro_step,
    delete_item,
    delete_macro_steps_for_item,
    get_item,
    list_items,
    list_macro_steps,
    resolve_macro_emr_target_profile,
    reorder_macro_steps,
    update_item,
    validate_macro_dry_run,
)
from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog
from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage
from KaosEghis.ui.tabs.settings_tab import SettingsTab


class KaosEghisTab(QWidget):
    TOP_PAGES = ["Macros", "Presets", "EMR", "Settings"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.macros_page = MacrosPage(db_path)
        self.presets_page = PresetsPage()
        self.emr_page = EmrTargetsPage(db_path)
        self.settings_page = SettingsTab(db_path)

        for page in (
            self.macros_page,
            self.presets_page,
            self.emr_page,
            self.settings_page,
        ):
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
        layout.addWidget(self.stacked_widget)

        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, "refresh_view"):
            current_widget.refresh_view()
        elif hasattr(current_widget, "load_settings"):
            current_widget.load_settings()


class MacrosPage(QWidget):
    SMOKE_TEST_MACRO_NAME = "Smoke Test - Notepad"

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("Macros")
        title.setObjectName("pageTitle")

        self.automation_summary = QLabel()
        self.automation_summary.setObjectName("macroSummary")

        self.macros_table = QTableWidget(0, 4)
        self.macros_table.setHorizontalHeaderLabels(
            ["id", "name", "EMR profile", "enabled"]
        )
        self.macros_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.macros_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.macros_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.add_macro_button = QPushButton("Add macro")
        self.add_macro_button.clicked.connect(self.add_macro)
        self.edit_macro_button = QPushButton("Edit selected macro")
        self.edit_macro_button.clicked.connect(self.edit_macro)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_macro)
        self.run_macro_button = QPushButton("Run selected macro")
        self.run_macro_button.clicked.connect(self.run_macro)
        self.create_smoke_test_button = QPushButton("Create smoke test macro")
        self.create_smoke_test_button.clicked.connect(self.create_smoke_test_macro)
        self.delete_macro_button = QPushButton("Delete selected macro")
        self.delete_macro_button.clicked.connect(self.delete_macro)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)

        controls = QHBoxLayout()
        controls.addWidget(self.add_macro_button)
        controls.addWidget(self.edit_macro_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addWidget(self.create_smoke_test_button)
        controls.addWidget(self.delete_macro_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro dry-run output will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.automation_summary)
        layout.addWidget(self.macros_table)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            macros = list_items(connection, "macro")

        self.macros_table.setRowCount(len(macros))
        with connect(self._db_path) as connection:
            for row_index, macro in enumerate(macros):
                profile = resolve_macro_emr_target_profile(connection, macro)
                self.macros_table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
                self.macros_table.setItem(row_index, 1, QTableWidgetItem(macro.name))
                self.macros_table.setItem(
                    row_index,
                    2,
                    QTableWidgetItem(profile.name if profile is not None else ""),
                )
                self.macros_table.setItem(
                    row_index, 3, QTableWidgetItem(_yes_no(macro.is_enabled))
                )
        self.macros_table.resizeColumnsToContents()
        macro_ids = ", ".join(str(macro.id) for macro in macros) or "None"
        self.automation_summary.setText(f"Saved automation IDs: {macro_ids}")

    def add_macro(self) -> None:
        dialog = MacroEditorDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            self.log.setPlainText("Macro name is required.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
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
        self.refresh_view()
        self.log.setPlainText("Macro added.")

    def edit_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to edit.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)

        dialog = MacroEditorDialog(self, item, steps)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
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
        self.refresh_view()
        self.log.setPlainText("Macro updated.")

    def dry_run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to dry run.")
            return

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=True)
        self.log.setPlainText(result.message)

    def run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to run.")
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Macro Execution",
                "Run the selected macro now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            self.log.setPlainText("Macro execution canceled.")
            return

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=False)
        lines = [
            f"success: {_yes_no(result.success)}",
            f"executed_steps: {result.executed_steps}",
            f"failed_step: {result.failed_step or ''}",
            f"message: {result.message}",
        ]
        self.log.setPlainText("\n".join(lines))

    def delete_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to delete.")
            return
        if (
            QMessageBox.question(self, "Confirm", "Delete selected macro?")
            != QMessageBox.StandardButton.Yes
        ):
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            deleted = delete_item(connection, item_id)
        self.refresh_view()
        self.log.setPlainText("Macro deleted." if deleted else "Macro not found.")

    def create_smoke_test_macro(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            existing = next(
                (
                    item
                    for item in list_items(connection, "macro")
                    if item.name == self.SMOKE_TEST_MACRO_NAME
                ),
                None,
            )
            if existing is not None:
                self.refresh_view()
                self.log.setPlainText("Smoke test macro already exists.")
                return

            item = create_item(
                connection,
                self.SMOKE_TEST_MACRO_NAME,
                "macro",
                False,
                None,
            )
            create_macro_step(connection, item.id, 1, "wait_window", value="Notepad")
            create_macro_step(
                connection,
                item.id,
                2,
                "paste_text",
                value="KaosEghis smoke test",
            )
            create_macro_step(connection, item.id, 3, "delay_ms", value="300")
            reorder_macro_steps(connection, item.id)

        self.refresh_view()
        self.log.setPlainText(
            "Smoke test macro created disabled. Enable it manually before any real run."
        )

    def _selected_macro_id(self) -> int | None:
        selected = self.macros_table.selectedItems()
        if not selected:
            return None
        item = self.macros_table.item(selected[0].row(), 0)
        if item is None:
            return None
        return int(item.text())


class PresetsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Presets")
        title.setObjectName("pageTitle")

        self.presets_table = QTableWidget(0, 3)
        self.presets_table.setHorizontalHeaderLabels(["id", "name", "type"])
        self.presets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.presets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.presets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.empty_state = QLabel("No preset strings configured.")
        self.empty_state.setObjectName("presetEmptyState")

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)

        controls = QHBoxLayout()
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.presets_table)
        layout.addLayout(controls)

        self.refresh_view()

    def refresh_view(self) -> None:
        initialize_database()
        with connect() as connection:
            preset_items = []
            for item_type in ("clipboard", "randomized_clipboard"):
                preset_items.extend(list_items(connection, item_type))

        self.presets_table.setRowCount(len(preset_items))
        for row_index, item in enumerate(preset_items):
            self.presets_table.setItem(row_index, 0, QTableWidgetItem(str(item.id)))
            self.presets_table.setItem(row_index, 1, QTableWidgetItem(item.name))
            self.presets_table.setItem(row_index, 2, QTableWidgetItem(item.item_type))
        self.presets_table.resizeColumnsToContents()
        has_presets = bool(preset_items)
        self.empty_state.setVisible(not has_presets)
        self.presets_table.setVisible(has_presets)


def _get_required_item(connection, item_id: int):
    item = get_item(connection, item_id)
    if item is not None:
        return item
    raise RuntimeError("Item not found.")


def _build_dry_run_output(connection, item_id: int) -> str:
    item = get_item(connection, item_id)
    if item is None:
        return "Macro not found."

    profile = resolve_macro_emr_target_profile(connection, item)
    steps = list_macro_steps(connection, item_id)
    errors = validate_macro_dry_run(connection, item_id)
    lines = [f"Dry run: {item.name}"]
    lines.append(
        f"Profile: {profile.name if profile is not None else '(No EMR profile)'}"
    )
    for step in steps:
        lines.append(_dry_run_step_line(step))
    if errors:
        lines.append("")
        missing_target = _missing_target_from_error(errors[0])
        if missing_target:
            lines.append(f"Result: Blocked - missing UI target: {missing_target}")
        else:
            lines.append(f"Result: Blocked - {errors[0]}")
    else:
        if not steps:
            lines.append("No steps defined.")
        lines.append("")
        lines.append("Result: OK - dry run only, no actions executed.")
    return "\n".join(lines)


def _dry_run_step_line(step) -> str:
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


def _missing_target_from_error(error: str) -> str | None:
    marker = "target_id '"
    if marker not in error:
        return None
    start = error.index(marker) + len(marker)
    end = error.find("'", start)
    if end == -1:
        return None
    return error[start:end]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
