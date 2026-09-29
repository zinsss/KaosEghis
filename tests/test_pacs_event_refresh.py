from datetime import date, timedelta
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from KaosEghis.core.kaospacs_client import KaosPacsSyncResult
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
    widget = module.PacsPanel(path)
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
    panel.handle_chart_clear(SimpleNamespace(day=clear_day))
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
        panel.handle_chart_clear(SimpleNamespace(day=date.today()))
        assert started.wait(2)
        for _ in range(20):
            panel.handle_chart_clear(SimpleNamespace(day=date.today()))
        assert len(panel._pending_refreshes) == 1
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
        panel.handle_chart_clear(SimpleNamespace(day=date.today()))
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
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
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
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    wait(panel)
    follow_up_now(panel)
    assert not panel.calls
    assert "failed" in messages[-1]
    assert "unavailable" in messages[-1]
    assert not panel._pending_refreshes
    monkeypatch.setattr(module, "check_kaospacs_health", lambda settings: True)
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    wait(panel)
    assert panel.calls == [date.today()]


def test_disabling_auto_cancels_follow_up_but_keeps_manual_available(panel):
    panel._runtime_started = True
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    wait(panel)
    panel.auto_poll_checkbox.setChecked(False)
    panel.apply_polling_settings()
    assert not panel._pending_refreshes
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    assert len(panel.calls) == 1
    panel.poll_now()
    wait(panel)
    assert len(panel.calls) == 2


def test_stop_drops_follow_up_and_ignores_late_requests(panel):
    panel._runtime_started = True
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    wait(panel)
    panel.stop_refresh_runtime()
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    panel.poll_now()
    assert not panel._pending_refreshes
    assert not panel._dispatch_timer.isActive()
    assert len(panel.calls) == 1


def test_legacy_timer_is_explicit_rollback_and_ignores_chart_events(panel):
    panel._runtime_started = True
    panel.refresh_mode_combo.setCurrentIndex(1)
    panel.apply_polling_settings()
    assert panel._poll_timer.isActive()
    panel.handle_chart_clear(SimpleNamespace(day=date.today()))
    assert not panel.calls
