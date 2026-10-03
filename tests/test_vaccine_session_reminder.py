import pytest
import threading
import sys
from time import monotonic, sleep
from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from KaosEghis.core.vaccine_session_keeper import VaccineSessionResetResult
from KaosEghis.ui.tabs import vaccine_tab


def wait_for_reset(page):
    deadline = monotonic() + 5
    while page._session_reset_in_progress and monotonic() < deadline:
        QApplication.processEvents()
        sleep(0.005)
    assert not page._session_reset_in_progress


@pytest.fixture
def idle_reminder(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    now = [1000.0]
    monkeypatch.setattr(vaccine_tab, "monotonic", lambda: now[0])
    original = vaccine_tab.QMessageBox

    class HiddenMessageBox(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)

    monkeypatch.setattr(vaccine_tab, "QMessageBox", HiddenMessageBox)
    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", lambda *_a, **_kw: pytest.fail("Unexpected reset"))
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", lambda *_a, **_kw: pytest.fail("Unexpected F5"))
    page = vaccine_tab.VaccineTab(tmp_path / "test.sqlite")
    yield page, now
    page._session_reset_cancel.set()
    if page._session_reset_thread is not None:
        page._session_reset_thread.join(5)
        wait_for_reset(page)
    if page._session_reset_alert is not None:
        page._session_reset_alert.close()
    page._session_reminder_timer.stop()
    page.close()
    page.deleteLater()
    app.processEvents()


@pytest.fixture
def reminder(idle_reminder):
    page, _now = idle_reminder
    page._start_session_reset_reminder()
    return idle_reminder


def test_startup_and_settings_reload_leave_reminder_idle(idle_reminder):
    page, now = idle_reminder
    assert page._session_reminder_started_at is None
    assert not page._session_reminder_timer.isActive()
    now[0] += 4 * 3600
    page._session_reminder_timer.timeout.emit()
    page.load_vaccine_settings()
    page.activate_page()
    assert page._session_reminder_started_at is None
    assert not page._session_reminder_timer.isActive()
    assert page._session_reset_alert is None
    assert "#a3b1c2" in page.session_reset_now_button.styleSheet()
    assert "not started" in page.session_reset_now_button.toolTip()
    assert page.settings_page.system_targets_editor.session_keeper_progress_bar.format() == "Reminder not started"


@pytest.mark.parametrize("system", ["general", "influenza", "covid"])
@pytest.mark.parametrize("outcome", ["opened", "already_open", "failed", "cancelled"])
def test_launch_result_starts_reminder_only_for_detected_system(idle_reminder, monkeypatch, system, outcome):
    page, now = idle_reminder
    calls = []
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        COINIT_MULTITHREADED=0, CoInitializeEx=lambda _mode: None, CoUninitialize=lambda: None,
    ))
    monkeypatch.setattr(vaccine_tab, "start_kdca_certificate_login", lambda *_a, **_kw:
        vaccine_tab.KdcaCertificateLoginResult(True, "signed_in", "Signed in", browser_handle=123))

    def launch(_settings, key, **_kwargs):
        calls.append(key)
        assert page._session_reminder_started_at is None
        if outcome == "cancelled":
            page._kdca_cancel.set()
        return vaccine_tab.VaccineSystemLaunchResult(outcome != "failed", outcome)

    monkeypatch.setattr(vaccine_tab, "open_vaccine_system", launch)
    now[0] += 2 * 3600
    assert page.open_vaccine_system(system)
    worker = page._kdca_thread
    worker.join(3)
    assert not worker.is_alive()
    QApplication.processEvents()
    assert page._kdca_thread is None
    assert calls == [system]
    if outcome in {"opened", "already_open"}:
        assert page._session_reminder_started_at == now[0]
        assert page._session_reminder_timer.isActive()
    else:
        assert page._session_reminder_started_at is None
        assert not page._session_reminder_timer.isActive()
    assert page._session_reset_alert is None


@pytest.mark.parametrize("success", [False, True])
def test_portal_login_alone_does_not_start_reminder(idle_reminder, success):
    page, now = idle_reminder
    now[0] += 3600
    page._finish_kdca_operation(vaccine_tab.KdcaCertificateLoginResult(success, "test", "Login result"))
    assert page._session_reminder_started_at is None
    assert not page._session_reminder_timer.isActive()


def test_later_launch_does_not_postpone_existing_reminder(reminder):
    page, now = reminder
    started = page._session_reminder_started_at
    now[0] += 90 * 60
    page._finish_kdca_operation(vaccine_tab.VaccineSystemLaunchResult(True, "Another system opened"))
    page._update_session_reset_reminder()
    assert page._session_reminder_started_at == started
    assert "#ef6b73" in page.session_reset_now_button.styleSheet()


def test_successful_reset_can_start_an_idle_reminder(idle_reminder, monkeypatch):
    page, now = idle_reminder
    install_outcomes(monkeypatch)
    now[0] += 3600
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert page._session_reminder_started_at == now[0]
    assert page._session_reminder_timer.isActive()


def test_reset_with_no_open_system_leaves_reminder_idle(idle_reminder, monkeypatch):
    page, _now = idle_reminder
    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", lambda target, **_kw:
        VaccineSessionResetResult(target.key, "not_open", "Not open"))
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", lambda *_a, **_kw:
        VaccineSessionResetResult("influenza", "not_open", "Not open"))
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert page._session_reminder_started_at is None
    assert not page._session_reminder_timer.isActive()


def install_outcomes(monkeypatch, *, covid="reset_sent", flu="not_open"):
    calls = []

    def reset(target, **_kwargs):
        calls.append(target.key)
        status = covid if target.key == "covid" else "reset_sent"
        return VaccineSessionResetResult(target.key, status, status, status == "reset_sent")

    def refresh(_settings, **_kwargs):
        calls.append("influenza")
        return VaccineSessionResetResult("influenza", flu, flu)

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", reset)
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", refresh)
    return calls


@pytest.mark.parametrize("minutes,color", [(0, "#a3b1c2"), (60, "#a3b1c2"), (75, "#c98e9a"), (90, "#ef6b73"), (114, "#ef6b73")])
def test_reminder_changes_only_text_color(reminder, minutes, color):
    page, now = reminder
    now[0] += minutes * 60
    page._session_reminder_timer.timeout.emit()
    for button in (page.session_reset_now_button, page.settings_page.system_targets_editor.session_reset_now_button):
        assert f"color: {color}" in button.styleSheet()
        assert "background-color: transparent" in button.styleSheet()
    assert page._session_reset_alert is None


def test_hidden_page_alert_at_115_minutes_is_nonmodal_and_close_never_resets(reminder):
    page, now = reminder
    assert not page.isVisible()
    now[0] += 115 * 60
    page._session_reminder_timer.timeout.emit()
    popup = page._session_reset_alert
    assert popup is not None and popup.isVisible()
    assert popup.windowModality() == Qt.WindowModality.NonModal
    assert popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert {button.text() for button in popup.buttons()} == {"Reset Now", "Close"}
    assert popup.defaultButton().text() == "Close"
    next(button for button in popup.buttons() if button.text() == "Close").click()
    assert page._session_reset_alert is None
    now[0] += 3600
    page._session_reminder_timer.timeout.emit()
    assert page._session_reset_alert is None
    assert "#ef6b73" in page.session_reset_now_button.styleSheet()


def test_popup_reset_is_manual_and_restarts_reminder_only_after_success(reminder, monkeypatch):
    page, now = reminder
    calls = install_outcomes(monkeypatch, flu="refresh_sent")
    now[0] += 115 * 60
    page._session_reminder_timer.timeout.emit()
    assert calls == []
    page._session_reset_alert_button.click()
    wait_for_reset(page)
    assert calls == ["general", "covid", "influenza"]
    assert page._session_reminder_started_at == now[0]
    assert page._session_reset_alert is None
    assert not page._session_reset_alert_shown
    assert "#a3b1c2" in page.session_reset_now_button.styleSheet()
    now[0] += 115 * 60
    page._session_reminder_timer.timeout.emit()
    assert page._session_reset_alert is not None
    assert calls == ["general", "covid", "influenza"]


@pytest.mark.parametrize("covid,flu", [("input_busy", "not_open"), ("point_not_ready", "refresh_sent"), ("reset_sent", "declined"), ("reset_sent", "ambiguous")])
def test_partial_or_declined_reset_stays_red_without_retry(reminder, monkeypatch, covid, flu):
    page, now = reminder
    calls = install_outcomes(monkeypatch, covid=covid, flu=flu)
    started = page._session_reminder_started_at
    now[0] += 90 * 60
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert page._session_reminder_started_at == started
    for _ in range(10):
        now[0] += 30
        page._session_reminder_timer.timeout.emit()
    assert calls == ["general", "covid", "influenza"]
    assert "#ef6b73" in page.session_reset_now_button.styleSheet()
    assert not hasattr(page, "_session_keeper_timers")


def test_settings_reload_does_not_postpone_reminder(reminder):
    page, now = reminder
    started = page._session_reminder_started_at
    now[0] += 91 * 60
    page.load_vaccine_settings()
    assert page._session_reminder_started_at == started
    assert "#ef6b73" in page.session_reset_now_button.styleSheet()


def test_popup_reset_is_disabled_during_other_vaccine_operations(reminder):
    page, now = reminder
    page._print_in_progress = True
    now[0] += 115 * 60
    page._session_reminder_timer.timeout.emit()
    assert not page._session_reset_alert_button.isEnabled()
    page._session_reset_alert_button.click()
    assert page._session_reset_alert is not None
    page._print_in_progress = False
    page._update_handoff_controls()
    assert page._session_reset_alert_button.isEnabled()


def test_successful_main_reset_closes_existing_alert(reminder, monkeypatch):
    page, now = reminder
    calls = install_outcomes(monkeypatch)
    now[0] += 115 * 60
    page._session_reminder_timer.timeout.emit()
    page.session_reset_now_button.click()
    wait_for_reset(page)
    assert calls == ["general", "covid", "influenza"]
    assert page._session_reset_alert is None
    assert not page._session_reset_alert_shown


def test_manual_reset_blocks_reentrant_reset_login_and_fetch(reminder, monkeypatch):
    page, _now = reminder
    calls = []
    entered, release = threading.Event(), threading.Event()

    def reset(target, **_kwargs):
        calls.append(target.key)
        entered.set()
        assert release.wait(3)
        return VaccineSessionResetResult(target.key, "reset_sent", "sent", True)

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", reset)
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", lambda *_a, **_kw:
        VaccineSessionResetResult("influenza", "not_open", "not open"))
    page.reset_vaccine_sessions_now()
    try:
        assert entered.wait(3)
        assert page._session_reset_in_progress
        assert not page.session_reset_now_button.isEnabled()
        page.reset_vaccine_sessions_now()
        assert "another vaccine operation" in page.status_label.text()
        assert not page.log_in_to_kdca()
        assert not page.fetch_current_patient_from_emr()
    finally:
        release.set()
    wait_for_reset(page)
    assert calls == ["general", "covid"]
    assert not page._session_reset_in_progress
    assert page.session_reset_now_button.isEnabled()


def test_reset_feedback_is_immediate_and_gui_remains_responsive(reminder, monkeypatch):
    from PySide6.QtCore import QTimer

    page, _now = reminder
    entered, release = threading.Event(), threading.Event()
    calls = install_outcomes(monkeypatch)
    original = vaccine_tab.reset_vaccine_session

    def slow_reset(target, **kwargs):
        assert threading.current_thread() is not threading.main_thread()
        entered.set()
        assert release.wait(3)
        return original(target, **kwargs)

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", slow_reset)
    page.reset_vaccine_sessions_now()
    assert "reading settings" in page.status_label.text()
    heartbeat = []
    try:
        assert entered.wait(3)
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        QApplication.processEvents()
        assert heartbeat == [True]
        assert "checking General" in page.status_label.text()
        assert page.kdca_stop_button.isEnabled()
    finally:
        release.set()
    wait_for_reset(page)
    assert calls == ["general", "covid", "influenza"]


def test_settings_failure_is_visible_and_controls_recover(reminder, monkeypatch):
    import sqlite3

    page, _now = reminder

    def fail(*_args, **_kwargs):
        raise sqlite3.OperationalError("Sensitive details must not appear")

    monkeypatch.setattr(vaccine_tab, "connect", fail)
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert "reading settings: Failed (OperationalError)" in page.status_label.text()
    assert "Sensitive" not in page.status_label.text()
    assert page.session_reset_now_button.isEnabled()
    assert not page.kdca_stop_button.isEnabled()


@pytest.mark.parametrize("stop", ["button", "timeout"])
def test_stop_or_timeout_does_not_proceed_after_stalled_check(reminder, monkeypatch, stop):
    page, now = reminder
    entered, release = threading.Event(), threading.Event()
    calls = []
    started = page._session_reminder_started_at
    now[0] += 90 * 60

    def slow_reset(target, *, cancelled):
        calls.append(target.key)
        entered.set()
        assert release.wait(3)
        assert cancelled()
        return VaccineSessionResetResult(target.key, "cancelled", "no click sent")

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", slow_reset)
    page.reset_vaccine_sessions_now()
    try:
        assert entered.wait(3)
        if stop == "button":
            page.kdca_stop_button.click()
        else:
            page._session_reset_watchdog.timeout.emit()
        QApplication.processEvents()
        assert ("stopped" if stop == "button" else "timed out") in page.status_label.text()
        assert not page.session_reset_now_button.isEnabled()
    finally:
        release.set()
    wait_for_reset(page)
    assert calls == ["general"]
    assert page._session_reminder_started_at == started
    assert "Reset stopped" in page.status_label.text()


def test_reset_now_approves_flu_refresh_without_another_popup(reminder, monkeypatch):
    page, _now = reminder
    install_outcomes(monkeypatch)
    approvals = []

    def unexpected_popup(*_args, **_kwargs):
        pytest.fail("Reset Now must not open a Flu confirmation popup")

    def refresh(_settings, *, confirm, cancelled):
        approvals.append(confirm())
        assert not cancelled()
        return VaccineSessionResetResult("influenza", "refresh_sent", "F5 sent")

    monkeypatch.setattr(vaccine_tab.QMessageBox, "__init__", unexpected_popup)
    monkeypatch.setattr(vaccine_tab.QMessageBox, "question", unexpected_popup)
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", refresh)
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert approvals == [True]
    assert "F5 sent" in page.status_label.text()


def test_reset_reads_settings_without_migrations_or_write_lock(reminder, monkeypatch):
    from KaosEghis.db.database import connect

    page, _now = reminder
    calls = install_outcomes(monkeypatch)
    monkeypatch.setattr(vaccine_tab, "initialize_database", lambda *_a: pytest.fail("No migrations during reset"))
    with connect(page._db_path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        page.reset_vaccine_sessions_now()
        wait_for_reset(page)
        writer.rollback()
    assert calls == ["general", "covid", "influenza"]


def test_worker_deadline_blocks_input_even_without_gui_timer(reminder, monkeypatch):
    page, now = reminder
    calls = []

    def slow_reset(target, *, cancelled):
        calls.append(target.key)
        now[0] += 61
        assert cancelled()
        return VaccineSessionResetResult(target.key, "cancelled", "no click sent")

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", slow_reset)
    page.reset_vaccine_sessions_now()
    page._session_reset_watchdog.stop()
    wait_for_reset(page)
    assert calls == ["general"]
    assert "Reset stopped" in page.status_label.text()


def test_timeout_revokes_flu_approval_before_input(reminder, monkeypatch):
    page, _now = reminder
    install_outcomes(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    approvals = []

    def refresh(_settings, *, confirm, cancelled):
        entered.set()
        assert release.wait(3)
        approvals.append(confirm())
        assert cancelled()
        return VaccineSessionResetResult("influenza", "cancelled", "no F5 sent")

    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", refresh)
    page.reset_vaccine_sessions_now()
    try:
        assert entered.wait(3)
        page._session_reset_timed_out()
    finally:
        release.set()
    wait_for_reset(page)
    assert approvals == [False]
    assert page.session_reset_now_button.isEnabled()


def test_window_checks_start_only_after_settings_connection_closes(reminder, monkeypatch):
    from contextlib import contextmanager

    page, _now = reminder
    calls = install_outcomes(monkeypatch)
    original_connect = vaccine_tab.connect
    original_reset = vaccine_tab.reset_vaccine_session
    connections = []

    @contextmanager
    def tracked_connect(*args, **kwargs):
        with original_connect(*args, **kwargs) as connection:
            connections.append(connection)
            assert connection.execute("PRAGMA query_only").fetchone() == (0,)
            yield connection
            assert connection.execute("PRAGMA query_only").fetchone() == (1,)

    def reset(target, **kwargs):
        import sqlite3

        assert len(connections) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connections[0].execute("SELECT 1")
        return original_reset(target, **kwargs)

    monkeypatch.setattr(vaccine_tab, "connect", tracked_connect)
    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", reset)
    page.reset_vaccine_sessions_now()
    wait_for_reset(page)
    assert calls == ["general", "covid", "influenza"]
