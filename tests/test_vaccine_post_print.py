import os
import sys
import time
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from KaosEghis.core.printer_service import VaccineLabelPrintResult
from KaosEghis.core.vaccine_system_input import VaccineHandoffResult
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_vaccine_type, get_today_vaccine_counts,
    list_vaccine_records, mark_vaccine_record_completed,
)
from KaosEghis.ui.tabs import vaccine_tab


@pytest.fixture
def page(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = tmp_path / "test.sqlite"
    initialize_database(db)
    with connect(db) as connection:
        create_vaccine_type(connection, name="Test General", code="test", program_type="general")
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: VaccineLabelPrintResult(True, "Printed."))
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda *_a, **_kw: VaccineHandoffResult(False, "Test failure."))
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        COINIT_MULTITHREADED=0, CoInitializeEx=lambda _mode: None, CoUninitialize=lambda: None,
    ))
    panel = vaccine_tab.VaccineTab(db)
    panel._select_vaccine_type(None, "Test General")
    panel.patient_chart_no_input.setText("0000")
    panel.patient_name_input.setText("Test Patient")
    panel.patient_resident_id_input.setText("700101-1000000")
    yield panel
    _wait(panel)
    panel.close()
    panel.deleteLater()
    app.processEvents()


def _wait(page):
    deadline = time.monotonic() + 5
    while page._handoff_thread is not None and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(0.005)
    assert page._handoff_thread is None


def test_declining_handoff_clears_only_form_after_print(page, monkeypatch):
    prompts = []
    def decline(*args):
        prompts.append(args)
        with connect(page._db_path) as connection:
            assert list_vaccine_records(connection)[0].status == "completed"
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "question", decline)
    page.print_label()
    assert len(prompts) == 1
    assert "General vaccine system" in prompts[0][2]
    assert "700101" not in prompts[0][2]
    assert prompts[0][-1] == QMessageBox.StandardButton.No
    assert page.patient_name_input.text() == ""
    assert page._current_record_id is None
    assert page._prepared_pair_ids is None
    assert page._pending_handoffs == []
    with connect(page._db_path) as connection:
        assert len(list_vaccine_records(connection)) == 1


def test_yes_uses_printed_snapshot_and_clears_after_success(page, monkeypatch):
    entered = []
    def accept(*_args):
        page.patient_resident_id_input.setText("different live form")
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", accept)
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda _s, request, **_kw: (
        entered.append(request) or VaccineHandoffResult(True, "Sent.")
    ))
    page.print_label()
    _wait(page)
    assert len(entered) == 1
    assert entered[0].resident_id == "700101-1000000"
    assert page.patient_resident_id_input.text() == ""
    assert page._pending_handoffs == []


def test_failure_retains_form_and_retry_does_not_print_or_count(page, monkeypatch):
    prints = []
    attempts = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: (
        prints.append(True) or VaccineLabelPrintResult(True, "Printed.")
    ))
    def enter(_settings, request, **_kw):
        attempts.append(request)
        return VaccineHandoffResult(len(attempts) > 1, "Test outcome.")
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    page.print_label()
    _wait(page)
    assert page.patient_name_input.text() == "Test Patient"
    assert not page.retry_handoff_button.isHidden()
    assert not page.fetch_button.isEnabled()
    assert page.fetch_current_patient_from_emr() is False
    page.print_label()
    with connect(page._db_path) as connection:
        before = list_vaccine_records(connection)
    page.retry_handoff_button.click()
    _wait(page)
    assert len(attempts) == 2
    assert len(prints) == 1
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before
    assert page.patient_name_input.text() == ""


def test_skip_after_failed_handoff_keeps_printed_record(page, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    page.print_label()
    _wait(page)
    page.skip_handoff_button.click()
    assert page.patient_chart_no_input.text() == ""
    assert page.fetch_button.isEnabled()
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection)[0].status == "completed"


@pytest.mark.parametrize("failure", ["printer", "program", "database"])
def test_failed_print_never_prompts_or_clears(page, monkeypatch, failure):
    prompts = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: prompts.append(True))
    if failure == "printer":
        monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: VaccineLabelPrintResult(False, "Failed."))
    elif failure == "program":
        monkeypatch.setattr(page, "_confirm_program_printing", lambda *_a: (False, False))
    else:
        def fail(*_a, **_kw):
            raise ValueError("completion failed")
        monkeypatch.setattr(vaccine_tab, "mark_vaccine_record_completed", fail)
    page.print_label()
    assert prompts == []
    assert page.patient_name_input.text() == "Test Patient"
    assert page._pending_handoffs == []


def _prepare_pair(page, monkeypatch):
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    pair = page.prepare_flu_and_covid()
    monkeypatch.setattr(page, "_confirm_program_printing", lambda *_a: (True, True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    return pair


def test_pair_prompts_once_after_both_prints_and_retries_only_failed_system(page, monkeypatch):
    pair = _prepare_pair(page, monkeypatch)
    printed = []
    entered = []
    prompts = []
    def confirm(*args):
        prompts.append(args[1])
        if args[1] == "Vaccine system patient lookup":
            assert len(printed) == 2
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", confirm)
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: (
        printed.append(True) or VaccineLabelPrintResult(True, "Printed.")
    ))
    def enter(_s, request, **_kw):
        entered.append(request.system)
        return VaccineHandoffResult(len(entered) != 2, "Test outcome.")
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    page.print_prepared_pair()
    _wait(page)
    assert entered == ["influenza", "covid"]
    assert prompts == ["Print Flu + COVID labels", "Vaccine system patient lookup"]
    assert page.patient_chart_no_input.text() == "0000"
    assert [r.system for r in page._pending_handoffs] == ["covid"]
    page._start_handoff()
    _wait(page)
    assert entered == ["influenza", "covid", "covid"]
    assert len(printed) == 2
    with connect(page._db_path) as connection:
        records = list_vaccine_records(connection)
        assert len(records) == 2
        assert get_today_vaccine_counts(connection, records[0].completed_on) == {"flu": 1, "covid": 1}
    assert page._prepared_pair_ids is None
    assert page.patient_chart_no_input.text() == ""


def test_pair_reprint_failure_not_mistaken_for_successful_print(page, monkeypatch):
    pair = _prepare_pair(page, monkeypatch)
    with connect(page._db_path) as connection:
        for record in pair:
            mark_vaccine_record_completed(connection, record.id)
    printed = []
    handoffs = []
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: (
        printed.append(True) or VaccineLabelPrintResult(len(printed) == 1, "Printer failed.")
    ))
    monkeypatch.setattr(page, "_begin_post_print_handoff", handoffs.append)
    page.print_prepared_pair()
    assert handoffs == []
    assert len(printed) == 2
    assert "1 of 2" in page.status_label.text()
    assert page._prepared_pair_ids is not None
    assert page.patient_chart_no_input.text() == "0000"


def test_pending_handoff_defers_resets_and_blocks_mutation(page, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    page.print_label()
    _wait(page)
    resets = []
    timers = []
    monkeypatch.setattr(vaccine_tab, "reset_vaccine_session", lambda *_a: resets.append(True))
    page._session_keeper_targets["general"] = SimpleNamespace(key="general")
    page._session_keeper_timers["general"] = SimpleNamespace(start=timers.append, stop=lambda: None)
    page._run_session_keeper("general")
    page.reset_vaccine_sessions_now()
    page.clear_form()
    page.start_new_vaccine_record()
    assert page.save_record() is None
    assert page.prepare_flu_and_covid() is None
    assert page.patient_chart_no_input.text() == "0000"
    assert resets == []
    assert timers == [vaccine_tab.SESSION_KEEPER_RETRY_MS]


def test_handoff_runs_off_gui_thread_is_single_flight_and_can_stop(page, monkeypatch):
    import threading

    entered, release = threading.Event(), threading.Event()
    main_thread = threading.get_ident()
    calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)

    def enter(_settings, _request, *, cancelled):
        assert threading.get_ident() != main_thread
        calls.append(True)
        entered.set()
        assert release.wait(3)
        assert cancelled()
        return VaccineHandoffResult(False, "Stopped.")

    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    try:
        page.print_label()
        assert entered.wait(2)
        page._start_handoff()
        assert not page.log_in_to_kdca()
        assert not page.fetch_button.isEnabled()
        assert not page.retry_handoff_button.isEnabled()
        assert page.kdca_stop_button.isEnabled()
        page._stop_kdca_operation()
    finally:
        release.set()
        _wait(page)
    assert len(calls) == 1
    assert page._pending_handoffs
    assert page.patient_chart_no_input.text() == "0000"
    assert page.retry_handoff_button.isEnabled()
