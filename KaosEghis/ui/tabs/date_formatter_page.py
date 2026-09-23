from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.date_formatting import (
    DateFormatValidationError,
    format_dates_korean_compact,
)


class DateFormatterPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Date Formatter")
        title.setObjectName("pageTitle")

        self.input_text = QPlainTextEdit()
        self.input_text.setObjectName("dateFormatterInput")
        self.output_text = QPlainTextEdit()
        self.output_text.setObjectName("dateFormatterOutput")
        self.output_text.setReadOnly(True)

        input_column = QVBoxLayout()
        input_column.addWidget(QLabel("Dates (YYYY-MM-DD)"))
        input_column.addWidget(self.input_text, 1)

        output_column = QVBoxLayout()
        output_column.addWidget(QLabel("Korean compact format"))
        output_column.addWidget(self.output_text, 1)

        editors = QHBoxLayout()
        editors.addLayout(input_column, 1)
        editors.addLayout(output_column, 1)

        self.format_button = QPushButton("Format")
        self.format_button.clicked.connect(self.format_input)
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_output)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)

        controls = QHBoxLayout()
        controls.addWidget(self.format_button)
        controls.addWidget(self.copy_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()

        self.status_label = QLabel("")
        self.status_label.setObjectName("dateFormatterStatus")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(editors, 1)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)

    def format_input(self) -> None:
        try:
            formatted = format_dates_korean_compact(self.input_text.toPlainText())
        except DateFormatValidationError:
            self.output_text.clear()
            self.status_label.setText(
                "Invalid date. Use valid YYYY-MM-DD dates separated by commas."
            )
            return
        self.output_text.setPlainText(formatted)
        self.status_label.setText("Formatted." if formatted else "")

    def copy_output(self) -> None:
        text = self.output_text.toPlainText()
        if not text:
            self.status_label.setText("Nothing to copy.")
            return
        try:
            copy_text(text)
        except RuntimeError:
            self.status_label.setText("Clipboard copy failed.")
            return
        self.status_label.setText("Copied.")

    def clear(self) -> None:
        self.input_text.clear()
        self.output_text.clear()
        self.status_label.clear()
