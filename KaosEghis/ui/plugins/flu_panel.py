from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import threading
import time

from PySide6.QtCore import Qt, Signal
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
from KaosEghis.db.database import connect
from KaosEghis.db.repositories import get_settings


class FluPanel(QWidget):
    """Weekly influenza report surface backed by the age-group practice count query."""

    REPORT_COLUMNS = ("Age Group", "Visits", "Patients")
    report_loaded = Signal(int, dict, int)
    report_failed = Signal(int, str)
    report_unconfigured = Signal(int)
    SETTINGS_READ_ATTEMPTS = 2
    SETTINGS_READ_TIMEOUT_SECONDS = 0.25
    SETTINGS_RETRY_DELAY_SECONDS = 0.1

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        iso_today = date.today().isocalendar()
        self._current_year = iso_today.year
        self._load_generation = 0
        self._loading = False

        title = QLabel("Weekly - Influenza Report")
        title.setObjectName("pluginTitle")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")

        self.week_input = QLineEdit(f"{iso_today.week}")
        self.week_input.setMaxLength(2)
        self.week_input.setFixedWidth(56)
        self.week_input.setStyleSheet("font-size: 20px; padding: 6px 8px;")

        self.date_range_label = QLabel("Not loaded yet.")
        self.date_range_label.setStyleSheet("font-size: 18px;")

        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet("font-size: 18px;")
        self.search_button.clicked.connect(self.load_report)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Week No."))
        controls.itemAt(0).widget().setStyleSheet("font-size: 18px;")
        controls.addWidget(self.week_input)
        controls.addWidget(QLabel(":"))
        controls.itemAt(2).widget().setStyleSheet("font-size: 18px;")
        controls.addWidget(self.date_range_label, 1)
        controls.addWidget(self.search_button)

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
        self.report_loaded.connect(self._handle_report_loaded)
        self.report_failed.connect(self._handle_report_failed)
        self.report_unconfigured.connect(self._handle_report_unconfigured)

    def load_report(self) -> None:
        if self._loading:
            self.status_label.setText("Report is already loading.")
            return

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

        self._loading = True
        self._load_generation += 1
        generation = self._load_generation
        self.search_button.setEnabled(False)
        self.status_label.setText("Loading report...")
        self._start_report_worker(week_number, generation)

    def _start_report_worker(
        self,
        week_number: int,
        generation: int,
    ) -> None:
        worker = threading.Thread(
            target=self._load_report_worker,
            args=(week_number, generation),
            daemon=True,
        )
        worker.start()

    def _load_report_worker(
        self,
        week_number: int,
        generation: int,
    ) -> None:
        try:
            settings = self._load_report_settings()
            if not (settings.get("eghis_db_connection_string") or "").strip():
                self.report_unconfigured.emit(generation)
                return
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
            self.report_failed.emit(generation, "Flu report DB query failed.")
            return
        except Exception:
            self.report_failed.emit(generation, "Flu report DB query failed.")
            return

        counts_by_age = {label: (0, 0) for label in AGE_GROUP_ORDER}
        total_visits = 0
        for row in rows:
            if row.age_group in counts_by_age:
                counts_by_age[row.age_group] = (row.visit_count, row.patient_count)
                total_visits += row.visit_count

        self.report_loaded.emit(generation, counts_by_age, total_visits)

    def _load_report_settings(self) -> dict[str, str]:
        for attempt in range(self.SETTINGS_READ_ATTEMPTS):
            try:
                with connect(
                    self._db_path,
                    timeout=self.SETTINGS_READ_TIMEOUT_SECONDS,
                ) as connection:
                    return get_settings(connection)
            except sqlite3.OperationalError as exc:
                message = str(exc).casefold()
                if "no such table" in message:
                    return {}
                is_transient = "locked" in message or "busy" in message
                if not is_transient or attempt + 1 >= self.SETTINGS_READ_ATTEMPTS:
                    raise
                time.sleep(self.SETTINGS_RETRY_DELAY_SECONDS)
        return {}

    def _handle_report_loaded(
        self,
        generation: int,
        counts_by_age: dict[str, tuple[int, int]],
        total_visits: int,
    ) -> None:
        if generation != self._load_generation:
            return
        self._loading = False
        self.search_button.setEnabled(True)

        self.total_visits_label.setText(
            f"Total Visits(Practice) Count: {total_visits}"
        )
        self._populate_table(counts_by_age)
        self.status_label.setText("Report loaded.")

    def _handle_report_failed(self, generation: int, message: str) -> None:
        if generation != self._load_generation:
            return
        self._loading = False
        self.search_button.setEnabled(True)
        self.total_visits_label.setText("Total Visits(Practice) Count: -")
        self.status_label.setText(message)
        self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})

    def _handle_report_unconfigured(self, generation: int) -> None:
        if generation != self._load_generation:
            return
        self._loading = False
        self.search_button.setEnabled(True)
        self.total_visits_label.setText("Total Visits(Practice) Count: 0")
        self.status_label.setText("No eGHIS DB connection configured.")
        self._populate_table({label: (0, 0) for label in AGE_GROUP_ORDER})

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
