from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.weekly_age_reporting import (
    AGE_GROUP_ORDER,
    WeeklyAgeReportingUnavailableError,
    fetch_weekly_age_report,
    iso_week_range,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


class FluPanel(QWidget):
    """Weekly influenza report surface backed by the age-group practice count query."""

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        iso_today = date.today().isocalendar()
        self._current_year = iso_today.year

        title = QLabel("Weekly - Influenza Report")
        title.setObjectName("pluginTitle")

        self.week_input = QLineEdit(f"{iso_today.week}")
        self.week_input.setMaxLength(2)
        self.week_input.setFixedWidth(48)
        self.date_range_label = QLabel()
        self.report_status = QLabel("Not loaded yet.")

        self.load_week_button = QPushButton("Load week")
        self.load_week_button.clicked.connect(self.load_report)
        self.generate_report_button = QPushButton("Generate report")
        self.generate_report_button.clicked.connect(self.load_report)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Week No."))
        controls.addWidget(self.week_input)
        controls.addWidget(QLabel(":"))
        controls.addWidget(self.date_range_label)
        controls.addWidget(self.load_week_button)
        controls.addWidget(self.generate_report_button)
        controls.addStretch()

        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(controls)
        layout.addWidget(self.report_status)
        layout.addWidget(self.report_output)

    def load_report(self) -> None:
        week_text = self.week_input.text().strip()
        try:
            week_number = int(week_text)
        except ValueError:
            self.date_range_label.setText("Invalid week")
            self.report_status.setText("Invalid week.")
            self.report_output.setPlainText("Enter a valid ISO week number.")
            return

        try:
            start_ymd, end_ymd = iso_week_range(self._current_year, week_number)
        except ValueError as exc:
            self.date_range_label.setText("Invalid week")
            self.report_status.setText("Invalid week.")
            self.report_output.setPlainText(str(exc))
            return

        self.date_range_label.setText(_format_display_range(start_ymd, end_ymd))

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        if not (settings.get("eghis_db_connection_string") or "").strip():
            self.report_status.setText("Eghis DB connection failed.")
            self.report_output.setPlainText(
                _render_report(
                    year=self._current_year,
                    week_number=week_number,
                    start_ymd=start_ymd,
                    end_ymd=end_ymd,
                    visit_count=0,
                    counts_by_age={label: 0 for label in AGE_GROUP_ORDER},
                )
            )
            return

        try:
            rows = fetch_weekly_age_report(
                settings,
                year=self._current_year,
                start_week=week_number,
                end_week=week_number,
            )
        except WeeklyAgeReportingUnavailableError:
            self.report_status.setText("Eghis DB connection failed.")
            self.report_output.setPlainText("Eghis DB connection failed.")
            return
        except Exception:
            self.report_status.setText("Eghis DB connection failed.")
            self.report_output.setPlainText("Eghis DB connection failed.")
            return

        counts_by_age = {label: 0 for label in AGE_GROUP_ORDER}
        total_visits = 0
        for row in rows:
            if row.age_group in counts_by_age:
                counts_by_age[row.age_group] = row.visit_count
                total_visits += row.visit_count

        self.report_output.setPlainText(
            _render_report(
                year=self._current_year,
                week_number=week_number,
                start_ymd=start_ymd,
                end_ymd=end_ymd,
                visit_count=total_visits,
                counts_by_age=counts_by_age,
            )
        )
        self.report_status.setText("Report loaded.")


def _format_display_range(start_ymd: str, end_ymd: str) -> str:
    start_date = date(int(start_ymd[:4]), int(start_ymd[4:6]), int(start_ymd[6:8]))
    end_date = date(int(end_ymd[:4]), int(end_ymd[4:6]), int(end_ymd[6:8]))
    return f"{start_date:%Y-%m-%d}~{end_date:%m-%d}"


def _render_report(
    *,
    year: int,
    week_number: int,
    start_ymd: str,
    end_ymd: str,
    visit_count: int,
    counts_by_age: dict[str, int],
) -> str:
    start_date = date(int(start_ymd[:4]), int(start_ymd[4:6]), int(start_ymd[6:8]))
    end_date = date(int(end_ymd[:4]), int(end_ymd[4:6]), int(end_ymd[6:8]))
    lines = [
        f"Week {week_number}, {year}-{start_date:%m-%d} ~ {end_date:%m-%d}",
        f"Total Visits(Practice) Count: {visit_count}",
    ]
    for label in AGE_GROUP_ORDER:
        display_label = label.replace("1-6", "01~06")
        lines.append(f"{display_label} : {counts_by_age.get(label, 0)}")
    return "\n".join(lines)
