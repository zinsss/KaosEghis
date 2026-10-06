import os
import sys
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from KaosEghis.core.printer_service import VaccineLabelPrintResult
from KaosEghis.core.vaccine_eligibility import CovidEligibilityResult, InfluenzaEligibilityResult
from KaosEghis.core.vaccine_patient_context import VaccinePatientContext, VaccinePatientFetchResult
from KaosEghis.core.vaccine_system_input import VaccineHandoffResult
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_vaccine_record, create_vaccine_type, get_today_vaccine_counts, get_today_vaccine_exception_counts,
    list_vaccine_records, list_vaccine_types, mark_vaccine_record_cancelled,
    mark_vaccine_record_completed, update_vaccine_type,
)
from KaosEghis.ui.tabs import vaccine_tab


@pytest.fixture
def shortcut_page(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = tmp_path / "shortcuts.sqlite"
    initialize_database(db)
    events = []
    context = VaccinePatientContext(
        chart_no="0000", resident_id="700101-1000000", patient_name="Test Patient",
        patient_sex="M", patient_age="56", patient_birth_date="1970-01-01",
        patient_phone="010-0000-0000", patient_address="Test Address",
    )
    monkeypatch.setattr(vaccine_tab, "get_active_emr_target_profile", lambda _c: SimpleNamespace(
        id=1, process_name="test-emr.exe", window_title_contains="Test EMR", executable_path="",
    ))
    monkeypatch.setattr(vaccine_tab, "get_emr_ui_target_by_key", lambda *_a: None)
    monkeypatch.setattr(vaccine_tab, "fetch_vaccine_patient_context", lambda *_a: (
        events.append("fetch") or VaccinePatientFetchResult(True, "Fetched.", context)
    ))
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: pytest.fail("Unexpected extra confirmation"))
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda content, **_kw: (
        events.append(("print", content)) or VaccineLabelPrintResult(True, "Printed.")
    ))
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda _s, request, **_kw: (
        events.append(("entry", request)) or VaccineHandoffResult(True, "Sent.")
    ))
    monkeypatch.setattr(vaccine_tab, "copy_text", lambda text: events.append(("copy", text)))
    monkeypatch.setattr(vaccine_tab, "paste_vaccine_charting", lambda _s, text, **_kw: (
        events.append(("charting", text)) or VaccineHandoffResult(True, "Pasted.")
    ))
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        COINIT_MULTITHREADED=0, CoInitializeEx=lambda _mode: None, CoUninitialize=lambda: None,
    ))
    page = vaccine_tab.VaccineTab(db)
    page.test_events = events
    page.test_context = context

    def confirm(_title, choices):
        events.append("confirm")
        assert not page.fetch_button.isEnabled()
        assert all(not button.isEnabled() for button in page.shortcut_buttons.values())
        return tuple(entries[-1] for entries in choices)

    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", confirm)
    monkeypatch.setattr(page, "_confirm_program_printing", lambda record, *_a: (
        events.append(("check", record.program_type)) or (True, record.program_type.startswith("national_"))
    ))
    yield page
    _wait(page)
    page.close()
    page.deleteLater()
    app.processEvents()


def _wait(page):
    deadline = time.monotonic() + 5
    while page._handoff_thread is not None and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(0.005)
    assert page._handoff_thread is None


def _records(page):
    with connect(page._db_path) as connection:
        return list_vaccine_records(connection)


def _types(page, program):
    with connect(page._db_path) as connection:
        return [entry for entry in list_vaccine_types(connection) if entry.program_type == program]


@pytest.mark.parametrize("key,programs,systems", [
    ("national_flu", ["national_influenza"], ["influenza"]),
    ("national_covid", ["national_covid"], ["covid"]),
    ("national_pair", ["national_influenza", "national_covid"], ["influenza", "covid"]),
    ("general_flu", ["general_influenza"], ["general"]),
])
def test_shortcuts_confirm_fetch_lookup_check_print_and_chart(shortcut_page, key, programs, systems):
    page = shortcut_page
    page.patient_name_input.setText("Stale Patient")
    page.shortcut_buttons[key].click()
    _wait(page)
    events = page.test_events
    assert events[:2] == ["confirm", "fetch"]
    assert [e[0] for e in events[2:]] == ["entry", "check", "print"] * len(programs) + ["copy", "charting"]
    assert [e[1] for e in events if isinstance(e, tuple) and e[0] == "check"] == programs
    entries = [e[1] for e in events if isinstance(e, tuple) and e[0] == "entry"]
    assert [entry.system for entry in entries] == systems
    assert all(entry.resident_id == page.test_context.resident_id for entry in entries)
    assert len([e for e in events if isinstance(e, tuple) and e[0] == "print"]) == len(programs)
    assert events[-1][0] == "charting"
    records = _records(page)
    assert sorted(record.program_type for record in records) == sorted(programs)
    assert all(record.status == "completed" and record.patient_name == "Test Patient" for record in records)
    if "national_covid" in programs:
        assert next(r for r in records if r.program_type == "national_covid").vaccine_type_name == "COVID-19 (Moderna)"
    with connect(page._db_path) as connection:
        counts = get_today_vaccine_counts(connection, vaccine_tab.datetime.now().date().isoformat())
    assert counts.get("flu", 0) == int("national_influenza" in programs)
    assert counts.get("covid", 0) == int("national_covid" in programs)
    assert page.patient_name_input.text() == ""
    assert page.vaccine_types_combo.currentIndex() == -1
    assert page._session_reminder_started_at is not None
    assert all(button.isEnabled() for button in page.shortcut_buttons.values())


@pytest.mark.parametrize("program", ["national_covid", "national_influenza"])
@pytest.mark.parametrize("count", [1, 2])
def test_dialog_requires_explicit_product_choice(shortcut_page, program, count):
    entries = _types(shortcut_page, program)
    if count == 2 and len(entries) == 1:
        entries.append(replace(entries[0], id=999, name="Second product"))
    entries = entries[:count]
    for _ in range(2):
        dialog = vaccine_tab.VaccineShortcutDialog("Test", [entries], shortcut_page)
        yes = dialog.buttons.button(QDialogButtonBox.StandardButton.Yes)
        needs_choice = program == "national_covid" or count == 2
        assert dialog.combos[0].currentIndex() == (-1 if needs_choice else 0)
        assert yes.isEnabled() == (not needs_choice)
        assert dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).isDefault()
        dialog.combos[0].setCurrentIndex(0)
        assert yes.isEnabled()
        assert dialog.selected_types() == (entries[0],)
        yes.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        dialog.deleteLater()


def test_decline_does_not_fetch_or_change_form(shortcut_page, monkeypatch):
    page = shortcut_page
    page.patient_name_input.setText("Preserved")
    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", lambda *_a: None)
    page.run_vaccine_shortcut("national_flu")
    assert page.test_events == []
    assert _records(page) == []
    assert page.patient_name_input.text() == "Preserved"
    assert page._session_reminder_started_at is None
    assert not page._shortcut_in_progress


def test_fetch_failure_stops_shortcut(shortcut_page, monkeypatch):
    page = shortcut_page
    page.patient_name_input.setText("Preserved")
    monkeypatch.setattr(vaccine_tab, "fetch_vaccine_patient_context", lambda *_a:
                        VaccinePatientFetchResult(False, "Synthetic fetch failure.", None))
    page.run_vaccine_shortcut("national_pair")
    assert page.test_events == ["confirm"]
    assert _records(page) == []
    assert page.patient_name_input.text() == "Preserved"
    assert "fetch failure" in page.status_label.text()


@pytest.mark.parametrize("field,value", [("chart_no", ""), ("patient_name", ""), ("resident_id", "700101")])
def test_incomplete_fetched_patient_stops_before_print(shortcut_page, monkeypatch, field, value):
    page = shortcut_page
    context = replace(page.test_context, **{field: value})
    monkeypatch.setattr(vaccine_tab, "fetch_vaccine_patient_context", lambda *_a:
                        VaccinePatientFetchResult(True, "Fetched.", context))
    page.run_vaccine_shortcut("national_flu")
    assert _records(page) == []
    assert "required" in page.status_label.text()
    assert page._session_reminder_started_at is None


@pytest.mark.parametrize("key", list(vaccine_tab.VACCINE_SHORTCUTS))
def test_missing_active_catalog_stops_before_fetch(shortcut_page, key):
    page = shortcut_page
    with connect(page._db_path) as connection:
        connection.execute("UPDATE vaccine_types SET is_active = 0")
        connection.commit()
    page.run_vaccine_shortcut(key)
    assert page.test_events == []
    assert _records(page) == []
    assert "configure an enabled vaccine" in page.status_label.text()


def test_catalog_change_after_confirmation_stops(shortcut_page, monkeypatch):
    page = shortcut_page
    def confirm(_title, choices):
        selected = choices[0][0]
        with connect(page._db_path) as connection:
            update_vaccine_type(connection, selected.id, name="Changed", code=selected.code,
                                program_type=selected.program_type, is_active=False)
        return (selected,)
    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", confirm)
    page.run_vaccine_shortcut("national_flu")
    assert page.test_events == ["fetch"]
    assert _records(page) == []
    assert "settings changed" in page.status_label.text()


def test_updated_catalog_and_multiple_flu_types_are_used(shortcut_page):
    page = shortcut_page
    with connect(page._db_path) as connection:
        new = create_vaccine_type(connection, name="New configured Flu", code="new-flu",
                                  program_type="national_influenza")
    page.run_vaccine_shortcut("national_pair")
    _wait(page)
    assert next(r for r in _records(page) if r.program_type == "national_influenza").vaccine_type_id == new.id


@pytest.mark.parametrize("status", ["prepared", "completed", "cancelled"])
@pytest.mark.parametrize("existing_program,key", [
    ("national_influenza", "national_flu"),
    ("general_influenza", "national_flu"),
    ("national_influenza", "general_flu"),
    ("national_covid", "national_pair"),
])
def test_existing_same_day_record_stops_duplicate(shortcut_page, existing_program, key, status):
    page = shortcut_page
    entry = _types(page, existing_program)[0]
    with connect(page._db_path) as connection:
        record = create_vaccine_record(connection, vaccine_type_id=entry.id,
                                       vaccine_type_name=entry.name, patient_chart_no="0000",
                                       patient_name="Test Patient", patient_resident_id="700101-1000000")
        if status == "completed":
            mark_vaccine_record_completed(connection, record.id)
        elif status == "cancelled":
            mark_vaccine_record_cancelled(connection, record.id)
    before = _records(page)
    page.run_vaccine_shortcut(key)
    _wait(page)
    if status == "cancelled":
        assert len(_records(page)) > 1
    else:
        assert _records(page) == before
        assert page.test_events == ["confirm", "fetch"]
        assert "Edit today's record" in page.status_label.text()
        assert page.edit_today_record_button.isEnabled()


def test_eligibility_rejection_keeps_form_without_print(shortcut_page, monkeypatch):
    page = shortcut_page
    monkeypatch.setattr(page, "_confirm_program_printing", lambda *_a: (False, False))
    page.run_vaccine_shortcut("national_flu")
    _wait(page)
    assert page.test_events[:2] == ["confirm", "fetch"]
    assert [e[0] for e in page.test_events[2:]] == ["entry"]
    assert _records(page)[0].status == "prepared"
    assert page.patient_name_input.text() == "Test Patient"
    assert page._session_reminder_started_at is None
    assert page.print_button.isEnabled()


@pytest.mark.parametrize("key,fail_on", [("national_flu", 1), ("national_pair", 1), ("national_pair", 2)])
def test_print_failure_keeps_record_after_lookup_without_charting(shortcut_page, monkeypatch, key, fail_on):
    page = shortcut_page
    attempts = []
    def print_label(*_a, **_kw):
        attempts.append(True)
        return VaccineLabelPrintResult(len(attempts) != fail_on, "Synthetic print failure")
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", print_label)
    page.run_vaccine_shortcut(key)
    _wait(page)
    assert len([e for e in page.test_events if isinstance(e, tuple) and e[0] == "entry"]) == fail_on
    assert not any(isinstance(e, tuple) and e[0] in {"copy", "charting"} for e in page.test_events)
    assert sum(r.status == "completed" for r in _records(page)) == fail_on - 1
    assert page.patient_name_input.text() == "Test Patient"
    assert "failure" in page.status_label.text()
    assert not page._shortcut_in_progress


def test_entry_failure_retains_form_and_retry_prints_only_after_success(shortcut_page, monkeypatch):
    page = shortcut_page
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda *_a, **_kw:
                        VaccineHandoffResult(False, "Synthetic entry failure"))
    page.run_vaccine_shortcut("national_flu")
    _wait(page)
    assert len(page._pending_handoffs) == 1
    assert page.patient_name_input.text() == "Test Patient"
    assert all(not b.isEnabled() for b in page.shortcut_buttons.values())
    assert page.retry_handoff_button.isEnabled()
    assert page.open_influenza_system_button.isEnabled()
    assert page.kdca_login_button.isEnabled()
    before = _records(page)
    assert all(r.status == "prepared" for r in before)
    assert not any(isinstance(e, tuple) and e[0] in {"print", "check", "copy", "charting"} for e in page.test_events)
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda *_a, **_kw:
                        VaccineHandoffResult(True, "Sent."))
    page.retry_handoff_button.click()
    _wait(page)
    after = _records(page)
    assert [r.id for r in after] == [r.id for r in before]
    assert all(r.status == "completed" for r in after)
    assert len([e for e in page.test_events if isinstance(e, tuple) and e[0] == "print"]) == 1
    assert page.patient_name_input.text() == ""


@pytest.mark.parametrize("key", ["national_flu", "national_covid", "national_pair"])
@pytest.mark.parametrize("accepted", [False, True])
def test_exception_review_is_after_lookup_and_before_print(shortcut_page, monkeypatch, key, accepted):
    page = shortcut_page
    monkeypatch.setattr(page, "_confirm_program_printing",
                        vaccine_tab.VaccineTab._confirm_program_printing.__get__(page))
    for name, result_type in (
        ("evaluate_influenza_program", InfluenzaEligibilityResult),
        ("evaluate_covid_program", CovidEligibilityResult),
    ):
        result = result_type(
            status="manual_verification_required", allowed=False,
            message="Synthetic exception review.", group_key=None, group_label=None,
            schedule_start=None, schedule_end=None, counted=False,
            today_count=0, daily_cap=100, remaining=100, requires_operator_confirmation=True,
        )
        monkeypatch.setattr(vaccine_tab, name, lambda *_a, result=result, **_kw: result)

    def confirm_exception(*args):
        assert page.test_events[-1][0] == "entry"
        assert "address" in args[2] and "qualifies for the exception" in args[2]
        assert args[-1] == QMessageBox.StandardButton.No
        assert not page.print_button.isEnabled()
        assert not page.fetch_button.isEnabled()
        assert not page.retry_handoff_button.isEnabled()
        assert not page.skip_handoff_button.isEnabled()
        page._start_handoff()
        page._skip_handoff()
        assert page._handoff_thread is None
        assert len(page._pending_handoffs) == 1
        assert not any(isinstance(e, tuple) and e[0] in {"copy", "charting"} for e in page.test_events)
        page.test_events.append(("exception", args[1]))
        return QMessageBox.StandardButton.Yes if accepted else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", confirm_exception)
    page.run_vaccine_shortcut(key)
    _wait(page)
    if accepted:
        total = 2 if key == "national_pair" else 1
        assert [e[0] for e in page.test_events[2:]] == ["entry", "exception", "print"] * total + ["copy", "charting"]
        assert all(r.status == "completed" and not r.counts_toward_cap for r in _records(page))
    else:
        assert [e[0] for e in page.test_events[2:]] == ["entry", "exception"]
        assert all(r.status == "prepared" for r in _records(page))
        assert page.patient_name_input.text() == "Test Patient"
    with connect(page._db_path) as connection:
        today = vaccine_tab.datetime.now().date().isoformat()
        assert get_today_vaccine_counts(connection, today) == {"flu": 0, "covid": 0}
        assert get_today_vaccine_exception_counts(connection, today) == {
            "flu": int(accepted and key != "national_covid"),
            "covid": int(accepted and key != "national_flu"),
        }


def test_pair_second_entry_failure_retries_only_second_lookup_and_label(shortcut_page, monkeypatch):
    page = shortcut_page
    attempts = []

    def enter(_s, request, **_kw):
        attempts.append(request.system)
        return VaccineHandoffResult(len(attempts) != 2, "Synthetic second entry failure")

    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    page.run_vaccine_shortcut("national_pair")
    _wait(page)
    assert attempts == ["influenza", "covid"]
    assert sorted(r.status for r in _records(page)) == ["completed", "prepared"]
    assert len([e for e in page.test_events if isinstance(e, tuple) and e[0] == "print"]) == 1
    assert not any(isinstance(e, tuple) and e[0] in {"copy", "charting"} for e in page.test_events)
    page.retry_handoff_button.click()
    _wait(page)
    assert attempts == ["influenza", "covid", "covid"]
    assert len([e for e in page.test_events if isinstance(e, tuple) and e[0] == "print"]) == 2
    assert all(r.status == "completed" for r in _records(page))
    assert page.test_events[-1][0] == "charting"


def test_cancel_after_entry_failure_never_prints_or_clears_patient(shortcut_page, monkeypatch):
    page = shortcut_page
    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", lambda *_a, **_kw:
                        VaccineHandoffResult(False, "Synthetic entry failure"))
    page.run_vaccine_shortcut("national_pair")
    _wait(page)
    assert page.skip_handoff_button.text() == "Cancel shortcut"
    page.skip_handoff_button.click()
    assert all(r.status == "prepared" for r in _records(page))
    assert page.patient_name_input.text() == "Test Patient"
    assert not page._pending_handoffs
    assert not page._shortcut_lookup_records
    assert page.fetch_button.isEnabled()
    assert page.skip_handoff_button.text() == "Skip and clear"
    assert page.test_events == ["confirm", "fetch"]


@pytest.mark.parametrize("interruption", ["stopped", "record_cancelled", "provider_error"])
def test_interrupted_lookup_does_not_print(shortcut_page, monkeypatch, interruption):
    page = shortcut_page

    def enter(*_a, **_kw):
        if interruption == "stopped":
            page._handoff_cancel.set()
        elif interruption == "record_cancelled":
            with connect(page._db_path) as connection:
                entry = list_vaccine_records(connection)[0]
                mark_vaccine_record_cancelled(connection, entry.id)
        else:
            raise RuntimeError("secret patient information")
        return VaccineHandoffResult(True, "Input sent")

    monkeypatch.setattr(vaccine_tab, "enter_vaccine_resident", enter)
    page.run_vaccine_shortcut("national_flu")
    _wait(page)
    assert page.test_events == ["confirm", "fetch"]
    assert all(r.status != "completed" for r in _records(page))
    assert page.patient_name_input.text() == "Test Patient"
    assert "secret" not in page.status_label.text()


def test_second_program_decline_preserves_first_completed_record(shortcut_page, monkeypatch):
    page = shortcut_page
    monkeypatch.setattr(page, "_confirm_program_printing", lambda record, *_a:
                        (record.program_type == "national_influenza", True))
    page.run_vaccine_shortcut("national_pair")
    _wait(page)
    assert [e[0] for e in page.test_events[2:]] == ["entry", "print", "entry"]
    records = {r.program_type: r for r in _records(page)}
    assert records["national_influenza"].status == "completed"
    assert records["national_covid"].status == "prepared"
    assert "1 label(s) completed" in page.status_label.text()
    assert page.charting_text_preview.toPlainText()
    assert not page._pending_handoffs
    assert not page._shortcut_lookup_records


def test_print_exception_after_lookup_is_redacted_and_does_not_chart(shortcut_page, monkeypatch):
    page = shortcut_page

    def fail(*_a, **_kw):
        raise RuntimeError("secret patient information")

    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", fail)
    page.run_vaccine_shortcut("national_flu")
    _wait(page)
    assert [e[0] for e in page.test_events[2:]] == ["entry", "check"]
    assert all(r.status == "prepared" for r in _records(page))
    assert not page._print_in_progress
    assert not page._shortcut_in_progress
    assert not page._pending_handoffs
    assert page.print_button.isEnabled()
    assert "secret" not in page.status_label.text()


@pytest.mark.parametrize("busy", ["_shortcut_in_progress", "_print_in_progress", "_session_reset_in_progress",
                                  "_kdca_thread", "_handoff_thread", "_pending_handoffs"])
def test_busy_shortcut_does_nothing(shortcut_page, busy):
    page = shortcut_page
    original = getattr(page, busy)
    setattr(page, busy, True)
    try:
        page.run_vaccine_shortcut("national_flu")
        assert page.test_events == []
        assert _records(page) == []
    finally:
        setattr(page, busy, original)


def test_confirmation_blocks_reentrant_operations(shortcut_page, monkeypatch):
    page = shortcut_page
    def confirm(_title, _choices):
        page.run_vaccine_shortcut("general_flu")
        assert not page.fetch_current_patient_from_emr()
        assert page.prepare_flu_and_covid() is None
        page.print_label()
        page.print_prepared_pair()
        assert not page.open_vaccine_system("general")
        page.reset_vaccine_sessions_now()
        assert not page._session_reset_in_progress
        assert not page.kdca_login_button.isEnabled()
        return None
    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", confirm)
    page.run_vaccine_shortcut("national_flu")
    assert page.test_events == []
    assert page.fetch_button.isEnabled()
    assert page.open_general_system_button.isEnabled()


def test_exception_restores_controls_without_exposing_patient_data(shortcut_page, monkeypatch):
    page = shortcut_page
    def fail(*_a):
        raise RuntimeError("secret patient information")
    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", fail)
    page.run_vaccine_shortcut("national_flu")
    assert not page._shortcut_in_progress
    assert all(b.isEnabled() for b in page.shortcut_buttons.values())
    assert "secret" not in page.status_label.text()
    assert _records(page) == []


def test_shortcut_keeps_real_program_configuration_guard(shortcut_page, monkeypatch):
    page = shortcut_page
    monkeypatch.setattr(page, "_confirm_program_printing",
                        vaccine_tab.VaccineTab._confirm_program_printing.__get__(page))
    page.run_vaccine_shortcut("national_flu")
    _wait(page)
    assert page.test_events[:2] == ["confirm", "fetch"]
    assert [e[0] for e in page.test_events[2:]] == ["entry"]
    assert not page._pending_handoffs
    assert _records(page)[0].status == "prepared"
    assert page._session_reminder_started_at is None


@pytest.mark.parametrize("product_code", ["covid-pfizer", "covid-moderna"])
def test_covid_shortcut_uses_explicitly_chosen_product(shortcut_page, monkeypatch, product_code):
    page = shortcut_page
    def confirm(_title, choices):
        return (next(entry for entry in choices[0] if entry.code == product_code),)
    monkeypatch.setattr(page, "_confirm_vaccine_shortcut", confirm)
    page.run_vaccine_shortcut("national_covid")
    _wait(page)
    expected = next(entry for entry in _types(page, "national_covid") if entry.code == product_code)
    assert _records(page)[0].vaccine_type_id == expected.id


@pytest.mark.parametrize("width,height", [(1280, 900), (1920, 1080)])
def test_shortcut_row_fits_desktop(shortcut_page, width, height):
    page = shortcut_page
    page.resize(width, height)
    page.ensurePolished()
    page.layout().activate()
    page.main_page.layout().activate()
    group = page.shortcut_buttons["national_flu"].parentWidget()
    group.layout().activate()
    previous_right = -1
    for button in page.shortcut_buttons.values():
        assert button.geometry().left() > previous_right
        assert button.geometry().right() < group.width()
        assert button.width() >= button.sizeHint().width()
        previous_right = button.geometry().right()
