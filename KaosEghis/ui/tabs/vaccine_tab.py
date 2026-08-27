from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from KaosEghis.core.eghis_connector import build_connector_settings
from KaosEghis.core.vaccine_patient_context import fetch_vaccine_patient_context
from KaosEghis.core.vaccine_eligibility import (
    InfluenzaEligibilityResult,
    evaluate_influenza_program,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_vaccine_record,
    create_vaccine_type,
    delete_vaccine_record,
    delete_vaccine_type,
    get_today_vaccine_counts,
    get_active_emr_target_profile,
    get_emr_ui_target_by_key,
    get_settings,
    get_vaccine_record,
    get_vaccine_type,
    list_vaccine_records,
    list_vaccine_types,
    reorder_vaccine_types,
    update_vaccine_record,
    update_vaccine_type,
)
from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage


VACCINE_TARGET_KEYS = {
    "chart_no": "vaccine.patient_chart_no",
    "resident_id": "vaccine.patient_resident_id",
    "patient_name": "vaccine.patient_name",
    "sex_age": "vaccine.patient_sex_age",
    "birth_date": "vaccine.patient_birth_date",
    "mobile_phone": "vaccine.patient_phone",
    "telephone": "vaccine.patient_telephone",
    "address": "vaccine.patient_address",
}


class VaccineTypeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, vaccine_type=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vaccine Type")

        self.name_input = QLineEdit(getattr(vaccine_type, "name", ""))
        self.code_input = QLineEdit(getattr(vaccine_type, "code", "") or "")
        self.chart_note_input = QPlainTextEdit(
            getattr(vaccine_type, "chart_note_template", "") or ""
        )
        self.active_button = QPushButton("Enabled")
        self.active_button.setCheckable(True)
        self.active_button.setChecked(bool(getattr(vaccine_type, "is_active", True)))

        form = QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Code", self.code_input)
        form.addRow("Chart note", self.chart_note_input)
        form.addRow("State", self.active_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(420, 320)

    def values(self) -> dict[str, object]:
        return {
            "name": self.name_input.text().strip(),
            "code": self.code_input.text().strip(),
            "chart_note_template": self.chart_note_input.toPlainText().strip(),
            "is_active": self.active_button.isChecked(),
        }


class VaccineTab(QWidget):
    TOP_PAGES = ["Main", "DB", "Settings"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._current_record_id: int | None = None
        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        title = QLabel("Vaccine")
        title.setObjectName("pageTitle")

        self.patient_chart_no_input = QLineEdit()
        self.patient_resident_id_input = QLineEdit()
        self.patient_name_input = QLineEdit()
        self.patient_sex_input = QLineEdit()
        self.patient_age_input = QLineEdit()
        self.patient_birth_date_input = QLineEdit()
        self.patient_phone_input = QLineEdit()
        self.patient_address_input = QLineEdit()

        self.today_influenza_count_label = QLabel("Influenza today: 0 / 100")
        self.today_covid_count_label = QLabel("COVID-19 today: 0 / 100")
        self.influenza_check_button = QPushButton("Check influenza program")
        self.influenza_check_button.clicked.connect(self.check_influenza_program)
        self.influenza_check_result = QLabel("Influenza program: Not checked.")
        self.influenza_check_result.setObjectName("influenzaProgramResult")
        self.influenza_check_result.setWordWrap(True)

        patient_form = QFormLayout()
        patient_form.addRow("Chart No", self.patient_chart_no_input)
        patient_form.addRow("Resident ID", self.patient_resident_id_input)
        patient_form.addRow("Name", self.patient_name_input)
        patient_form.addRow("Sex", self.patient_sex_input)
        patient_form.addRow("Age", self.patient_age_input)
        patient_form.addRow("DOB", self.patient_birth_date_input)
        patient_form.addRow("Phone", self.patient_phone_input)
        patient_form.addRow("Address", self.patient_address_input)

        self.vaccine_types_list = QListWidget()
        self.vaccine_types_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.vaccine_types_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.vaccine_types_list.model().rowsMoved.connect(
            lambda *_args: self.persist_vaccine_type_order()
        )
        self.vaccine_types_list.currentItemChanged.connect(
            self._refresh_chart_note_preview
        )

        self.add_type_button = QPushButton("Add type")
        self.add_type_button.clicked.connect(self.add_vaccine_type)
        self.edit_type_button = QPushButton("Edit type")
        self.edit_type_button.clicked.connect(self.edit_vaccine_type)
        self.delete_type_button = QPushButton("Delete type")
        self.delete_type_button.clicked.connect(self.delete_vaccine_type)

        vaccine_type_controls = QHBoxLayout()
        vaccine_type_controls.addWidget(self.add_type_button)
        vaccine_type_controls.addWidget(self.edit_type_button)
        vaccine_type_controls.addWidget(self.delete_type_button)
        vaccine_type_controls.addStretch()

        self.chart_note_preview = QPlainTextEdit()
        self.chart_note_preview.setReadOnly(True)
        self.chart_note_preview.setPlaceholderText(
            "Selected vaccine chart note template."
        )
        self.label_preview = QPlainTextEdit()
        self.label_preview.setReadOnly(True)
        self.label_preview.setPlaceholderText("Thermal label preview appears here.")
        self.charting_text_preview = QPlainTextEdit()
        self.charting_text_preview.setReadOnly(True)
        self.charting_text_preview.setPlaceholderText("Prepared charting text appears here.")
        for widget in (
            self.patient_chart_no_input,
            self.patient_resident_id_input,
            self.patient_name_input,
            self.patient_sex_input,
            self.patient_age_input,
            self.patient_birth_date_input,
            self.patient_phone_input,
            self.patient_address_input,
        ):
            widget.textChanged.connect(self._refresh_previews)
        self.patient_resident_id_input.textChanged.connect(
            lambda _text: self._reset_influenza_check()
        )

        self.records_table = self._create_records_table()
        self.general_records_table = self._create_records_table()
        self.flu_records_table = self._create_records_table()
        self.covid_records_table = self._create_records_table()

        self.fetch_button = QPushButton("Fetch from EMR")
        self.fetch_button.clicked.connect(self.fetch_current_patient_from_emr)
        self.save_button = QPushButton("Save record")
        self.save_button.clicked.connect(self.save_record)
        self.clear_button = QPushButton("Clear form")
        self.clear_button.clicked.connect(self.clear_form)
        self.load_button = QPushButton("Load selected")
        self.load_button.clicked.connect(self.load_selected_record)
        self.delete_button = QPushButton("Delete selected")
        self.delete_button.clicked.connect(self.delete_selected_record)
        self.refresh_records_button = QPushButton("Refresh records")
        self.refresh_records_button.clicked.connect(self.refresh_view)

        self.main_page = self._build_main_page(patient_form, vaccine_type_controls)
        self.db_page = self._build_db_page()
        self.settings_page = VaccineSettingsPage(self._db_path)
        self.settings_page.settings_changed.connect(
            self._handle_vaccine_settings_changed
        )
        for page in (self.main_page, self.db_page, self.settings_page):
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

        self.status_label = QLabel("Ready.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(self.top_nav_row)
        layout.addWidget(self.stacked_widget, 1)
        layout.addWidget(self.status_label)

        self.show_page(0)
        self.refresh_view()

    def activate_page(self) -> None:
        self.refresh_view()

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

    def refresh_view(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            vaccine_types = list_vaccine_types(connection)
            records = list_vaccine_records(connection)
            settings = get_settings(connection)
            counts = get_today_vaccine_counts(
                connection,
                datetime.now().date().isoformat(),
            )
        self._populate_vaccine_types(vaccine_types)
        self._populate_records(self.records_table, records)
        self._populate_records(self.general_records_table, self._filter_records(records, "general"))
        self._populate_records(self.flu_records_table, self._filter_records(records, "flu"))
        self._populate_records(self.covid_records_table, self._filter_records(records, "covid"))
        self._update_today_counts(settings, counts)
        self._refresh_previews()

    def fetch_current_patient_from_emr(self) -> bool:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_active_emr_target_profile(connection)
            settings = get_settings(connection)

        if profile is None:
            self.status_label.setText("No enabled EMR profile is available.")
            return False

        connector_settings = build_connector_settings(
            settings,
            process_name=profile.process_name or settings.get("eghis_process_name"),
            window_title_contains=profile.window_title_contains
            or settings.get("eghis_window_title_contains"),
            executable_path=profile.executable_path
            or settings.get("eghis_executable_path"),
            main_window_automation_id=getattr(profile, "main_window_automation_id", None)
            or settings.get("eghis_main_window_automation_id"),
            patient_status_tab_automation_id=getattr(
                profile, "patient_status_tab_automation_id", None
            )
            or settings.get("eghis_patient_status_tab_automation_id")
            or "tabProc",
            prescription_grid_automation_id=getattr(
                profile, "prescription_grid_automation_id", None
            )
            or settings.get("eghis_prescription_grid_automation_id")
            or "tree처방",
            symptom_grid_automation_id=getattr(
                profile, "symptom_grid_automation_id", None
            )
            or settings.get("eghis_symptom_grid_automation_id")
            or "grdSymp",
            diagnosis_grid_automation_id=getattr(
                profile, "diagnosis_grid_automation_id", None
            )
            or settings.get("eghis_diagnosis_grid_automation_id")
            or "tree상병",
            patient_list_grid_automation_id=getattr(
                profile, "patient_list_grid_automation_id", None
            )
            or settings.get("eghis_patient_list_grid_automation_id")
            or "grdOpdList",
        )

        target_automation_ids: dict[str, str] = {}
        with connect(self._db_path) as connection:
            for field_name, target_key in VACCINE_TARGET_KEYS.items():
                target = get_emr_ui_target_by_key(connection, profile.id, target_key)
                if target is not None and target.automation_id:
                    target_automation_ids[field_name] = target.automation_id

        result = fetch_vaccine_patient_context(
            connector_settings,
            target_automation_ids,
        )
        if not result.success or result.context is None:
            self.status_label.setText(result.message)
            return False

        context = result.context
        self.patient_chart_no_input.setText(context.chart_no)
        self.patient_resident_id_input.setText(context.resident_id)
        self.patient_name_input.setText(context.patient_name)
        self.patient_sex_input.setText(context.patient_sex)
        self.patient_age_input.setText(context.patient_age)
        self.patient_birth_date_input.setText(context.patient_birth_date)
        self.patient_phone_input.setText(context.patient_phone)
        self.patient_address_input.setText(context.patient_address)
        self.status_label.setText(result.message)
        return True

    def check_influenza_program(self) -> InfluenzaEligibilityResult:
        initialize_database(self._db_path)
        today = datetime.now().date()
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            counts = get_today_vaccine_counts(connection, today.isoformat())
        result = evaluate_influenza_program(
            settings,
            self.patient_resident_id_input.text(),
            on_date=today,
            counted_today=counts.get("flu", 0),
        )
        self._show_influenza_check(result)
        return result

    def save_record(self) -> None:
        selected = self.vaccine_types_list.currentItem()
        if selected is None:
            self.status_label.setText("Select a vaccine type first.")
            return
        vaccine_type_id = selected.data(Qt.ItemDataRole.UserRole)
        vaccine_type_name = selected.text()
        if not self.patient_name_input.text().strip() and not self.patient_resident_id_input.text().strip():
            self.status_label.setText("Load or enter patient context first.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            if self._current_record_id is None:
                create_vaccine_record(
                    connection,
                    vaccine_type_id=vaccine_type_id if isinstance(vaccine_type_id, int) else None,
                    vaccine_type_name=vaccine_type_name,
                    patient_chart_no=self.patient_chart_no_input.text(),
                    patient_resident_id=self.patient_resident_id_input.text(),
                    patient_name=self.patient_name_input.text(),
                    patient_sex=self.patient_sex_input.text(),
                    patient_age=self.patient_age_input.text(),
                    patient_phone=self.patient_phone_input.text(),
                    patient_address=self.patient_address_input.text(),
                )
                self.status_label.setText("Vaccine record saved.")
            else:
                update_vaccine_record(
                    connection,
                    self._current_record_id,
                    vaccine_type_id=vaccine_type_id if isinstance(vaccine_type_id, int) else None,
                    vaccine_type_name=vaccine_type_name,
                    patient_chart_no=self.patient_chart_no_input.text(),
                    patient_resident_id=self.patient_resident_id_input.text(),
                    patient_name=self.patient_name_input.text(),
                    patient_sex=self.patient_sex_input.text(),
                    patient_age=self.patient_age_input.text(),
                    patient_phone=self.patient_phone_input.text(),
                    patient_address=self.patient_address_input.text(),
                )
                self.status_label.setText("Vaccine record updated.")

        self._current_record_id = None
        self.refresh_view()

    def load_selected_record(self) -> None:
        selected_row = self._selected_record_id()
        if selected_row is None:
            self.status_label.setText("Select a vaccine record to load.")
            return
        record_id = selected_row
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            record = get_vaccine_record(connection, record_id)
        if record is None:
            self.status_label.setText("Vaccine record not found.")
            return

        self._current_record_id = record.id
        self.patient_chart_no_input.setText(record.patient_chart_no or "")
        self.patient_resident_id_input.setText(record.patient_resident_id or "")
        self.patient_name_input.setText(record.patient_name or "")
        self.patient_sex_input.setText(record.patient_sex or "")
        self.patient_age_input.setText(record.patient_age or "")
        self.patient_birth_date_input.clear()
        self.patient_phone_input.setText(record.patient_phone or "")
        self.patient_address_input.setText(record.patient_address or "")
        self._select_vaccine_type(record.vaccine_type_id, record.vaccine_type_name)
        self.status_label.setText("Loaded vaccine record.")

    def delete_selected_record(self) -> None:
        selected_row = self._selected_record_id()
        if selected_row is None:
            self.status_label.setText("Select a vaccine record to delete.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete vaccine record",
                "Delete selected vaccine record?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        record_id = selected_row
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            deleted = delete_vaccine_record(connection, record_id)
        if self._current_record_id == record_id:
            self._current_record_id = None
        self.refresh_view()
        self.status_label.setText(
            "Vaccine record deleted." if deleted else "Vaccine record not found."
        )

    def clear_form(self) -> None:
        self._current_record_id = None
        for widget in (
            self.patient_chart_no_input,
            self.patient_resident_id_input,
            self.patient_name_input,
            self.patient_sex_input,
            self.patient_age_input,
            self.patient_birth_date_input,
            self.patient_phone_input,
            self.patient_address_input,
        ):
            widget.clear()
        self.status_label.setText("Form cleared.")

    def save_vaccine_settings(self) -> None:
        if self.settings_page.save_settings():
            self.status_label.setText("Vaccine settings saved.")

    def load_vaccine_settings(self) -> None:
        self.settings_page.load_settings()
        self._handle_vaccine_settings_changed()

    def _handle_vaccine_settings_changed(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            counts = get_today_vaccine_counts(
                connection,
                datetime.now().date().isoformat(),
            )
        self._update_today_counts(settings, counts)
        self._reset_influenza_check()
        self.status_label.setText("Vaccine settings loaded.")

    def add_vaccine_type(self) -> None:
        dialog = VaccineTypeDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            self.status_label.setText("Vaccine type name is required.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            create_vaccine_type(connection, **values)
        self.refresh_view()
        self.status_label.setText("Vaccine type added.")

    def edit_vaccine_type(self) -> None:
        item = self.vaccine_types_list.currentItem()
        if item is None:
            self.status_label.setText("Select a vaccine type to edit.")
            return
        vaccine_type_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(vaccine_type_id, int):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            vaccine_type = get_vaccine_type(connection, vaccine_type_id)
        if vaccine_type is None:
            self.status_label.setText("Vaccine type not found.")
            return
        dialog = VaccineTypeDialog(self, vaccine_type)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            self.status_label.setText("Vaccine type name is required.")
            return
        with connect(self._db_path) as connection:
            update_vaccine_type(connection, vaccine_type_id, **values)
        self.refresh_view()
        self.status_label.setText("Vaccine type updated.")

    def delete_vaccine_type(self) -> None:
        item = self.vaccine_types_list.currentItem()
        if item is None:
            self.status_label.setText("Select a vaccine type to delete.")
            return
        vaccine_type_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(vaccine_type_id, int):
            return
        if (
            QMessageBox.question(
                self,
                "Delete vaccine type",
                "Delete selected vaccine type?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            deleted = delete_vaccine_type(connection, vaccine_type_id)
        self.refresh_view()
        self.status_label.setText(
            "Vaccine type deleted." if deleted else "Vaccine type not found."
        )

    def persist_vaccine_type_order(self) -> None:
        ordered_ids: list[int] = []
        for index in range(self.vaccine_types_list.count()):
            item = self.vaccine_types_list.item(index)
            value = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(value, int):
                ordered_ids.append(value)
        if not ordered_ids:
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            reorder_vaccine_types(connection, ordered_ids)

    def _populate_vaccine_types(self, vaccine_types: list) -> None:
        selected_id = None
        current = self.vaccine_types_list.currentItem()
        if current is not None:
            value = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(value, int):
                selected_id = value
        self.vaccine_types_list.clear()
        for vaccine_type in vaccine_types:
            item = QListWidgetItem(vaccine_type.name)
            item.setData(Qt.ItemDataRole.UserRole, vaccine_type.id)
            item.setToolTip(vaccine_type.code or "")
            self.vaccine_types_list.addItem(item)
            if selected_id == vaccine_type.id:
                self.vaccine_types_list.setCurrentItem(item)
        if self.vaccine_types_list.currentItem() is None and self.vaccine_types_list.count():
            self.vaccine_types_list.setCurrentRow(0)

    def _populate_records(self, table: QTableWidget, records: list) -> None:
        table.setRowCount(len(records))
        for row, record in enumerate(records):
            table.setItem(row, 0, QTableWidgetItem(str(record.id)))
            table.setItem(row, 1, QTableWidgetItem(record.vaccine_type_name))
            table.setItem(row, 2, QTableWidgetItem(record.patient_name or ""))
            table.setItem(
                row,
                3,
                QTableWidgetItem(
                    " / ".join(
                        value for value in (record.patient_sex, record.patient_age) if value
                    )
                ),
            )
            table.setItem(row, 4, QTableWidgetItem(record.patient_phone or ""))
            table.setItem(row, 5, QTableWidgetItem(record.status))
        table.resizeColumnsToContents()

    def _select_vaccine_type(
        self, vaccine_type_id: int | None, vaccine_type_name: str | None
    ) -> None:
        for index in range(self.vaccine_types_list.count()):
            item = self.vaccine_types_list.item(index)
            if vaccine_type_id is not None and item.data(Qt.ItemDataRole.UserRole) == vaccine_type_id:
                self.vaccine_types_list.setCurrentItem(item)
                return
            if vaccine_type_name and item.text() == vaccine_type_name:
                self.vaccine_types_list.setCurrentItem(item)
                return

    def _refresh_chart_note_preview(self) -> None:
        item = self.vaccine_types_list.currentItem()
        if item is None:
            self.chart_note_preview.clear()
            return
        vaccine_type_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(vaccine_type_id, int):
            self.chart_note_preview.clear()
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            vaccine_type = get_vaccine_type(connection, vaccine_type_id)
        self.chart_note_preview.setPlainText(
            vaccine_type.chart_note_template
            if vaccine_type is not None and vaccine_type.chart_note_template
            else ""
        )
        self._refresh_previews()

    def _update_today_counts(
        self,
        settings: dict[str, str],
        counts: dict[str, int],
    ) -> None:
        influenza_cap = settings.get("vaccine_influenza_daily_cap", "100").strip() or "100"
        covid_cap = settings.get("vaccine_covid_daily_cap", "100").strip() or "100"
        self.today_influenza_count_label.setText(
            f"Influenza today: {counts.get('flu', 0)} / {influenza_cap}"
        )
        self.today_covid_count_label.setText(
            f"COVID-19 today: {counts.get('covid', 0)} / {covid_cap}"
        )

    def _reset_influenza_check(self) -> None:
        self.influenza_check_result.setText("Influenza program: Not checked.")
        self.influenza_check_result.setProperty("resultState", "neutral")
        self.influenza_check_result.style().unpolish(self.influenza_check_result)
        self.influenza_check_result.style().polish(self.influenza_check_result)

    def _show_influenza_check(self, result: InfluenzaEligibilityResult) -> None:
        labels = {
            "eligible": "Eligible by configured rules",
            "blocked": "Blocked",
            "cap_reached": "Daily cap reached",
            "review_required": "Operator review required",
            "private_or_unmatched": "No national-program match",
            "configuration_required": "Configuration review required",
            "configuration_error": "Configuration error",
            "patient_context_required": "Patient context required",
        }
        lines = [f"Influenza program: {labels.get(result.status, result.status)}"]
        if result.group_label:
            lines.append(f"Group: {result.group_label}")
        if result.schedule_start and result.schedule_end:
            lines.append(f"Window: {result.schedule_start} to {result.schedule_end}")
        if result.group_key and result.status in {
            "eligible",
            "review_required",
            "cap_reached",
        }:
            lines.append(
                "Cap handling: Counts toward the shared daily cap."
                if result.counted
                else "Cap handling: Does not consume the shared daily cap."
            )
        lines.append(
            f"Counted today: {result.today_count} / {result.daily_cap} "
            f"(remaining {result.remaining})"
        )
        lines.append(result.message)
        self.influenza_check_result.setText("\n".join(lines))
        state = "success" if result.allowed else (
            "warning" if result.requires_operator_confirmation else "error"
        )
        self.influenza_check_result.setProperty("resultState", state)
        self.influenza_check_result.style().unpolish(self.influenza_check_result)
        self.influenza_check_result.style().polish(self.influenza_check_result)

    def _build_main_page(
        self,
        patient_form: QFormLayout,
        vaccine_type_controls: QHBoxLayout,
    ) -> QWidget:
        page = QWidget()
        controls = QHBoxLayout()
        controls.addWidget(self.fetch_button)
        controls.addWidget(self.influenza_check_button)
        controls.addWidget(self.save_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()

        counts_row = QHBoxLayout()
        counts_row.addWidget(self.today_influenza_count_label)
        counts_row.addSpacing(16)
        counts_row.addWidget(self.today_covid_count_label)
        counts_row.addStretch()

        left_column = QVBoxLayout()
        left_column.addLayout(patient_form)
        left_column.addWidget(QLabel("Vaccine list"))
        left_column.addWidget(self.vaccine_types_list, 1)
        left_column.addLayout(vaccine_type_controls)

        right_column = QVBoxLayout()
        right_column.addWidget(QLabel("Print preview"))
        right_column.addWidget(self.label_preview, 1)
        right_column.addWidget(QLabel("Charting text"))
        right_column.addWidget(self.charting_text_preview, 1)
        right_column.addWidget(QLabel("Selected chart note template"))
        right_column.addWidget(self.chart_note_preview, 1)

        content = QGridLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setHorizontalSpacing(16)
        content.addLayout(left_column, 0, 0)
        content.addLayout(right_column, 0, 1)
        content.setColumnStretch(0, 2)
        content.setColumnStretch(1, 3)

        layout = QVBoxLayout(page)
        layout.addLayout(controls)
        layout.addLayout(counts_row)
        layout.addWidget(self.influenza_check_result)
        layout.addLayout(content, 1)
        return page

    def _build_db_page(self) -> QWidget:
        page = QWidget()
        controls = QHBoxLayout()
        controls.addWidget(self.load_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.refresh_records_button)
        controls.addStretch()

        layout = QVBoxLayout(page)
        layout.addLayout(controls)
        layout.addWidget(QLabel("General"))
        layout.addWidget(self.general_records_table, 1)
        layout.addWidget(QLabel("Flu (national workflow records)"))
        layout.addWidget(self.flu_records_table, 1)
        layout.addWidget(QLabel("COVID"))
        layout.addWidget(self.covid_records_table, 1)
        return page

    @staticmethod
    def _create_records_table() -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["id", "vaccine", "name", "sex/age", "phone", "status"]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _selected_record_id(self) -> int | None:
        for table in (
            self.general_records_table,
            self.flu_records_table,
            self.covid_records_table,
            self.records_table,
        ):
            selected = table.selectedItems()
            if not selected:
                continue
            item = table.item(selected[0].row(), 0)
            if item is None:
                continue
            try:
                return int(item.text())
            except ValueError:
                return None
        return None

    def _refresh_previews(self) -> None:
        selected_item = self.vaccine_types_list.currentItem()
        vaccine_name = selected_item.text() if selected_item is not None else "(no vaccine selected)"
        patient_name = self.patient_name_input.text().strip() or "(no patient name)"
        patient_chart_no = self.patient_chart_no_input.text().strip() or "-"
        patient_sex = self.patient_sex_input.text().strip()
        patient_age = self.patient_age_input.text().strip()
        patient_phone = self.patient_phone_input.text().strip() or "-"
        sex_age = " / ".join(value for value in (patient_sex, patient_age) if value) or "-"
        chart_note = self.chart_note_preview.toPlainText().strip()
        self.label_preview.setPlainText(
            "\n".join(
                [
                    f"Vaccine: {vaccine_name}",
                    f"Patient: {patient_name}",
                    f"Chart No: {patient_chart_no}",
                    f"Sex/Age: {sex_age}",
                    f"Phone: {patient_phone}",
                ]
            )
        )
        self.charting_text_preview.setPlainText(
            chart_note if chart_note else f"{vaccine_name} 예방접종 준비."
        )

    @staticmethod
    def _record_bucket(record) -> str:
        code = (getattr(record, "vaccine_type_name", "") or "").strip().lower()
        if code in {"influenza", "flu"}:
            return "flu"
        if code in {"covid-19", "covid19", "covid"}:
            return "covid"
        return "general"

    def _filter_records(self, records: list, bucket: str) -> list:
        return [record for record in records if self._record_bucket(record) == bucket]
