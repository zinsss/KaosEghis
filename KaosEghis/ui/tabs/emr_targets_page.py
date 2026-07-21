from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    EmrUiTargetRecord,
    create_emr_target_profile,
    create_emr_ui_target,
    delete_emr_target_profile,
    delete_emr_ui_target,
    get_default_emr_target_profile,
    get_emr_target_profile,
    get_emr_ui_target,
    list_emr_target_profiles,
    list_emr_ui_targets,
    set_default_emr_target_profile,
    update_emr_target_profile,
    update_emr_ui_target,
)
from KaosEghis.core.eghis_connector import (
    build_connector_settings,
    clear_cached_eghis_state,
    get_cached_eghis_state,
    refresh_cached_eghis_state,
)
from KaosEghis.core.ui_capture import (
    GlobalClickCaptureController,
    PointInspectionResult,
    format_capture_result,
)
from KaosEghis.db.repositories import get_settings


class EmrTargetsPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._current_profile_id: int | None = None
        self._current_ui_targets: list[EmrUiTargetRecord] = []
        self._capture_controller = GlobalClickCaptureController(self)

        title = QLabel("EMR")
        title.setObjectName("pageTitle")

        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._on_profile_changed)

        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self.create_profile)
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_profile)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_profile)
        self.set_default_button = QPushButton("Set default")
        self.set_default_button.clicked.connect(self.set_default_profile)

        profile_controls = QHBoxLayout()
        profile_controls.addWidget(self.new_button)
        profile_controls.addWidget(self.duplicate_button)
        profile_controls.addWidget(self.delete_button)
        profile_controls.addWidget(self.set_default_button)
        profile_controls.addStretch()

        self.name_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.enabled_checkbox = QCheckBox("Enabled")
        self.process_name_input = QLineEdit()
        self.executable_path_input = QLineEdit()
        self.window_title_input = QLineEdit()
        self.window_class_input = QLineEdit()
        self.root_automation_id_input = QLineEdit()
        self.main_window_automation_id_input = QLineEdit()
        self.login_window_automation_id_input = QLineEdit()
        self.patient_search_automation_id_input = QLineEdit()
        self.default_status_label = QLabel()

        detail_form = QFormLayout()
        detail_form.addRow("Name", self.name_input)
        detail_form.addRow("Description", self.description_input)
        detail_form.addRow("", self.enabled_checkbox)
        detail_form.addRow("Process name", self.process_name_input)
        detail_form.addRow("Executable path", self.executable_path_input)
        detail_form.addRow("Window title contains", self.window_title_input)
        detail_form.addRow("Window class", self.window_class_input)
        detail_form.addRow("Root automation ID", self.root_automation_id_input)
        detail_form.addRow(
            "Main window automation ID", self.main_window_automation_id_input
        )
        detail_form.addRow(
            "Login window automation ID", self.login_window_automation_id_input
        )
        detail_form.addRow(
            "Patient search automation ID", self.patient_search_automation_id_input
        )
        detail_form.addRow("Default profile", self.default_status_label)

        self.save_profile_button = QPushButton("Save profile")
        self.save_profile_button.clicked.connect(self.save_profile)
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_profile)
        self.connection_toggle = QPushButton("Connect application")
        self.connection_toggle.setCheckable(True)
        self.connection_toggle.toggled.connect(self.toggle_connection)
        self.connection_status_label = QLabel("Application connection: disconnected.")

        detail_controls = QHBoxLayout()
        detail_controls.addWidget(self.save_profile_button)
        detail_controls.addWidget(self.reload_button)
        detail_controls.addWidget(self.connection_toggle)
        detail_controls.addStretch()

        self.ui_targets_table = QTableWidget(0, 6)
        self.ui_targets_table.setHorizontalHeaderLabels(
            ["Key", "Label", "Control type", "Scope anchor", "Automation ID", "Parent key"]
        )
        self.ui_targets_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.ui_targets_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.ui_targets_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.add_target_button = QPushButton("Add target")
        self.add_target_button.clicked.connect(self.add_ui_target)
        self.edit_target_button = QPushButton("Edit target")
        self.edit_target_button.clicked.connect(self.edit_ui_target)
        self.delete_target_button = QPushButton("Delete target")
        self.delete_target_button.clicked.connect(self.delete_ui_target)
        self.capture_button = QPushButton("Capture next click")
        self.capture_button.clicked.connect(self.arm_capture)
        self.copy_capture_button = QPushButton("Copy capture details")
        self.copy_capture_button.clicked.connect(self.copy_capture_details)
        self.capture_hotkey_label = QLabel()
        self.capture_status_label = QLabel("Capture idle.")
        self.capture_result = QPlainTextEdit()
        self.capture_result.setReadOnly(True)
        self.capture_result.setPlaceholderText(
            "Captured UI details and value will appear here."
        )

        target_controls = QHBoxLayout()
        target_controls.addWidget(self.add_target_button)
        target_controls.addWidget(self.edit_target_button)
        target_controls.addWidget(self.delete_target_button)
        target_controls.addStretch()

        self.status_label = QLabel("Not loaded yet.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)

        left_column = QVBoxLayout()
        left_column.addWidget(QLabel("Profiles"))
        left_column.addWidget(self.profile_list)
        left_column.addLayout(profile_controls)
        left_column.addLayout(detail_form)
        left_column.addLayout(detail_controls)
        left_column.addWidget(self.connection_status_label)
        left_column.addStretch()

        right_column = QVBoxLayout()
        right_column.addWidget(QLabel("UI targets"))
        right_column.addWidget(self.ui_targets_table, 1)
        right_column.addLayout(target_controls)
        right_column.addWidget(QLabel("Capture from screen"))
        right_column.addWidget(self.capture_hotkey_label)
        capture_controls = QHBoxLayout()
        capture_controls.addWidget(self.capture_button)
        capture_controls.addWidget(self.copy_capture_button)
        capture_controls.addStretch()
        right_column.addLayout(capture_controls)
        right_column.addWidget(self.capture_status_label)
        right_column.addWidget(self.capture_result)

        content_grid = QGridLayout()
        content_grid.setContentsMargins(0, 0, 0, 0)
        content_grid.setHorizontalSpacing(16)
        content_grid.addLayout(left_column, 0, 0)
        content_grid.addLayout(right_column, 0, 1)
        content_grid.setColumnStretch(0, 1)
        content_grid.setColumnStretch(1, 1)

        layout.addLayout(content_grid, 1)
        layout.addWidget(self.status_label)

        self._capture_controller.armed_changed.connect(self._on_capture_armed_changed)
        self._capture_controller.capture_ready.connect(self._handle_capture_ready)
        self._capture_controller.capture_failed.connect(self._handle_capture_failed)
        hotkey_started = self._capture_controller.start_hotkey_listener()
        self.capture_hotkey_label.setText(
            "Global capture hotkey: Ctrl+Shift+F8"
            if hotkey_started
            else "Global capture hotkey unavailable. Use the button."
        )

        self.refresh_view()

    def refresh_view(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profiles = list_emr_target_profiles(connection)
            default_profile = get_default_emr_target_profile(connection)

        selected_profile_id = self._current_profile_id
        if selected_profile_id is None and default_profile is not None:
            selected_profile_id = default_profile.id
        elif selected_profile_id is None and profiles:
            selected_profile_id = profiles[0].id

        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for profile in profiles:
            label = profile.name
            if profile.is_default:
                label += " [default]"
            if not profile.is_enabled:
                label += " [disabled]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self.profile_list.addItem(item)
        self.profile_list.blockSignals(False)

        if selected_profile_id is None:
            self._current_profile_id = None
            self._load_profile_form(None)
            self._current_ui_targets = []
            self._refresh_ui_targets_table()
            self._refresh_connection_status()
            self.status_label.setText("No EMR target profiles available.")
            return

        self._select_profile_in_list(selected_profile_id)
        self._load_profile(selected_profile_id)

    def create_profile(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = create_emr_target_profile(
                connection,
                name=self._next_profile_name(connection, "New EMR Profile"),
                description="",
                is_enabled=True,
                is_default=False,
            )
        self._current_profile_id = profile.id
        self.refresh_view()
        self.status_label.setText("Profile created.")

    def duplicate_profile(self) -> None:
        profile_id = self._current_profile_id
        if profile_id is None:
            self.status_label.setText("Select a profile to duplicate.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_emr_target_profile(connection, profile_id)
            if profile is None:
                self.status_label.setText("Selected profile was not found.")
                return
            duplicate = create_emr_target_profile(
                connection,
                name=self._next_profile_name(connection, f"{profile.name} Copy"),
                description=profile.description,
                is_enabled=profile.is_enabled,
                is_default=False,
                process_name=profile.process_name,
                executable_path=profile.executable_path,
                window_title_contains=profile.window_title_contains,
                window_class=profile.window_class,
                root_automation_id=profile.root_automation_id,
                main_window_automation_id=profile.main_window_automation_id,
                login_window_automation_id=profile.login_window_automation_id,
                patient_search_automation_id=profile.patient_search_automation_id,
            )
            for target in list_emr_ui_targets(connection, profile.id):
                create_emr_ui_target(
                    connection,
                    profile_id=duplicate.id,
                    target_key=target.target_key,
                    label=target.label,
                    description=target.description,
                    scope_automation_id=target.scope_automation_id,
                    automation_id=target.automation_id,
                    control_type=target.control_type,
                    class_name=target.class_name,
                    name_match=target.name_match,
                    parent_target_key=target.parent_target_key,
                    ancestor_path=target.ancestor_path,
                )
        self._current_profile_id = duplicate.id
        self.refresh_view()
        self.status_label.setText("Profile duplicated.")

    def delete_profile(self) -> None:
        profile_id = self._current_profile_id
        if profile_id is None:
            self.status_label.setText("Select a profile to delete.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete EMR profile",
                "Delete the selected EMR target profile?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        initialize_database(self._db_path)
        try:
            with connect(self._db_path) as connection:
                deleted = delete_emr_target_profile(connection, profile_id)
        except ValueError as error:
            self.status_label.setText(str(error))
            return

        self._current_profile_id = None
        self.refresh_view()
        self.status_label.setText("Profile deleted." if deleted else "Profile not found.")

    def set_default_profile(self) -> None:
        profile_id = self._current_profile_id
        if profile_id is None:
            self.status_label.setText("Select a profile to set as default.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = set_default_emr_target_profile(connection, profile_id)
        self._current_profile_id = profile.id if profile is not None else None
        self.refresh_view()
        self.status_label.setText("Default profile updated.")

    def save_profile(self) -> None:
        profile_id = self._current_profile_id
        if profile_id is None:
            self.status_label.setText("Select a profile to save.")
            return
        name = self.name_input.text().strip()
        if not name:
            self.status_label.setText("Profile name is required.")
            return

        initialize_database(self._db_path)
        try:
            with connect(self._db_path) as connection:
                update_emr_target_profile(
                    connection,
                    profile_id,
                    name=name,
                    description=self.description_input.toPlainText().strip(),
                    is_enabled=self.enabled_checkbox.isChecked(),
                    is_default="[default]" in self.default_status_label.text(),
                    process_name=self.process_name_input.text(),
                    executable_path=self.executable_path_input.text(),
                    window_title_contains=self.window_title_input.text(),
                    window_class=self.window_class_input.text(),
                    root_automation_id=self.root_automation_id_input.text(),
                    main_window_automation_id=self.main_window_automation_id_input.text(),
                    login_window_automation_id=self.login_window_automation_id_input.text(),
                    patient_search_automation_id=self.patient_search_automation_id_input.text(),
                )
        except sqlite3.IntegrityError:
            self.status_label.setText("Profile name must be unique.")
            return

        self.refresh_view()
        self.status_label.setText("Profile saved.")

    def reload_profile(self) -> None:
        if self._current_profile_id is None:
            self.status_label.setText("Select a profile to reload.")
            return
        self._load_profile(self._current_profile_id)
        self.status_label.setText("Profile reloaded.")

    def add_ui_target(self) -> None:
        if self._current_profile_id is None:
            self.status_label.setText("Select a profile before adding UI targets.")
            return
        dialog = EmrUiTargetDialog(self, existing_targets=self._current_ui_targets)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database(self._db_path)
        try:
            with connect(self._db_path) as connection:
                create_emr_ui_target(
                    connection,
                    profile_id=self._current_profile_id,
                    **values,
                )
        except sqlite3.IntegrityError:
            self.status_label.setText("Target key must be unique within the profile.")
            return
        self._load_profile(self._current_profile_id)
        self.status_label.setText("UI target added.")

    def edit_ui_target(self) -> None:
        ui_target_id = self._selected_ui_target_id()
        if ui_target_id is None:
            self.status_label.setText("Select a UI target to edit.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            target = get_emr_ui_target(connection, ui_target_id)
        if target is None:
            self.status_label.setText("Selected UI target was not found.")
            return

        dialog = EmrUiTargetDialog(
            self,
            target,
            existing_targets=self._current_ui_targets,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database(self._db_path)
        try:
            with connect(self._db_path) as connection:
                update_emr_ui_target(connection, ui_target_id, **values)
        except sqlite3.IntegrityError:
            self.status_label.setText("Target key must be unique within the profile.")
            return
        if self._current_profile_id is not None:
            self._load_profile(self._current_profile_id)
        self.status_label.setText("UI target updated.")

    def delete_ui_target(self) -> None:
        ui_target_id = self._selected_ui_target_id()
        if ui_target_id is None:
            self.status_label.setText("Select a UI target to delete.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete UI target",
                "Delete the selected UI target?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            deleted = delete_emr_ui_target(connection, ui_target_id)
        if self._current_profile_id is not None:
            self._load_profile(self._current_profile_id)
        self.status_label.setText("UI target deleted." if deleted else "UI target not found.")

    def _on_profile_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        profile_id = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(profile_id, int):
            self._load_profile(profile_id)

    def _load_profile(self, profile_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_emr_target_profile(connection, profile_id)
            ui_targets = list_emr_ui_targets(connection, profile_id)

        if profile is None:
            self._current_profile_id = None
            self._load_profile_form(None)
            self._current_ui_targets = []
            self._refresh_ui_targets_table()
            self._refresh_connection_status()
            self.status_label.setText("Profile not found.")
            return

        self._current_profile_id = profile.id
        self._load_profile_form(profile)
        self._current_ui_targets = ui_targets
        self._refresh_ui_targets_table()
        self._refresh_connection_status()

    def _load_profile_form(self, profile) -> None:
        if profile is None:
            self.name_input.clear()
            self.description_input.clear()
            self.enabled_checkbox.setChecked(False)
            self.process_name_input.clear()
            self.executable_path_input.clear()
            self.window_title_input.clear()
            self.window_class_input.clear()
            self.root_automation_id_input.clear()
            self.main_window_automation_id_input.clear()
            self.login_window_automation_id_input.clear()
            self.patient_search_automation_id_input.clear()
            self.default_status_label.setText("")
            return

        self.name_input.setText(profile.name)
        self.description_input.setPlainText(profile.description or "")
        self.enabled_checkbox.setChecked(profile.is_enabled)
        self.process_name_input.setText(profile.process_name or "")
        self.executable_path_input.setText(profile.executable_path or "")
        self.window_title_input.setText(profile.window_title_contains or "")
        self.window_class_input.setText(profile.window_class or "")
        self.root_automation_id_input.setText(profile.root_automation_id or "")
        self.main_window_automation_id_input.setText(
            profile.main_window_automation_id or ""
        )
        self.login_window_automation_id_input.setText(
            profile.login_window_automation_id or ""
        )
        self.patient_search_automation_id_input.setText(
            profile.patient_search_automation_id or ""
        )
        self.default_status_label.setText(
            "[default]" if profile.is_default else "No"
        )

    def toggle_connection(self, checked: bool) -> None:
        if checked:
            self.connect_selected_profile()
            return
        clear_cached_eghis_state()
        self._refresh_connection_status()
        self.status_label.setText("Application disconnected.")

    def connect_selected_profile(self) -> None:
        settings = self._selected_profile_connector_settings()
        if settings is None:
            self.connection_toggle.blockSignals(True)
            self.connection_toggle.setChecked(False)
            self.connection_toggle.blockSignals(False)
            self.status_label.setText("Select a profile to connect.")
            self._refresh_connection_status()
            return

        state = refresh_cached_eghis_state(settings)
        connected = state.status in {"green", "yellow"} and state.pid is not None
        self.connection_toggle.blockSignals(True)
        self.connection_toggle.setChecked(connected)
        self.connection_toggle.blockSignals(False)
        self._refresh_connection_status()
        self.status_label.setText(state.message)

    def _selected_profile_connector_settings(self) -> dict[str, str] | None:
        profile_id = self._current_profile_id
        if profile_id is None:
            return None
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_emr_target_profile(connection, profile_id)
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
        settings = self._selected_profile_connector_settings()
        if state is None:
            self.connection_status_label.setText("Application connection: disconnected.")
            self.connection_toggle.setText("Connect application")
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
                    "Application connection: cached app does not match this preset."
                )
                self.connection_toggle.setText("Connect application")
                self._set_toggle_checked(False)
                return
        self.connection_status_label.setText(f"Application connection: {state.message}")
        self.connection_toggle.setText(
            "Disconnect application" if state.status in {"green", "yellow"} else "Connect application"
        )
        self._set_toggle_checked(state.status in {"green", "yellow"})

    def _set_toggle_checked(self, checked: bool) -> None:
        self.connection_toggle.blockSignals(True)
        self.connection_toggle.setChecked(checked)
        self.connection_toggle.blockSignals(False)

    def _refresh_ui_targets_table(self) -> None:
        self.ui_targets_table.setRowCount(len(self._current_ui_targets))
        for row_index, target in enumerate(self._current_ui_targets):
            key_item = QTableWidgetItem(target.target_key)
            key_item.setData(Qt.ItemDataRole.UserRole, target.id)
            self.ui_targets_table.setItem(row_index, 0, key_item)
            self.ui_targets_table.setItem(row_index, 1, QTableWidgetItem(target.label))
            self.ui_targets_table.setItem(
                row_index, 2, QTableWidgetItem(target.control_type or "")
            )
            self.ui_targets_table.setItem(
                row_index, 3, QTableWidgetItem(target.scope_automation_id or "")
            )
            self.ui_targets_table.setItem(
                row_index, 4, QTableWidgetItem(target.automation_id or "")
            )
            self.ui_targets_table.setItem(
                row_index, 5, QTableWidgetItem(target.parent_target_key or "")
            )
        self.ui_targets_table.resizeColumnsToContents()

    def _selected_ui_target_id(self) -> int | None:
        selected = self.ui_targets_table.selectedItems()
        if not selected:
            return None
        item = self.ui_targets_table.item(selected[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None

    def _select_profile_in_list(self, profile_id: int) -> None:
        for index in range(self.profile_list.count()):
            item = self.profile_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == profile_id:
                self.profile_list.setCurrentRow(index)
                return

    def _next_profile_name(
        self, connection: sqlite3.Connection, base_name: str
    ) -> str:
        existing_names = {profile.name for profile in list_emr_target_profiles(connection)}
        if base_name not in existing_names:
            return base_name
        index = 2
        while True:
            candidate = f"{base_name} {index}"
            if candidate not in existing_names:
                return candidate
            index += 1

    def arm_capture(self) -> None:
        if self._capture_controller.arm_capture():
            self.capture_status_label.setText(
                "Capture armed. Click any EMR control to inspect it."
            )
        else:
            self.capture_status_label.setText("Capture is unavailable.")

    def copy_capture_details(self) -> None:
        text = self.capture_result.toPlainText().strip()
        if not text:
            self.capture_status_label.setText("No capture details to copy yet.")
            return
        try:
            copy_text(text)
        except Exception:
            self.capture_status_label.setText("Capture details could not be copied.")
            return
        self.capture_status_label.setText("Capture details copied to clipboard.")

    def _on_capture_armed_changed(self, armed: bool) -> None:
        if armed:
            self.capture_button.setText("Capture armed...")
            return
        self.capture_button.setText("Capture next click")

    def _handle_capture_ready(self, result: PointInspectionResult) -> None:
        details = format_capture_result(result)
        self.capture_result.setPlainText(details)
        try:
            copy_text(details)
            copied = True
        except Exception:
            copied = False
        if result.success:
            suffix = " Details copied to clipboard." if copied else ""
            self.capture_status_label.setText(f"{result.message}{suffix}")
        else:
            self.capture_status_label.setText(result.message)

    def _handle_capture_failed(self, message: str) -> None:
        self.capture_status_label.setText(message)

    def closeEvent(self, event) -> None:
        self._capture_controller.stop()
        super().closeEvent(event)


class EmrUiTargetDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        target: EmrUiTargetRecord | None = None,
        existing_targets: list[EmrUiTargetRecord] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("EMR UI Target")
        self._existing_targets = existing_targets or []

        self.target_key_input = QLineEdit()
        self.label_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.scope_automation_id_input = QLineEdit()
        self.automation_id_input = QLineEdit()
        self.control_type_input = QLineEdit()
        self.class_name_input = QLineEdit()
        self.name_match_input = QLineEdit()
        self.parent_target_key_input = QLineEdit()
        self.ancestor_path_preview = QPlainTextEdit()
        self.ancestor_path_preview.setReadOnly(True)
        self.ancestor_path_preview.setPlaceholderText(
            "Parsed ancestor path will appear here."
        )
        self.inspector_dump_input = QPlainTextEdit()
        self.inspector_dump_input.setPlaceholderText(
            "Paste Inspector.exe details here to auto-fill fields."
        )
        self.parse_inspector_button = QPushButton("Parse Inspector text")
        self.parse_inspector_button.clicked.connect(self._apply_inspector_dump)
        self.parse_status_label = QLabel("")

        form = QFormLayout(self)
        form.addRow("Key", self.target_key_input)
        form.addRow("Label", self.label_input)
        form.addRow("Description", self.description_input)
        form.addRow("Scope automation ID", self.scope_automation_id_input)
        form.addRow("Automation ID", self.automation_id_input)
        form.addRow("Control type", self.control_type_input)
        form.addRow("Class name", self.class_name_input)
        form.addRow("Name match", self.name_match_input)
        form.addRow("Parent key", self.parent_target_key_input)
        form.addRow("Ancestor path", self.ancestor_path_preview)
        form.addRow("Inspector paste", self.inspector_dump_input)
        form.addRow("", self.parse_inspector_button)
        form.addRow("", self.parse_status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._ancestor_path_value = ""

        if target is not None:
            self.target_key_input.setText(target.target_key)
            self.label_input.setText(target.label)
            self.description_input.setPlainText(target.description or "")
            self.scope_automation_id_input.setText(target.scope_automation_id or "")
            self.automation_id_input.setText(target.automation_id or "")
            self.control_type_input.setText(target.control_type or "")
            self.class_name_input.setText(target.class_name or "")
            self.name_match_input.setText(target.name_match or "")
            self.parent_target_key_input.setText(target.parent_target_key or "")
            self._ancestor_path_value = target.ancestor_path or ""
            self.ancestor_path_preview.setPlainText(
                summarize_ancestor_path(self._ancestor_path_value)
            )

    def accept(self) -> None:
        if not self.target_key_input.text().strip():
            QMessageBox.warning(self, "Validation", "Target key is required.")
            return
        if not self.label_input.text().strip():
            QMessageBox.warning(self, "Validation", "Label is required.")
            return
        super().accept()

    def values(self) -> dict[str, str]:
        return {
            "target_key": self.target_key_input.text().strip(),
            "label": self.label_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "scope_automation_id": self.scope_automation_id_input.text().strip(),
            "automation_id": self.automation_id_input.text().strip(),
            "control_type": self.control_type_input.text().strip(),
            "class_name": self.class_name_input.text().strip(),
            "name_match": self.name_match_input.text().strip(),
            "parent_target_key": self.parent_target_key_input.text().strip(),
            "ancestor_path": self._ancestor_path_value,
        }

    def _apply_inspector_dump(self) -> None:
        parsed = parse_inspector_dump(
            self.inspector_dump_input.toPlainText(),
            self._existing_targets,
        )
        if not parsed:
            self.parse_status_label.setText("Inspector text could not be parsed.")
            return

        automation_id = parsed.get("automation_id", "")
        scope_automation_id = parsed.get("scope_automation_id", "")
        label = parsed.get("label", "")
        name_match = parsed.get("name_match", "")
        control_type = parsed.get("control_type", "")
        class_name = parsed.get("class_name", "")
        target_key = parsed.get("target_key", "")
        parent_target_key = parsed.get("parent_target_key", "")
        ancestor_path = parsed.get("ancestor_path", "")
        ancestor_summary = parsed.get("ancestor_summary", "")

        if target_key and not self.target_key_input.text().strip():
            self.target_key_input.setText(target_key)
        if label and not self.label_input.text().strip():
            self.label_input.setText(label)
        if scope_automation_id and not self.scope_automation_id_input.text().strip():
            self.scope_automation_id_input.setText(scope_automation_id)
        if automation_id:
            self.automation_id_input.setText(automation_id)
        if control_type:
            self.control_type_input.setText(control_type)
        if class_name:
            self.class_name_input.setText(class_name)
        if name_match:
            self.name_match_input.setText(name_match)
        if parent_target_key and not self.parent_target_key_input.text().strip():
            self.parent_target_key_input.setText(parent_target_key)
        if ancestor_path:
            self._ancestor_path_value = ancestor_path
            self.ancestor_path_preview.setPlainText(
                ancestor_summary or summarize_ancestor_path(ancestor_path)
            )

        if ancestor_summary and not self.description_input.toPlainText().strip():
            self.description_input.setPlainText(ancestor_summary)

        message_parts = ["Inspector fields applied."]
        if parent_target_key:
            message_parts.append(f"Matched parent key: {parent_target_key}")
        if ancestor_path:
            message_parts.append("Stored ancestor path.")
        self.parse_status_label.setText(" ".join(message_parts))


_QUOTED_VALUE_PATTERNS = {
    "automation_id": (
        re.compile(r"automationid\s*[:=]\s*\"([^\"]+)\"", re.IGNORECASE),
        re.compile(r"automation id\s*[:=]\s*\"([^\"]+)\"", re.IGNORECASE),
    ),
    "class_name": (
        re.compile(r"classname\s*[:=]\s*\"([^\"]+)\"", re.IGNORECASE),
        re.compile(r"class name\s*[:=]\s*\"([^\"]+)\"", re.IGNORECASE),
    ),
    "name_match": (
        re.compile(r"name\s*[:=]\s*\"([^\"]+)\"", re.IGNORECASE),
    ),
}

_CONTROL_TYPE_PATTERNS = (
    re.compile(r"controltype\s*[:=]\s*uia_([a-z0-9]+)controltypeid", re.IGNORECASE),
    re.compile(r"control type\s*[:=]\s*uia_([a-z0-9]+)controltypeid", re.IGNORECASE),
)

_KOREAN_CONTROL_TYPE_MAP = {
    "도구 모음": "ToolBar",
    "그룹": "Group",
    "창": "Window",
    "단추": "Button",
    "버튼": "Button",
    "편집": "Edit",
    "문서": "Document",
    "목록": "List",
    "테이블": "Table",
    "콤보 상자": "ComboBox",
    "탭": "Tab",
    "탭 항목": "TabItem",
    "텍스트": "Text",
    "창틀": "Pane",
}


def parse_inspector_dump(
    text: str,
    existing_targets: list[EmrUiTargetRecord] | None = None,
) -> dict[str, str]:
    inspector_text = text.strip()
    if not inspector_text:
        return {}

    parsed: dict[str, str] = {}
    for key, patterns in _QUOTED_VALUE_PATTERNS.items():
        value = _first_match(inspector_text, patterns)
        if value:
            parsed[key] = value

    control_type = _parse_control_type(inspector_text)
    if control_type:
        parsed["control_type"] = control_type

    label = parsed.get("name_match") or parsed.get("automation_id") or ""
    if label:
        parsed["label"] = label
    target_key = _suggest_target_key(parsed.get("automation_id"), parsed.get("name_match"))
    if target_key:
        parsed["target_key"] = target_key

    ancestor_nodes = _parse_ancestor_nodes(inspector_text)
    if ancestor_nodes:
        parsed["ancestor_path"] = json.dumps(ancestor_nodes, ensure_ascii=False)
        parsed["ancestor_summary"] = summarize_ancestor_path(parsed["ancestor_path"])
        scope_automation_id = _infer_scope_automation_id(ancestor_nodes)
        if scope_automation_id:
            parsed["scope_automation_id"] = scope_automation_id
        parent_target_key = _match_parent_target_key(ancestor_nodes, existing_targets or [])
        if parent_target_key:
            parsed["parent_target_key"] = parent_target_key

    return parsed


def _first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def _parse_control_type(text: str) -> str:
    for pattern in _CONTROL_TYPE_PATTERNS:
        match = pattern.search(text)
        if match:
            token = match.group(1).strip()
            return token[:1].upper() + token[1:]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith('"'):
            continue
        for korean_label, control_type in _KOREAN_CONTROL_TYPE_MAP.items():
            if line.endswith(korean_label):
                return control_type
    return ""


def _suggest_target_key(automation_id: str | None, name_match: str | None) -> str:
    source = (automation_id or name_match or "").strip()
    if not source:
        return ""
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", source)
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized


def _parse_ancestor_nodes(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    ancestors: list[dict[str, str]] = []
    in_ancestors = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("ancestors:"):
            in_ancestors = True
            remainder = line.partition(":")[2].strip()
            if remainder.startswith('"'):
                node = _parse_ancestor_line(remainder)
                if node:
                    ancestors.append(node)
            continue
        if not in_ancestors:
            continue
        if not line.startswith('"'):
            break
        node = _parse_ancestor_line(line)
        if node:
            ancestors.append(node)
    return ancestors


def _extract_leading_quoted_value(line: str) -> str:
    match = re.match(r'"([^\"]*)"', line)
    if not match:
        return ""
    return match.group(1).strip()


def _parse_ancestor_line(line: str) -> dict[str, str]:
    name = _extract_leading_quoted_value(line)
    remainder = line[len(f'"{name}"') :].strip() if name else line.strip()
    control_type = ""
    for korean_label, mapped in _KOREAN_CONTROL_TYPE_MAP.items():
        if remainder.endswith(korean_label):
            control_type = mapped
            break
    node: dict[str, str] = {}
    if name:
        node["name"] = name
    if control_type:
        node["control_type"] = control_type
    return node


def _infer_scope_automation_id(ancestor_nodes: list[dict[str, str]]) -> str:
    if not ancestor_nodes:
        return ""
    for node in ancestor_nodes:
        automation_id = str(node.get("automation_id", "")).strip()
        if automation_id:
            return automation_id
        name = str(node.get("name", "")).strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", name):
            return name
    return ""


def summarize_ancestor_path(ancestor_path: str | None) -> str:
    if not ancestor_path:
        return ""
    try:
        nodes = json.loads(ancestor_path)
    except json.JSONDecodeError:
        return ancestor_path
    if not isinstance(nodes, list):
        return ""
    names = [
        str(node.get("name", "")).strip()
        for node in nodes
        if isinstance(node, dict) and str(node.get("name", "")).strip()
    ]
    if not names:
        return ""
    return "Ancestors: " + " > ".join(names)


def _match_parent_target_key(
    ancestors: list[dict[str, str]],
    existing_targets: list[EmrUiTargetRecord],
) -> str:
    ancestor_names = [
        str(node.get("name", "")).strip()
        for node in ancestors
        if isinstance(node, dict)
    ]
    meaningful_ancestors = [
        name for name in ancestor_names if name and name not in {"", "데스크톱 2"}
    ]
    for ancestor_name in meaningful_ancestors:
        matches = [
            target.target_key
            for target in existing_targets
            if ancestor_name.casefold()
            in {
                (target.label or "").casefold(),
                (target.name_match or "").casefold(),
                (target.automation_id or "").casefold(),
            }
        ]
        if len(matches) == 1:
            return matches[0]
    return ""
