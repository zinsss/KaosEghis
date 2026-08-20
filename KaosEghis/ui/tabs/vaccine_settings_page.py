from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    VaccineProgramSeasonRecord,
    create_vaccine_program_season,
    delete_vaccine_program_season,
    duplicate_vaccine_program_season,
    get_vaccine_program_season,
    list_vaccine_program_seasons,
    sync_active_vaccine_seasons_to_settings,
    update_vaccine_program_season,
)


class OptionalDateInput(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.enabled_check = QCheckBox("Set")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setEnabled(False)
        self.enabled_check.toggled.connect(self.date_edit.setEnabled)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.date_edit, 1)

    def value(self) -> str:
        if not self.enabled_check.isChecked():
            return ""
        return self.date_edit.date().toString("yyyy-MM-dd")

    def set_value(self, value: object) -> None:
        text = str(value or "").strip()
        parsed = QDate.fromString(text, "yyyy-MM-dd")
        if not parsed.isValid():
            parsed = QDate.fromString(text, "yyyyMMdd")
        self.enabled_check.setChecked(parsed.isValid())
        if parsed.isValid():
            self.date_edit.setDate(parsed)


class VaccineSeasonEditor(QWidget):
    settings_changed = Signal()

    INFLUENZA_GROUPS = (
        ("elderly_75_plus", "Elderly 75+"),
        ("elderly_70_74", "Elderly 70-74"),
        ("elderly_65_69", "Elderly 65-69"),
        ("child_two_dose", "Eligible child"),
    )

    def __init__(self, program: str, db_path: Path | None = None) -> None:
        super().__init__()
        self.program = program
        self._db_path = db_path
        self._current_season_id: int | None = None

        self.season_combo = QComboBox()
        self.season_combo.currentIndexChanged.connect(self._load_selected_season)
        self.new_button = QPushButton("New season")
        self.new_button.clicked.connect(lambda: self.create_season())
        self.duplicate_button = QPushButton("Duplicate next season")
        self.duplicate_button.clicked.connect(self.duplicate_season)
        self.delete_button = QPushButton("Delete season")
        self.delete_button.clicked.connect(self.delete_season)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Season"))
        selector.addWidget(self.season_combo, 1)
        selector.addWidget(self.new_button)
        selector.addWidget(self.duplicate_button)
        selector.addWidget(self.delete_button)

        self.season_name_input = QLineEdit()
        self.active_check = QCheckBox("Active for program checks")
        self.daily_cap_input = QSpinBox()
        self.daily_cap_input.setRange(0, 9999)
        self.daily_cap_input.setValue(100)

        common_form = QFormLayout()
        common_form.addRow("Season name", self.season_name_input)
        common_form.addRow("State", self.active_check)
        common_form.addRow("Daily cap", self.daily_cap_input)

        self.date_inputs: dict[str, OptionalDateInput] = {}
        self.birth_inputs: dict[str, tuple[OptionalDateInput, OptionalDateInput]] = {}
        self.allow_exception_check: QCheckBox | None = None

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.addLayout(common_form)
        if program == "influenza":
            editor_layout.addWidget(self._build_influenza_schedule_group())
            editor_layout.addWidget(self._build_influenza_birth_group())
        else:
            editor_layout.addWidget(self._build_covid_schedule_group())
            editor_layout.addWidget(self._build_covid_birth_group())
        editor_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(editor)

        self.save_button = QPushButton("Save season")
        self.save_button.clicked.connect(self.save_season)
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(lambda: self.reload())
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch()

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(selector)
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)

        self.reload()

    def _build_influenza_schedule_group(self) -> QGroupBox:
        group = QGroupBox("Influenza program dates")
        grid = QGridLayout(group)
        rows = (
            ("75+ start", "elderly_75_plus_start", None),
            ("70-74 start", "elderly_70_74_start", None),
            ("65-69 start", "elderly_65_69_start", None),
            ("Elderly end", "elderly_program_end", None),
            ("Child two-dose", "child_two_dose_start", "child_two_dose_end"),
            ("Child one-dose", "child_one_dose_start", "child_one_dose_end"),
        )
        grid.addWidget(QLabel("Group"), 0, 0)
        grid.addWidget(QLabel("Start"), 0, 1)
        grid.addWidget(QLabel("End"), 0, 2)
        for row, (label, start_key, end_key) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row, 0)
            start_input = OptionalDateInput()
            self.date_inputs[start_key] = start_input
            grid.addWidget(start_input, row, 1)
            if end_key:
                end_input = OptionalDateInput()
                self.date_inputs[end_key] = end_input
                grid.addWidget(end_input, row, 2)
        self.allow_exception_check = QCheckBox("Allow elderly exception review path")
        grid.addWidget(self.allow_exception_check, len(rows) + 1, 0, 1, 3)
        return group

    def _build_influenza_birth_group(self) -> QGroupBox:
        group = QGroupBox("Influenza birth-date ranges")
        grid = QGridLayout(group)
        grid.addWidget(QLabel("Group"), 0, 0)
        grid.addWidget(QLabel("From"), 0, 1)
        grid.addWidget(QLabel("To"), 0, 2)
        for row, (key, label) in enumerate(self.INFLUENZA_GROUPS, start=1):
            lower = OptionalDateInput()
            upper = OptionalDateInput()
            self.birth_inputs[key] = (lower, upper)
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(lower, row, 1)
            grid.addWidget(upper, row, 2)
        return group

    def _build_covid_schedule_group(self) -> QGroupBox:
        group = QGroupBox("COVID program dates")
        form = QFormLayout(group)
        for label, key in (("Program start", "program_start"), ("Program end", "program_end")):
            date_input = OptionalDateInput()
            self.date_inputs[key] = date_input
            form.addRow(label, date_input)
        return group

    def _build_covid_birth_group(self) -> QGroupBox:
        group = QGroupBox("COVID birth-date range")
        grid = QGridLayout(group)
        lower = OptionalDateInput()
        upper = OptionalDateInput()
        self.birth_inputs["national_covid"] = (lower, upper)
        grid.addWidget(QLabel("From"), 0, 0)
        grid.addWidget(QLabel("To"), 0, 1)
        grid.addWidget(lower, 1, 0)
        grid.addWidget(upper, 1, 1)
        return group

    def reload(self, select_id: int | None = None) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            seasons = list_vaccine_program_seasons(connection, self.program)
        target_id = select_id if select_id is not None else self._current_season_id
        self.season_combo.blockSignals(True)
        self.season_combo.clear()
        for season in seasons:
            label = f"{season.season_name}{' [active]' if season.is_active else ''}"
            self.season_combo.addItem(label, season.id)
        selected_index = self.season_combo.findData(target_id)
        self.season_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.season_combo.blockSignals(False)
        self._load_selected_season()

    def create_season(self, season_name: str | None = None) -> None:
        name = season_name
        if name is None:
            name, accepted = QInputDialog.getText(self, "New vaccine season", "Season name")
            if not accepted:
                return
        name = str(name).strip()
        if not name:
            self.status_label.setText("Season name is required.")
            return
        try:
            with connect(self._db_path) as connection:
                season = create_vaccine_program_season(
                    connection,
                    program=self.program,
                    season_name=name,
                    schedule=self._empty_schedule(),
                    age_groups=self._empty_age_groups(),
                )
        except Exception as error:
            self.status_label.setText(self._safe_save_error(error))
            return
        self.reload(season.id)
        self.status_label.setText("Season created. Review all values before activation.")

    def duplicate_season(self) -> None:
        if self._current_season_id is None:
            self.status_label.setText("Select a season to duplicate.")
            return
        try:
            with connect(self._db_path) as connection:
                season = duplicate_vaccine_program_season(
                    connection, self._current_season_id
                )
        except Exception as error:
            self.status_label.setText(self._safe_save_error(error))
            return
        self.reload(season.id)
        self.status_label.setText(
            "Next season duplicated and shifted by one year. Review before activation."
        )

    def delete_season(self) -> None:
        if self._current_season_id is None:
            self.status_label.setText("Select a season to delete.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete vaccine season",
                f"Delete '{self.season_name_input.text().strip()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            delete_vaccine_program_season(connection, self._current_season_id)
            sync_active_vaccine_seasons_to_settings(connection)
        self._current_season_id = None
        self.reload()
        self.settings_changed.emit()
        self.status_label.setText("Season deleted.")

    def save_season(self) -> bool:
        if self._current_season_id is None:
            self.status_label.setText("Select or create a season first.")
            return False
        season_name = self.season_name_input.text().strip()
        if not season_name:
            self.status_label.setText("Season name is required.")
            return False
        schedule = self._collect_schedule()
        age_groups = self._collect_age_groups()
        validation_error = self._validate_active_values(schedule, age_groups)
        if validation_error:
            self.status_label.setText(validation_error)
            return False
        try:
            with connect(self._db_path) as connection:
                updated = update_vaccine_program_season(
                    connection,
                    self._current_season_id,
                    season_name=season_name,
                    daily_cap=self.daily_cap_input.value(),
                    schedule=schedule,
                    age_groups=age_groups,
                    is_active=self.active_check.isChecked(),
                )
                sync_active_vaccine_seasons_to_settings(connection)
        except Exception as error:
            self.status_label.setText(self._safe_save_error(error))
            return False
        if updated is None:
            self.status_label.setText("Season was not found.")
            return False
        self.reload(updated.id)
        self.settings_changed.emit()
        self.status_label.setText("Vaccine season saved.")
        return True

    def _load_selected_season(self, _index: int | None = None) -> None:
        season_id = self.season_combo.currentData()
        if not isinstance(season_id, int):
            self._current_season_id = None
            self._clear_editor()
            return
        with connect(self._db_path) as connection:
            season = get_vaccine_program_season(connection, season_id)
        if season is None:
            self._current_season_id = None
            self._clear_editor()
            return
        self._current_season_id = season.id
        self._load_record(season)

    def _load_record(self, season: VaccineProgramSeasonRecord) -> None:
        self.season_name_input.setText(season.season_name)
        self.active_check.setChecked(season.is_active)
        self.daily_cap_input.setValue(season.daily_cap)
        for key, date_input in self.date_inputs.items():
            date_input.set_value(season.schedule.get(key))
        if self.allow_exception_check is not None:
            self.allow_exception_check.setChecked(
                self._as_bool(
                    season.schedule.get("allow_elderly_exception", False)
                )
            )
        groups = {
            str(group.get("key", "")): group for group in season.age_groups
        }
        for key, (lower, upper) in self.birth_inputs.items():
            group = groups.get(key)
            if key == "child_two_dose" and group is None:
                group = groups.get("child_one_dose")
            lower.set_value(group.get("birth_date_from") if group else "")
            upper.set_value(group.get("birth_date_to") if group else "")

    def _clear_editor(self) -> None:
        self.season_name_input.clear()
        self.active_check.setChecked(False)
        self.daily_cap_input.setValue(100)
        for date_input in self.date_inputs.values():
            date_input.set_value("")
        for lower, upper in self.birth_inputs.values():
            lower.set_value("")
            upper.set_value("")
        if self.allow_exception_check is not None:
            self.allow_exception_check.setChecked(False)

    def _collect_schedule(self) -> dict[str, object]:
        schedule: dict[str, object] = {
            key: date_input.value() for key, date_input in self.date_inputs.items()
        }
        if self.allow_exception_check is not None:
            schedule["allow_elderly_exception"] = (
                self.allow_exception_check.isChecked()
            )
        return schedule

    def _collect_age_groups(self) -> list[dict[str, object]]:
        if self.program == "covid":
            lower, upper = self.birth_inputs["national_covid"]
            return [
                {
                    "key": "national_covid",
                    "label": "National COVID",
                    "vaccine": "covid",
                    "birth_date_from": lower.value(),
                    "birth_date_to": upper.value(),
                }
            ]
        groups: list[dict[str, object]] = []
        labels = dict(self.INFLUENZA_GROUPS)
        for key, (lower, upper) in self.birth_inputs.items():
            payload = {
                "key": key,
                "label": labels[key],
                "vaccine": "influenza",
                "birth_date_from": lower.value(),
                "birth_date_to": upper.value(),
            }
            groups.append(payload)
            if key == "child_two_dose":
                groups.append(
                    payload
                    | {
                        "key": "child_one_dose",
                        "label": "Eligible child",
                    }
                )
        groups.append(
            {
                "key": "exception_influenza",
                "label": "Exception influenza",
                "vaccine": "influenza",
                "birth_date_from": "",
                "birth_date_to": "",
            }
        )
        return groups

    def _validate_active_values(
        self,
        schedule: dict[str, object],
        age_groups: list[dict[str, object]],
    ) -> str | None:
        if not self.active_check.isChecked():
            return None
        missing_dates = [key for key, value in schedule.items() if key != "allow_elderly_exception" and not value]
        if missing_dates:
            return "Complete all program dates before activating this season."
        for group in age_groups:
            if group.get("key") == "exception_influenza":
                continue
            if not group.get("birth_date_from") or not group.get("birth_date_to"):
                return "Complete all birth-date ranges before activating this season."
            if str(group["birth_date_from"]) > str(group["birth_date_to"]):
                return "A birth-date range starts after it ends."
        for start_key, end_key in self._schedule_pairs():
            if str(schedule[start_key]) > str(schedule[end_key]):
                return "A program date range starts after it ends."
        return None

    def _schedule_pairs(self) -> tuple[tuple[str, str], ...]:
        if self.program == "covid":
            return (("program_start", "program_end"),)
        return (
            ("elderly_75_plus_start", "elderly_program_end"),
            ("elderly_70_74_start", "elderly_program_end"),
            ("elderly_65_69_start", "elderly_program_end"),
            ("child_two_dose_start", "child_two_dose_end"),
            ("child_one_dose_start", "child_one_dose_end"),
        )

    def _empty_schedule(self) -> dict[str, object]:
        schedule = {key: "" for key in self.date_inputs}
        if self.program == "influenza":
            schedule["allow_elderly_exception"] = False
        return schedule

    def _empty_age_groups(self) -> list[dict[str, object]]:
        if self.program == "covid":
            return [
                {
                    "key": "national_covid",
                    "label": "National COVID",
                    "vaccine": "covid",
                    "birth_date_from": "",
                    "birth_date_to": "",
                }
            ]
        groups = [
            {
                "key": key,
                "label": label,
                "vaccine": "influenza",
                "birth_date_from": "",
                "birth_date_to": "",
            }
            for key, label in self.INFLUENZA_GROUPS
        ]
        groups.append(
            {
                "key": "child_one_dose",
                "label": "Eligible child",
                "vaccine": "influenza",
                "birth_date_from": "",
                "birth_date_to": "",
            }
        )
        groups.append(
            {
                "key": "exception_influenza",
                "label": "Exception influenza",
                "vaccine": "influenza",
                "birth_date_from": "",
                "birth_date_to": "",
            }
        )
        return groups

    @staticmethod
    def _safe_save_error(error: Exception) -> str:
        text = str(error).lower()
        if "unique" in text:
            return "A season with that name already exists."
        if isinstance(error, ValueError):
            return str(error)
        return "Vaccine season could not be saved."

    @staticmethod
    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class VaccineSettingsPage(QWidget):
    settings_changed = Signal()

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self.tabs = QTabWidget()
        self.influenza_editor = VaccineSeasonEditor("influenza", db_path)
        self.covid_editor = VaccineSeasonEditor("covid", db_path)
        self.tabs.addTab(self.influenza_editor, "Influenza schedules")
        self.tabs.addTab(self.covid_editor, "COVID schedules")
        self.influenza_editor.settings_changed.connect(self.settings_changed.emit)
        self.covid_editor.settings_changed.connect(self.settings_changed.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def reload(self) -> None:
        self.influenza_editor.reload()
        self.covid_editor.reload()
