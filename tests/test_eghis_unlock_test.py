from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from KaosEghis.core import macro_runner
from KaosEghis.core.eghis_shutdown import create_eghis_end_of_day_macro
from KaosEghis.core.macro_models import MacroRunResult, MacroStep
from KaosEghis.core.windows_desktop import DESKTOP_UNAVAILABLE_MESSAGE
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import create_scheduler_job, get_item, list_scheduler_jobs


@pytest.fixture(autouse=True)
def desktop_available(monkeypatch):
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", lambda: None)


def test_unlock_test_is_one_fixed_action_and_does_not_enable_shutdown(tmp_path, monkeypatch):
    path = tmp_path / "unlock.sqlite"
    initialize_database(path)
    with connect(path) as connection:
        macro, _ = create_eghis_end_of_day_macro(connection)
        job = create_scheduler_job(connection, "Shutdown", macro.id, "20:30", (0,))
    runner = macro_runner.MacroRunner(path)
    calls = []

    def unlock(step, settings):
        calls.append(step)
        assert runner._current_profile_id == macro.emr_target_profile_id
        return MacroRunResult(True, "unlocked", 1)

    monkeypatch.setattr(runner, "_run_unlock_eghis", unlock)
    monkeypatch.setattr(macro_runner, "validate_cached_connection_identity", lambda _s: SimpleNamespace(status="yellow"))
    monkeypatch.setattr(macro_runner, "get_cached_eghis_state", lambda: None)
    monkeypatch.setattr(macro_runner, "list_macro_steps", Mock(side_effect=AssertionError("Must not load saved steps")))
    result = runner.execute_unlock_test()
    assert result.success
    assert result.executed_steps == 1
    assert len(calls) == 1
    assert calls[0].action == "unlock_eghis"
    assert calls[0].target_id == "shutdown.lock_password"
    assert calls[0].value == "eGhis EMR"
    assert calls[0].retries == 0
    with connect(path) as connection:
        assert get_item(connection, macro.id).is_enabled is False
        assert list_scheduler_jobs(connection) == [job]


def test_unlock_test_respects_process_wide_macro_lock(monkeypatch):
    lock = Mock()
    lock.acquire.return_value = False
    monkeypatch.setattr(macro_runner, "_MACRO_EXECUTION_LOCK", lock)
    result = macro_runner.MacroRunner().execute_unlock_test()
    assert not result.success
    assert "another macro" in result.message
    lock.release.assert_not_called()


def test_unlock_test_releases_macro_lock_on_error(tmp_path, monkeypatch):
    path = tmp_path / "unlock.sqlite"
    initialize_database(path)
    runner = macro_runner.MacroRunner(path)
    lock = Mock()
    lock.acquire.return_value = True
    monkeypatch.setattr(macro_runner, "_MACRO_EXECUTION_LOCK", lock)
    monkeypatch.setattr(runner, "run", Mock(side_effect=RuntimeError("test error")))
    with pytest.raises(RuntimeError):
        runner.execute_unlock_test()
    lock.release.assert_called_once()


def test_unlock_test_requires_cached_connection(tmp_path, monkeypatch):
    path = tmp_path / "unlock.sqlite"
    initialize_database(path)
    monkeypatch.setattr(macro_runner, "validate_cached_connection_identity", lambda _s: SimpleNamespace(status="red", message="EMR not connected"))
    runner = macro_runner.MacroRunner(path)
    input_action = Mock(side_effect=AssertionError("No input without a connection"))
    monkeypatch.setattr(runner, "_execute_step", input_action)
    result = runner.execute_unlock_test()
    assert not result.success
    assert "not connected" in result.message
    input_action.assert_not_called()


def test_locked_desktop_blocks_before_connection_checks_or_secrets(monkeypatch):
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", lambda: DESKTOP_UNAVAILABLE_MESSAGE)
    connection_check = Mock(side_effect=AssertionError("Must not inspect EMR"))
    monkeypatch.setattr(macro_runner, "validate_cached_connection_identity", connection_check)
    password = Mock(side_effect=AssertionError("Must not request password"))
    runner = macro_runner.MacroRunner(password_provider=password)
    result = runner.run([MacroStep("unlock_eghis")], dry_run=False, settings={})
    assert not result.success
    assert result.executed_steps == 0
    assert result.failed_step is None
    assert result.message == DESKTOP_UNAVAILABLE_MESSAGE
    password.assert_not_called()
    connection_check.assert_not_called()


def test_windows_locks_during_emr_focus_blocks_direct_password_fallback(monkeypatch):
    checks = iter([None, DESKTOP_UNAVAILABLE_MESSAGE])
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", lambda: next(checks))
    password = Mock(side_effect=AssertionError("Must not request password"))
    runner = macro_runner.MacroRunner(password_provider=password)
    monkeypatch.setattr(runner, "_resolve_process_target", lambda _key: (object(), "found"))
    monkeypatch.setattr(runner, "_top_level_window_handle", lambda _target: 441)
    monkeypatch.setattr(macro_runner, "focus_cached_eghis_process_window", lambda *_a: (False, "focus failed"))
    direct = Mock(side_effect=AssertionError("Must not use direct input"))
    monkeypatch.setattr(runner, "_set_secret_on_exact_lock_target_and_submit", direct)
    result = runner._run_unlock_eghis(MacroStep("unlock_eghis", "shutdown.lock_password", "eGhis EMR"), {})
    assert result.message == DESKTOP_UNAVAILABLE_MESSAGE
    password.assert_not_called()
    direct.assert_not_called()


def test_locked_desktop_blocks_next_step_and_preserves_reason(monkeypatch):
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", lambda: DESKTOP_UNAVAILABLE_MESSAGE)
    runner = macro_runner.MacroRunner()
    runner._requires_interactive_desktop = True
    send = Mock(side_effect=AssertionError("Must not send Alt+F4"))
    monkeypatch.setattr(runner, "_run_hotkey", send)
    result = runner._execute_step(MacroStep("hotkey", value="{ALT}{F4}"))
    assert result.message == DESKTOP_UNAVAILABLE_MESSAGE
    assert runner._sanitize_failure_message("hotkey", result.message) == DESKTOP_UNAVAILABLE_MESSAGE
    send.assert_not_called()


def test_dry_run_does_not_probe_desktop(monkeypatch):
    probe = Mock(side_effect=AssertionError("Dry run must not inspect desktop"))
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", probe)
    assert macro_runner.MacroRunner().run([MacroStep("unlock_eghis")], dry_run=True).success
    probe.assert_not_called()


def test_ordinary_macro_does_not_use_shutdown_desktop_probe(monkeypatch):
    probe = Mock(side_effect=AssertionError("Ordinary macro behavior must not change"))
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", probe)
    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _s: SimpleNamespace(status="green"))
    monkeypatch.setattr(macro_runner, "get_cached_eghis_state", lambda: None)
    result = macro_runner.MacroRunner().run([MacroStep("delay_ms", value="0")], dry_run=False, settings={})
    assert result.success
    probe.assert_not_called()
