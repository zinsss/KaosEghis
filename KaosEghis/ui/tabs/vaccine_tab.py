from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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
from KaosEghis.core.printer_service import (
    VaccineLabelContent,
    print_vaccine_label,
)
from KaosEghis.core.vaccine_patient_context import (
    fetch_vaccine_patient_context,
    resident_id_for_label,
)
from KaosEghis.core.vaccine_eligibility import (
    CovidEligibilityResult,
    InfluenzaEligibilityResult,
    evaluate_covid_program,
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
    mark_vaccine_record_cancelled,
    mark_vaccine_record_completed,
    mark_vaccine_record_printed,
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
    PROGRAM_TYPES = (
        ("General / private", "general"),
        ("National influenza", "national_influenza"),
        ("National COVID-19", "national_covid"),
    )

    def __init__(self, parent: QWidget | None = None, vaccine_type=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vaccine Type")

        self.name_input = QLineEdit(getattr(vaccine_type, "name", ""))
        self.code_input = QLineEdit(getattr(vaccine_type, "code", "") or "")
        self.chart_note_input = QPlainTextEdit(
            getattr(vaccine_type, "chart_note_template", "") or ""
        )
        self.program_type_combo = QComboBox()
        for label, value in self.PROGRAM_TYPES:
            self.program_type_combo.addItem(label, value)
        current_program_type = getattr(vaccine_type, "program_type", "general")
        current_index = self.program_type_combo.findData(current_program_type)
        self.program_type_combo.setCurrentIndex(max(0, current_index))
        self.active_button = QPushButton("Enabled")
        self.active_button.setCheckable(True)
        self.active_button.setChecked(bool(getattr(vaccine_type, "is_active", True)))

        form = QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Code", self.code_input)
        form.addRow("Program", self.program_type_combo)
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
            "program_type": self.program_type_combo.currentData(),
            "is_active": self.active_button.isChecked(),
        }


class VaccineTab(QWidget):
    TOP_PAGES = ["Main", "DB", "Settings"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._current_record_id: int | None = None
        self._prepared_pair_ids: tuple[int, int] | None = None
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
        self.covid_check_button = QPushButton("Check COVID program")
        self.covid_check_button.clicked.connect(self.check_covid_program)
        self.covid_check_result = QLabel("COVID program: Not checked.")
        self.covid_check_result.setObjectName("covidProgramResult")
        self.covid_check_result.setWordWrap(True)
        self.rural_exception_check = QCheckBox(
            "Rural-area exception manually checked in the national system"
        )
        self.rural_exception_check.setChecked(True)
        self.rural_exception_check.setToolTip(
            "This does not establish eligibility. Early group printing still requires confirmation."
        )
        self.rural_exception_check.toggled.connect(
            lambda _checked: self._reset_program_checks()
        )
        self.prepared_pair_label = QLabel("Flu + COVID: Not prepared.")
        self.prepared_pair_label.setWordWrap(True)

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
            lambda _text: self._reset_program_checks()
        )

        self.records_table = self._create_records_table()
        self.general_records_table = self._create_records_table()
        self.flu_records_table = self._create_records_table()
        self.covid_records_table = self._create_records_table()

        self.fetch_button = QPushButton("Fetch from EMR")
        self.fetch_button.clicked.connect(self.fetch_current_patient_from_emr)
        self.save_button = QPushButton("Save record")
        self.save_button.clicked.connect(self.save_record)
        self.new_record_button = QPushButton("New vaccine record")
        self.new_record_button.clicked.connect(self.start_new_vaccine_record)
        self.prepare_flu_covid_button = QPushButton("Prepare Flu + COVID")
        self.prepare_flu_covid_button.clicked.connect(self.prepare_flu_and_covid)
        self.print_button = QPushButton("Print label")
        self.print_button.clicked.connect(self.print_label)
        self.print_prepared_pair_button = QPushButton("Print prepared pair")
        self.print_prepared_pair_button.clicked.connect(self.print_prepared_pair)
        self.clear_button = QPushButton("Clear form")
        self.clear_button.clicked.connect(self.clear_form)
        self.load_button = QPushButton("Load selected")
        self.load_button.clicked.connect(self.load_selected_record)
        self.complete_button = QPushButton("Mark completed")
        self.complete_button.clicked.connect(self.mark_selected_record_completed)
        self.cancel_record_button = QPushButton("Cancel record")
        self.cancel_record_button.clicked.connect(self.cancel_selected_record)
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
            rural_exception_checked=self.rural_exception_check.isChecked(),
        )
        self._show_influenza_check(result)
        return result

    def check_covid_program(self) -> CovidEligibilityResult:
        initialize_database(self._db_path)
        today = datetime.now().date()
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            counts = get_today_vaccine_counts(connection, today.isoformat())
        result = evaluate_covid_program(
            settings,
            self.patient_resident_id_input.text(),
            on_date=today,
            counted_today=counts.get("covid", 0),
            rural_exception_checked=self.rural_exception_check.isChecked(),
        )
        self._show_covid_check(result)
        return result

    def save_record(self):
        selected = self.vaccine_types_list.currentItem()
        if selected is None:
            self.status_label.setText("Select a vaccine type first.")
            return None
        vaccine_type_id = selected.data(Qt.ItemDataRole.UserRole)
        vaccine_type_name = selected.text()
        if not self.patient_name_input.text().strip() and not self.patient_resident_id_input.text().strip():
            self.status_label.setText("Load or enter patient context first.")
            return None

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            if self._current_record_id is None:
                saved_record = create_vaccine_record(
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
                saved_record = update_vaccine_record(
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

        self._current_record_id = saved_record.id if saved_record is not None else None
        self.refresh_view()
        return saved_record

    def prepare_flu_and_covid(self) -> tuple[object, object] | None:
        """Create separate Flu and COVID preparation records from one patient context."""

        if (
            not self.patient_name_input.text().strip()
            and not self.patient_resident_id_input.text().strip()
        ):
            self.status_label.setText("Load or enter patient context first.")
            return None
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            vaccine_types = list_vaccine_types(connection)
            flu_types = [
                entry
                for entry in vaccine_types
                if entry.is_active and entry.program_type == "national_influenza"
            ]
            covid_types = [
                entry
                for entry in vaccine_types
                if entry.is_active and entry.program_type == "national_covid"
            ]
            if len(flu_types) != 1 or len(covid_types) != 1:
                self.status_label.setText(
                    "Prepare Flu + COVID requires exactly one active national Flu and COVID type."
                )
                return None
            flu_type = flu_types[0]
            covid_type = covid_types[0]
            flu_record = self._create_record_for_type(connection, flu_type)
            covid_record = self._create_record_for_type(connection, covid_type)

        self._prepared_pair_ids = (flu_record.id, covid_record.id)
        self._current_record_id = flu_record.id
        self._select_vaccine_type(flu_record.vaccine_type_id, flu_record.vaccine_type_name)
        self.prepared_pair_label.setText(
            "Flu + COVID: Two separate records prepared. Review and print the pair explicitly."
        )
        self.refresh_view()
        self.status_label.setText("Flu + COVID prepared from one patient context.")
        return flu_record, covid_record

    def print_prepared_pair(self) -> None:
        if self._prepared_pair_ids is None:
            self.status_label.setText("Prepare a Flu + COVID pair first.")
            return
        if (
            QMessageBox.question(
                self,
                "Print Flu + COVID labels",
                "Print two separate labels after their individual program checks?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            self.status_label.setText("Flu + COVID pair printing cancelled by operator.")
            return

        printed: list[str] = []
        for record_id in self._prepared_pair_ids:
            initialize_database(self._db_path)
            with connect(self._db_path) as connection:
                record = get_vaccine_record(connection, record_id)
            if record is None:
                self.status_label.setText("A prepared pair record is no longer available.")
                return
            self._current_record_id = record.id
            self._select_vaccine_type(record.vaccine_type_id, record.vaccine_type_name)
            self.print_label()
            with connect(self._db_path) as connection:
                refreshed = get_vaccine_record(connection, record.id)
            if refreshed is None or refreshed.status != "completed":
                completed = ", ".join(printed) or "No labels"
                self.status_label.setText(
                    f"{completed} printed; {record.vaccine_type_name} needs operator review."
                )
                self.refresh_view()
                return
            printed.append(record.vaccine_type_name)

        self.refresh_view()
        self.status_label.setText("Flu + COVID labels printed and completed separately.")

    def _create_record_for_type(self, connection, vaccine_type):
        return create_vaccine_record(
            connection,
            vaccine_type_id=vaccine_type.id,
            vaccine_type_name=vaccine_type.name,
            patient_chart_no=self.patient_chart_no_input.text(),
            patient_resident_id=self.patient_resident_id_input.text(),
            patient_name=self.patient_name_input.text(),
            patient_sex=self.patient_sex_input.text(),
            patient_age=self.patient_age_input.text(),
            patient_phone=self.patient_phone_input.text(),
            patient_address=self.patient_address_input.text(),
        )

    def print_label(self) -> None:
        """Print the current vaccine label and checkpoint the successful output only."""

        record = self._record_for_label_print()
        if record is None:
            return
        if record.status in {"cancelled", "error"}:
            self.status_label.setText("Cancelled or errored vaccine records cannot be printed.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            counts = get_today_vaccine_counts(connection, datetime.now().date().isoformat())

        if record.status == "completed":
            permitted, counts_toward_cap = True, bool(record.counts_toward_cap)
        else:
            permitted, counts_toward_cap = self._confirm_program_printing(
                record,
                settings,
                counts,
            )
        if not permitted:
            return

        print_result = print_vaccine_label(
            self._label_content(record, settings, counts, counts_toward_cap),
            printer_name=settings.get("vaccine_label_printer_name", ""),
        )
        if not print_result.success:
            self.status_label.setText(print_result.message)
            return

        try:
            with connect(self._db_path) as connection:
                current = get_vaccine_record(connection, record.id)
                if current is None:
                    self.status_label.setText("Vaccine record not found after printing.")
                    return
                if current.status == "prepared":
                    current = mark_vaccine_record_printed(connection, current.id)
                if current is not None and current.status != "completed":
                    mark_vaccine_record_completed(
                        connection,
                        current.id,
                        counts_toward_cap=counts_toward_cap,
                    )
        except ValueError:
            self.status_label.setText("Vaccine label printed, but record completion needs operator review.")
            self.refresh_view()
            return

        self.refresh_view()
        self.status_label.setText(
            "Vaccine label reprinted."
            if record.status == "completed"
            else "Vaccine label printed and record completed."
        )

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
                "Delete selected vaccine record? The lifecycle audit will remain.",
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

    def mark_selected_record_completed(self) -> None:
        record_id = self._selected_record_id()
        if record_id is None:
            self.status_label.setText("Select a vaccine record to complete.")
            return
        with connect(self._db_path) as connection:
            record = get_vaccine_record(connection, record_id)
        if record is None:
            self.status_label.setText("Vaccine record not found.")
            return
        counted = record.program_type in {
            "national_influenza",
            "national_covid",
        }
        count_note = (
            "This will add one to the applicable national daily count."
            if counted
            else "This general/private vaccination will not affect a national count."
        )
        if (
            QMessageBox.question(
                self,
                "Complete vaccine record",
                f"Mark the selected vaccination completed?\n\n{count_note}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with connect(self._db_path) as connection:
                updated = mark_vaccine_record_completed(connection, record_id)
        except ValueError as error:
            self.status_label.setText(str(error))
            return
        self.refresh_view()
        self.status_label.setText(
            "Vaccine record marked completed."
            if updated is not None
            else "Vaccine record not found."
        )

    def cancel_selected_record(self) -> None:
        record_id = self._selected_record_id()
        if record_id is None:
            self.status_label.setText("Select a vaccine record to cancel.")
            return
        if (
            QMessageBox.question(
                self,
                "Cancel vaccine record",
                "Cancel the selected vaccine record? Any counted completion will be removed from today's total.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            updated = mark_vaccine_record_cancelled(connection, record_id)
        self.refresh_view()
        self.status_label.setText(
            "Vaccine record cancelled."
            if updated is not None
            else "Vaccine record not found."
        )

    def clear_form(self) -> None:
        self._current_record_id = None
        self._prepared_pair_ids = None
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
        self.rural_exception_check.setChecked(True)
        self.status_label.setText("Form cleared.")

    def start_new_vaccine_record(self) -> None:
        """Keep the fetched patient context while preparing another vaccine entry."""

        self._current_record_id = None
        self._prepared_pair_ids = None
        self.prepared_pair_label.setText("Flu + COVID: Not prepared.")
        self.vaccine_types_list.clearSelection()
        self.vaccine_types_list.setCurrentItem(None)
        self.chart_note_preview.clear()
        self._reset_influenza_check()
        self._refresh_previews()
        self.status_label.setText(
            "Patient context retained. Select the next vaccine type."
        )

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
            table.setItem(
                row,
                2,
                QTableWidgetItem(
                    {
                        "general": "General/private",
                        "national_influenza": "National influenza",
                        "national_covid": "National COVID-19",
                    }.get(record.program_type, record.program_type)
                ),
            )
            table.setItem(row, 3, QTableWidgetItem(record.patient_name or ""))
            table.setItem(
                row,
                4,
                QTableWidgetItem(
                    " / ".join(
                        value for value in (record.patient_sex, record.patient_age) if value
                    )
                ),
            )
            table.setItem(row, 5, QTableWidgetItem(record.patient_phone or ""))
            table.setItem(row, 6, QTableWidgetItem(record.status))
            table.setItem(row, 7, QTableWidgetItem(record.completed_on or ""))
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

    def _reset_program_checks(self) -> None:
        self.influenza_check_result.setText("Influenza program: Not checked.")
        self.influenza_check_result.setProperty("resultState", "neutral")
        self.influenza_check_result.style().unpolish(self.influenza_check_result)
        self.influenza_check_result.style().polish(self.influenza_check_result)
        self.covid_check_result.setText("COVID program: Not checked.")
        self.covid_check_result.setProperty("resultState", "neutral")
        self.covid_check_result.style().unpolish(self.covid_check_result)
        self.covid_check_result.style().polish(self.covid_check_result)

    def _reset_influenza_check(self) -> None:
        """Compatibility shim for callers from the earlier single-program UI."""

        self._reset_program_checks()

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

    def _show_covid_check(self, result: CovidEligibilityResult) -> None:
        labels = {
            "eligible": "Eligible by configured rules",
            "blocked": "Blocked",
            "cap_reached": "Daily cap reached",
            "review_required": "Operator review required",
            "manual_verification_required": "Manual national-system verification required",
            "configuration_required": "Configuration review required",
            "configuration_error": "Configuration error",
            "patient_context_required": "Patient context required",
        }
        lines = [f"COVID program: {labels.get(result.status, result.status)}"]
        if result.group_label:
            lines.append(f"Group: {result.group_label}")
        if result.schedule_start and result.schedule_end:
            lines.append(f"Window: {result.schedule_start} to {result.schedule_end}")
        lines.append(
            f"Counted today: {result.today_count} / {result.daily_cap} "
            f"(remaining {result.remaining})"
        )
        lines.append(result.message)
        self.covid_check_result.setText("\n".join(lines))
        self.covid_check_result.setProperty(
            "resultState",
            "success" if result.allowed else (
                "warning"
                if result.status in {"manual_verification_required", "review_required"}
                else "error"
            ),
        )
        self.covid_check_result.style().unpolish(self.covid_check_result)
        self.covid_check_result.style().polish(self.covid_check_result)

    def _record_for_label_print(self):
        if self._current_record_id is None:
            return self.save_record()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            record = get_vaccine_record(connection, self._current_record_id)
        if record is None:
            self._current_record_id = None
            self.status_label.setText("Save the vaccine record before printing.")
        return record

    def _confirm_program_printing(
        self,
        record,
        settings: dict[str, str],
        counts: dict[str, int],
    ) -> tuple[bool, bool]:
        if record.program_type == "general":
            return True, False
        if record.program_type == "national_covid":
            result = evaluate_covid_program(
                settings,
                record.patient_resident_id or "",
                on_date=datetime.now().date(),
                counted_today=counts.get("covid", 0),
                rural_exception_checked=self.rural_exception_check.isChecked(),
            )
            self._show_covid_check(result)
            if result.allowed:
                return True, result.counted
            if result.requires_operator_confirmation:
                return self._confirm_rural_exception_printing("COVID", result)
            self.status_label.setText("COVID label printing blocked by the program check.")
            return False, False
        if record.program_type != "national_influenza":
            self.status_label.setText("Vaccine program type needs operator review.")
            return False, False

        result = evaluate_influenza_program(
            settings,
            record.patient_resident_id or "",
            on_date=datetime.now().date(),
            counted_today=counts.get("flu", 0),
            rural_exception_checked=self.rural_exception_check.isChecked(),
        )
        self._show_influenza_check(result)
        if result.allowed:
            return True, result.counted
        if not result.requires_operator_confirmation:
            self.status_label.setText("Influenza label printing blocked by the program check.")
            return False, False
        return self._confirm_rural_exception_printing("Influenza", result)

    def _confirm_rural_exception_printing(self, program: str, result) -> tuple[bool, bool]:
        confirmation = (
            f"{result.message}\n\n"
            "Proceed only after manually verifying the individual patient's "
            "rural-area exception in the national vaccination system."
        )
        if (
            QMessageBox.question(
                self,
                f"Confirm {program} rural-area exception",
                confirmation,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            self.status_label.setText(f"{program} exception printing cancelled by operator.")
            return False, False
        return True, result.counted

    def _label_content(
        self,
        record,
        settings: dict[str, str],
        counts: dict[str, int],
        counts_toward_cap: bool,
    ) -> VaccineLabelContent:
        count_summary = ""
        if record.program_type == "national_influenza":
            cap = settings.get("vaccine_influenza_daily_cap", "100").strip() or "100"
            printed_count = counts.get("flu", 0)
            if counts_toward_cap and record.status != "completed":
                printed_count += 1
            count_summary = f"{printed_count}/{cap}"
        elif record.program_type == "national_covid":
            cap = settings.get("vaccine_covid_daily_cap", "100").strip() or "100"
            printed_count = counts.get("covid", 0)
            if counts_toward_cap and record.status != "completed":
                printed_count += 1
            count_summary = f"{printed_count}/{cap}"
        return VaccineLabelContent(
            vaccine_name=record.vaccine_type_name,
            patient_name=record.patient_name or "",
            chart_no=record.patient_chart_no or "",
            resident_id=resident_id_for_label(record.patient_resident_id or ""),
            phone=record.patient_phone or "",
            printed_at=datetime.now(),
            count_summary=count_summary,
        )

    def _build_main_page(
        self,
        patient_form: QFormLayout,
        vaccine_type_controls: QHBoxLayout,
    ) -> QWidget:
        page = QWidget()
        controls = QHBoxLayout()
        controls.addWidget(self.fetch_button)
        controls.addWidget(self.influenza_check_button)
        controls.addWidget(self.covid_check_button)
        controls.addWidget(self.save_button)
        controls.addWidget(self.new_record_button)
        controls.addWidget(self.prepare_flu_covid_button)
        controls.addWidget(self.print_button)
        controls.addWidget(self.print_prepared_pair_button)
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
        layout.addWidget(self.rural_exception_check)
        layout.addWidget(self.prepared_pair_label)
        layout.addWidget(self.influenza_check_result)
        layout.addWidget(self.covid_check_result)
        layout.addLayout(content, 1)
        return page

    def _build_db_page(self) -> QWidget:
        page = QWidget()
        controls = QHBoxLayout()
        controls.addWidget(self.load_button)
        controls.addWidget(self.complete_button)
        controls.addWidget(self.cancel_record_button)
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
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(
            [
                "id",
                "vaccine",
                "program",
                "name",
                "sex/age",
                "phone",
                "status",
                "completed",
            ]
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
        patient_resident_id = (
            resident_id_for_label(self.patient_resident_id_input.text()) or "-"
        )
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
                    f"Resident No: {patient_resident_id}",
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
        if getattr(record, "program_type", "") == "national_influenza":
            return "flu"
        if getattr(record, "program_type", "") == "national_covid":
            return "covid"
        code = (getattr(record, "vaccine_type_name", "") or "").strip().lower()
        if code in {"influenza", "flu"}:
            return "flu"
        if code in {"covid-19", "covid19", "covid"}:
            return "covid"
        return "general"

    def _filter_records(self, records: list, bucket: str) -> list:
        return [record for record in records if self._record_bucket(record) == bucket]
