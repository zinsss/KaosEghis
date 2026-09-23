from __future__ import annotations

from datetime import date, datetime, timedelta
import threading

from PySide6.QtCore import QDate, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDateEdit, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from KaosEghis.core.claim_preparation import (
    ClaimHistory, ClaimPreviewError, build_claim_plan,
)
from KaosEghis.core.claim_screen_reader import connected_claim_identity, read_claim_history


class ClaimPreviewDialog(QDialog):
    read_finished = Signal(int, object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Claim preparation - read-only preview")
        self.resize(790, 320)
        self.histories: dict[date, ClaimHistory] = {}
        self._generation = 0
        self._thread: threading.Thread | None = None
        self.claim_date = QDateEdit(QDate.currentDate())
        self.claim_date.setCalendarPopup(True)
        self.claim_date.setDisplayFormat("yyyy-MM-dd")
        self.claim_date.dateChanged.connect(self.clear_history)
        self.read_button = QPushButton("Read selected EMR month")
        self.read_button.setToolTip("Select the month and 주단위 in the EMR claim screen, then read.")
        self.read_button.clicked.connect(self.read_month)
        self.clear_button = QPushButton("Clear preview")
        self.clear_button.clicked.connect(self.clear_history)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Claim date"))
        controls.addWidget(self.claim_date)
        controls.addWidget(self.read_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Month", "Period", "Latest week", "Next week", "Read at", "Status",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.status = QLabel("Month not read.")
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table)
        layout.addWidget(self.status)
        self.read_finished.connect(self._finish_read)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._read_timeout)
        self._validity_timer = QTimer(self)
        self._validity_timer.setInterval(1000)
        self._validity_timer.timeout.connect(self._invalidate_old_history)
        self._validity_timer.start()
        self._render()

    def clear_history(self, *_args) -> None:
        self._generation += 1
        self.histories.clear()
        self.status.setText("Month not read.")
        self._render()

    def reject(self) -> None:
        self.clear_history()
        super().reject()

    def _render(self) -> None:
        try:
            parts = build_claim_plan(self.claim_date.date().toPython(), self.histories)
        except ClaimPreviewError as error:
            self.table.setRowCount(0)
            self.status.setText(str(error))
            return
        self.table.setRowCount(len(parts))
        for row, part in enumerate(parts):
            values = (
                part.month.strftime("%Y/%m"),
                f"{part.start:%m/%d} - {part.end:%m/%d}",
                "Not read" if part.latest_week is None else (
                    "Empty" if part.latest_week == 0 else f"{part.latest_week}주"
                ),
                f"{part.next_week}주" if part.next_week is not None else "-",
                part.captured_at.strftime("%H:%M:%S") if part.captured_at else "-",
                part.status,
            )
            for column, text in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(text))

    def _invalidate_old_history(self) -> None:
        if not self.histories:
            return
        connection = connected_claim_identity()
        cutoff = datetime.now() - timedelta(minutes=5)
        if any(
            history.connection != connection or history.captured_at < cutoff
            for history in self.histories.values()
        ):
            self.clear_history()
            self.status.setText("Preview expired or EMR connection changed. Read the months again.")

    def read_month(self) -> None:
        if self._thread is not None:
            return
        try:
            build_claim_plan(self.claim_date.date().toPython(), {})
        except ClaimPreviewError as error:
            self.status.setText(str(error))
            return
        self._invalidate_old_history()
        self._generation += 1
        generation = self._generation
        self.read_button.setEnabled(False)
        self.claim_date.setEnabled(False)
        self.status.setText("Reading selected claim month...")

        def worker() -> None:
            try:
                history, error = read_claim_history(), ""
            except ClaimPreviewError as exc:
                history, error = None, str(exc)
            except Exception:
                history, error = None, "Claim screen read failed. No week was inferred."
            self.read_finished.emit(generation, history, error)

        self._thread = threading.Thread(
            target=worker, name="KaosEghis claim preview", daemon=True,
        )
        self._timeout.start(10000)
        self._thread.start()

    def _read_timeout(self) -> None:
        self.clear_history()
        self.status.setText("UIA read timed out. Waiting for the reader to return; no new read started.")
        # COM calls cannot be interrupted safely. Keep one worker, reject late results.
        self.claim_date.setEnabled(True)

    def _finish_read(self, generation: int, history: ClaimHistory | None, error: str) -> None:
        self._timeout.stop()
        self._thread = None
        self.read_button.setEnabled(True)
        self.claim_date.setEnabled(True)
        if generation != self._generation:
            if self.status.text().startswith("UIA read timed out"):
                self.status.setText("Timed-out read discarded. No week was inferred.")
            return
        if history is None:
            self.clear_history()
            self.status.setText(error)
            return
        if history.connection != connected_claim_identity():
            self.clear_history()
            self.status.setText("EMR connection changed. Read the months again.")
            return
        parts = build_claim_plan(self.claim_date.date().toPython(), {})
        if history.month not in {part.month for part in parts}:
            self.status.setText("Selected EMR month is outside this claim period.")
            return
        if not history.weeks and QMessageBox.question(
            self,
            "Empty claim history",
            f"{history.month:%Y/%m}: zero rows were read. Has this month finished "
            "loading and is its claim list empty? Use 1주 in the preview?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            self.histories.pop(history.month, None)
            self._render()
            self.status.setText("Empty history was not confirmed. No week was inferred.")
            return
        if (
            generation != self._generation
            or history.connection != connected_claim_identity()
            or history.captured_at < datetime.now() - timedelta(minutes=5)
        ):
            self.clear_history()
            self.status.setText("Preview expired or EMR connection changed. Read the months again.")
            return
        self.histories[history.month] = history
        self._render()
        self.status.setText("Preview updated. No aggregation was run.")
