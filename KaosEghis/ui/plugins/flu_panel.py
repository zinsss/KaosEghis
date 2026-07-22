from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.weekly_age_reporting import (
    AGE_GROUP_ORDER,
    WeeklyAgeReportingUnavailableError,
    fetch_weekly_age_report,
    iso_week_range,
)
from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


class FluPanel(QWidget):
    """Weekly influenza report surface backed by the age-group practice count query."""

    REPORT_COLUMNS = ("Age Group", "Visits", "Patients")

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        iso_today = date.today().isocalendar()
        self._current_year = iso_today.year

        title = QLabel("Weekly - Influenza Report")
        title.setObjectName("pluginTitle")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")

        self.week_input = QLineEdit(f"{iso_today.week}")
        self.week_input.setMaxLength(2)
        self.week_input.setFixedWidth(56)
        self.week_input.setStyleSheet("font-size: 20px; padding: 6px 8px;")

        self.date_range_label = QLabel("Not loaded yet.")
        self.date_range_label.setStyleSheet("font-size: 18px;")

        search_button = QPushButton("Search")
        search_button.setStyleSheet("font-size: 18px; padding: 8px 16px;")
        search_button.clicked.connect(self.load_report)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Week No."))
        controls.itemAt(0).widget().setStyleSheet("font-size: 18px;")
        controls.addWidget(self.week_input)
        controls.addWidget(QLabel(":"))
        controls.itemAt(2).widget().setStyleSheet("font-size: 18px;")
        controls.addWidget(self.date_range_label, 1)
        controls.addWidget(search_button)

        self.summary_label = QLabel("Week -")
        self.summary_label.setStyleSheet("font-size: 26px; font-weight: 600;")

        self.total_visits_label = QLabel("Total Visits(Practice) Count: -")
        self.total_visits_label.setStyleSheet("font-size: 22px;")

        self.status_label = QLabel("Not loaded yet.")
        self.status_label.setStyleSheet("font-size: 18px;")

        self.report_table = QTableWidget(0, len(self.REPORT_COLUMNS))
        self.report_table.setHorizontalHeaderLabels(list(self.REPORT_COLUMNS))
        self.report_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.report_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.horizontalHeader().setStretchLastSection(True)
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setStyleSheet(
            "QTableWidget { font-size: 18px; }"
            "QHeaderView::section { font-size: 17px; font-weight: 600; padding: 8px; }"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(controls)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.total_visits_label)
        layout.addWidget(self.report_table, 1)
        layout.addWidget(self.status_label)

        self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})

    def load_report(self) -> None:
        week_text = self.week_input.text().strip()
        try:
            week_number = int(week_text)
        except ValueError:
            self.date_range_label.setText("Invalid week")
            self.summary_label.setText("Week -")
            self.total_visits_label.setText("Total Visits(Practice) Count: -")
            self.status_label.setText("Enter a valid ISO week number.")
            self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})
            return

        try:
            start_ymd, end_ymd = iso_week_range(self._current_year, week_number)
        except ValueError as exc:
            self.date_range_label.setText("Invalid week")
            self.summary_label.setText("Week -")
            self.total_visits_label.setText("Total Visits(Practice) Count: -")
            self.status_label.setText(str(exc))
            self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})
            return

        self.date_range_label.setText(_format_display_range(start_ymd, end_ymd))
        self.summary_label.setText(
            f"Week {week_number}, {_format_summary_range(self._current_year, start_ymd, end_ymd)}"
        )

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        if not (settings.get("eghis_db_connection_string") or "").strip():
            counts = {label: (0, 0) for label in AGE_GROUP_ORDER}
            self.total_visits_label.setText("Total Visits(Practice) Count: 0")
            self._populate_table(counts)
            self.status_label.setText("No eGHIS DB connection configured.")
            return

        try:
            rows = fetch_weekly_age_report(
                settings,
                year=self._current_year,
                start_week=week_number,
                end_week=week_number,
            )
        except (
            WeeklyAgeReportingUnavailableError,
            EghisDbUnavailableError,
            EghisDbQueryRejectedError,
        ):
            self.total_visits_label.setText("Total Visits(Practice) Count: -")
            self.status_label.setText("Flu report DB query failed.")
            self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})
            return
        except Exception:
            self.total_visits_label.setText("Total Visits(Practice) Count: -")
            self.status_label.setText("Flu report DB query failed.")
            self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})
            return

        counts_by_age = {label: (0, 0) for label in AGE_GROUP_ORDER}
        total_visits = 0
        for row in rows:
            if row.age_group in counts_by_age:
                counts_by_age[row.age_group] = (row.visit_count, row.patient_count)
                total_visits += row.visit_count

        self.total_visits_label.setText(
            f"Total Visits(Practice) Count: {total_visits}"
        )
        self._populate_table(counts_by_age)
        self.status_label.setText("Report loaded.")

    def _populate_table(self, counts_by_age: dict[str, tuple[int, int]]) -> None:
        self.report_table.setRowCount(len(AGE_GROUP_ORDER))
        for row_index, label in enumerate(AGE_GROUP_ORDER):
            visits, patients = counts_by_age.get(label, (0, 0))
            display_label = label.replace("1-6", "01~06")
            values = [display_label, str(visits), str(patients)]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                    )
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)
        self.report_table.resizeColumnsToContents()
        self.report_table.verticalHeader().setDefaultSectionSize(40)


def _format_display_range(start_ymd: str, end_ymd: str) -> str:
    start_date = date(int(start_ymd[:4]), int(start_ymd[4:6]), int(start_ymd[6:8]))
    end_date = date(int(end_ymd[:4]), int(end_ymd[4:6]), int(end_ymd[6:8]))
    return f"{start_date:%Y-%m-%d}~{end_date:%m-%d}"


def _format_summary_range(year: int, start_ymd: str, end_ymd: str) -> str:
    start_date = date(int(start_ymd[:4]), int(start_ymd[4:6]), int(start_ymd[6:8]))
    end_date = date(int(end_ymd[:4]), int(end_ymd[4:6]), int(end_ymd[6:8]))
    return f"{year}-{start_date:%m-%d} ~ {end_date:%m-%d}"
