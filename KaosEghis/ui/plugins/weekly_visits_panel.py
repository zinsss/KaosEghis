from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.weekly_age_reporting import (
    AGE_GROUP_ORDER,
    WeeklyAgeReportingUnavailableError,
    fetch_weekly_age_report,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


class WeeklyVisitsPanel(QWidget):
    REPORT_COLUMNS = ["Age Group", "Visits", "Patients"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        iso_today = date.today().isocalendar()

        title = QLabel("KaosEghis-weekly-practice-count")
        title.setObjectName("pluginTitle")

        self.db_status = QLabel("Eghis DB: not configured")
        self.report_status = QLabel("Report status: waiting")

        status_row = QHBoxLayout()
        status_row.addWidget(self.db_status)
        status_row.addWidget(self.report_status)
        status_row.addStretch()

        self.year_input = QSpinBox()
        self.year_input.setRange(2000, 2100)
        self.year_input.setValue(iso_today.year)

        self.start_week_input = QSpinBox()
        self.start_week_input.setRange(1, 53)
        self.start_week_input.setValue(iso_today.week)

        self.end_week_input = QSpinBox()
        self.end_week_input.setRange(1, 53)
        self.end_week_input.setValue(iso_today.week)

        load_button = QPushButton("Load report")
        load_button.clicked.connect(self.load_report)

        form = QFormLayout()
        form.addRow("Year", self.year_input)
        form.addRow("Start ISO week", self.start_week_input)
        form.addRow("End ISO week", self.end_week_input)

        action_row = QHBoxLayout()
        action_row.addLayout(form)
        action_row.addWidget(load_button)
        action_row.addStretch()

        self.report_table = QTableWidget(0, len(self.REPORT_COLUMNS))
        self.report_table.setHorizontalHeaderLabels(self.REPORT_COLUMNS)

        footer = QLabel(
            "Weekly practice counts by age group from the Eghis PostgreSQL database. "
            "Patients is a secondary distinct-patient count."
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(status_row)
        layout.addLayout(action_row)
        layout.addWidget(self.report_table)
        layout.addWidget(footer)

        self.load_report()

    def load_report(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        if not (settings.get("eghis_db_connection_string") or "").strip():
            self.db_status.setText("Eghis DB: not configured")
            self.report_status.setText("Report status: unavailable")
            self._populate_rows([])
            return

        self.db_status.setText("Eghis DB: configured")
        try:
            rows = fetch_weekly_age_report(
                settings,
                year=self.year_input.value(),
                start_week=self.start_week_input.value(),
                end_week=self.end_week_input.value(),
            )
        except ValueError as exc:
            self.report_status.setText(f"Report status: {exc}")
            self._populate_rows([])
            return
        except WeeklyAgeReportingUnavailableError as exc:
            self.report_status.setText(f"Report status: {exc}")
            self._populate_rows([])
            return

        self.report_status.setText(f"Report status: loaded {len(rows)} rows")
        self._populate_rows(rows)

    def _populate_rows(self, rows) -> None:
        order_index = {label: index for index, label in enumerate(AGE_GROUP_ORDER)}
        ordered_rows = sorted(
            rows,
            key=lambda row: order_index.get(row.age_group, len(AGE_GROUP_ORDER)),
        )
        self.report_table.setRowCount(len(ordered_rows))
        for row_index, item in enumerate(ordered_rows):
            values = [item.age_group, str(item.visit_count), str(item.patient_count)]
            for col_index, value in enumerate(values):
                self.report_table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.report_table.resizeColumnsToContents()
