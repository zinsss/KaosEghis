import os
from dataclasses import replace
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from KaosEghis.core.vaccine_patient_context import (
    VaccinePatientContext,
    VaccinePatientFetchResult,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    list_vaccine_records,
    mark_vaccine_record_completed,
)
from KaosEghis.ui.tabs import vaccine_tab


@pytest.fixture
def fetched_page(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    monkeypatch.setattr(
        vaccine_tab,
        "get_active_emr_target_profile",
        lambda _connection: SimpleNamespace(
            id=1,
            process_name="test-emr.exe",
            window_title_contains="Test EMR",
            executable_path="",
        ),
    )
    monkeypatch.setattr(vaccine_tab, "get_emr_ui_target_by_key", lambda *_args: None)
    context = VaccinePatientContext(
        chart_no="0000",
        resident_id="700101-1000000",
        patient_name="Test Patient",
        patient_sex="M",
        patient_age="56",
        patient_birth_date="1970-01-01",
        patient_phone="010-0000-0000",
        patient_address="Test Address",
    )
    monkeypatch.setattr(
        vaccine_tab,
        "fetch_vaccine_patient_context",
        lambda *_args: VaccinePatientFetchResult(True, "Fetched.", context),
    )
    page = vaccine_tab.VaccineTab(db_path)
    page._select_vaccine_type(None, "Influenza")
    assert page.fetch_current_patient_from_emr()
    yield page, context
    page.close()
    page.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("same_patient", [True, False])
@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("save_method", ["save_record", "_record_for_label_print"])
def test_successful_fetch_starts_new_record_without_changing_previous(
    fetched_page, monkeypatch, same_patient, completed, save_method
):
    page, context = fetched_page
    first = page.save_record()
    assert first is not None
    if completed:
        with connect(page._db_path) as connection:
            mark_vaccine_record_completed(connection, first.id)
    with connect(page._db_path) as connection:
        before = list_vaccine_records(connection)

    if not same_patient:
        context = replace(context, chart_no="0001", patient_name="Next Patient")
    monkeypatch.setattr(
        vaccine_tab,
        "fetch_vaccine_patient_context",
        lambda *_args: VaccinePatientFetchResult(True, "Fetched.", context),
    )
    page.influenza_check_result.setText("Previous flu check")
    page.covid_check_result.setText("Previous COVID check")

    assert page.fetch_current_patient_from_emr()

    assert page._current_record_id is None
    assert page._prepared_pair_ids is None
    assert page.vaccine_types_list.currentItem().text() == "Influenza"
    assert page.patient_chart_no_input.text() == context.chart_no
    assert f"Patient: {context.patient_name}" in page.label_preview.toPlainText()
    assert page.influenza_check_result.text() == "Influenza program: Not checked."
    assert page.covid_check_result.text() == "COVID program: Not checked."
    assert "New vaccine record ready." in page.status_label.text()
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before

    second = getattr(page, save_method)()
    assert second is not None
    assert second.id != first.id
    assert second.patient_chart_no == context.chart_no
    assert second.status == "prepared"
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == [second, *before]


def test_successful_fetch_detaches_prepared_pair(fetched_page):
    page, _context = fetched_page
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    assert page.prepare_flu_and_covid() is not None
    with connect(page._db_path) as connection:
        before = list_vaccine_records(connection)

    assert page.fetch_current_patient_from_emr()

    assert page._current_record_id is None
    assert page._prepared_pair_ids is None
    assert page.prepared_pair_label.text() == "Flu + COVID: Not prepared."
    page.print_prepared_pair()
    assert page.status_label.text() == "Prepare a Flu + COVID pair first."
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before


@pytest.mark.parametrize("failure", ["unavailable", "missing_context", "no_profile"])
def test_failed_fetch_preserves_form_record_and_pair(fetched_page, monkeypatch, failure):
    page, context = fetched_page
    page._select_vaccine_type(None, "COVID-19 (Pfizer)")
    pair = page.prepare_flu_and_covid()
    assert pair is not None
    pair_label = page.prepared_pair_label.text()
    preview = page.label_preview.toPlainText()
    page.influenza_check_result.setText("Previous flu check")
    page.covid_check_result.setText("Previous COVID check")
    with connect(page._db_path) as connection:
        before = list_vaccine_records(connection)
    monkeypatch.setattr(
        vaccine_tab,
        "fetch_vaccine_patient_context",
        lambda *_args: VaccinePatientFetchResult(
            failure == "missing_context", "Failed.", None
        ),
    )
    if failure == "no_profile":
        monkeypatch.setattr(vaccine_tab, "get_active_emr_target_profile", lambda _c: None)

    assert page.fetch_current_patient_from_emr() is False

    assert page._current_record_id == pair[0].id
    assert page._prepared_pair_ids == (pair[0].id, pair[1].id)
    assert page.prepared_pair_label.text() == pair_label
    assert page.patient_chart_no_input.text() == context.chart_no
    assert page.patient_resident_id_input.text() == context.resident_id
    assert page.patient_name_input.text() == context.patient_name
    assert page.patient_sex_input.text() == context.patient_sex
    assert page.patient_age_input.text() == context.patient_age
    assert page.patient_birth_date_input.text() == context.patient_birth_date
    assert page.patient_phone_input.text() == context.patient_phone
    assert page.patient_address_input.text() == context.patient_address
    assert page.label_preview.toPlainText() == preview
    assert page.influenza_check_result.text() == "Previous flu check"
    assert page.covid_check_result.text() == "Previous COVID check"
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == before
