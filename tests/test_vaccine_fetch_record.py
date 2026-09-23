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
    create_vaccine_record,
    delete_vaccine_record,
    get_today_vaccine_counts,
    get_vaccine_record,
    list_patient_vaccine_records_for_date,
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


@pytest.mark.parametrize("completed", [False, True])
def test_today_record_menu_explicitly_edits_existing_record(fetched_page, completed):
    page, _context = fetched_page
    first = page.save_record()
    with connect(page._db_path) as connection:
        if completed:
            first = mark_vaccine_record_completed(connection, first.id)
        counts = get_today_vaccine_counts(connection, first.completed_on or "")

    assert page.fetch_current_patient_from_emr()
    assert page._current_record_id is None
    assert page.record_state_label.text() == "New vaccine record"
    assert not page.edit_today_record_button.isHidden()
    actions = page.edit_today_record_menu.actions()
    assert len(actions) == 1
    assert actions[0].data() == first.id
    assert first.vaccine_type_name in actions[0].text()
    assert first.status in actions[0].text()

    actions[0].trigger()

    assert page._current_record_id == first.id
    assert page.record_state_label.text() == f"Vaccine record #{first.id}"
    page.patient_phone_input.setText("010-0000-9999")
    saved = page.save_record()
    assert saved.id == first.id
    assert saved.patient_phone == "010-0000-9999"
    assert saved.status == first.status
    assert saved.completed_on == first.completed_on
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == [saved]
        assert get_today_vaccine_counts(connection, first.completed_on or "") == counts

    page.start_new_vaccine_record()
    assert page._current_record_id is None
    assert page.record_state_label.text() == "New vaccine record"
    assert not page.edit_today_record_button.isHidden()


def test_today_record_menu_lists_both_vaccinations_and_loads_chosen_one(fetched_page):
    page, _context = fetched_page
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    flu, covid = page.prepare_flu_and_covid()

    assert page.fetch_current_patient_from_emr()
    actions = page.edit_today_record_menu.actions()
    assert [action.data() for action in actions] == [covid.id, flu.id]
    actions[0].trigger()

    assert page._current_record_id == covid.id
    assert page._prepared_pair_ids is None
    assert page.vaccine_types_list.currentItem().text() == covid.vaccine_type_name
    page.patient_phone_input.setText("010-0000-9999")
    page.save_record()
    with connect(page._db_path) as connection:
        assert len(list_vaccine_records(connection)) == 2
        assert get_vaccine_record(connection, flu.id) == flu


@pytest.mark.parametrize("change", ["patient", "date", "deleted"])
def test_today_record_menu_revalidates_before_loading(fetched_page, change):
    page, _context = fetched_page
    record = page.save_record()
    assert page.fetch_current_patient_from_emr()
    if change == "patient":
        page.patient_chart_no_input.setText("0001")
        assert page.edit_today_record_button.isHidden()
    else:
        with connect(page._db_path) as connection:
            if change == "deleted":
                delete_vaccine_record(connection, record.id)
            else:
                connection.execute(
                    "UPDATE vaccine_records SET created_at = '2000-01-01 12:00:00' WHERE id = ?",
                    (record.id,),
                )
                connection.commit()

    page._edit_today_record(record.id)

    assert page._current_record_id is None
    assert page.edit_today_record_button.isHidden()
    assert "no longer matches" in page.status_label.text()


def test_today_record_menu_hidden_without_matches_and_after_clear(fetched_page):
    page, _context = fetched_page
    assert page.edit_today_record_button.isHidden()
    page.save_record()
    assert not page.edit_today_record_button.isHidden()
    page.clear_form()
    assert page.edit_today_record_button.isHidden()
    assert page.edit_today_record_menu.actions() == []


def test_today_record_button_refreshes_and_opens_menu(fetched_page, monkeypatch):
    page, _context = fetched_page
    popups = []
    monkeypatch.setattr(page.edit_today_record_menu, "popup", popups.append)
    page.edit_today_record_button.click()
    assert popups == []
    saved = page.save_record()
    page.edit_today_record_button.click()
    assert len(popups) == 1
    assert [action.data() for action in page.edit_today_record_menu.actions()] == [saved.id]


def test_patient_date_lookup_is_exact_readonly_and_uses_local_creation_date(tmp_path):
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        records = []
        for chart, local_time in (
            ("0000", "2026-09-21 00:05:00"),
            ("0000", "2026-09-20 23:55:00"),
            ("0000", "2026-09-22 00:05:00"),
            ("00001", "2026-09-21 00:05:00"),
            ("0", "2026-09-21 00:05:00"),
            (None, "2026-09-21 00:05:00"),
        ):
            record = create_vaccine_record(
                connection,
                vaccine_type_id=None,
                vaccine_type_name="Test Vaccine",
                patient_chart_no=chart,
                patient_name="Same Name",
            )
            connection.execute(
                "UPDATE vaccine_records SET created_at = datetime(?, 'utc') WHERE id = ?",
                (local_time, record.id),
            )
            records.append(record)
        connection.commit()
        changes = connection.total_changes

        matches = list_patient_vaccine_records_for_date(connection, " 0000 ", "2026-09-21")

        assert [record.id for record in matches] == [records[0].id]
        assert list_patient_vaccine_records_for_date(connection, "", "2026-09-21") == []
        assert connection.total_changes == changes


def test_patient_date_lookup_uses_completion_date_over_creation_date(tmp_path):
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        record = create_vaccine_record(
            connection,
            vaccine_type_id=None,
            vaccine_type_name="Test Vaccine",
            patient_chart_no="0000",
        )
        connection.execute(
            "UPDATE vaccine_records SET created_at = datetime(?, 'utc') WHERE id = ?",
            ("2026-09-20 12:00:00", record.id),
        )
        mark_vaccine_record_completed(connection, record.id, completed_at="2026-09-21T12:00:00")

        assert [r.id for r in list_patient_vaccine_records_for_date(
            connection, "0000", "2026-09-21"
        )] == [record.id]
        assert list_patient_vaccine_records_for_date(connection, "0000", "2026-09-20") == []
