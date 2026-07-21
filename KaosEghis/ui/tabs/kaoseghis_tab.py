from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.macro_runner import MacroRunner
from KaosEghis.core.eghis_connector import (
    build_connector_settings,
    clear_cached_eghis_state,
    get_cached_eghis_state,
    refresh_cached_eghis_state,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    LAUNCHER_SECTIONS,
    create_item,
    create_macro_step,
    delete_item,
    delete_macro_steps_for_item,
    get_active_emr_target_profile,
    get_item,
    list_clipboard_variants,
    list_items,
    list_launcher_items,
    list_macro_steps,
    get_settings,
    resolve_macro_emr_target_profile,
    reorder_macro_steps,
    replace_clipboard_variants,
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

        self.connection_toggle = QPushButton("Connect EMR")
        self.connection_toggle.setCheckable(True)
        self.connection_toggle.toggled.connect(self.toggle_connection)
        self.connection_status_label = QLabel("EMR: disconnected.")

        connection_row = QHBoxLayout()
        connection_row.addWidget(self.connection_toggle)
        connection_row.addWidget(self.connection_status_label, 1)
        connection_row.addStretch()

        self.launcher_lists: dict[str, LauncherListWidget] = {}
        columns = QGridLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setHorizontalSpacing(12)
        for index, section in enumerate(LAUNCHER_SECTIONS):
            section_label = QLabel(section)
            section_label.setObjectName("launcherSectionTitle")
            section_list = LauncherListWidget(section, self)
            section_list.itemDoubleClicked.connect(
                lambda item, list_widget=section_list: self.activate_launcher_item(
                    list_widget, item
                )
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
        layout.addLayout(connection_row)
        layout.addLayout(columns, 1)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        launcher_items = _load_launcher_items(self._db_path)
        self._populate_launcher_lists(launcher_items)
        self._refresh_connection_status()

    def toggle_connection(self, checked: bool) -> None:
        if checked:
            self.connect_active_profile()
            return
        clear_cached_eghis_state()
        self._refresh_connection_status()
        self.log.setPlainText("EMR disconnected.")

    def connect_active_profile(self) -> None:
        settings = self._active_profile_connector_settings()
        if settings is None:
            self._set_toggle_checked(False)
            self.log.setPlainText("No enabled EMR profile is available.")
            self._refresh_connection_status()
            return

        state = refresh_cached_eghis_state(settings)
        connected = state.status in {"green", "yellow"} and state.pid is not None
        self._set_toggle_checked(connected)
        self._refresh_connection_status()
        self.log.setPlainText(state.message)

    def _active_profile_connector_settings(self) -> dict[str, str] | None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_active_emr_target_profile(connection)
            settings = get_settings(connection)
        if profile is None:
            return None
        return build_connector_settings(
            settings,
            process_name=profile.process_name or settings.get("eghis_process_name"),
            window_title_contains=profile.window_title_contains
            or settings.get("eghis_window_title_contains"),
            executable_path=profile.executable_path or settings.get("eghis_executable_path"),
        )

    def _refresh_connection_status(self) -> None:
        state = get_cached_eghis_state()
        settings = self._active_profile_connector_settings()
        profile_name = self._active_profile_name()
        if state is None:
            self.connection_status_label.setText(
                f"EMR: disconnected{f' ({profile_name})' if profile_name else ''}."
            )
            self.connection_toggle.setText("Connect EMR")
            self._set_connection_visual_state("disconnected")
            self._set_toggle_checked(False)
            return
        if settings is not None:
            configured_process = (settings.get("eghis_process_name") or "").strip()
            cached_process = (state.process_name or "").strip()
            configured_path = (settings.get("eghis_executable_path") or "").strip()
            cached_path = (state.exe_path or "").strip()
            mismatch = bool(
                (configured_process and cached_process and configured_process.casefold() != cached_process.casefold())
                or (
                    configured_path
                    and cached_path
                    and Path(configured_path).name.casefold() != Path(cached_path).name.casefold()
                )
            )
            if mismatch:
                self.connection_status_label.setText(
                    f"EMR: reconnect required{f' ({profile_name})' if profile_name else ''}."
                )
                self.connection_toggle.setText("Reconnect EMR")
                self._set_connection_visual_state("stale")
                self._set_toggle_checked(False)
                return
        self.connection_status_label.setText(
            f"EMR: {state.message}{f' ({profile_name})' if profile_name else ''}"
        )
        if state.status in {"green", "yellow"}:
            self.connection_toggle.setText("EMR Connected")
            self._set_connection_visual_state("connected")
        else:
            self.connection_toggle.setText("Reconnect EMR")
            self._set_connection_visual_state("stale")
        self._set_toggle_checked(state.status in {"green", "yellow"})

    def _active_profile_name(self) -> str | None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_active_emr_target_profile(connection)
        if profile is None:
            return None
        return profile.name

    def _set_toggle_checked(self, checked: bool) -> None:
        self.connection_toggle.blockSignals(True)
        self.connection_toggle.setChecked(checked)
        self.connection_toggle.blockSignals(False)

    def _set_connection_visual_state(self, state: str) -> None:
        self.connection_toggle.setProperty("emrConnectionState", state)
        style = self.connection_toggle.style()
        style.unpolish(self.connection_toggle)
        style.polish(self.connection_toggle)
        self.connection_toggle.update()

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

    def activate_launcher_item(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
    ) -> None:
        item_id = item.data(list_widget.ITEM_ID_ROLE)
        item_type = item.data(list_widget.ITEM_TYPE_ROLE)
        if not isinstance(item_id, int):
            return
        list_widget.setCurrentItem(item)
        if item_type == "macro":
            self._run_macro_by_id(item_id)
            return
        if item_type in {"clipboard", "randomized_clipboard"}:
            self._copy_macrotext_by_id(item_id)

    # Compatibility name retained for callers that still invoke the old handler.
    def run_macro_from_list(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
    ) -> None:
        self.activate_launcher_item(list_widget, item)

    def _copy_macrotext_by_id(self, item_id: int) -> None:
        success, message = _copy_macrotext(self._db_path, item_id)
        self.log.setPlainText(message)

    def _run_macro_by_id(self, item_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = get_item(connection, item_id)
        if item is None:
            self.log.setPlainText("Macro not found.")
            return
        if item.item_type != "macro":
            self.log.setPlainText("Select a macro to run.")
            return

        self.log.setPlainText(f"Running '{item.name}'...")
        application = QApplication.instance()
        if application is not None:
            application.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
            )

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=False)
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            QMessageBox.warning(
                self,
                "Application reconnection required",
                result.message,
            )
        outcome = "Completed" if result.success else "Stopped"
        self.log.setPlainText(
            f"{outcome} '{item.name}'.\n\n{_format_macro_run_result(result)}"
        )

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

    def _populate_launcher_lists(self, launcher_items: list) -> None:
        by_section = {section: [] for section in LAUNCHER_SECTIONS}
        for launcher_item in launcher_items:
            by_section.setdefault(launcher_item.launcher_section, []).append(
                launcher_item
            )
        for section, list_widget in self.launcher_lists.items():
            list_widget.blockSignals(True)
            list_widget.clear()
            for launcher_item in by_section.get(section, []):
                item = QListWidgetItem(launcher_item.name)
                item.setData(list_widget.ITEM_ID_ROLE, launcher_item.id)
                item.setData(list_widget.ITEM_TYPE_ROLE, launcher_item.item_type)
                if launcher_item.item_type == "macro":
                    item.setToolTip(_macro_profile_text(self._db_path, launcher_item))
                else:
                    mode = (
                        "Random selection"
                        if launcher_item.item_type == "randomized_clipboard"
                        else "Simple copy"
                    )
                    item.setToolTip(f"MacroText: {mode}")
                list_widget.addItem(item)
            list_widget.blockSignals(False)

    def _selected_macro_id(self) -> int | None:
        for list_widget in self.launcher_lists.values():
            current = list_widget.currentItem()
            if current is None:
                continue
            item_id = current.data(list_widget.ITEM_ID_ROLE)
            item_type = current.data(list_widget.ITEM_TYPE_ROLE)
            if isinstance(item_id, int) and item_type == "macro":
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

        self.executable_macros_table = _create_macro_table()
        self.non_executable_macros_table = _create_macro_table()
        self.macros_table = self.executable_macros_table

        self.add_macro_button = QPushButton("Add macro")
        self.add_macro_button.clicked.connect(self.add_macro)
        self.copy_macro_button = QPushButton("Copy selected macro")
        self.copy_macro_button.clicked.connect(self.copy_macro)
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
        controls.addWidget(self.copy_macro_button)
        controls.addWidget(self.edit_macro_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addWidget(self.delete_macro_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro status will appear here.")

        executable_column = QVBoxLayout()
        executable_column.addWidget(QLabel("Executable macros"))
        executable_column.addWidget(self.executable_macros_table)

        non_executable_column = QVBoxLayout()
        non_executable_column.addWidget(QLabel("Non-executable macros"))
        non_executable_column.addWidget(self.non_executable_macros_table)

        tables_row = QGridLayout()
        tables_row.setContentsMargins(0, 0, 0, 0)
        tables_row.setHorizontalSpacing(12)
        tables_row.addLayout(executable_column, 0, 0)
        tables_row.addLayout(non_executable_column, 0, 1)
        tables_row.setColumnStretch(0, 1)
        tables_row.setColumnStretch(1, 1)

        self.executable_macros_table.itemSelectionChanged.connect(
            lambda: self._sync_macro_selection(self.executable_macros_table)
        )
        self.non_executable_macros_table.itemSelectionChanged.connect(
            lambda: self._sync_macro_selection(self.non_executable_macros_table)
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.automation_summary)
        layout.addLayout(tables_row)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        macros = _load_macros(self._db_path)
        executable_macros = [macro for macro in macros if macro.is_enabled]
        non_executable_macros = [macro for macro in macros if not macro.is_enabled]
        _populate_macro_table(
            self.executable_macros_table, executable_macros, self._db_path
        )
        _populate_macro_table(
            self.non_executable_macros_table, non_executable_macros, self._db_path
        )
        macro_ids = ", ".join(str(macro.id) for macro in macros) or "None"
        self.automation_summary.setText(f"Saved automation IDs: {macro_ids}")

    def add_macro(self) -> None:
        dialog = MacroEditorDialog(self, db_path=self._db_path)
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

        dialog = MacroEditorDialog(self, item, steps, db_path=self._db_path)
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

    def copy_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to copy.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)
            copied = create_item(
                connection,
                _next_macro_copy_name(connection, item.name),
                "macro",
                item.is_enabled,
                item.emr_target_profile_id,
                launcher_section=item.launcher_section,
            )
            for step in steps:
                create_macro_step(
                    connection,
                    copied.id,
                    step.step_order,
                    step.action,
                    target_id=step.target_id,
                    value=step.value,
                    timeout_seconds=step.timeout_seconds,
                    retries=step.retries,
                    press_enter_before=getattr(step, "press_enter_before", False),
                    press_enter_after=step.press_enter_after,
                    wait_before_enabled=step.wait_before_enabled,
                    wait_before_ms=step.wait_before_ms,
                )
            reorder_macro_steps(connection, copied.id)
        self.refresh_view()
        self.log.setPlainText("Macro copied.")

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
        for table in (self.executable_macros_table, self.non_executable_macros_table):
            item_id = _selected_macro_id(table)
            if item_id is not None:
                return item_id
        return None

    def _sync_macro_selection(self, active_table: QTableWidget) -> None:
        if active_table.selectedItems():
            other_table = (
                self.non_executable_macros_table
                if active_table is self.executable_macros_table
                else self.executable_macros_table
            )
            other_table.blockSignals(True)
            other_table.clearSelection()
            other_table.blockSignals(False)
            self.macros_table = active_table


class MacroTextsPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("MacroTexts")
        title.setObjectName("pageTitle")

        self.presets_table = QTableWidget(0, 4)
        self.presets_table.setHorizontalHeaderLabels(
            ["id", "name", "mode", "options"]
        )
        self.presets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.presets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.presets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.empty_state = QLabel("No preset strings configured.")
        self.empty_state.setObjectName("presetEmptyState")

        self.add_button = QPushButton("Add MacroText")
        self.add_button.clicked.connect(self.add_macrotext)
        self.edit_button = QPushButton("Edit MacroText")
        self.edit_button.clicked.connect(self.edit_macrotext)
        self.delete_button = QPushButton("Delete MacroText")
        self.delete_button.clicked.connect(self.delete_macrotext)
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_macrotext)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)

        self.status_label = QLabel("")
        self.presets_table.cellDoubleClicked.connect(
            lambda _row, _column: self.copy_macrotext()
        )

        controls = QHBoxLayout()
        controls.addWidget(self.add_button)
        controls.addWidget(self.edit_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.copy_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.presets_table)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)

        self.refresh_view()

    def refresh_view(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            preset_items = []
            for item_type in ("clipboard", "randomized_clipboard"):
                preset_items.extend(list_items(connection, item_type))
            variant_counts = {
                item.id: len(list_clipboard_variants(connection, item.id))
                for item in preset_items
            }

        self.presets_table.setRowCount(len(preset_items))
        for row_index, item in enumerate(preset_items):
            self.presets_table.setItem(row_index, 0, QTableWidgetItem(str(item.id)))
            self.presets_table.setItem(row_index, 1, QTableWidgetItem(item.name))
            mode = (
                "Random selection"
                if item.item_type == "randomized_clipboard"
                else "Simple copy"
            )
            self.presets_table.setItem(row_index, 2, QTableWidgetItem(mode))
            self.presets_table.setItem(
                row_index, 3, QTableWidgetItem(str(variant_counts[item.id]))
            )
        self.presets_table.resizeColumnsToContents()
        has_presets = bool(preset_items)
        self.empty_state.setVisible(not has_presets)
        self.presets_table.setVisible(has_presets)

    def add_macrotext(self) -> None:
        dialog = MacroTextDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not self._validate_values(values):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = create_item(
                connection,
                values["name"],
                values["item_type"],
                True,
                launcher_section="Comments",
            )
            replace_clipboard_variants(connection, item.id, values["bodies"])
        self.refresh_view()
        self.status_label.setText("MacroText added to Comments.")

    def edit_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to edit.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = get_item(connection, item_id)
            variants = list_clipboard_variants(connection, item_id)
        if item is None:
            self.status_label.setText("MacroText not found.")
            return
        dialog = MacroTextDialog(self, item, [variant.body for variant in variants])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not self._validate_values(values):
            return
        with connect(self._db_path) as connection:
            update_item(
                connection,
                item_id,
                values["name"],
                values["item_type"],
                True,
                launcher_section="Comments",
            )
            replace_clipboard_variants(connection, item_id, values["bodies"])
        self.refresh_view()
        self.status_label.setText("MacroText updated.")

    def delete_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to delete.")
            return
        if (
            QMessageBox.question(self, "Confirm", "Delete selected MacroText?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            deleted = delete_item(connection, item_id)
        self.refresh_view()
        self.status_label.setText(
            "MacroText deleted." if deleted else "MacroText not found."
        )

    def copy_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to copy.")
            return
        _success, message = _copy_macrotext(self._db_path, item_id)
        self.status_label.setText(message)

    def _selected_item_id(self) -> int | None:
        selected = self.presets_table.selectedItems()
        if not selected:
            return None
        id_item = self.presets_table.item(selected[0].row(), 0)
        return int(id_item.text()) if id_item is not None else None

    def _validate_values(self, values: dict) -> bool:
        if not values["name"]:
            self.status_label.setText("MacroText name is required.")
            return False
        if not values["bodies"]:
            self.status_label.setText("MacroText content is required.")
            return False
        return True


class MacroTextDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        item=None,
        bodies: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("MacroText")
        self.name = QLineEdit(item.name if item is not None else "")
        self.randomized = QCheckBox("Choose one option at random")
        self.randomized.setChecked(
            item is not None and item.item_type == "randomized_clipboard"
        )
        self.content = QPlainTextEdit()
        self.content.setPlaceholderText("Enter text to copy.")
        self.content.setPlainText(
            self._display_content(bodies or [], self.randomized.isChecked())
        )
        self.randomized.toggled.connect(self._update_content_hint)
        self._update_content_hint(self.randomized.isChecked())

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Mode", self.randomized)
        form.addRow("Text", self.content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(560, 420)

    def values(self) -> dict:
        content = self.content.toPlainText().strip()
        if self.randomized.isChecked():
            bodies = self._randomized_bodies(content)
            item_type = "randomized_clipboard"
        else:
            bodies = [content] if content else []
            item_type = "clipboard"
        return {
            "name": self.name.text().strip(),
            "item_type": item_type,
            "bodies": bodies,
        }

    def _display_content(self, bodies: list[str], randomized: bool) -> str:
        return ("\n---\n" if randomized else "\n").join(bodies)

    def _randomized_bodies(self, content: str) -> list[str]:
        bodies: list[str] = []
        current_lines: list[str] = []
        for line in content.splitlines():
            if line.strip() == "---":
                body = "\n".join(current_lines).strip()
                if body:
                    bodies.append(body)
                current_lines = []
                continue
            current_lines.append(line)

        body = "\n".join(current_lines).strip()
        if body:
            bodies.append(body)
        return bodies

    def _update_content_hint(self, randomized: bool) -> None:
        self.content.setPlaceholderText(
            "Separate options with --- on its own line. Options may be multiline."
            if randomized
            else "Enter the text to copy. Multiline text is supported."
        )


PresetsPage = MacroTextsPage


class LauncherListWidget(QListWidget):
    ITEM_ID_ROLE = 256
    ITEM_TYPE_ROLE = 257

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
            " border: 1px solid #4c566a;"
            " border-radius: 6px;"
            " padding: 4px;"
            " background-color: #2e3440;"
            "}"
        )

    def dropEvent(self, event) -> None:
        source = event.source()
        if isinstance(source, LauncherListWidget):
            source_item = source.currentItem()
            item_type = (
                source_item.data(self.ITEM_TYPE_ROLE)
                if source_item is not None
                else None
            )
            if (
                item_type in {"clipboard", "randomized_clipboard"}
                and self.section != "Comments"
            ):
                event.ignore()
                return
        super().dropEvent(event)
        if event.isAccepted():
            QTimer.singleShot(0, self.launcher_page.persist_launcher_layout)


def _create_macro_table() -> QTableWidget:
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["id", "name", "EMR profile", "executable"])
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return table


def _load_macros(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return list_items(connection, "macro")


def _load_launcher_items(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return list_launcher_items(connection)


def _load_launcher_macros(db_path: Path | None) -> list:
    return [
        item for item in _load_launcher_items(db_path) if item.item_type == "macro"
    ]


def _copy_macrotext(db_path: Path | None, item_id: int) -> tuple[bool, str]:
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = get_item(connection, item_id)
        variants = list_clipboard_variants(connection, item_id)
    if item is None or item.item_type not in {"clipboard", "randomized_clipboard"}:
        return False, "MacroText not found."
    if not variants:
        return False, f"MacroText '{item.name}' has no text."
    text = (
        random.choice(variants).body
        if item.item_type == "randomized_clipboard"
        else variants[0].body
    )
    try:
        copy_text(text)
    except Exception:
        return False, "Clipboard copy failed."
    return True, f"Copied '{item.name}' to clipboard."


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


def _next_macro_copy_name(connection, base_name: str) -> str:
    existing_names = {
        item.name
        for item in list_items(connection, "macro")
    }
    if f"{base_name} Copy" not in existing_names:
        return f"{base_name} Copy"
    index = 2
    while True:
        candidate = f"{base_name} Copy {index}"
        if candidate not in existing_names:
            return candidate
        index += 1


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
