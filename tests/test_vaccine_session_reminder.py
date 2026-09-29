import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from KaosEghis.core.vaccine_session_keeper import VaccineSessionResetResult
from KaosEghis.ui.tabs import vaccine_tab


@pytest.fixture
def reminder(tmp_path, monkeypatch):
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
    if page._session_reset_alert is not None:
        page._session_reset_alert.close()
    page._session_reminder_timer.stop()
    page.close()
    page.deleteLater()
    app.processEvents()


def install_outcomes(monkeypatch, *, covid="reset_sent", flu="not_open"):
    calls = []

    def reset(target):
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
    assert calls == ["general", "covid", "influenza"]
    assert page._session_reset_alert is None
    assert not page._session_reset_alert_shown


def test_manual_reset_blocks_reentrant_reset_login_and_fetch(reminder, monkeypatch):
    page, _now = reminder
    calls = []

    def reset(target):
        calls.append(target.key)
        assert page._session_reset_in_progress
        assert not page._print_in_progress
        assert not page.session_reset_now_button.isEnabled()
        page.reset_vaccine_sessions_now()
        assert not page.log_in_to_kdca()
        assert not page.fetch_current_patient_from_emr()
        return VaccineSessionResetResult(target.key, "reset_sent", "sent", True)

    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", reset)
    monkeypatch.setattr(vaccine_tab, "refresh_influenza_session", lambda *_a, **_kw:
        VaccineSessionResetResult("influenza", "not_open", "not open"))
    page.reset_vaccine_sessions_now()
    assert calls == ["general", "covid"]
    assert not page._session_reset_in_progress
    assert page.session_reset_now_button.isEnabled()
