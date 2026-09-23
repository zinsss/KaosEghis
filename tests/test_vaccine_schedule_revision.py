from copy import deepcopy
from datetime import date, timedelta
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from KaosEghis.core.vaccine_eligibility import (
    evaluate_covid_program_for_birth_date,
    evaluate_influenza_program_for_birth_date,
)
from KaosEghis.db.database import (
    _migrate_vaccine_september_2026_schedule_revision,
    connect, initialize_database,
)
from KaosEghis.db.repositories import DEFAULT_SETTINGS, get_settings, set_settings


def revised_schedules():
    return json.loads(DEFAULT_SETTINGS["vaccine_schedule_rules_json"])


def old_schedules():
    schedules = revised_schedules()
    for section in schedules.values():
        section.pop("schedule_notice_revision")
        section.update({
            "program_enabled": True,
            "elderly_75_plus_start": "2026-10-12",
            "elderly_70_74_start": "2026-10-15",
            "elderly_65_69_start": "2026-10-19",
        })
    schedules["influenza"]["child_one_dose_start"] = "2026-09-28"
    return schedules


def store_schedules(connection, schedules):
    set_settings(connection, {"vaccine_schedule_rules_json": json.dumps(schedules)})


def stored_schedules(connection):
    return json.loads(get_settings(connection)["vaccine_schedule_rules_json"])


def test_new_defaults_match_the_september_amendment_without_auto_enabling():
    schedules = revised_schedules()
    flu, covid = schedules["influenza"], schedules["covid"]
    assert [flu[key] for key in ("elderly_75_plus_start", "elderly_70_74_start", "elderly_65_69_start")] == [
        "2026-10-06", "2026-10-12", "2026-10-15",
    ]
    assert flu["child_one_dose_start"] == flu["child_two_dose_start"] == "2026-09-21"
    assert [covid[key] for key in ("elderly_75_plus_start", "elderly_70_74_start", "elderly_65_69_start")] == [
        "2026-10-12", "2026-10-12", "2026-10-15",
    ]
    assert flu["program_enabled"] is covid["program_enabled"] is False
    assert flu["daily_cap"] == covid["daily_cap"] == 100
    assert flu["elderly_program_end"] == "2027-04-30"
    assert covid["elderly_program_end"] == "2027-06-30"


def test_existing_dates_amended_once_preserving_custom_data_and_counts(tmp_path):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    schedules = old_schedules()
    schedules["influenza"]["daily_cap"] = 87
    schedules["influenza"]["allow_rural_exception"] = False
    schedules["covid"]["custom_note"] = "retained"
    with connect(path) as con:
        store_schedules(con, schedules)
        set_settings(con, {"vaccine_age_groups_json": '[{"custom":true}]', "vaccine_label_printer_name": "Custom printer"})
        previous_records = con.execute("SELECT * FROM vaccine_records").fetchall()
    initialize_database(path)
    with connect(path) as con:
        updated = stored_schedules(con)
        expected = deepcopy(schedules)
        for program in expected:
            defaults = revised_schedules()[program]
            for key in ("elderly_75_plus_start", "elderly_70_74_start", "elderly_65_69_start", "child_one_dose_start"):
                if key in defaults:
                    expected[program][key] = defaults[key]
            expected[program]["schedule_notice_revision"] = defaults["schedule_notice_revision"]
            expected[program]["program_enabled"] = False
        assert updated == expected
        assert con.execute("SELECT * FROM vaccine_records").fetchall() == previous_records
        settings = get_settings(con)
        assert settings["vaccine_age_groups_json"] == '[{"custom":true}]'
        assert settings["vaccine_label_printer_name"] == "Custom printer"

        # Later operator changes are not reapplied or disabled on every startup.
        updated["covid"]["program_enabled"] = True
        updated["covid"]["elderly_70_74_start"] = "2026-10-15"
        store_schedules(con, updated)
    initialize_database(path)
    with connect(path) as con:
        assert stored_schedules(con) == updated


def test_revision_leaves_other_seasons_and_unknown_custom_dates_unchanged(tmp_path):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    schedules = old_schedules()
    schedules["influenza"]["season_name"] = "2027-2028"
    schedules["covid"]["elderly_70_74_start"] = "2026-10-09"
    schedules["covid"]["elderly_65_69_start"] = "2026-10-10"
    with connect(path) as con:
        store_schedules(con, schedules)
        _migrate_vaccine_september_2026_schedule_revision(con)
        assert stored_schedules(con) == schedules


def test_partial_custom_schedule_preserves_custom_field_but_requires_review(tmp_path):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    schedules = old_schedules()
    schedules["influenza"]["elderly_75_plus_start"] = "2026-10-07"
    schedules["influenza"]["elderly_70_74_start"] = "20261015"
    with connect(path) as con:
        store_schedules(con, schedules)
        _migrate_vaccine_september_2026_schedule_revision(con)
        flu = stored_schedules(con)["influenza"]
        assert flu["elderly_75_plus_start"] == "2026-10-07"
        assert flu["elderly_70_74_start"] == "2026-10-12"
        assert flu["program_enabled"] is False


@pytest.mark.parametrize("legacy_exception", [False, True])
def test_disabling_for_review_preserves_legacy_exception_option_across_restarts(tmp_path, legacy_exception):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    schedules = old_schedules()
    for section in schedules.values():
        section.pop("allow_rural_exception")
        section["allow_elderly_exception"] = legacy_exception
    with connect(path) as con:
        store_schedules(con, schedules)
    initialize_database(path)
    initialize_database(path)
    with connect(path) as con:
        for section in stored_schedules(con).values():
            assert section["allow_rural_exception"] is legacy_exception
            assert section["program_enabled"] is False


@pytest.mark.parametrize("raw", ['invalid JSON', '[]', 'null', '{"influenza":null}', '{"influenza":[]}'])
def test_invalid_or_missing_sections_are_not_replaced_with_defaults(tmp_path, raw):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    with connect(path) as con:
        set_settings(con, {"vaccine_schedule_rules_json": raw})
        _migrate_vaccine_september_2026_schedule_revision(con)
        assert get_settings(con)["vaccine_schedule_rules_json"] == raw


def elderly_groups(program):
    groups = json.loads(DEFAULT_SETTINGS["vaccine_age_groups_json"])
    groups = [g for g in groups if g["vaccine"] == "covid"]
    if program == "influenza":
        for group in groups:
            group["vaccine"] = "influenza"
            group["key"] = group["key"].removeprefix("covid_")
    return groups


@pytest.mark.parametrize("program,birth,opening", [
    ("influenza", date(1951, 12, 31), date(2026, 10, 6)),
    ("influenza", date(1952, 1, 1), date(2026, 10, 12)),
    ("influenza", date(1957, 1, 1), date(2026, 10, 15)),
    ("covid", date(1951, 12, 31), date(2026, 10, 12)),
    ("covid", date(1952, 1, 1), date(2026, 10, 12)),
    ("covid", date(1957, 1, 1), date(2026, 10, 15)),
])
def test_revised_standard_windows_and_caps(program, birth, opening):
    evaluate = evaluate_influenza_program_for_birth_date if program == "influenza" else evaluate_covid_program_for_birth_date
    schedule = revised_schedules()[program]
    args = (schedule, elderly_groups(program), birth)
    before = evaluate(*args, on_date=opening - timedelta(days=1), rural_exception_checked=False)
    at_start = evaluate(*args, on_date=opening, rural_exception_checked=False, counted_today=99)
    at_cap = evaluate(*args, on_date=opening, rural_exception_checked=False, counted_today=100)
    assert before.status == "blocked"
    assert not before.allowed
    assert at_start.allowed and at_start.counted
    assert at_cap.status == "cap_reached"


def test_children_no_longer_have_an_early_two_dose_only_window():
    groups = [{
        "key": key, "label": "Child", "vaccine": "influenza",
        "birth_date_from": "2012-01-01", "birth_date_to": "2026-08-31",
    } for key in ("child_one_dose", "child_two_dose")]
    args = (revised_schedules()["influenza"], groups, date(2020, 1, 1))
    before = evaluate_influenza_program_for_birth_date(*args, on_date=date(2026, 9, 20))
    at_start = evaluate_influenza_program_for_birth_date(*args, on_date=date(2026, 9, 21))
    at_cap = evaluate_influenza_program_for_birth_date(*args, on_date=date(2026, 9, 21), counted_today=100)
    assert before.status == "blocked"
    assert at_start.allowed and not at_start.requires_operator_confirmation
    assert at_start.counted
    assert at_cap.status == "cap_reached"


@pytest.mark.parametrize("birth,day,status,counted", [
    (date(1950, 1, 1), date(2026, 10, 5), "blocked", False),
    (date(1950, 1, 1), date(2026, 10, 6), "cap_reached", True),
    (date(1953, 1, 1), date(2026, 10, 6), "review_required", False),
    (date(1958, 1, 1), date(2026, 10, 6), "review_required", False),
    (date(1953, 1, 1), date(2026, 10, 12), "cap_reached", True),
    (date(1958, 1, 1), date(2026, 10, 12), "review_required", False),
    (date(1958, 1, 1), date(2026, 10, 15), "cap_reached", True),
])
def test_flu_exception_and_cap_stages_follow_revised_dates(birth, day, status, counted):
    result = evaluate_influenza_program_for_birth_date(
        revised_schedules()["influenza"], elderly_groups("influenza"), birth,
        on_date=day, counted_today=100, rural_exception_checked=True,
    )
    assert result.status == status
    assert result.counted is counted
    assert result.requires_operator_confirmation == (status == "review_required")


def test_settings_show_amended_dates_and_review_notice(tmp_path):
    from PySide6.QtWidgets import QApplication
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    with connect(path) as con:
        store_schedules(con, old_schedules())
    page = VaccineSettingsPage(path)
    assert page.influenza_editor.date_inputs["elderly_75_plus_start"].value() == "2026-10-06"
    assert page.influenza_editor.date_inputs["child_one_dose_start"].value() == "2026-09-21"
    assert page.covid_editor.date_inputs["elderly_70_74_start"].value() == "2026-10-12"
    assert not page.influenza_editor.program_enabled_check.isChecked()
    assert "2026-09-16" in page.influenza_editor.schedule_notice_label.text()
    assert "Review" in page.covid_editor.schedule_notice_label.text()
    page.covid_editor.program_enabled_check.setChecked(True)
    assert page.save_settings()
    assert "Schedule enabled" in page.covid_editor.schedule_notice_label.text()
    page.close()
    app.processEvents()
