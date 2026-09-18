import pytest
from PySide6.QtWidgets import QApplication

from KaosEghis.core.vaccine_session_keeper import (
    SESSION_KEEPER_INTERVAL_MS,
    SESSION_KEEPER_RETRY_MS,
    VaccineSessionResetResult,
)
from KaosEghis.db.repositories import DEFAULT_SETTINGS
from KaosEghis.ui.tabs import vaccine_tab


@pytest.fixture
def keeper(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    now = [1000.0]
    monkeypatch.setattr(vaccine_tab, "monotonic", lambda: now[0])
    page = vaccine_tab.VaccineTab(tmp_path / "test.sqlite")
    page._configure_session_keeper(DEFAULT_SETTINGS | {"vaccine_session_keeper_enabled": "true"})
    yield page, now
    for timer in page._session_keeper_timers.values():
        timer.stop()
    page._session_keeper_progress_timer.stop()
    page.close()


def install_outcomes(monkeypatch, outcomes):
    calls = []

    def reset(target, *, require_idle=False):
        calls.append((target.key, require_idle))
        status = outcomes[target.key]
        return VaccineSessionResetResult(target.key, status, status, status == "reset_sent")

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", reset)
    return calls


@pytest.mark.parametrize("status", ["input_busy", "point_not_ready", "input_failed", "desktop_unavailable"])
def test_transient_failure_retries_only_failed_system(keeper, monkeypatch, status):
    page, now = keeper
    calls = install_outcomes(monkeypatch, {"general": status})
    peer_remaining = page._session_keeper_timers["covid"].remainingTime()
    page._run_session_keeper("general")
    assert calls == [("general", True)]
    assert page._session_keeper_timers["general"].interval() == SESSION_KEEPER_RETRY_MS
    assert page._session_keeper_retry_deadlines == {"general": now[0] + 600}
    assert page._session_keeper_timers["covid"].remainingTime() <= peer_remaining
    assert page._session_keeper_timers["covid"].interval() == SESSION_KEEPER_INTERVAL_MS
    assert "Next retry in" in page.settings_page.system_targets_editor.session_keeper_progress_bar.format()


def test_retry_succeeds_then_rearms_ninety_minutes(keeper, monkeypatch):
    page, now = keeper
    outcomes = {"general": "input_busy"}
    calls = install_outcomes(monkeypatch, outcomes)
    page._run_session_keeper("general")
    first_deadline = page._session_keeper_retry_deadlines["general"]
    now[0] += 30
    page._run_session_keeper("general")
    assert page._session_keeper_retry_deadlines["general"] == first_deadline
    outcomes["general"] = "reset_sent"
    now[0] += 30
    page._run_session_keeper("general")
    assert len(calls) == 3
    assert "general" not in page._session_keeper_retry_deadlines
    assert page._session_keeper_timers["general"].interval() == SESSION_KEEPER_INTERVAL_MS


def test_retry_deadline_stops_before_more_input_and_peer_cannot_hide_warning(keeper, monkeypatch):
    page, now = keeper
    calls = install_outcomes(monkeypatch, {"general": "input_busy", "covid": "reset_sent"})
    page._run_session_keeper("general")
    now[0] += 601
    page._run_session_keeper("general")
    assert calls == [("general", True)]
    assert not page._session_keeper_timers["general"].isActive()
    assert "Reset required" in page.status_label.text()
    page._run_session_keeper("covid")
    assert "Reset required" in page.settings_page.system_targets_editor.session_keeper_status_label.text()
    assert page._session_keeper_timers["covid"].isActive()


@pytest.mark.parametrize("status", ["ambiguous", "configuration_required", "unavailable"])
def test_unsafe_configuration_stops_without_repeated_input(keeper, monkeypatch, status):
    page, _now = keeper
    install_outcomes(monkeypatch, {"general": status})
    page._run_session_keeper("general")
    assert not page._session_keeper_timers["general"].isActive()
    assert "Reset required" in page.status_label.text()


def test_closed_system_keeps_normal_interval_without_retry(keeper, monkeypatch):
    page, _now = keeper
    install_outcomes(monkeypatch, {"general": "not_open"})
    page._run_session_keeper("general")
    assert not page._session_keeper_retry_deadlines
    assert page._session_keeper_timers["general"].interval() == SESSION_KEEPER_INTERVAL_MS


def test_manual_partial_success_does_not_restart_failed_peer_timer(keeper, monkeypatch):
    page, _now = keeper
    calls = install_outcomes(monkeypatch, {"general": "reset_sent", "covid": "point_not_ready"})
    page.reset_vaccine_sessions_now()
    assert calls == [("general", False), ("covid", False)]
    assert page._session_keeper_timers["general"].interval() == SESSION_KEEPER_INTERVAL_MS
    assert page._session_keeper_timers["covid"].interval() == SESSION_KEEPER_RETRY_MS
    assert "covid" in page._session_keeper_retry_deadlines


def test_disabling_keeper_clears_pending_retries(keeper, monkeypatch):
    page, _now = keeper
    calls = install_outcomes(monkeypatch, {"general": "input_busy"})
    page._run_session_keeper("general")
    page._configure_session_keeper(DEFAULT_SETTINGS | {"vaccine_session_keeper_enabled": "false"})
    assert not page._session_keeper_retry_deadlines
    assert all(not timer.isActive() for timer in page._session_keeper_timers.values())
    page._run_session_keeper("general")
    assert calls == [("general", True)]
