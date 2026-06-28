from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FluPanel(QWidget):
    """Visible working-status scaffold for the KaosEghis-flu plugin."""

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Weekly - Influenza Report")
        title.setObjectName("pluginTitle")

        self.db_status = QLabel("Eghis DB access: not connected")
        self.report_status = QLabel("Report readiness: waiting")

        status_row = QHBoxLayout()
        status_row.addWidget(self.db_status)
        status_row.addWidget(self.report_status)
        status_row.addStretch()

        self.week_selector = QComboBox()
        self.week_selector.addItems(_epidemiologic_week_labels())

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.sync_week_from_calendar)

        load_button = QPushButton("Load week")
        load_button.clicked.connect(self.load_week)

        generate_button = QPushButton("Generate report")
        generate_button.clicked.connect(self.generate_report)

        export_button = QPushButton("Export / Copy")
        export_button.clicked.connect(self.export_report)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Week:"))
        controls.addWidget(self.week_selector)
        controls.addWidget(load_button)
        controls.addWidget(generate_button)
        controls.addWidget(export_button)
        controls.addStretch()

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Weekly influenza surveillance report preview will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(status_row)
        layout.addLayout(controls)
        layout.addWidget(self.calendar)
        layout.addWidget(self.preview)

        self.load_week()

    def sync_week_from_calendar(self) -> None:
        selected = self.calendar.selectedDate()
        iso_year, iso_week, _weekday = date(selected.year(), selected.month(), selected.day()).isocalendar()
        label = f"{iso_year}-W{iso_week:02d}"
        index = self.week_selector.findText(label)
        if index >= 0:
            self.week_selector.setCurrentIndex(index)

    def load_week(self) -> None:
        week = self.week_selector.currentText()
        self.report_status.setText("Report readiness: not connected")
        self.preview.setPlainText(
            f"KaosEghis-flu weekly report scaffold\n\n"
            f"Selected week: {week}\n"
            "Eghis DB access is not connected in this UI scaffold PR.\n"
            "Existing Flu report services can be wired here in a later backend PR."
        )

    def generate_report(self) -> None:
        week = self.week_selector.currentText()
        self.report_status.setText("Report readiness: preview only")
        self.preview.setPlainText(
            f"Weekly national influenza surveillance report\n"
            f"Week: {week}\n\n"
            "Status: preview only.\n"
            "No Eghis database query was executed.\n"
            "No public-health report file was exported."
        )

    def export_report(self) -> None:
        self.report_status.setText("Report readiness: export not connected")
        self.preview.appendPlainText("\nExport / Copy requested, but backend export is not implemented in this PR.")


def _epidemiologic_week_labels() -> list[str]:
    today = date.today()
    current_year = today.isocalendar().year
    labels: list[str] = []
    for year in [current_year - 1, current_year, current_year + 1]:
        for week in range(1, 54):
            labels.append(f"{year}-W{week:02d}")
    return labels
