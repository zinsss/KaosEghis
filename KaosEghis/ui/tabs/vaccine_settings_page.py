from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings, set_settings


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


class VaccineProgramEditor(QWidget):
    INFLUENZA_GROUPS = (
        ("elderly_75_plus", "Elderly 75+"),
        ("elderly_70_74", "Elderly 70-74"),
        ("elderly_65_69", "Elderly 65-69"),
        ("child_two_dose", "Eligible child"),
    )

    def __init__(self, program: str) -> None:
        super().__init__()
        self.program = program
        self.season_name_input = QLineEdit()
        self.program_enabled_check = QCheckBox("Use this schedule for program checks")
        self.daily_cap_input = QSpinBox()
        self.daily_cap_input.setRange(0, 9999)
        self.daily_cap_input.setValue(100)
        self.date_inputs: dict[str, OptionalDateInput] = {}
        self.birth_inputs: dict[str, tuple[OptionalDateInput, OptionalDateInput]] = {}
        self.allow_exception_check: QCheckBox | None = None

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        common = QFormLayout()
        common.addRow("Program year", self.season_name_input)
        common.addRow("State", self.program_enabled_check)
        common.addRow("Daily cap", self.daily_cap_input)
        editor_layout.addLayout(common)
        if program == "influenza":
            editor_layout.addWidget(self._build_influenza_dates())
            editor_layout.addWidget(self._build_influenza_birth_ranges())
        else:
            editor_layout.addWidget(self._build_covid_dates())
            editor_layout.addWidget(self._build_covid_birth_range())
        editor_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(editor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def _build_influenza_dates(self) -> QGroupBox:
        group = QGroupBox("Program dates")
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
            start = OptionalDateInput()
            self.date_inputs[start_key] = start
            grid.addWidget(start, row, 1)
            if end_key:
                end = OptionalDateInput()
                self.date_inputs[end_key] = end
                grid.addWidget(end, row, 2)
        self.allow_exception_check = QCheckBox("Allow elderly exception review path")
        grid.addWidget(self.allow_exception_check, len(rows) + 1, 0, 1, 3)
        return group

    def _build_influenza_birth_ranges(self) -> QGroupBox:
        group = QGroupBox("Inclusive birth-date ranges")
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

    def _build_covid_dates(self) -> QGroupBox:
        group = QGroupBox("Program dates")
        form = QFormLayout(group)
        for label, key in (("Program start", "program_start"), ("Program end", "program_end")):
            date_input = OptionalDateInput()
            self.date_inputs[key] = date_input
            form.addRow(label, date_input)
        return group

    def _build_covid_birth_range(self) -> QGroupBox:
        group = QGroupBox("Inclusive birth-date range")
        grid = QGridLayout(group)
        lower = OptionalDateInput()
        upper = OptionalDateInput()
        self.birth_inputs["national_covid"] = (lower, upper)
        grid.addWidget(QLabel("From"), 0, 0)
        grid.addWidget(QLabel("To"), 0, 1)
        grid.addWidget(lower, 1, 0)
        grid.addWidget(upper, 1, 1)
        return group

    def load_values(
        self,
        schedule: dict[str, object],
        groups: dict[str, dict[str, object]],
    ) -> None:
        self.season_name_input.setText(str(schedule.get("season_name", "")))
        self.program_enabled_check.setChecked(
            _as_bool(schedule.get("program_enabled", False))
        )
        try:
            daily_cap = int(schedule.get("daily_cap", 100))
        except (TypeError, ValueError):
            daily_cap = 100
        self.daily_cap_input.setValue(max(0, daily_cap))
        for key, date_input in self.date_inputs.items():
            date_input.set_value(schedule.get(key))
        if self.allow_exception_check is not None:
            self.allow_exception_check.setChecked(
                _as_bool(schedule.get("allow_elderly_exception", False))
            )
        for key, (lower, upper) in self.birth_inputs.items():
            source = groups.get(key, {})
            if key == "child_two_dose" and not source:
                source = groups.get("child_one_dose", {})
            lower.set_value(source.get("birth_date_from"))
            upper.set_value(source.get("birth_date_to"))

    def schedule_values(self) -> dict[str, object]:
        values: dict[str, object] = {
            "season_name": self.season_name_input.text().strip(),
            "program_enabled": self.program_enabled_check.isChecked(),
            "daily_cap": self.daily_cap_input.value(),
        }
        values.update({key: widget.value() for key, widget in self.date_inputs.items()})
        if self.allow_exception_check is not None:
            values["allow_elderly_exception"] = self.allow_exception_check.isChecked()
        return values

    def age_group_values(self) -> list[dict[str, object]]:
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
        labels = dict(self.INFLUENZA_GROUPS)
        values: list[dict[str, object]] = []
        for key, (lower, upper) in self.birth_inputs.items():
            value = {
                "key": key,
                "label": labels[key],
                "vaccine": "influenza",
                "birth_date_from": lower.value(),
                "birth_date_to": upper.value(),
            }
            values.append(value)
            if key == "child_two_dose":
                values.append(value | {"key": "child_one_dose"})
        return values

    def validation_error(self) -> str | None:
        if not self.program_enabled_check.isChecked():
            return None
        if not self.season_name_input.text().strip():
            return "Enter the program year before enabling this schedule."
        schedule = self.schedule_values()
        if any(not schedule.get(key) for key in self.date_inputs):
            return "Complete all program dates before enabling this schedule."
        for lower, upper in self.birth_inputs.values():
            if not lower.value() or not upper.value():
                return "Complete all birth-date ranges before enabling this schedule."
            if lower.value() > upper.value():
                return "A birth-date range starts after it ends."
        for start_key, end_key in self._date_pairs():
            if str(schedule[start_key]) > str(schedule[end_key]):
                return "A program date range starts after it ends."
        return None

    def _date_pairs(self) -> tuple[tuple[str, str], ...]:
        if self.program == "covid":
            return (("program_start", "program_end"),)
        return (
            ("elderly_75_plus_start", "elderly_program_end"),
            ("elderly_70_74_start", "elderly_program_end"),
            ("elderly_65_69_start", "elderly_program_end"),
            ("child_two_dose_start", "child_two_dose_end"),
            ("child_one_dose_start", "child_one_dose_end"),
        )


class VaccineSettingsPage(QWidget):
    settings_changed = Signal()

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._schedule_data: dict[str, object] = {}
        self._age_groups: list[object] = []
        self.tabs = QTabWidget()
        self.influenza_editor = VaccineProgramEditor("influenza")
        self.covid_editor = VaccineProgramEditor("covid")
        self.tabs.addTab(self.influenza_editor, "Influenza schedule")
        self.tabs.addTab(self.covid_editor, "COVID schedule")

        self.save_button = QPushButton("Save vaccine settings")
        self.save_button.clicked.connect(self.save_settings)
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.load_settings)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch()

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)
        self.load_settings()

    def load_settings(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        self._schedule_data = _json_object(settings.get("vaccine_schedule_rules_json"))
        self._age_groups = _json_list(settings.get("vaccine_age_groups_json"))
        groups = {
            str(group.get("key", "")): group
            for group in self._age_groups
            if isinstance(group, dict)
        }
        influenza = self._schedule_data.get("influenza", {})
        covid = self._schedule_data.get("covid", {})
        self.influenza_editor.load_values(
            influenza if isinstance(influenza, dict) else {}, groups
        )
        self.covid_editor.load_values(covid if isinstance(covid, dict) else {}, groups)
        self.status_label.setText("Vaccine settings loaded.")

    def reload(self) -> None:
        self.load_settings()

    def save_settings(self) -> bool:
        for editor in (self.influenza_editor, self.covid_editor):
            error = editor.validation_error()
            if error:
                self.tabs.setCurrentWidget(editor)
                self.status_label.setText(error)
                return False

        schedule_data = dict(self._schedule_data)
        for editor in (self.influenza_editor, self.covid_editor):
            previous = schedule_data.get(editor.program, {})
            section = dict(previous) if isinstance(previous, dict) else {}
            section.update(editor.schedule_values())
            schedule_data[editor.program] = section

        replacement_groups = (
            self.influenza_editor.age_group_values()
            + self.covid_editor.age_group_values()
        )
        replaced_keys = {str(group["key"]) for group in replacement_groups}
        age_groups = [
            group
            for group in self._age_groups
            if not isinstance(group, dict)
            or str(group.get("key", "")) not in replaced_keys
        ]
        age_groups.extend(replacement_groups)

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(
                connection,
                {
                    "vaccine_schedule_rules_json": json.dumps(
                        schedule_data, ensure_ascii=False, indent=2
                    ),
                    "vaccine_age_groups_json": json.dumps(
                        age_groups, ensure_ascii=False, indent=2
                    ),
                    "vaccine_influenza_daily_cap": str(
                        self.influenza_editor.daily_cap_input.value()
                    ),
                    "vaccine_covid_daily_cap": str(
                        self.covid_editor.daily_cap_input.value()
                    ),
                },
            )
        self._schedule_data = schedule_data
        self._age_groups = age_groups
        self.status_label.setText("Vaccine settings saved.")
        self.settings_changed.emit()
        return True


def _json_object(value: object) -> dict[str, object]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: object) -> list[object]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
