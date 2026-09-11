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
    COVID_GROUPS = (
        ("covid_elderly_75_plus", "COVID 75+"),
        ("covid_elderly_70_74", "COVID 70-74"),
        ("covid_elderly_65_69", "COVID 65-69"),
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
            editor_layout.addWidget(self._build_covid_birth_ranges())
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
        self.allow_exception_check = QCheckBox(
            "Allow manually verified rural-area exception"
        )
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
        grid = QGridLayout(group)
        rows = (
            ("75+ start", "elderly_75_plus_start"),
            ("70-74 start", "elderly_70_74_start"),
            ("65-69 start", "elderly_65_69_start"),
            ("Program end", "elderly_program_end"),
        )
        for row, (label, key) in enumerate(rows):
            date_input = OptionalDateInput()
            self.date_inputs[key] = date_input
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(date_input, row, 1)
        self.allow_exception_check = QCheckBox(
            "Allow manually verified rural-area exception"
        )
        grid.addWidget(self.allow_exception_check, len(rows), 0, 1, 2)
        return group

    def _build_covid_birth_ranges(self) -> QGroupBox:
        group = QGroupBox("Inclusive birth-date ranges")
        grid = QGridLayout(group)
        grid.addWidget(QLabel("Group"), 0, 0)
        grid.addWidget(QLabel("From"), 0, 1)
        grid.addWidget(QLabel("To"), 0, 2)
        for row, (key, label) in enumerate(self.COVID_GROUPS, start=1):
            lower = OptionalDateInput()
            upper = OptionalDateInput()
            self.birth_inputs[key] = (lower, upper)
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(lower, row, 1)
            grid.addWidget(upper, row, 2)
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
                _as_bool(
                    schedule.get(
                        "allow_rural_exception",
                        schedule.get("allow_elderly_exception", True),
                    )
                )
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
            values["allow_rural_exception"] = self.allow_exception_check.isChecked()
        return values

    def age_group_values(self) -> list[dict[str, object]]:
        if self.program == "covid":
            labels = dict(self.COVID_GROUPS)
            return [
                {
                    "key": key,
                    "label": labels[key],
                    "vaccine": "covid",
                    "birth_date_from": lower.value(),
                    "birth_date_to": upper.value(),
                }
                for key, (lower, upper) in self.birth_inputs.items()
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
            return (
                ("elderly_75_plus_start", "elderly_program_end"),
                ("elderly_70_74_start", "elderly_program_end"),
                ("elderly_65_69_start", "elderly_program_end"),
            )
        return (
            ("elderly_75_plus_start", "elderly_program_end"),
            ("elderly_70_74_start", "elderly_program_end"),
            ("elderly_65_69_start", "elderly_program_end"),
            ("child_two_dose_start", "child_two_dose_end"),
            ("child_one_dose_start", "child_one_dose_end"),
        )


class VaccineSystemTargetsEditor(QWidget):
    """Editable stable selectors for external-system handoff and session reset."""

    def __init__(self) -> None:
        super().__init__()
        self.general_launch_url_input = QLineEdit()
        self.general_window_title_input = QLineEdit()
        self.general_window_class_input = QLineEdit()
        self.general_resident_x_input = self._coordinate_input()
        self.general_resident_y_input = self._coordinate_input()
        self.general_keepalive_x_input = self._coordinate_input()
        self.general_keepalive_y_input = self._coordinate_input()

        self.influenza_window_title_input = QLineEdit()
        self.influenza_launch_url_input = QLineEdit()
        self.influenza_resident_automation_id_input = QLineEdit()
        self.influenza_resident_control_type_input = QLineEdit()
        self.influenza_resident_class_input = QLineEdit()
        self.influenza_resident_x_input = self._coordinate_input()
        self.influenza_resident_y_input = self._coordinate_input()

        self.covid_window_title_input = QLineEdit()
        self.covid_launch_url_input = QLineEdit()
        self.covid_window_class_input = QLineEdit()
        self.covid_resident_x_input = self._coordinate_input()
        self.covid_resident_y_input = self._coordinate_input()
        self.covid_keepalive_x_input = self._coordinate_input()
        self.covid_keepalive_y_input = self._coordinate_input()

        self.kdca_portal_url_input = QLineEdit()
        self.kdca_browser_title_input = QLineEdit()
        self.kdca_login_control_name_input = QLineEdit()
        self.kdca_login_x_input = self._coordinate_input()
        self.kdca_login_y_input = self._coordinate_input()
        self.kdca_certificate_window_title_input = QLineEdit()
        self.kdca_certificate_name_input = QLineEdit()
        self.kdca_password_window_title_input = QLineEdit()
        self.kdca_password_automation_id_input = QLineEdit()
        self.kdca_password_control_type_input = QLineEdit()
        self.kdca_confirm_control_name_input = QLineEdit()
        self.kdca_credential_reference_input = QLineEdit()
        self.session_keeper_enabled_check = QCheckBox(
            "Keep General and COVID sessions active every 90 minutes"
        )
        self.session_keeper_status_label = QLabel("Session keeper: off.")
        self.session_keeper_status_label.setWordWrap(True)

        general_group = QGroupBox("General vaccine system")
        general_form = QFormLayout(general_group)
        general_form.addRow("Launch URL", self.general_launch_url_input)
        general_form.addRow("Window title", self.general_window_title_input)
        general_form.addRow("Window class", self.general_window_class_input)
        general_form.addRow("Resident input X", self.general_resident_x_input)
        general_form.addRow("Resident input Y", self.general_resident_y_input)
        general_form.addRow("Session reset X", self.general_keepalive_x_input)
        general_form.addRow("Session reset Y", self.general_keepalive_y_input)

        influenza_group = QGroupBox("Influenza browser system")
        influenza_form = QFormLayout(influenza_group)
        influenza_form.addRow("Launch URL", self.influenza_launch_url_input)
        influenza_form.addRow("Window or tab title", self.influenza_window_title_input)
        influenza_form.addRow(
            "Resident input automation ID",
            self.influenza_resident_automation_id_input,
        )
        influenza_form.addRow(
            "Resident input control type",
            self.influenza_resident_control_type_input,
        )
        influenza_form.addRow(
            "Resident input class",
            self.influenza_resident_class_input,
        )
        influenza_form.addRow("Fallback input X", self.influenza_resident_x_input)
        influenza_form.addRow("Fallback input Y", self.influenza_resident_y_input)

        covid_group = QGroupBox("COVID system")
        covid_form = QFormLayout(covid_group)
        covid_form.addRow("Launch URL", self.covid_launch_url_input)
        covid_form.addRow("Window title", self.covid_window_title_input)
        covid_form.addRow("Window class", self.covid_window_class_input)
        covid_form.addRow("Resident input X", self.covid_resident_x_input)
        covid_form.addRow("Resident input Y", self.covid_resident_y_input)
        covid_form.addRow("Session reset X", self.covid_keepalive_x_input)
        covid_form.addRow("Session reset Y", self.covid_keepalive_y_input)

        kdca_group = QGroupBox("KDCA certificate login")
        kdca_form = QFormLayout(kdca_group)
        kdca_form.addRow("Portal URL", self.kdca_portal_url_input)
        kdca_form.addRow("Browser title contains", self.kdca_browser_title_input)
        kdca_form.addRow("Login control text", self.kdca_login_control_name_input)
        kdca_form.addRow("Login fallback X", self.kdca_login_x_input)
        kdca_form.addRow("Login fallback Y", self.kdca_login_y_input)
        kdca_form.addRow(
            "Certificate picker title contains",
            self.kdca_certificate_window_title_input,
        )
        kdca_form.addRow("Certificate label", self.kdca_certificate_name_input)
        kdca_form.addRow(
            "Password window title contains",
            self.kdca_password_window_title_input,
        )
        kdca_form.addRow(
            "Password automation ID (optional)",
            self.kdca_password_automation_id_input,
        )
        kdca_form.addRow(
            "Password control type",
            self.kdca_password_control_type_input,
        )
        kdca_form.addRow("Confirm control text", self.kdca_confirm_control_name_input)
        kdca_form.addRow(
            "KaosEghis-pw credential entry",
            self.kdca_credential_reference_input,
        )

        note = QLabel(
            "Windows Handle values are not saved because they change each time an "
            "application starts. Save stable window titles, UIA automation IDs, and "
            "coordinates instead. These settings do not submit vaccination records."
        )
        note.setWordWrap(True)
        session_note = QLabel(
            "When enabled, KaosEghis checks only the configured General and COVID "
            "native windows every 90 minutes. It clicks the saved session-reset point "
            "only when that exact visible window owns the point. It never runs for "
            "the Influenza browser, types credentials, or changes vaccination records."
        )
        session_note.setWordWrap(True)
        kdca_note = QLabel(
            "KDCA certificate login runs only when the operator presses Log in to KDCA. "
            "It opens the portal, requires one visible matching browser, certificate, "
            "password field, and confirmation control, then types the encrypted vault "
            "password without using clipboard. It never runs at startup or retries blindly."
        )
        kdca_note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(general_group)
        layout.addWidget(influenza_group)
        layout.addWidget(covid_group)
        layout.addWidget(kdca_group)
        layout.addWidget(kdca_note)
        layout.addWidget(self.session_keeper_enabled_check)
        layout.addWidget(session_note)
        layout.addWidget(self.session_keeper_status_label)
        layout.addWidget(note)
        layout.addStretch()

    @staticmethod
    def _coordinate_input() -> QSpinBox:
        input_widget = QSpinBox()
        input_widget.setRange(0, 9999)
        return input_widget

    def load_values(self, settings: dict[str, str]) -> None:
        self.general_window_title_input.setText(
            settings.get("vaccine_general_system_window_title", "")
        )
        self.general_launch_url_input.setText(
            settings.get("vaccine_general_system_launch_url", "")
        )
        self.general_window_class_input.setText(
            settings.get("vaccine_general_system_window_class", "")
        )
        self.general_resident_x_input.setValue(
            _setting_coordinate(settings, "vaccine_general_system_resident_x")
        )
        self.general_resident_y_input.setValue(
            _setting_coordinate(settings, "vaccine_general_system_resident_y")
        )
        self.general_keepalive_x_input.setValue(
            _setting_coordinate(settings, "vaccine_general_system_keepalive_x")
        )
        self.general_keepalive_y_input.setValue(
            _setting_coordinate(settings, "vaccine_general_system_keepalive_y")
        )

        self.influenza_window_title_input.setText(
            settings.get("vaccine_influenza_system_window_title", "")
        )
        self.influenza_launch_url_input.setText(
            settings.get("vaccine_influenza_system_launch_url", "")
        )
        self.influenza_resident_automation_id_input.setText(
            settings.get("vaccine_influenza_system_resident_automation_id", "")
        )
        self.influenza_resident_control_type_input.setText(
            settings.get("vaccine_influenza_system_resident_control_type", "")
        )
        self.influenza_resident_class_input.setText(
            settings.get("vaccine_influenza_system_resident_class", "")
        )
        self.influenza_resident_x_input.setValue(
            _setting_coordinate(settings, "vaccine_influenza_system_resident_x")
        )
        self.influenza_resident_y_input.setValue(
            _setting_coordinate(settings, "vaccine_influenza_system_resident_y")
        )

        self.covid_window_title_input.setText(
            settings.get("vaccine_covid_system_window_title", "")
        )
        self.covid_launch_url_input.setText(
            settings.get("vaccine_covid_system_launch_url", "")
        )
        self.covid_window_class_input.setText(
            settings.get("vaccine_covid_system_window_class", "")
        )
        self.covid_resident_x_input.setValue(
            _setting_coordinate(settings, "vaccine_covid_system_resident_x")
        )
        self.covid_resident_y_input.setValue(
            _setting_coordinate(settings, "vaccine_covid_system_resident_y")
        )
        self.covid_keepalive_x_input.setValue(
            _setting_coordinate(settings, "vaccine_covid_system_keepalive_x")
        )
        self.covid_keepalive_y_input.setValue(
            _setting_coordinate(settings, "vaccine_covid_system_keepalive_y")
        )
        self.kdca_portal_url_input.setText(settings.get("vaccine_kdca_portal_url", ""))
        self.kdca_browser_title_input.setText(
            settings.get("vaccine_kdca_browser_window_title_contains", "")
        )
        self.kdca_login_control_name_input.setText(
            settings.get("vaccine_kdca_login_control_name", "")
        )
        self.kdca_login_x_input.setValue(
            _setting_coordinate(settings, "vaccine_kdca_login_x")
        )
        self.kdca_login_y_input.setValue(
            _setting_coordinate(settings, "vaccine_kdca_login_y")
        )
        self.kdca_certificate_window_title_input.setText(
            settings.get("vaccine_kdca_certificate_window_title_contains", "")
        )
        self.kdca_certificate_name_input.setText(
            settings.get("vaccine_kdca_certificate_name", "")
        )
        self.kdca_password_window_title_input.setText(
            settings.get("vaccine_kdca_password_window_title_contains", "")
        )
        self.kdca_password_automation_id_input.setText(
            settings.get("vaccine_kdca_password_automation_id", "")
        )
        self.kdca_password_control_type_input.setText(
            settings.get("vaccine_kdca_password_control_type", "Edit")
        )
        self.kdca_confirm_control_name_input.setText(
            settings.get("vaccine_kdca_confirm_control_name", "")
        )
        self.kdca_credential_reference_input.setText(
            settings.get("vaccine_kdca_credential_reference", "")
        )
        self.session_keeper_enabled_check.setChecked(
            _as_bool(settings.get("vaccine_session_keeper_enabled", "false"))
        )

    def values(self) -> dict[str, str]:
        return {
            "vaccine_general_system_launch_url": (
                self.general_launch_url_input.text().strip()
            ),
            "vaccine_general_system_window_title": (
                self.general_window_title_input.text().strip()
            ),
            "vaccine_general_system_window_class": (
                self.general_window_class_input.text().strip()
            ),
            "vaccine_general_system_resident_x": str(
                self.general_resident_x_input.value()
            ),
            "vaccine_general_system_resident_y": str(
                self.general_resident_y_input.value()
            ),
            "vaccine_general_system_keepalive_x": str(
                self.general_keepalive_x_input.value()
            ),
            "vaccine_general_system_keepalive_y": str(
                self.general_keepalive_y_input.value()
            ),
            "vaccine_influenza_system_window_title": (
                self.influenza_window_title_input.text().strip()
            ),
            "vaccine_influenza_system_launch_url": (
                self.influenza_launch_url_input.text().strip()
            ),
            "vaccine_influenza_system_resident_automation_id": (
                self.influenza_resident_automation_id_input.text().strip()
            ),
            "vaccine_influenza_system_resident_control_type": (
                self.influenza_resident_control_type_input.text().strip()
            ),
            "vaccine_influenza_system_resident_class": (
                self.influenza_resident_class_input.text().strip()
            ),
            "vaccine_influenza_system_resident_x": str(
                self.influenza_resident_x_input.value()
            ),
            "vaccine_influenza_system_resident_y": str(
                self.influenza_resident_y_input.value()
            ),
            "vaccine_covid_system_window_title": (
                self.covid_window_title_input.text().strip()
            ),
            "vaccine_covid_system_launch_url": (
                self.covid_launch_url_input.text().strip()
            ),
            "vaccine_covid_system_window_class": (
                self.covid_window_class_input.text().strip()
            ),
            "vaccine_covid_system_resident_x": str(
                self.covid_resident_x_input.value()
            ),
            "vaccine_covid_system_resident_y": str(
                self.covid_resident_y_input.value()
            ),
            "vaccine_covid_system_keepalive_x": str(
                self.covid_keepalive_x_input.value()
            ),
            "vaccine_covid_system_keepalive_y": str(
                self.covid_keepalive_y_input.value()
            ),
            "vaccine_kdca_portal_url": self.kdca_portal_url_input.text().strip(),
            "vaccine_kdca_browser_window_title_contains": (
                self.kdca_browser_title_input.text().strip()
            ),
            "vaccine_kdca_login_control_name": (
                self.kdca_login_control_name_input.text().strip()
            ),
            "vaccine_kdca_login_x": str(self.kdca_login_x_input.value()),
            "vaccine_kdca_login_y": str(self.kdca_login_y_input.value()),
            "vaccine_kdca_certificate_window_title_contains": (
                self.kdca_certificate_window_title_input.text().strip()
            ),
            "vaccine_kdca_certificate_name": (
                self.kdca_certificate_name_input.text().strip()
            ),
            "vaccine_kdca_password_window_title_contains": (
                self.kdca_password_window_title_input.text().strip()
            ),
            "vaccine_kdca_password_automation_id": (
                self.kdca_password_automation_id_input.text().strip()
            ),
            "vaccine_kdca_password_control_type": (
                self.kdca_password_control_type_input.text().strip()
            ),
            "vaccine_kdca_confirm_control_name": (
                self.kdca_confirm_control_name_input.text().strip()
            ),
            "vaccine_kdca_credential_reference": (
                self.kdca_credential_reference_input.text().strip()
            ),
            "vaccine_session_keeper_enabled": (
                "true" if self.session_keeper_enabled_check.isChecked() else "false"
            ),
        }

    def set_session_keeper_status(self, message: str) -> None:
        self.session_keeper_status_label.setText(message)


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
        self.system_targets_editor = VaccineSystemTargetsEditor()
        self.tabs.addTab(self.influenza_editor, "Influenza schedule")
        self.tabs.addTab(self.covid_editor, "COVID schedule")
        self.tabs.addTab(self.system_targets_editor, "System targets")

        self.printer_name_input = QLineEdit()
        printer_group = QGroupBox("Thermal label printer")
        printer_form = QFormLayout(printer_group)
        printer_form.addRow("Windows printer name", self.printer_name_input)

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
        layout.addWidget(printer_group)
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
        self.printer_name_input.setText(
            settings.get("vaccine_label_printer_name", "4BARCODE 4B-2054L")
        )
        self.system_targets_editor.load_values(settings)
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
        replaced_keys.add("national_covid")
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
                    "vaccine_label_printer_name": self.printer_name_input.text().strip(),
                }
                | self.system_targets_editor.values(),
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


def _setting_coordinate(settings: dict[str, str], key: str) -> int:
    try:
        return max(0, min(int(settings.get(key, "0")), 9999))
    except (TypeError, ValueError):
        return 0
