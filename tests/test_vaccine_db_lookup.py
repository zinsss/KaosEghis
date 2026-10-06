import os
import sys
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from KaosEghis.core.vaccine_system_input import VaccineHandoffRequest, VaccineHandoffResult
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_vaccine_record, create_vaccine_type, delete_vaccine_record,
    get_vaccine_record, list_vaccine_records, mark_vaccine_record_cancelled,
    mark_vaccine_record_completed,
)
from KaosEghis.ui.tabs import vaccine_tab


def wait_for_lookup(panel):
    deadline = time.monotonic() + 5
    while panel._handoff_thread is not None and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(0.005)
    assert panel._handoff_thread is None


@pytest.fixture
def page(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = tmp_path / "vaccine.sqlite"
    initialize_database(db)
    records = {}
    with connect(db) as connection:
        for index, program in enumerate(("general", "general_influenza", "national_influenza", "national_covid")):
            vaccine = create_vaccine_type(connection, name="Synthetic " + program, program_type=program)
            records[program] = create_vaccine_record(
                connection, vaccine_type_id=vaccine.id, vaccine_type_name=vaccine.name,
                patient_chart_no=f"TEST-{index}", patient_name="Synthetic DB Patient",
                patient_resident_id=f"700101-100000{index}",
            )
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        COINIT_MULTITHREADED=0, CoInitializeEx=lambda _mode: None, CoUninitialize=lambda: None,
    ))
    entered = []
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda _settings, request, **_kw: (
        entered.append(request) or VaccineHandoffResult(True, "Patient lookup input sent.")
    ))
    def forbidden(*_args, **_kwargs):
        pytest.fail("A DB lookup must not print, chart, fetch, launch or use the clipboard")
    for name in ("print_vaccine_label", "paste_vaccine_charting", "copy_text",
                 "fetch_vaccine_patient_context", "open_vaccine_system"):
        monkeypatch.setattr(vaccine_tab, name, forbidden)
    panel = vaccine_tab.VaccineTab(db)
    panel.patient_name_input.setText("Unfinished form patient")
    panel.patient_resident_id_input.setText("800101-2000000")
    panel.patient_chart_no_input.setText("TEST-FORM")
    panel._current_record_id = records["general"].id
    panel._prepared_pair_ids = (records["national_influenza"].id, records["national_covid"].id)
    panel.test_records = records
    panel.test_entered = entered
    yield panel
    panel._handoff_cancel.set()
    wait_for_lookup(panel)
    panel.close()
    panel.deleteLater()
    app.processEvents()


def record_row(panel, program):
    bucket = {"national_influenza": "flu", "national_covid": "covid"}.get(program, "general")
    table = getattr(panel, bucket + "_records_table")
    record = panel.test_records[program]
    row = next(row for row in range(table.rowCount()) if table.item(row, 0).text() == str(record.id))
    return table, row


def form_snapshot(panel):
    return (
        panel.patient_name_input.text(), panel.patient_resident_id_input.text(),
        panel.patient_chart_no_input.text(), panel._current_record_id,
        panel._prepared_pair_ids, panel.vaccine_types_combo.currentIndex(),
        panel.charting_text_preview.toPlainText(),
    )


@pytest.mark.parametrize("program,bucket", [
    ("general", "general"), ("general_influenza", "general"),
    ("national_influenza", "flu"), ("national_covid", "covid"),
    (None, "general"), ("", "general"), ("unknown", "general"),
])
@pytest.mark.parametrize("name", ["Influenza", "flu", "COVID-19", "Custom vaccine"])
def test_db_bucket_uses_saved_program_not_vaccine_name(program, bucket, name):
    record = SimpleNamespace(program_type=program, vaccine_type_name=name)
    assert vaccine_tab.VaccineTab._record_bucket(record) == bucket


def test_db_tables_separate_private_flu_without_changing_records(page):
    with connect(page._db_path) as connection:
        before = list_vaccine_records(connection)
    page.refresh_view()
    expected = {
        "general": {page.test_records["general"].id, page.test_records["general_influenza"].id},
        "flu": {page.test_records["national_influenza"].id},
        "covid": {page.test_records["national_covid"].id},
    }
    for bucket, ids in expected.items():
        table = getattr(page, bucket + "_records_table")
        assert {int(table.item(row, 0).text()) for row in range(table.rowCount())} == ids
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before


@pytest.mark.parametrize("program,system", [
    ("general", "general"), ("general_influenza", "general"),
    ("national_influenza", "influenza"), ("national_covid", "covid"),
])
def test_double_click_uses_saved_row_and_correct_system_without_side_effects(page, program, system):
    before_form = form_snapshot(page)
    with connect(page._db_path) as connection:
        before_records = list_vaccine_records(connection)
        before_audit = connection.execute("SELECT count(*) FROM vaccine_audit_events").fetchone()[0]
    # Selections in other tables must not redirect the double-click.
    for table in (page.general_records_table, page.flu_records_table, page.covid_records_table):
        table.selectRow(0)
    table, row = record_row(page, program)
    table.cellDoubleClicked.emit(row, 3)
    assert page._db_lookup_in_progress and not page.print_button.isEnabled()
    wait_for_lookup(page)
    assert len(page.test_entered) == 1
    request = page.test_entered[0]
    assert request.system == system
    assert request.resident_id == page.test_records[program].patient_resident_id
    assert request.charting_text == ""
    assert form_snapshot(page) == before_form
    assert page._pending_handoffs == [] and not page._db_lookup_in_progress
    assert "Saved record and form unchanged" in page.status_label.text()
    assert request.resident_id not in page.status_label.text()
    assert page._session_reminder_started_at is None
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before_records
        assert connection.execute("SELECT count(*) FROM vaccine_audit_events").fetchone()[0] == before_audit


def test_real_table_double_click_signal_is_wired(page):
    page.resize(1000, 800)
    page.show_page(1)
    page.show()
    QApplication.instance().processEvents()
    table, row = record_row(page, "national_influenza")
    point = table.visualItemRect(table.item(row, 3)).center()
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert page.test_entered == [] and page._handoff_thread is None
    QTest.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseRelease(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    wait_for_lookup(page)
    assert len(page.test_entered) == 1 and page.test_entered[0].system == "influenza"


@pytest.mark.parametrize("lifecycle", ["completed", "cancelled"])
def test_lookup_does_not_change_historical_record_lifecycle(page, lifecycle):
    record = page.test_records["general"]
    with connect(page._db_path) as connection:
        if lifecycle == "completed":
            mark_vaccine_record_completed(connection, record.id)
        else:
            mark_vaccine_record_cancelled(connection, record.id)
        before = get_vaccine_record(connection, record.id)
    page.refresh_view()
    table, row = record_row(page, "general")
    table.cellDoubleClicked.emit(row, 6)
    wait_for_lookup(page)
    assert len(page.test_entered) == 1
    with connect(page._db_path) as connection:
        assert get_vaccine_record(connection, record.id) == before


def test_failed_lookup_retains_form_and_double_click_can_retry(page, monkeypatch):
    attempts = []
    def enter(_settings, request, **_kw):
        attempts.append(request)
        return VaccineHandoffResult(len(attempts) == 2, "Synthetic input outcome.")
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    before = form_snapshot(page)
    table, row = record_row(page, "national_covid")
    table.cellDoubleClicked.emit(row, 3)
    wait_for_lookup(page)
    assert "Double-click the record to retry" in page.status_label.text()
    assert form_snapshot(page) == before
    assert page._pending_handoffs == []
    assert page.retry_handoff_button.isHidden()
    table.cellDoubleClicked.emit(row, 3)
    wait_for_lookup(page)
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert form_snapshot(page) == before


@pytest.mark.parametrize("busy", ["pending", "handoff", "kdca", "print", "shortcut", "reset"])
def test_busy_workflow_blocks_db_lookup(page, busy):
    attributes = {
        "pending": ("_pending_handoffs", [VaccineHandoffRequest("general", "7001011000000")]),
        "handoff": ("_handoff_thread", object()), "kdca": ("_kdca_thread", object()),
        "print": ("_print_in_progress", True), "shortcut": ("_shortcut_in_progress", True),
        "reset": ("_session_reset_in_progress", True),
    }
    attr, value = attributes[busy]
    original = getattr(page, attr)
    setattr(page, attr, value)
    before = form_snapshot(page)
    try:
        table, row = record_row(page, "general")
        table.cellDoubleClicked.emit(row, 3)
        assert getattr(page, attr) is value
        assert not page._db_lookup_in_progress and page.test_entered == []
        assert form_snapshot(page) == before
        assert "Finish the current vaccine operation" in page.status_label.text()
    finally:
        setattr(page, attr, original)


def test_repeated_double_click_cannot_queue_second_patient(page, monkeypatch):
    release = threading.Event()
    entered = []
    def enter(_settings, request, **_kw):
        entered.append(request)
        assert release.wait(3)
        return VaccineHandoffResult(True, "Sent.")
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    table, row = record_row(page, "national_influenza")
    other, other_row = record_row(page, "national_covid")
    try:
        table.cellDoubleClicked.emit(row, 3)
        other.cellDoubleClicked.emit(other_row, 3)
        assert len(page._pending_handoffs) == 1
    finally:
        release.set()
        wait_for_lookup(page)
    assert len(entered) == 1 and entered[0].system == "influenza"


@pytest.mark.parametrize("resident", [None, "", "700101-1", "X" * 13, "1" * 14, "\uff17" * 13])
def test_invalid_resident_number_stops_before_system_input(page, monkeypatch, resident):
    record = replace(page.test_records["general"], patient_resident_id=resident)
    monkeypatch.setattr(vaccine_tab, "get_vaccine_record", lambda *_a: record)
    table, row = record_row(page, "general")
    table.cellDoubleClicked.emit(row, 3)
    assert page._handoff_thread is None and page.test_entered == []
    assert "13-digit" in page.status_label.text()


def test_unknown_program_does_not_guess_system(page, monkeypatch):
    record = replace(page.test_records["general"], program_type="unknown")
    monkeypatch.setattr(vaccine_tab, "get_vaccine_record", lambda *_a: record)
    table, row = record_row(page, "general")
    table.cellDoubleClicked.emit(row, 3)
    assert page._handoff_thread is None and page.test_entered == []
    assert "mapping is not configured" in page.status_label.text()


def test_deleted_record_stale_table_never_sends_input(page):
    table, row = record_row(page, "general")
    with connect(page._db_path) as connection:
        delete_vaccine_record(connection, page.test_records["general"].id)
    table.cellDoubleClicked.emit(row, 3)
    assert page._handoff_thread is None and page.test_entered == []
    assert "record not found" in page.status_label.text()


@pytest.mark.parametrize("failure", ["read", "start", "worker"])
def test_exceptions_are_redacted_and_controls_recover(page, monkeypatch, failure):
    def fail(*_args, **_kwargs):
        raise RuntimeError("PRIVATE RESIDENT DATA")
    if failure == "read":
        monkeypatch.setattr(vaccine_tab, "get_vaccine_record", fail)
    elif failure == "start":
        monkeypatch.setattr(page, "_start_handoff", fail)
    else:
        monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", fail)
    before = form_snapshot(page)
    table, row = record_row(page, "general")
    table.cellDoubleClicked.emit(row, 3)
    wait_for_lookup(page)
    assert form_snapshot(page) == before
    assert not page._db_lookup_in_progress and not page._pending_handoffs
    assert "PRIVATE" not in page.status_label.text()
    assert page.fetch_button.isEnabled()


def test_stop_during_mouse_release_delay_sends_nothing(page):
    before = form_snapshot(page)
    table, row = record_row(page, "general")
    table.cellDoubleClicked.emit(row, 3)
    page._stop_kdca_operation()
    wait_for_lookup(page)
    assert page.test_entered == []
    assert not page._db_lookup_in_progress and page._pending_handoffs == []
    assert form_snapshot(page) == before
