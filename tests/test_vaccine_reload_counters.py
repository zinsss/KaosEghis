from datetime import datetime
import sqlite3

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import connect
from KaosEghis.db.repositories import (
    create_vaccine_record,
    list_vaccine_records,
    mark_vaccine_record_cancelled,
    mark_vaccine_record_completed,
    mark_vaccine_record_printed,
    set_settings,
)
from KaosEghis.ui.tabs import vaccine_tab


TODAY = "2026-10-10"
PATIENT_FIELDS = (
    "chart_no", "resident_id", "name", "sex", "age", "birth_date", "phone", "address",
)


@pytest.fixture
def page(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 10, 10, 12)

    monkeypatch.setattr(vaccine_tab, "datetime", Clock)
    app = QApplication.instance() or QApplication([])
    panel = vaccine_tab.VaccineTab(tmp_path / "synthetic.sqlite")
    panel.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    yield panel
    panel.close()
    panel.deleteLater()
    app.processEvents()


def complete(connection, program, *, counted=True, day=TODAY, name="Synthetic vaccine"):
    record = create_vaccine_record(
        connection, vaccine_type_id=None, vaccine_type_name=name, program_type=program,
    )
    return mark_vaccine_record_completed(
        connection, record.id, counts_toward_cap=counted,
        completed_at=f"{day}T09:00:00+09:00",
    )


def counter_texts(page):
    return page.today_influenza_count_label.text(), page.today_covid_count_label.text()


def assert_counts(page, flu, covid, flu_exceptions, covid_exceptions, caps=(100, 100)):
    assert counter_texts(page) == (
        f"Influenza today: {flu}\u00a0/\u00a0{caps[0]}\n\uc608\uc678: {flu_exceptions}",
        f"COVID-19 today: {covid}\u00a0/\u00a0{caps[1]}\n\uc608\uc678: {covid_exceptions}",
    )


def form_state(page):
    return (
        tuple(getattr(page, f"patient_{name}_input").text() for name in PATIENT_FIELDS),
        page.vaccine_types_combo.currentIndex(),
        page.vaccine_types_combo.currentData(),
        page.vaccine_types_combo.currentText(),
        page._current_record_id,
        page._prepared_pair_ids,
        page.prepared_pair_label.text(),
        page.record_state_label.text(),
        page.rural_exception_check.isChecked(),
        page.influenza_check_result.text(),
        page.covid_check_result.text(),
        page.chart_note_preview.toPlainText(),
        page.charting_text_preview.toPlainText(),
        page.label_preview.toPlainText(),
        page.records_table.currentRow(),
        page.records_table.rowCount(),
        tuple(action.text() for action in page.edit_today_record_menu.actions()),
    )


def test_button_requeries_today_totals_and_exceptions_with_existing_rules(page):
    assert_counts(page, 0, 0, 0, 0)
    assert page.reload_counters_button.text() == "Reload counters"
    assert not page.reload_counters_button.icon().isNull()
    with connect(page._db_path) as connection:
        set_settings(connection, {
            "vaccine_influenza_daily_cap": "80", "vaccine_covid_daily_cap": "90",
        })
        complete(connection, "national_influenza")
        complete(connection, "national_influenza", counted=False)
        for product in ("Pfizer", "Moderna"):
            complete(connection, "national_covid", name=f"COVID-19 ({product})")
            complete(connection, "national_covid", counted=False, name=f"COVID-19 ({product})")
        for program in ("national_influenza", "national_covid"):
            for day in ("2026-10-09", "2026-10-11"):
                for counted in (True, False):
                    complete(connection, program, day=day, counted=counted)
            for counted in (True, False):
                cancelled = complete(connection, program, counted=counted)
                mark_vaccine_record_cancelled(connection, cancelled.id)
            for printed in (False, True):
                record = create_vaccine_record(
                    connection, vaccine_type_id=None, vaccine_type_name="Not completed",
                    program_type=program,
                )
                if printed:
                    mark_vaccine_record_printed(connection, record.id)
        for program in ("general", "general_influenza"):
            complete(connection, program, counted=False)
        before = list_vaccine_records(connection)

    page.reload_counters_button.click()

    assert_counts(page, 1, 2, 1, 2, caps=(80, 90))
    assert page.status_label.text() == "Today's vaccine counters reloaded."
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before


@pytest.mark.parametrize("state", ["unselected", "selected", "saved", "pair"])
def test_reload_preserves_form_selection_record_and_previews(page, monkeypatch, state):
    for name, value in zip(PATIENT_FIELDS, (
        "0000", "700101-1000000", "Synthetic Patient", "M", "56", "1970-01-01",
        "010-0000-0000", "Synthetic address",
    )):
        getattr(page, f"patient_{name}_input").setText(value)
    if state != "unselected":
        page._select_vaccine_type(None, "COVID-19 (Moderna)")
        assert page.vaccine_types_combo.currentIndex() >= 0
    if state == "saved":
        with connect(page._db_path) as connection:
            record = create_vaccine_record(
                connection, vaccine_type_id=page.vaccine_types_combo.currentData(),
                vaccine_type_name=page.vaccine_types_combo.currentText(),
                patient_chart_no="0000", patient_name="Synthetic Patient",
            )
        page._current_record_id = record.id
        page._populate_records(page.records_table, [record])
        page.records_table.selectRow(0)
    elif state == "pair":
        assert page.prepare_flu_and_covid() is not None
    page.patient_phone_input.setText("010-0000-9999")
    page.rural_exception_check.setChecked(False)
    page.influenza_check_result.setText("Existing flu check")
    page.covid_check_result.setText("Existing COVID check")
    before = form_state(page)
    with connect(page._db_path) as connection:
        complete(connection, "national_influenza")
        complete(connection, "national_covid", counted=False)
        records_before = list_vaccine_records(connection)

    def forbidden():
        pytest.fail("Counter reload must not refresh the whole page")

    monkeypatch.setattr(page, "refresh_view", forbidden)
    page.reload_counters_button.click()

    assert_counts(page, 1, 0, 0, 1)
    assert form_state(page) == before
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == records_before


def test_repeated_reload_reflects_cancellations_and_zero_counts(page):
    with connect(page._db_path) as connection:
        records = [
            complete(connection, program, counted=counted)
            for program in ("national_influenza", "national_covid")
            for counted in (True, False)
        ]
    page.reload_counters_button.click()
    assert_counts(page, 1, 1, 1, 1)
    with connect(page._db_path) as connection:
        for record in records:
            mark_vaccine_record_cancelled(connection, record.id)

    page.reload_counters_button.click()

    assert_counts(page, 0, 0, 0, 0)


def test_reload_uses_current_day_at_click_time(page, monkeypatch):
    with connect(page._db_path) as connection:
        complete(connection, "national_influenza")
        complete(connection, "national_covid", counted=False, day="2026-10-11")
    page.reload_counters_button.click()
    assert_counts(page, 1, 0, 0, 0)
    monkeypatch.setattr(vaccine_tab.datetime, "now", lambda: datetime(2026, 10, 11))

    page.reload_counters_button.click()

    assert_counts(page, 0, 0, 0, 1)


@pytest.mark.parametrize("failure_stage", [
    "connect", "get_settings", "get_today_vaccine_counts", "get_today_vaccine_exception_counts",
])
def test_database_failure_preserves_both_counters_and_form_then_allows_retry(
    page, monkeypatch, failure_stage,
):
    page.patient_name_input.setText("Synthetic Patient")
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    assert page.save_record() is not None
    with connect(page._db_path) as connection:
        complete(connection, "national_influenza")
        complete(connection, "national_covid", counted=False)
    page.reload_counters_button.click()
    assert_counts(page, 1, 0, 0, 1)
    old_counts, old_form = counter_texts(page), form_state(page)
    with connect(page._db_path) as connection:
        complete(connection, "national_influenza")
        complete(connection, "national_covid")
        complete(connection, "national_influenza", counted=False)
        records_before = list_vaccine_records(connection)

    opened = []

    def fail(*args):
        if failure_stage != "connect":
            opened.append(args[0])
        raise sqlite3.OperationalError("Synthetic sensitive database error")

    with monkeypatch.context() as patch:
        patch.setattr(vaccine_tab, failure_stage, fail)
        page.reload_counters_button.click()

    assert counter_texts(page) == old_counts
    assert form_state(page) == old_form
    assert page.status_label.text() == (
        "Could not reload vaccine counters from the database. Previous counts retained."
    )
    assert page.reload_counters_button.isEnabled()
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == records_before

    page.reload_counters_button.click()
    assert_counts(page, 2, 1, 1, 1)
    assert form_state(page) == old_form
    assert page.status_label.text() == "Today's vaccine counters reloaded."
