from __future__ import annotations

from datetime import datetime, time as clock_time, timedelta
from pathlib import Path
import threading
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from KaosEghis.core.macro_models import MacroRunResult
from KaosEghis.core.macro_runner import MacroRunner
from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    SchedulerJobRecord,
    create_scheduler_run,
    finish_scheduler_run,
    get_item,
    get_scheduler_job,
    list_due_scheduler_jobs,
    list_scheduler_jobs,
    start_scheduler_run,
    update_scheduler_job_runtime,
)


WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def calculate_next_run(
    schedule_time: str,
    weekdays: tuple[int, ...],
    now: datetime,
) -> datetime:
    hour, minute = _parse_schedule_time(schedule_time)
    allowed_days = set(weekdays)
    if not allowed_days:
        raise ValueError("At least one weekday is required.")
    for offset in range(8):
        candidate_date = now.date() + timedelta(days=offset)
        if candidate_date.weekday() not in allowed_days:
            continue
        candidate = datetime.combine(candidate_date, clock_time(hour, minute))
        if candidate > now:
            return candidate
    raise ValueError("Could not calculate the next scheduler run.")


def format_weekdays(weekdays: tuple[int, ...]) -> str:
    return ", ".join(WEEKDAY_LABELS[index] for index in weekdays)


def prepare_scheduler_startup(
    db_path: Path | None = None,
    now: datetime | None = None,
) -> None:
    """Recalculate future runs without executing a missed job on app startup."""

    effective_path = db_path or get_database_path()
    current = (now or datetime.now()).replace(microsecond=0)
    initialize_database(effective_path)
    with connect(effective_path) as connection:
        for job in list_scheduler_jobs(connection):
            next_run_at = None
            if job.is_enabled:
                next_run_at = _to_iso(
                    calculate_next_run(job.schedule_time, job.weekdays, current)
                )
            update_scheduler_job_runtime(
                connection,
                job.id,
                next_run_at=next_run_at,
            )


class SchedulerRuntime(QObject):
    notification_requested = Signal(str, str)
    state_changed = Signal()
    _worker_finished = Signal(object)

    POLL_INTERVAL_MS = 5_000
    DEFAULT_COUNTDOWN_SECONDS = 10
    MISSED_TOLERANCE_SECONDS = 60

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        runner_factory: Callable[[Path | None], MacroRunner] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._runner_factory = runner_factory or (lambda path: MacroRunner(path))
        self._now_provider = now_provider or datetime.now
        self._countdown_seconds = max(int(countdown_seconds), 0)
        self._started = False
        self._pending_job: SchedulerJobRecord | None = None
        self._pending_run_id: int | None = None
        self._pending_trigger: str | None = None
        self._countdown_remaining = 0
        self._active_runner: MacroRunner | None = None
        self._active_thread: threading.Thread | None = None
        self._active_job: SchedulerJobRecord | None = None
        self._active_run_id: int | None = None
        self._active_trigger: str | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.check_due_jobs)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1_000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._worker_finished.connect(self._finish_worker_result)

    @property
    def is_busy(self) -> bool:
        return self._pending_job is not None or self._active_runner is not None

    @property
    def active_job_name(self) -> str | None:
        job = self._active_job or self._pending_job
        return job.name if job is not None else None

    def start(self) -> None:
        if self._started:
            return
        prepare_scheduler_startup(self._db_path, self._now())
        self._started = True
        self._poll_timer.start()
        self.state_changed.emit()

    def stop(self) -> None:
        self._poll_timer.stop()
        self._countdown_timer.stop()
        self.cancel_active_run()
        self._started = False

    def check_due_jobs(self) -> None:
        if self.is_busy:
            return
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            due_jobs = list_due_scheduler_jobs(connection, _to_iso(self._now()))
        if not due_jobs:
            return
        job = due_jobs[0]
        scheduled_for = _from_iso(job.next_run_at)
        is_missed = (
            scheduled_for is None
            or (self._now() - scheduled_for).total_seconds()
            > self.MISSED_TOLERANCE_SECONDS
        )
        if is_missed or job.missed_run_policy == "prompt":
            self._record_missed_run(job, prompt=job.missed_run_policy == "prompt")
            return
        self._begin_countdown(job, "scheduled")

    def run_job_now(self, job_id: int) -> bool:
        if self.is_busy:
            self.notification_requested.emit("Scheduler is already running", "warning")
            return False
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            job = get_scheduler_job(connection, job_id)
        if job is None:
            self.notification_requested.emit("Scheduled job not found", "error")
            return False
        if not job.is_enabled:
            self.notification_requested.emit("Scheduled job is disabled", "warning")
            return False
        self._begin_countdown(job, "manual")
        return True

    def cancel_active_run(self) -> bool:
        if self._pending_job is not None:
            self._countdown_timer.stop()
            job = self._pending_job
            run_id = self._pending_run_id
            trigger = self._pending_trigger
            self._clear_pending()
            if run_id is not None:
                self._finish_run_record(
                    job,
                    run_id,
                    trigger or "scheduled",
                    "cancelled",
                    0,
                    "Cancelled by operator.",
                )
            self.notification_requested.emit("Scheduled macro cancelled", "warning")
            self.state_changed.emit()
            return True
        if self._active_runner is not None:
            self._active_runner.cancel()
            self.notification_requested.emit("Cancelling scheduled macro", "warning")
            return True
        return False

    def _begin_countdown(self, job: SchedulerJobRecord, trigger: str) -> None:
        effective_path = self._db_path or get_database_path()
        scheduled_for = job.next_run_at if trigger == "scheduled" else _to_iso(self._now())
        with connect(effective_path) as connection:
            run = create_scheduler_run(
                connection,
                job.id,
                job.macro_item_id,
                trigger,
                scheduled_for or _to_iso(self._now()),
            )
        self._pending_job = job
        self._pending_run_id = run.id
        self._pending_trigger = trigger
        self._countdown_remaining = self._countdown_seconds
        self.state_changed.emit()
        if self._countdown_remaining <= 0:
            self._execute_pending()
            return
        self.notification_requested.emit(
            f"'{job.name}' starts in {self._countdown_remaining}s",
            "warning",
        )
        self._countdown_timer.start()

    def _record_missed_run(self, job: SchedulerJobRecord, *, prompt: bool) -> None:
        effective_path = self._db_path or get_database_path()
        summary = (
            "Operator start required."
            if prompt
            else "Missed schedule skipped."
        )
        with connect(effective_path) as connection:
            run = create_scheduler_run(
                connection,
                job.id,
                job.macro_item_id,
                "scheduled",
                job.next_run_at or _to_iso(self._now()),
                status="missed",
            )
        self._finish_run_record(
            job,
            run.id,
            "scheduled",
            "missed",
            0,
            summary,
        )
        message = (
            f"'{job.name}' is due - run from Scheduler"
            if prompt
            else f"Missed '{job.name}' was skipped"
        )
        self.notification_requested.emit(message, "warning")
        self.state_changed.emit()
        QTimer.singleShot(0, self.check_due_jobs)

    def _countdown_tick(self) -> None:
        if self._pending_job is None:
            self._countdown_timer.stop()
            return
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._countdown_timer.stop()
            self._execute_pending()
            return
        self.notification_requested.emit(
            f"'{self._pending_job.name}' starts in {self._countdown_remaining}s",
            "warning",
        )

    def _execute_pending(self) -> None:
        job = self._pending_job
        run_id = self._pending_run_id
        trigger = self._pending_trigger
        self._clear_pending()
        if job is None or run_id is None or trigger is None:
            return

        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            current_job = get_scheduler_job(connection, job.id)
            macro = get_item(connection, job.macro_item_id)
        if current_job is None or not current_job.is_enabled:
            self._finish_run_record(
                job, run_id, trigger, "blocked", 0, "Scheduled job is disabled."
            )
            return
        if macro is None or macro.item_type != "macro" or not macro.is_enabled:
            self._finish_run_record(
                job, run_id, trigger, "blocked", 0, "Scheduled macro is unavailable."
            )
            return

        started_at = _to_iso(self._now())
        with connect(effective_path) as connection:
            start_scheduler_run(connection, run_id, started_at)
        self._active_job = current_job
        self._active_run_id = run_id
        self._active_trigger = trigger
        self._active_runner = self._runner_factory(self._db_path)
        runner = self._active_runner
        self.notification_requested.emit(f"Running '{job.name}'...", "info")
        self.state_changed.emit()

        def worker() -> None:
            try:
                result = runner.execute_macro(job.macro_item_id, dry_run=False)
            except Exception:
                result = MacroRunResult(False, "unknown error", 0, None)
            self._worker_finished.emit(result)

        self._active_thread = threading.Thread(target=worker, daemon=True)
        self._active_thread.start()

    def _finish_worker_result(self, result: MacroRunResult) -> None:
        job = self._active_job
        run_id = self._active_run_id
        trigger = self._active_trigger
        self._active_runner = None
        self._active_thread = None
        self._active_job = None
        self._active_run_id = None
        self._active_trigger = None
        if job is None or run_id is None or trigger is None:
            return

        status = _scheduler_status_from_result(result)
        summary = _safe_scheduler_summary(result, status)
        self._finish_run_record(
            job,
            run_id,
            trigger,
            status,
            result.executed_steps,
            summary,
        )
        tone = "success" if status == "succeeded" else "error"
        if status == "cancelled":
            tone = "warning"
        message = (
            f"'{job.name}' completed"
            if status == "succeeded"
            else f"'{job.name}' {status}"
        )
        self.notification_requested.emit(message, tone)
        self.state_changed.emit()
        QTimer.singleShot(0, self.check_due_jobs)

    def _finish_run_record(
        self,
        job: SchedulerJobRecord,
        run_id: int,
        trigger: str,
        status: str,
        executed_steps: int,
        summary: str,
    ) -> None:
        finished_at = self._now()
        effective_path = self._db_path or get_database_path()
        with connect(effective_path) as connection:
            finish_scheduler_run(
                connection,
                run_id,
                status,
                _to_iso(finished_at),
                executed_steps,
                summary,
            )
            current_job = get_scheduler_job(connection, job.id)
            next_run_at = current_job.next_run_at if current_job is not None else None
            if trigger == "scheduled" and current_job is not None and current_job.is_enabled:
                next_run_at = _to_iso(
                    calculate_next_run(
                        current_job.schedule_time,
                        current_job.weekdays,
                        finished_at + timedelta(seconds=1),
                    )
                )
            update_scheduler_job_runtime(
                connection,
                job.id,
                next_run_at=next_run_at,
                last_run_at=_to_iso(finished_at),
                last_status=status,
            )

    def _clear_pending(self) -> None:
        self._pending_job = None
        self._pending_run_id = None
        self._pending_trigger = None
        self._countdown_remaining = 0

    def _now(self) -> datetime:
        return self._now_provider().replace(microsecond=0)


def _parse_schedule_time(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Schedule time must use HH:MM.")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Schedule time must use HH:MM.")
    return hour, minute


def _to_iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _scheduler_status_from_result(result: MacroRunResult) -> str:
    if result.success:
        return "succeeded"
    message = (result.message or "").casefold()
    if "cancel" in message:
        return "cancelled"
    if any(
        marker in message
        for marker in (
            "blocked",
            "disabled",
            "not ready",
            "reconnect",
            "target not",
            "window",
            "another macro",
        )
    ):
        return "blocked"
    return "failed"


def _safe_scheduler_summary(result: MacroRunResult, status: str) -> str:
    categories = {
        "succeeded": "Macro completed.",
        "cancelled": "Cancelled by operator.",
        "blocked": "Macro safety check blocked execution.",
        "failed": "Macro execution failed.",
    }
    return categories.get(status, "Unknown scheduler result.")
