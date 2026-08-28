from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.macro_runner import MacroRunner
from KaosEghis.core.eghis_shutdown import create_eghis_end_of_day_macro
from KaosEghis.core.scheduler import (
    SchedulerRuntime,
    calculate_next_run,
    format_weekdays,
)
from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    SchedulerJobRecord,
    create_scheduler_job,
    delete_scheduler_job,
    get_item,
    get_scheduler_job,
    list_items,
    list_scheduler_jobs,
    list_scheduler_runs,
    update_scheduler_job,
)


class SchedulerTab(QWidget):
    def __init__(
        self,
        db_path: Path | None = None,
        runtime: SchedulerRuntime | None = None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self.runtime = runtime or SchedulerRuntime(db_path, parent=self)

        title = QLabel("Scheduler")
        title.setObjectName("pageTitle")
        explanation = QLabel(
            "Schedules run saved macros while KaosEghis is open. Enabled jobs use a "
            "10-second countdown and the existing EMR/macro safety checks."
        )
        explanation.setWordWrap(True)

        self.status_label = QLabel("Scheduler not started.")
        self.jobs_table = QTableWidget(0, 7)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Enabled", "Name", "Macro", "Time", "Days", "Next run", "Last result"]
        )
        self.jobs_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.jobs_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.jobs_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

        self.new_button = QPushButton("New schedule")
        self.new_button.clicked.connect(self.add_job)
        self.create_shutdown_macro_button = QPushButton("Create end-of-day macro")
        self.create_shutdown_macro_button.clicked.connect(
            self.create_end_of_day_macro
        )
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_job)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_job)
        self.toggle_button = QPushButton("Enable / Disable")
        self.toggle_button.clicked.connect(self.toggle_job)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_job)
        self.run_now_button = QPushButton("Run now")
        self.run_now_button.clicked.connect(self.run_job_now)
        self.cancel_button = QPushButton("Cancel active")
        self.cancel_button.clicked.connect(self.cancel_active)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)

        controls = QHBoxLayout()
        for button in (
            self.new_button,
            self.create_shutdown_macro_button,
            self.edit_button,
            self.delete_button,
            self.toggle_button,
            self.dry_run_button,
            self.run_now_button,
            self.cancel_button,
            self.refresh_button,
        ):
            controls.addWidget(button)
        controls.addStretch()

        history_title = QLabel("Run history")
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(
            ["Time", "Job", "Trigger", "Status", "Steps", "Summary"]
        )
        self.history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        self.log.setPlaceholderText("Dry-run and scheduler results appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(self.status_label)
        layout.addWidget(self.jobs_table, 2)
        layout.addLayout(controls)
        layout.addWidget(history_title)
        layout.addWidget(self.history_table, 1)
        layout.addWidget(self.log)

        self.runtime.state_changed.connect(self.refresh_view)
        self.refresh_view()

    def activate_page(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        effective_path = self._db_path or get_database_path()
        initialize_database(effective_path)
        with connect(effective_path) as connection:
            jobs = list_scheduler_jobs(connection)
            runs = list_scheduler_runs(connection, limit=100)
            macros = {item.id: item for item in list_items(connection, "macro")}

        selected_id = self._selected_job_id()
        self.jobs_table.setRowCount(len(jobs))
        for row_index, job in enumerate(jobs):
            macro = macros.get(job.macro_item_id)
            values = (
                "Yes" if job.is_enabled else "No",
                job.name,
                macro.name if macro is not None else "(missing macro)",
                job.schedule_time,
                format_weekdays(job.weekdays),
                _display_timestamp(job.next_run_at),
                job.last_status or "",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, job.id)
                self.jobs_table.setItem(row_index, column, item)
            if selected_id == job.id:
                self.jobs_table.selectRow(row_index)

        job_names = {job.id: job.name for job in jobs}
        self.history_table.setRowCount(len(runs))
        for row_index, run in enumerate(runs):
            values = (
                _display_timestamp(run.finished_at or run.scheduled_for),
                job_names.get(run.job_id, f"Job {run.job_id}"),
                run.trigger,
                run.status,
                str(run.executed_steps),
                run.summary,
            )
            for column, value in enumerate(values):
                self.history_table.setItem(
                    row_index, column, QTableWidgetItem(value)
                )

        enabled_count = sum(job.is_enabled for job in jobs)
        if self.runtime.is_busy:
            self.status_label.setText(
                f"Active: {self.runtime.active_job_name or 'scheduled macro'}"
            )
        else:
            self.status_label.setText(
                f"Scheduler ready. Enabled jobs: {enabled_count}."
            )

    def add_job(self) -> None:
        dialog = SchedulerJobDialog(self._db_path, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.job_data()
        next_run_at = _next_run_text(data) if data["is_enabled"] else None
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            create_scheduler_job(connection, next_run_at=next_run_at, **data)
        self.refresh_view()
        self.log.setPlainText("Schedule created. No macro was run.")

    def create_end_of_day_macro(self) -> None:
        effective_path = self._db_path or get_database_path()
        initialize_database(effective_path)
        try:
            with connect(effective_path) as connection:
                macro, created = create_eghis_end_of_day_macro(connection)
        except (RuntimeError, ValueError):
            self.log.setPlainText("End-of-day macro could not be created.")
            return
        self.refresh_view()
        if created:
            self.log.setPlainText(
                f"Created or corrected disabled macro '{macro.name}'. Review and enable it before "
                "creating a schedule. No macro was run."
            )
            return
        self.log.setPlainText(
            f"Macro '{macro.name}' already exists. No macro was changed or run."
        )

    def edit_job(self) -> None:
        job = self._selected_job()
        if job is None:
            self.log.setPlainText("Select a schedule to edit.")
            return
        dialog = SchedulerJobDialog(self._db_path, job=job, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.job_data()
        next_run_at = _next_run_text(data) if data["is_enabled"] else None
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            update_scheduler_job(
                connection,
                job.id,
                next_run_at=next_run_at,
                **data,
            )
        self.refresh_view()
        self.log.setPlainText("Schedule updated. No macro was run.")

    def delete_job(self) -> None:
        job = self._selected_job()
        if job is None:
            self.log.setPlainText("Select a schedule to delete.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete schedule",
                f"Delete schedule '{job.name}' and its local run history?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            delete_scheduler_job(connection, job.id)
        self.refresh_view()
        self.log.setPlainText("Schedule deleted. The macro was not deleted.")

    def toggle_job(self) -> None:
        job = self._selected_job()
        if job is None:
            self.log.setPlainText("Select a schedule to enable or disable.")
            return
        is_enabled = not job.is_enabled
        data = {
            "name": job.name,
            "macro_item_id": job.macro_item_id,
            "schedule_time": job.schedule_time,
            "weekdays": job.weekdays,
            "is_enabled": is_enabled,
            "missed_run_policy": job.missed_run_policy,
        }
        next_run_at = _next_run_text(data) if is_enabled else None
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            update_scheduler_job(
                connection,
                job.id,
                next_run_at=next_run_at,
                **data,
            )
        self.refresh_view()
        self.log.setPlainText(
            "Schedule enabled." if is_enabled else "Schedule disabled."
        )

    def dry_run_job(self) -> None:
        job = self._selected_job()
        if job is None:
            self.log.setPlainText("Select a schedule to dry run.")
            return
        result = MacroRunner(self._db_path).execute_macro(
            job.macro_item_id,
            dry_run=True,
        )
        self.log.setPlainText(
            f"Schedule: {job.name}\nTime: {job.schedule_time} "
            f"({format_weekdays(job.weekdays)})\n\n{result.message}"
        )

    def run_job_now(self) -> None:
        job = self._selected_job()
        if job is None:
            self.log.setPlainText("Select a schedule to run.")
            return
        if (
            QMessageBox.question(
                self,
                "Run scheduled macro now",
                f"Start the countdown for '{job.name}' now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.runtime.run_job_now(job.id):
            self.log.setPlainText("Countdown started. Use Cancel active to stop it.")

    def cancel_active(self) -> None:
        if not self.runtime.cancel_active_run():
            self.log.setPlainText("No scheduled macro is active.")

    def _selected_job_id(self) -> int | None:
        selected = self.jobs_table.selectedItems()
        if not selected:
            return None
        item = self.jobs_table.item(selected[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None

    def _selected_job(self) -> SchedulerJobRecord | None:
        job_id = self._selected_job_id()
        if job_id is None:
            return None
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            return get_scheduler_job(connection, job_id)


class SchedulerJobDialog(QDialog):
    def __init__(
        self,
        db_path: Path | None = None,
        job: SchedulerJobRecord | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit schedule" if job is not None else "New schedule")
        self._db_path = db_path
        self.name_input = QLineEdit(job.name if job is not None else "")
        self.macro_combo = QComboBox()
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(job.is_enabled if job is not None else False)
        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH:mm")
        self.time_input.setTime(
            QTime.fromString(job.schedule_time, "HH:mm")
            if job is not None
            else QTime.currentTime().addSecs(3600)
        )
        self.weekday_checks = [QCheckBox(label) for label in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
        selected_days = set(job.weekdays if job is not None else range(5))
        for index, checkbox in enumerate(self.weekday_checks):
            checkbox.setChecked(index in selected_days)

        self.missed_policy = QComboBox()
        self.missed_policy.addItem("Skip missed run", "skip")
        self.missed_policy.addItem("Prompt operator", "prompt")
        if job is not None:
            index = self.missed_policy.findData(job.missed_run_policy)
            if index >= 0:
                self.missed_policy.setCurrentIndex(index)

        effective_path = self._db_path or get_database_path()
        initialize_database(effective_path)
        with connect(effective_path) as connection:
            macros = list_items(connection, "macro")
        for macro in macros:
            suffix = "" if macro.is_enabled else " [disabled]"
            self.macro_combo.addItem(f"{macro.name}{suffix}", macro.id)
        if job is not None:
            index = self.macro_combo.findData(job.macro_item_id)
            if index >= 0:
                self.macro_combo.setCurrentIndex(index)

        weekdays_widget = QWidget()
        weekdays_layout = QHBoxLayout(weekdays_widget)
        weekdays_layout.setContentsMargins(0, 0, 0, 0)
        for checkbox in self.weekday_checks:
            weekdays_layout.addWidget(checkbox)
        weekdays_layout.addStretch()

        warning = QLabel(
            "Enabling this schedule authorizes automatic macro execution while "
            "KaosEghis is open. A 10-second countdown is shown first."
        )
        warning.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self.name_input)
        form.addRow("Macro", self.macro_combo)
        form.addRow("Time", self.time_input)
        form.addRow("Days", weekdays_widget)
        form.addRow("Missed run", self.missed_policy)
        form.addRow("", self.enabled_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(warning)
        layout.addWidget(buttons)

    def job_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "macro_item_id": int(self.macro_combo.currentData()),
            "schedule_time": self.time_input.time().toString("HH:mm"),
            "weekdays": tuple(
                index
                for index, checkbox in enumerate(self.weekday_checks)
                if checkbox.isChecked()
            ),
            "is_enabled": self.enabled_checkbox.isChecked(),
            "missed_run_policy": str(self.missed_policy.currentData()),
        }

    def _validate_and_accept(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Invalid schedule", "Name is required.")
            return
        if self.macro_combo.currentData() is None:
            QMessageBox.warning(self, "Invalid schedule", "Create a macro first.")
            return
        if not any(checkbox.isChecked() for checkbox in self.weekday_checks):
            QMessageBox.warning(
                self, "Invalid schedule", "Select at least one weekday."
            )
            return
        self.accept()


def _next_run_text(data: dict) -> str:
    next_run = calculate_next_run(
        str(data["schedule_time"]),
        tuple(data["weekdays"]),
        datetime.now().replace(microsecond=0),
    )
    return next_run.isoformat(timespec="seconds")


def _display_timestamp(value: str | None) -> str:
    return (value or "").replace("T", " ")
