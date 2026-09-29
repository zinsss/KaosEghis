from datetime import date, timedelta
import threading
import time

import pytest
from PySide6.QtWidgets import QApplication

from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
from KaosEghis.core.emr_refresh_probe import RefreshRequest
from KaosEghis.core.pacs_polling import PollResult
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import set_settings
from KaosEghis.ui.plugins import pacs_panel as module


def wait(panel):
    deadline = time.monotonic() + 3
    while panel._poll_in_progress:
        assert time.monotonic() < deadline
        QApplication.instance().processEvents()
        time.sleep(0.005)


def follow_up_now(panel):
    panel._dispatch_timer.stop()
    panel._pending_refreshes = {day: (0, job) for day, (_, job) in panel._pending_refreshes.items()}
    panel._dispatch_refresh()
    wait(panel)


def chart_clear(panel, day=None):
    panel.handle_chart_refresh(RefreshRequest(None, day or panel._today(), "Chart cleared", panel._clock() + 28))


def chart_load(panel, day=None):
    panel.handle_chart_refresh(RefreshRequest(None, day or panel._today(), "Chart loaded"))


@pytest.fixture
def panel(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "test.sqlite"
    initialize_database(path)
    with connect(path) as connection:
        set_settings(connection, {"eghis_db_connection_string": "mock", "pacs_auto_poll_enabled": "true"})
    monkeypatch.setattr(module, "QWebEngineView", None)
    monkeypatch.setattr(module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(module, "run_readonly_query", lambda *a, **k: (["value"], [(1,)]))
    calls, syncs = [], []
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist",
                        lambda settings, path, selected_date=None: calls.append(selected_date) or PollResult(1, 0, 0))
    monkeypatch.setattr(module, "sync_local_worklist_to_kaospacs",
                        lambda *a: syncs.append(True) or KaosPacsSyncResult(1, 0, 0, 0))
    clock, today = [100.0], [date.today()]
    widget = module.PacsPanel(path, clock=lambda: clock[0], today=lambda: today[0])
    widget.test_clock, widget.test_today = clock, today
    monkeypatch.setattr(widget, "_schedule_admin_reload", lambda: None)
    widget.calls, widget.syncs = calls, syncs
    yield widget
    widget.stop_refresh_runtime()
    wait(widget)
    widget.close()
    assert app is not None


def test_default_event_mode_preserves_enabled_and_stops_regular_timer(panel):
    assert panel.auto_poll_checkbox.isChecked()
    assert panel.refresh_mode_combo.currentData() == "chart_clear"
    assert not panel._poll_timer.isActive()
    assert not panel.interval_spinbox.isEnabled()
    assert not panel.calls


@pytest.mark.parametrize("delivery_failure", [False, True])
def test_operation_reports_separate_timings_and_preserves_source_success(panel, monkeypatch, delivery_failure):
    clock = [0.0]
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])
    def check(settings):
        clock[0] += 2
        return True
    def poll(*args, **kwargs):
        clock[0] += 3
        return PollResult(1, 0, 0, source_read_seconds=2.5)
    def deliver(*args):
        clock[0] += 7
        if delivery_failure:
            raise RuntimeError("simulated delivery failure")
        return KaosPacsSyncResult(1, 0, 0, 0)
    monkeypatch.setattr(module, "check_kaospacs_health", check)
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", poll)
    monkeypatch.setattr(module, "sync_local_worklist_to_kaospacs", deliver)
    result = panel._perform_poll_operation({"eghis_db_connection_string": "mock"},
                                          selected_date=date.today(), is_auto_poll=True)
    assert (result.checks_seconds, result.poll_seconds, result.delivery_seconds) == (2, 3, 7)
    assert result.timing_summary() == "checks=2.00s, source=2.50s, local=0.50s, delivery=7.00s"
    assert result.error_message is None and result.poll_result.message is None
    assert result.sync_result.errors == int(delivery_failure)
    panel._record_refresh_result(module._RefreshJob(date.today(), "Safety check", True), result)
    assert panel._next_safety_at == panel._clock() + 300


def test_refresh_log_contains_timing_and_unchanged_counters(panel, monkeypatch):
    messages = []
    panel.refresh_status.connect(messages.append)
    monkeypatch.setattr(module, "sync_local_worklist_to_kaospacs",
                        lambda *args: KaosPacsSyncResult(0, 0, 3, 53, unchanged=53, invalid=3))
    panel.poll_now()
    wait(panel)
    assert len(messages) == 1
    for field in ("sent=0", "unchanged=53", "invalid=3", "checks=", "source=", "local=", "delivery=", "total="):
        assert field in messages[0]


def test_startup_and_one_follow_up_only(panel):
    panel.start_refresh_runtime()
    panel.start_refresh_runtime()
    wait(panel)
    assert panel.calls == [date.today()]
    follow_up_now(panel)
    assert panel.calls == [date.today(), date.today()]
    assert not panel._pending_refreshes
    assert not panel._poll_timer.isActive()


def test_clear_uses_event_date_not_visible_historical_date(panel):
    panel._runtime_started = True
    panel._selected_date = date.today() - timedelta(days=30)
    clear_day = date.today() - timedelta(days=1)
    chart_clear(panel, clear_day)
    wait(panel)
    assert panel.calls == [clear_day]
    assert panel._selected_date != clear_day
    follow_up_now(panel)
    assert panel.calls == [clear_day, clear_day]


def test_clear_while_refreshing_coalesces_and_is_not_lost(panel, monkeypatch):
    panel._runtime_started = True
    started, release = threading.Event(), threading.Event()
    active = [0]

    def slow(*args, selected_date=None):
        assert active[0] == 0
        active[0] += 1
        panel.calls.append(selected_date)
        started.set()
        assert release.wait(3)
        active[0] -= 1
        return PollResult(1, 0, 0)

    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", slow)
    try:
        chart_clear(panel)
        assert started.wait(2)
        for _ in range(20):
            chart_clear(panel)
        assert len(panel._pending_refreshes) == 2
        assert len(panel.calls) == 1
    finally:
        release.set()
    wait(panel)
    assert len(panel.calls) == 2
    follow_up_now(panel)
    assert len(panel.calls) == 3
    assert not panel._pending_refreshes


def test_manual_poll_is_background_and_queued_during_automatic_read(panel, monkeypatch):
    panel._runtime_started = True
    started, release = threading.Event(), threading.Event()

    def slow(*args, selected_date=None):
        panel.calls.append(selected_date)
        started.set()
        assert release.wait(3)
        return PollResult(0, 0, 0)

    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", slow)
    try:
        chart_clear(panel)
        assert started.wait(2)
        panel._selected_date = date.today() - timedelta(days=1)
        at = time.monotonic()
        panel.poll_now()
        assert time.monotonic() - at < 0.5
        assert len(panel.calls) == 1
    finally:
        release.set()
    wait(panel)
    assert panel.calls[:2] == [date.today(), panel._selected_date]


def test_reconnect_refreshes_once_without_treating_focus_as_new_connection(panel):
    panel._runtime_started = True
    panel.handle_emr_connection(None)
    panel.handle_emr_connection((42, 100))
    panel.handle_emr_connection((42, 100))
    wait(panel)
    assert panel.calls == [date.today()]
    follow_up_now(panel)
    panel.handle_emr_connection(None)
    panel.handle_emr_connection((43, 200))
    wait(panel)
    assert len(panel.calls) == 3


def test_failed_read_keeps_previous_success_time_and_has_bounded_retry(panel, monkeypatch):
    panel._runtime_started = True
    panel.poll_now()
    wait(panel)
    previous = panel.last_poll_time_label.text()
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", lambda *a, **k: PollResult(0, 0, 0, message="unavailable"))
    chart_clear(panel)
    wait(panel)
    assert panel.last_poll_time_label.text() == previous
    assert len(panel.syncs) == 1
    assert "unavailable" in panel.polling_status.text()
    follow_up_now(panel)
    assert panel.last_poll_time_label.text() == previous
    assert not panel._pending_refreshes
    assert len(panel.syncs) == 1


def test_offline_service_is_reported_and_next_trigger_can_retry(panel, monkeypatch):
    panel._runtime_started = True
    messages = []
    panel.refresh_status.connect(messages.append)
    monkeypatch.setattr(module, "check_kaospacs_health", lambda settings: False)
    chart_clear(panel)
    wait(panel)
    follow_up_now(panel)
    assert not panel.calls
    assert "failed" in messages[-1]
    assert "unavailable" in messages[-1]
    assert not panel._pending_refreshes
    monkeypatch.setattr(module, "check_kaospacs_health", lambda settings: True)
    chart_clear(panel)
    wait(panel)
    assert panel.calls == [date.today()]


def test_disabling_auto_cancels_follow_up_but_keeps_manual_available(panel):
    panel._runtime_started = True
    chart_clear(panel)
    wait(panel)
    panel.auto_poll_checkbox.setChecked(False)
    panel.apply_polling_settings()
    assert not panel._pending_refreshes
    chart_clear(panel)
    assert len(panel.calls) == 1
    panel.poll_now()
    wait(panel)
    assert len(panel.calls) == 2


def test_stop_drops_follow_up_and_ignores_late_requests(panel):
    panel._runtime_started = True
    chart_clear(panel)
    wait(panel)
    panel.stop_refresh_runtime()
    chart_clear(panel)
    panel.poll_now()
    assert not panel._pending_refreshes
    assert not panel._dispatch_timer.isActive()
    assert len(panel.calls) == 1


def test_legacy_timer_is_explicit_rollback_and_ignores_chart_events(panel):
    panel._runtime_started = True
    panel.refresh_mode_combo.setCurrentIndex(1)
    panel.apply_polling_settings()
    assert panel._poll_timer.isActive()
    chart_clear(panel)
    assert not panel.calls


def activate_events(panel):
    panel._runtime_started = True
    panel._update_safety_timer()


def advance(panel, at):
    panel.test_clock[0] = at
    panel._dispatch_timer.stop()
    panel._dispatch_refresh()
    wait(panel)


def test_load_only_reads_once_without_a_follow_up(panel):
    activate_events(panel)
    chart_load(panel)
    wait(panel)
    assert panel.calls == [date.today()]
    assert not panel._pending_refreshes


def test_load_preserves_clear_follow_up_at_original_deadline(panel):
    activate_events(panel)
    chart_clear(panel)
    wait(panel)
    key = (date.today(), "follow_up")
    assert panel._pending_refreshes[key][0] == 128
    advance(panel, 110)
    chart_load(panel)
    wait(panel)
    assert len(panel.calls) == 2
    assert panel._pending_refreshes[key][0] == 128
    advance(panel, 127.99)
    assert len(panel.calls) == 2
    advance(panel, 128)
    assert len(panel.calls) == 3
    assert not panel._pending_refreshes


def test_new_clear_replaces_follow_up_without_multiplying_jobs(panel):
    activate_events(panel)
    chart_clear(panel)
    wait(panel)
    advance(panel, 110)
    chart_clear(panel)
    wait(panel)
    assert len(panel._pending_refreshes) == 1
    assert panel._pending_refreshes[(date.today(), "follow_up")][0] == 138
    advance(panel, 128)
    assert len(panel.calls) == 2
    advance(panel, 138)
    assert len(panel.calls) == 3


def test_late_finishing_early_read_does_not_consume_follow_up(panel, monkeypatch):
    activate_events(panel)

    def slow(settings, path, selected_date=None):
        panel.calls.append(selected_date)
        panel.test_clock[0] = 135
        return PollResult(0, 0, 0)

    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", slow)
    chart_clear(panel)
    wait(panel)
    assert len(panel.calls) == 2  # Started at 100 and 135; clear deadline was 128.
    assert not panel._pending_refreshes


def test_due_load_and_follow_up_are_one_read(panel):
    activate_events(panel)
    chart_clear(panel)
    wait(panel)
    panel.test_clock[0] = 128
    chart_load(panel)
    wait(panel)
    assert len(panel.calls) == 2
    assert not panel._pending_refreshes


def test_safety_check_catches_missed_last_signal_without_chart_events(panel):
    activate_events(panel)
    assert panel._safety_timer.isActive()
    panel.test_clock[0] = 399.99
    panel._check_safety_refresh()
    assert not panel.calls
    panel.test_clock[0] = 400
    panel._check_safety_refresh()
    wait(panel)
    assert panel.calls == [date.today()]
    assert panel._next_safety_at == 700
    panel._check_safety_refresh()
    assert len(panel.calls) == 1


def test_only_successful_current_day_reads_reset_safety_timer(panel, monkeypatch):
    activate_events(panel)
    advance(panel, 200)
    chart_load(panel, date.today() - timedelta(days=1))
    wait(panel)
    assert panel._next_safety_at == 400
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist",
                        lambda *a, **k: PollResult(0, 0, 0, message="failed"))
    chart_load(panel)
    wait(panel)
    assert panel._next_safety_at == 400
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist",
                        lambda *a, **k: PollResult(0, 0, 0))
    monkeypatch.setattr(module, "sync_local_worklist_to_kaospacs",
                        lambda *a: KaosPacsSyncResult(0, 0, 3, 0))
    panel.poll_now()
    wait(panel)
    assert panel._next_safety_at == 500  # Delivery errors are not source-read failures.


def test_safety_failures_back_off_without_a_five_second_retry_loop(panel, monkeypatch):
    activate_events(panel)
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist",
                        lambda *a, **k: PollResult(0, 0, 0, message="failed"))
    for delay in (60, 120, 240, 300, 300):
        panel.test_clock[0] = panel._next_safety_at
        attempted_at = panel._clock()
        panel._check_safety_refresh()
        wait(panel)
        assert panel._next_safety_at == attempted_at + delay
        panel.test_clock[0] += 5
        panel._check_safety_refresh()
        assert not panel._poll_in_progress
    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist",
                        lambda *a, **k: PollResult(0, 0, 0))
    chart_load(panel)
    wait(panel)
    assert panel._next_safety_at == panel._clock() + 300
    assert panel._safety_backoff == 60


def test_safety_does_not_add_read_while_today_read_is_in_flight(panel, monkeypatch):
    activate_events(panel)
    started, release = threading.Event(), threading.Event()

    def slow(settings, path, selected_date=None):
        panel.calls.append(selected_date)
        started.set()
        assert release.wait(3)
        return PollResult(0, 0, 0)

    monkeypatch.setattr(module, "poll_eghis_image_orders_into_local_worklist", slow)
    try:
        chart_load(panel)
        assert started.wait(2)
        panel.test_clock[0] = 400
        panel._check_safety_refresh()
        assert not panel._pending_refreshes
        assert panel._next_safety_at == 400
    finally:
        release.set()
    wait(panel)
    assert len(panel.calls) == 1
    assert panel._next_safety_at == 700


@pytest.mark.parametrize("action", ["disable", "legacy", "stop"])
def test_auto_off_stops_safety_checks(panel, action):
    activate_events(panel)
    chart_clear(panel)
    wait(panel)
    if action == "stop":
        panel.stop_refresh_runtime()
    else:
        if action == "disable":
            panel.auto_poll_checkbox.setChecked(False)
        else:
            panel.refresh_mode_combo.setCurrentIndex(1)
        panel.apply_polling_settings()
    assert not panel._safety_timer.isActive()
    assert panel._next_safety_at is None
    assert not panel._pending_refreshes
    panel.test_clock[0] = 1000
    panel._check_safety_refresh()
    assert len(panel.calls) == 1


def test_midnight_safety_checks_new_day_without_dropping_old_follow_up(panel):
    activate_events(panel)
    chart_clear(panel)
    wait(panel)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    panel.test_today[0] = tomorrow
    panel.test_clock[0] = 110
    panel._check_safety_refresh()
    wait(panel)
    assert panel.calls == [today, tomorrow]
    assert (today, "follow_up") in panel._pending_refreshes
    assert panel._next_safety_at == 410
    advance(panel, 128)
    assert panel.calls == [today, tomorrow, today]
    assert panel._next_safety_at == 410
