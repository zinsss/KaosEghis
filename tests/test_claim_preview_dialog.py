from datetime import date, datetime, timedelta
import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest

from KaosEghis.core.claim_preparation import ClaimHistory, ClaimPreviewError
from KaosEghis.ui import claim_preview_dialog as ui


@pytest.fixture
def dialog(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui, "connected_claim_identity", lambda: (100, 200))
    widget = ui.ClaimPreviewDialog()
    widget.claim_date.setDate(QDate(2026, 10, 2))
    yield app, widget
    widget.reject()
    widget.deleteLater()
    app.processEvents()


def snapshot(month=date(2026, 9, 1), weeks=(1, 2, 3, 4)):
    return ClaimHistory(month, weeks, (1, 2, 3, 4, 5, 6), datetime.now(), (100, 200))


def wait_until(app, predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and not predicate():
        app.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_two_month_preview_and_empty_history_confirmation(dialog, monkeypatch):
    _, widget = dialog
    widget._finish_read(widget._generation, snapshot(), "")
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)
    widget._finish_read(widget._generation, snapshot(date(2026, 10, 1), ()), "")
    assert widget.table.rowCount() == 2
    assert widget.table.item(0, 3).text() == "5주"
    assert widget.table.item(1, 3).text() == "1주"
    assert "No aggregation" in widget.status.text()


def test_empty_month_declined_does_not_infer_first_week(dialog, monkeypatch):
    _, widget = dialog
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)
    widget._finish_read(widget._generation, snapshot(date(2026, 10, 1), ()), "")
    assert not widget.histories
    assert widget.table.item(1, 3).text() == "-"


def test_background_read_does_not_block_ui_or_spawn_duplicate_worker(dialog, monkeypatch):
    app, widget = dialog
    entered, release = threading.Event(), threading.Event()
    threads = []

    def read():
        threads.append(threading.get_ident())
        entered.set()
        release.wait(2)
        return snapshot()

    monkeypatch.setattr(ui, "read_claim_history", read)
    try:
        widget.read_month()
        assert entered.wait(1)
        assert not widget.read_button.isEnabled()
        widget.read_month()
        app.processEvents()
        assert len(threads) == 1
        assert threads[0] != threading.get_ident()
    finally:
        release.set()
    wait_until(app, lambda: widget._thread is None)
    assert widget.table.item(0, 3).text() == "5주"


def test_timeout_rejects_late_read_and_waits_before_allowing_another(dialog, monkeypatch):
    app, widget = dialog
    release = threading.Event()
    monkeypatch.setattr(ui, "read_claim_history", lambda: (release.wait(2), snapshot())[1])
    try:
        widget.read_month()
        widget._read_timeout()
        assert not widget.read_button.isEnabled()
        assert "timed out" in widget.status.text()
    finally:
        release.set()
    wait_until(app, lambda: widget._thread is None)
    assert not widget.histories
    assert widget.read_button.isEnabled()


def test_failed_read_clears_previous_result_without_showing_exception_payload(dialog, monkeypatch):
    app, widget = dialog
    widget._finish_read(widget._generation, snapshot(), "")

    def fail():
        raise RuntimeError("PRIVATE SCREEN PAYLOAD")

    monkeypatch.setattr(ui, "read_claim_history", fail)
    widget.read_month()
    wait_until(app, lambda: widget._thread is None)
    assert not widget.histories
    assert "PRIVATE" not in widget.status.text()


def test_read_error_message_displayed(dialog, monkeypatch):
    app, widget = dialog

    def fail():
        raise ClaimPreviewError("Total claim row count is unavailable")

    monkeypatch.setattr(ui, "read_claim_history", fail)
    widget.read_month()
    wait_until(app, lambda: widget._thread is None)
    assert "row count" in widget.status.text()


@pytest.mark.parametrize("change", ["date", "connection", "expired", "close"])
def test_stale_snapshots_are_discarded(dialog, monkeypatch, change):
    _, widget = dialog
    widget._finish_read(widget._generation, snapshot(), "")
    if change == "date":
        widget.claim_date.setDate(QDate(2026, 10, 9))
    elif change == "connection":
        monkeypatch.setattr(ui, "connected_claim_identity", lambda: None)
        widget._invalidate_old_history()
    elif change == "expired":
        from dataclasses import replace
        key = date(2026, 9, 1)
        widget.histories[key] = replace(widget.histories[key], captured_at=datetime.now() - timedelta(minutes=6))
        widget._invalidate_old_history()
    else:
        generation = widget._generation
        widget.reject()
        widget._finish_read(generation, snapshot(), "")
    assert not widget.histories


def test_wrong_month_not_added_and_disconnected_result_rejected(dialog, monkeypatch):
    _, widget = dialog
    widget._finish_read(widget._generation, snapshot(date(2026, 8, 1)), "")
    assert not widget.histories
    assert "outside" in widget.status.text()
    monkeypatch.setattr(ui, "connected_claim_identity", lambda: None)
    widget._finish_read(widget._generation, snapshot(), "")
    assert not widget.histories
    assert "connection changed" in widget.status.text()


def test_scheduler_opens_preview_without_creating_job_or_macro(tmp_path):
    from KaosEghis.db.database import connect
    from KaosEghis.db.repositories import list_items, list_scheduler_jobs
    from KaosEghis.ui.tabs.scheduler_tab import SchedulerTab

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "scheduler.sqlite"
    tab = SchedulerTab(path)
    try:
        with connect(path) as connection:
            before = list_items(connection), list_scheduler_jobs(connection)
        tab.open_claim_preview()
        app.processEvents()
        assert tab._claim_preview_dialog.isVisible()
        with connect(path) as connection:
            assert (list_items(connection), list_scheduler_jobs(connection)) == before
    finally:
        tab._claim_preview_dialog.reject()
        tab.close()
