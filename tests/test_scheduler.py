from __future__ import annotations

from datetime import datetime
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_scheduler_repository_crud_and_history(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        create_scheduler_run,
        delete_scheduler_job,
        finish_scheduler_run,
        get_scheduler_job,
        list_scheduler_jobs,
        list_scheduler_runs,
        start_scheduler_run,
        update_scheduler_job,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "12:30",
            (0, 1, 2, 3, 4),
        )

        assert job.is_enabled is False
        assert job.weekdays == (0, 1, 2, 3, 4)
        assert list_scheduler_jobs(connection) == [job]

        updated = update_scheduler_job(
            connection,
            job.id,
            "Lunch backup updated",
            macro.id,
            "12:45",
            (0, 2, 4),
            True,
            next_run_at="2026-08-03T12:45:00",
        )
        assert updated is not None
        assert updated.is_enabled is True
        assert updated.schedule_time == "12:45"
        assert updated.weekdays == (0, 2, 4)

        run = create_scheduler_run(
            connection,
            job.id,
            macro.id,
            "manual",
            "2026-08-03T10:00:00",
        )
        start_scheduler_run(connection, run.id, "2026-08-03T10:00:01")
        finished = finish_scheduler_run(
            connection,
            run.id,
            "succeeded",
            "2026-08-03T10:00:02",
            3,
            "Macro completed.",
        )
        assert finished is not None
        assert finished.executed_steps == 3
        assert list_scheduler_runs(connection, job.id)[0].status == "succeeded"

        assert delete_scheduler_job(connection, job.id) is True
        assert get_scheduler_job(connection, job.id) is None
        assert list_scheduler_runs(connection, job.id) == []


def test_scheduler_job_requires_macro_item(tmp_path) -> None:
    import pytest

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_scheduler_job

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        text_item = create_item(connection, "Comment", "clipboard", True)
        with pytest.raises(ValueError, match="macro item"):
            create_scheduler_job(
                connection,
                "Invalid",
                text_item.id,
                "12:00",
                (0,),
            )


def test_calculate_next_run_uses_selected_weekdays() -> None:
    from KaosEghis.core.scheduler import calculate_next_run

    monday_morning = datetime(2026, 8, 3, 9, 0, 0)
    assert calculate_next_run("12:00", (0,), monday_morning) == datetime(
        2026, 8, 3, 12, 0, 0
    )
    monday_afternoon = datetime(2026, 8, 3, 13, 0, 0)
    assert calculate_next_run("12:00", (0,), monday_afternoon) == datetime(
        2026, 8, 10, 12, 0, 0
    )


def test_scheduler_startup_recalculates_future_without_running(tmp_path) -> None:
    from KaosEghis.core.scheduler import prepare_scheduler_startup
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        get_scheduler_job,
        list_scheduler_runs,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "12:00",
            (0,),
            is_enabled=True,
            next_run_at="2026-07-27T12:00:00",
        )

    prepare_scheduler_startup(db_path, datetime(2026, 8, 3, 13, 0, 0))

    with connect(db_path) as connection:
        refreshed = get_scheduler_job(connection, job.id)
        assert refreshed is not None
        assert refreshed.next_run_at == "2026-08-10T12:00:00"
        assert list_scheduler_runs(connection) == []


def test_due_scheduler_job_runs_macro_after_countdown(tmp_path) -> None:
    app = _app()

    from KaosEghis.core.macro_models import MacroRunResult
    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        list_scheduler_runs,
        update_scheduler_job_runtime,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    calls: list[int] = []

    class FakeRunner:
        def execute_macro(self, item_id: int, dry_run: bool = False):
            calls.append(item_id)
            return MacroRunResult(True, "Macro execution completed.", 2, None)

        def cancel(self) -> None:
            pass

    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "12:00",
            (0,),
            is_enabled=True,
        )

    runtime = SchedulerRuntime(
        db_path,
        runner_factory=lambda _path: FakeRunner(),
        now_provider=lambda: datetime(2026, 8, 3, 11, 0, 0),
        countdown_seconds=0,
    )
    runtime.start()
    with connect(db_path) as connection:
        update_scheduler_job_runtime(
            connection,
            job.id,
            next_run_at="2026-08-03T10:59:00",
        )

    runtime.check_due_jobs()
    deadline = time.monotonic() + 2
    while runtime.is_busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()

    assert calls == [macro.id]
    with connect(db_path) as connection:
        runs = list_scheduler_runs(connection, job.id)
    assert runs[0].status == "succeeded"
    assert runs[0].executed_steps == 2
    runtime.stop()


def test_late_scheduler_job_is_recorded_as_missed_without_running(tmp_path) -> None:
    _app()

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        get_scheduler_job,
        list_scheduler_runs,
        update_scheduler_job_runtime,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    calls: list[int] = []

    class FakeRunner:
        def execute_macro(self, item_id: int, dry_run: bool = False):
            calls.append(item_id)

        def cancel(self) -> None:
            pass

    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "10:58",
            (0,),
            is_enabled=True,
        )

    now = datetime(2026, 8, 3, 11, 0, 0)
    runtime = SchedulerRuntime(
        db_path,
        runner_factory=lambda _path: FakeRunner(),
        now_provider=lambda: now,
        countdown_seconds=0,
    )
    runtime.start()
    with connect(db_path) as connection:
        update_scheduler_job_runtime(
            connection,
            job.id,
            next_run_at="2026-08-03T10:58:00",
        )

    runtime.check_due_jobs()

    assert calls == []
    with connect(db_path) as connection:
        runs = list_scheduler_runs(connection, job.id)
        refreshed = get_scheduler_job(connection, job.id)
    assert runs[0].status == "missed"
    assert runs[0].summary == "Missed schedule skipped."
    assert refreshed is not None
    assert refreshed.next_run_at == "2026-08-10T10:58:00"
    runtime.stop()


def test_prompt_policy_never_auto_runs_due_job(tmp_path) -> None:
    _app()

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        list_scheduler_runs,
        update_scheduler_job_runtime,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    calls: list[int] = []

    class FakeRunner:
        def execute_macro(self, item_id: int, dry_run: bool = False):
            calls.append(item_id)

        def cancel(self) -> None:
            pass

    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "11:00",
            (0,),
            is_enabled=True,
            missed_run_policy="prompt",
        )

    runtime = SchedulerRuntime(
        db_path,
        runner_factory=lambda _path: FakeRunner(),
        now_provider=lambda: datetime(2026, 8, 3, 11, 0, 10),
        countdown_seconds=0,
    )
    runtime.start()
    with connect(db_path) as connection:
        update_scheduler_job_runtime(
            connection,
            job.id,
            next_run_at="2026-08-03T11:00:00",
        )

    runtime.check_due_jobs()

    assert calls == []
    with connect(db_path) as connection:
        runs = list_scheduler_runs(connection, job.id)
    assert runs[0].status == "missed"
    assert runs[0].summary == "Operator start required."
    runtime.stop()


def test_scheduler_countdown_can_be_cancelled_without_running_macro(tmp_path) -> None:
    _app()

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_scheduler_job,
        list_scheduler_runs,
    )

    db_path = tmp_path / "scheduler.sqlite"
    initialize_database(db_path)
    calls: list[int] = []

    class FakeRunner:
        def execute_macro(self, item_id: int, dry_run: bool = False):
            calls.append(item_id)

        def cancel(self) -> None:
            pass

    with connect(db_path) as connection:
        macro = create_item(connection, "Backup macro", "macro", True)
        job = create_scheduler_job(
            connection,
            "Lunch backup",
            macro.id,
            "12:00",
            (0,),
            is_enabled=True,
        )

    runtime = SchedulerRuntime(
        db_path,
        runner_factory=lambda _path: FakeRunner(),
        now_provider=lambda: datetime(2026, 8, 3, 11, 0, 0),
        countdown_seconds=10,
    )
    runtime.start()
    assert runtime.run_job_now(job.id) is True
    assert runtime.cancel_active_run() is True

    assert calls == []
    with connect(db_path) as connection:
        runs = list_scheduler_runs(connection, job.id)
    assert runs[0].status == "cancelled"
    runtime.stop()


def test_scheduler_tab_instantiates_without_running_macro(tmp_path) -> None:
    _app()

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.ui.tabs.scheduler_tab import SchedulerTab

    runtime = SchedulerRuntime(tmp_path / "scheduler.sqlite")
    tab = SchedulerTab(tmp_path / "scheduler.sqlite", runtime=runtime)

    assert tab.jobs_table.columnCount() == 7
    assert tab.new_button.text() == "New schedule"
    assert tab.create_shutdown_macro_button.text() == "Create end-of-day macro"
    assert tab.check_shutdown_button.text() == "Check shutdown setup"
    assert tab.dry_run_button.text() == "Dry run"
    assert tab.run_now_button.text() == "Run now"
    assert runtime.is_busy is False


def test_scheduler_creates_disabled_end_of_day_macro_without_schedule(tmp_path) -> None:
    _app()

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_items, list_scheduler_jobs
    from KaosEghis.ui.tabs.scheduler_tab import SchedulerTab

    db_path = tmp_path / "scheduler.sqlite"
    runtime = SchedulerRuntime(db_path)
    tab = SchedulerTab(db_path, runtime=runtime)

    tab.create_end_of_day_macro()

    with connect(db_path) as connection:
        macros = [
            item
            for item in list_items(connection, "macro")
            if item.name == "eGHIS End-of-Day Backup and Power Off"
        ]
        jobs = list_scheduler_jobs(connection)

    assert len(macros) == 1
    assert macros[0].is_enabled is False
    assert macros[0].is_launcher_exposed is False
    assert jobs == []
    assert "No macro was run" in tab.log.toPlainText()


def test_real_macro_execution_blocks_when_another_macro_holds_lock(
    monkeypatch,
) -> None:
    import KaosEghis.core.macro_runner as macro_runner

    class BusyLock:
        def acquire(self, *, blocking: bool) -> bool:
            assert blocking is False
            return False

        def release(self) -> None:
            raise AssertionError("An unacquired lock must not be released.")

    monkeypatch.setattr(macro_runner, "_MACRO_EXECUTION_LOCK", BusyLock())

    result = macro_runner.MacroRunner().execute_macro(999, dry_run=False)

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "Macro execution blocked: another macro is running."
