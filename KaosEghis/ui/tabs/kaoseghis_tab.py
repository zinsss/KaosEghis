from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
    LAUNCHER_SECTIONS,
    create_item,
    create_macro_step,
    delete_item,
    delete_macro_steps_for_item,
    get_item,
    list_items,
    list_launcher_items,
    list_macro_steps,
    resolve_macro_emr_target_profile,
    reorder_macro_steps,
    update_item_launcher_placement,
    update_item,
)
from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog
from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage


class KaosEghisTab(QWidget):
    TOP_PAGES = ["Launcher", "Builder", "MacroTexts", "EMR"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.launcher_page = LauncherPage(db_path)
        self.builder_page = MacrosPage(db_path)
        self.macrotexts_page = MacroTextsPage(db_path)
        self.emr_page = EmrTargetsPage(db_path)

        # Compatibility aliases for older tests and code paths.
        self.macros_page = self.builder_page
        self.presets_page = self.macrotexts_page

        for page in (
            self.launcher_page,
            self.builder_page,
            self.macrotexts_page,
            self.emr_page,
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


class LauncherPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("Launcher")
        title.setObjectName("pageTitle")

        self.summary_label = QLabel("Double-click a macro to run it. Drag between columns to organize.")
        self.summary_label.setObjectName("macroSummary")

        self.launcher_lists: dict[str, LauncherListWidget] = {}
        columns = QGridLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setHorizontalSpacing(12)
        for index, section in enumerate(LAUNCHER_SECTIONS):
            section_label = QLabel(section)
            section_label.setObjectName("launcherSectionTitle")
            section_list = LauncherListWidget(section, self)
            section_list.itemDoubleClicked.connect(
                lambda item, list_widget=section_list: self.run_macro_from_list(list_widget, item)
            )
            self.launcher_lists[section] = section_list
            columns.addWidget(section_label, 0, index)
            columns.addWidget(section_list, 1, index)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_macro)
        self.run_macro_button = QPushButton("Run selected macro")
        self.run_macro_button.clicked.connect(self.run_macro)

        controls = QHBoxLayout()
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro status will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.summary_label)
        layout.addLayout(columns, 1)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        macros = _load_launcher_macros(self._db_path)
        self._populate_launcher_lists(macros)
        macro_names = ", ".join(macro.name for macro in macros[:6])
        if len(macros) > 6:
            macro_names += ", ..."
        self.summary_label.setText(
            macro_names if macro_names else "No saved macros available."
        )

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
        self._run_macro_by_id(item_id)

    def run_macro_from_list(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
    ) -> None:
        item_id = item.data(list_widget.ITEM_ID_ROLE)
        if isinstance(item_id, int):
            list_widget.setCurrentItem(item)
            self._run_macro_by_id(item_id)

    def _run_macro_by_id(self, item_id: int) -> None:
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
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            QMessageBox.warning(
                self,
                "Application reconnection required",
                result.message,
            )
        self.log.setPlainText(_format_macro_run_result(result))

    def persist_launcher_layout(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            for section, list_widget in self.launcher_lists.items():
                for index in range(list_widget.count()):
                    item = list_widget.item(index)
                    item_id = item.data(list_widget.ITEM_ID_ROLE)
                    if isinstance(item_id, int):
                        update_item_launcher_placement(
                            connection,
                            item_id,
                            section,
                            index + 1,
                        )

    def _populate_launcher_lists(self, macros: list) -> None:
        by_section = {section: [] for section in LAUNCHER_SECTIONS}
        for macro in macros:
            by_section.setdefault(macro.launcher_section, []).append(macro)
        for section, list_widget in self.launcher_lists.items():
            list_widget.blockSignals(True)
            list_widget.clear()
            for macro in by_section.get(section, []):
                profile_text = _macro_profile_text(self._db_path, macro)
                item = QListWidgetItem(macro.name)
                item.setData(list_widget.ITEM_ID_ROLE, macro.id)
                item.setToolTip(profile_text)
                list_widget.addItem(item)
            list_widget.blockSignals(False)

    def _selected_macro_id(self) -> int | None:
        for list_widget in self.launcher_lists.values():
            current = list_widget.currentItem()
            if current is None:
                continue
            item_id = current.data(list_widget.ITEM_ID_ROLE)
            if isinstance(item_id, int):
                return item_id
        return None


class MacrosPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("Builder")
        title.setObjectName("pageTitle")

        self.automation_summary = QLabel("Create and edit saved macros.")
        self.automation_summary.setObjectName("macroSummary")

        self.macros_table = _create_macro_table()

        self.add_macro_button = QPushButton("Add macro")
        self.add_macro_button.clicked.connect(self.add_macro)
        self.edit_macro_button = QPushButton("Edit selected macro")
        self.edit_macro_button.clicked.connect(self.edit_macro)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_macro)
        self.run_macro_button = QPushButton("Run selected macro")
        self.run_macro_button.clicked.connect(self.run_macro)
        self.delete_macro_button = QPushButton("Delete selected macro")
        self.delete_macro_button.clicked.connect(self.delete_macro)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)

        controls = QHBoxLayout()
        controls.addWidget(self.add_macro_button)
        controls.addWidget(self.edit_macro_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addWidget(self.delete_macro_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro status will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.automation_summary)
        layout.addWidget(self.macros_table)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        macros = _load_macros(self._db_path)
        _populate_macro_table(self.macros_table, macros, self._db_path)
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
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            QMessageBox.warning(
                self,
                "Application reconnection required",
                result.message,
            )
        self.log.setPlainText(_format_macro_run_result(result))

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

    def _selected_macro_id(self) -> int | None:
        return _selected_macro_id(self.macros_table)


class MacroTextsPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("MacroTexts")
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
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
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


PresetsPage = MacroTextsPage


class LauncherListWidget(QListWidget):
    ITEM_ID_ROLE = 256

    def __init__(self, section: str, launcher_page: LauncherPage) -> None:
        super().__init__()
        self.section = section
        self.launcher_page = launcher_page
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setStyleSheet(
            "QListWidget {"
            " border: 1px solid #45475a;"
            " border-radius: 6px;"
            " padding: 4px;"
            " background-color: #1e1e2e;"
            "}"
        )

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.launcher_page.persist_launcher_layout()


def _create_macro_table() -> QTableWidget:
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["id", "name", "EMR profile", "enabled"])
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return table


def _load_macros(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return list_items(connection, "macro")


def _load_launcher_macros(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return list_launcher_items(connection)


def _populate_macro_table(
    table: QTableWidget, macros: list, db_path: Path | None
) -> None:
    table.setRowCount(len(macros))
    with connect(db_path) as connection:
        for row_index, macro in enumerate(macros):
            profile = resolve_macro_emr_target_profile(connection, macro)
            table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
            table.setItem(row_index, 1, QTableWidgetItem(macro.name))
            table.setItem(
                row_index,
                2,
                QTableWidgetItem(profile.name if profile is not None else ""),
            )
            table.setItem(
                row_index, 3, QTableWidgetItem(_yes_no(macro.is_enabled))
            )
    table.resizeColumnsToContents()


def _selected_macro_id(table: QTableWidget) -> int | None:
    selected = table.selectedItems()
    if not selected:
        return None
    item = table.item(selected[0].row(), 0)
    if item is None:
        return None
    return int(item.text())


def _get_required_item(connection, item_id: int):
    item = get_item(connection, item_id)
    if item is not None:
        return item
    raise RuntimeError("Item not found.")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _macro_profile_text(db_path: Path | None, macro) -> str:
    with connect(db_path) as connection:
        profile = resolve_macro_emr_target_profile(connection, macro)
    return f"Profile: {profile.name if profile is not None else '(No EMR profile)'}"


def _format_macro_run_result(result) -> str:
    if result.success:
        return f"Completed. Steps: {result.executed_steps}"

    if result.failed_step:
        return (
            f"Stopped at step {result.failed_step}. "
            f"{result.message}"
        )

    if result.executed_steps:
        return f"Stopped after {result.executed_steps} step(s). {result.message}"

    return result.message
