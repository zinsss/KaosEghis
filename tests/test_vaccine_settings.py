import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _set_date(widget, value: str) -> None:
    from PySide6.QtCore import QDate

    widget.enabled_check.setChecked(True)
    widget.date_edit.setDate(QDate.fromString(value, "yyyy-MM-dd"))


def test_single_schedule_editor_loads_existing_settings(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "vaccine_schedule_rules_json": json.dumps(
                    {
                        "influenza": {
                            "season_name": "2027-2028",
                            "program_enabled": False,
                            "daily_cap": 88,
                            "elderly_75_plus_start": "2027-10-01",
                        },
                        "covid": {
                            "season_name": "2027",
                            "program_enabled": False,
                            "daily_cap": 25,
                        },
                    }
                ),
                "vaccine_age_groups_json": json.dumps(
                    [
                        {
                            "key": "elderly_75_plus",
                            "label": "Elderly 75+",
                            "vaccine": "influenza",
                            "birth_date_from": "1900-01-01",
                            "birth_date_to": "1952-12-31",
                        }
                    ]
                ),
            },
        )

    page = VaccineSettingsPage(db_path)

    assert page.influenza_editor.season_name_input.text() == "2027-2028"
    assert page.influenza_editor.daily_cap_input.value() == 88
    assert (
        page.influenza_editor.date_inputs["elderly_75_plus_start"].value()
        == "2027-10-01"
    )
    assert page.covid_editor.season_name_input.text() == "2027"
    assert page.covid_editor.daily_cap_input.value() == 25


def test_single_schedule_editor_saves_in_place_to_existing_settings(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    influenza = page.influenza_editor
    covid = page.covid_editor
    influenza.program_enabled_check.setChecked(False)
    influenza.season_name_input.setText("2027-2028")
    influenza.daily_cap_input.setValue(91)
    _set_date(influenza.date_inputs["elderly_75_plus_start"], "2027-10-02")
    covid.program_enabled_check.setChecked(False)
    covid.season_name_input.setText("2027")
    covid.daily_cap_input.setValue(37)

    assert page.save_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)
    schedules = json.loads(settings["vaccine_schedule_rules_json"])
    assert schedules["influenza"]["season_name"] == "2027-2028"
    assert schedules["influenza"]["elderly_75_plus_start"] == "2027-10-02"
    assert schedules["covid"]["season_name"] == "2027"
    assert settings["vaccine_influenza_daily_cap"] == "91"
    assert settings["vaccine_covid_daily_cap"] == "37"


def test_enabled_schedule_requires_complete_dates_and_birth_ranges(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    page.influenza_editor.program_enabled_check.setChecked(True)
    page.influenza_editor.date_inputs["elderly_75_plus_start"].set_value("")

    assert not page.save_settings()
    assert "Complete all program dates" in page.status_label.text()


def test_disabled_incomplete_schedule_can_be_saved_as_draft(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    page.influenza_editor.program_enabled_check.setChecked(False)
    page.influenza_editor.date_inputs["elderly_75_plus_start"].set_value("")

    assert page.save_settings()


def test_covid_editor_has_the_published_staged_age_group_schedule(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)

    covid = page.covid_editor
    assert covid.program_enabled_check.isChecked() is False
    assert covid.date_inputs["elderly_75_plus_start"].value() == "2026-10-12"
    assert covid.date_inputs["elderly_70_74_start"].value() == "2026-10-15"
    assert covid.date_inputs["elderly_65_69_start"].value() == "2026-10-19"
    assert covid.date_inputs["elderly_program_end"].value() == "2027-06-30"
    assert set(covid.birth_inputs) == {
        "covid_elderly_75_plus",
        "covid_elderly_70_74",
        "covid_elderly_65_69",
    }


def test_blank_existing_covid_draft_is_migrated_but_not_enabled(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "vaccine_schedule_rules_json": json.dumps(
                    {
                        "covid": {
                            "season_name": "2026-2027",
                            "program_start": "",
                            "program_end": "",
                            "daily_cap": 100,
                        }
                    }
                ),
                "vaccine_age_groups_json": json.dumps(
                    [
                        {
                            "key": "national_covid",
                            "vaccine": "covid",
                            "birth_date_from": "",
                            "birth_date_to": "",
                        }
                    ]
                ),
            },
        )

    initialize_database(db_path)
    with connect(db_path) as connection:
        settings = get_settings(connection)
    schedules = json.loads(settings["vaccine_schedule_rules_json"])
    groups = json.loads(settings["vaccine_age_groups_json"])

    assert schedules["covid"]["program_enabled"] is False
    assert schedules["covid"]["elderly_75_plus_start"] == "2026-10-12"
    assert schedules["covid"]["elderly_program_end"] == "2027-06-30"
    assert {group["key"] for group in groups} == {
        "covid_elderly_75_plus",
        "covid_elderly_70_74",
        "covid_elderly_65_69",
    }


def test_database_has_no_multi_year_vaccine_season_table(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'vaccine_program_seasons'"
        ).fetchone()
    assert table is None


def test_system_target_settings_load_captured_stable_selectors(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    targets = page.system_targets_editor

    assert page.tabs.tabText(2) == "System targets"
    assert targets.general_window_title_input.text() == "예방접종통합관리시스템"
    assert targets.general_window_class_input.text() == "CyWindowClass"
    assert targets.general_resident_x_input.value() == 448
    assert targets.general_resident_y_input.value() == 2074
    assert targets.general_keepalive_x_input.value() == 1154
    assert targets.general_keepalive_y_input.value() == 1968
    assert targets.influenza_resident_automation_id_input.text() == "edtPtntRrn1"
    assert targets.influenza_resident_x_input.value() == 2924
    assert targets.influenza_resident_y_input.value() == 1415
    assert targets.covid_window_title_input.text() == "코로나19통합관리시스템"
    assert targets.covid_window_class_input.text() == "CyWindowClass"
    assert targets.covid_resident_x_input.value() == 1466
    assert targets.covid_resident_y_input.value() == 2107
    assert targets.covid_keepalive_x_input.value() == 2456
    assert targets.covid_keepalive_y_input.value() == 1982


def test_system_target_settings_save_editable_stable_values_without_handle(
    tmp_path,
) -> None:
    _app()
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    targets = page.system_targets_editor
    targets.general_window_title_input.setText("Updated general system")
    targets.general_resident_x_input.setValue(100)
    targets.general_resident_y_input.setValue(200)
    targets.general_keepalive_x_input.setValue(201)
    targets.general_keepalive_y_input.setValue(202)
    targets.influenza_window_title_input.setText("Influenza browser")
    targets.influenza_resident_automation_id_input.setText("updatedResidentInput")
    targets.influenza_resident_x_input.setValue(300)
    targets.influenza_resident_y_input.setValue(400)
    targets.covid_keepalive_x_input.setValue(401)
    targets.covid_keepalive_y_input.setValue(402)

    assert page.save_settings()

    with connect(db_path) as connection:
        settings = get_settings(connection)
    assert settings["vaccine_general_system_window_title"] == "Updated general system"
    assert settings["vaccine_general_system_resident_x"] == "100"
    assert settings["vaccine_general_system_resident_y"] == "200"
    assert settings["vaccine_general_system_keepalive_x"] == "201"
    assert settings["vaccine_general_system_keepalive_y"] == "202"
    assert settings["vaccine_influenza_system_window_title"] == "Influenza browser"
    assert (
        settings["vaccine_influenza_system_resident_automation_id"]
        == "updatedResidentInput"
    )
    assert settings["vaccine_influenza_system_resident_x"] == "300"
    assert settings["vaccine_influenza_system_resident_y"] == "400"
    assert settings["vaccine_covid_system_keepalive_x"] == "401"
    assert settings["vaccine_covid_system_keepalive_y"] == "402"
    assert "1513248" not in settings.values()


def test_external_system_coordinate_migration_updates_only_old_seed_values(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "vaccine_general_system_resident_x": "443",
                "vaccine_general_system_resident_y": "2076",
                "vaccine_covid_system_resident_x": "0",
                "vaccine_covid_system_resident_y": "0",
            },
        )

    initialize_database(db_path)
    with connect(db_path) as connection:
        settings = get_settings(connection)
    assert settings["vaccine_general_system_resident_x"] == "448"
    assert settings["vaccine_general_system_resident_y"] == "2074"
    assert settings["vaccine_covid_system_resident_x"] == "1466"
    assert settings["vaccine_covid_system_resident_y"] == "2107"


def test_external_system_coordinate_migration_preserves_custom_values(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "vaccine_general_system_resident_x": "449",
                "vaccine_general_system_resident_y": "2074",
                "vaccine_covid_system_resident_x": "1466",
                "vaccine_covid_system_resident_y": "2107",
            },
        )

    initialize_database(db_path)
    with connect(db_path) as connection:
        settings = get_settings(connection)
    assert settings["vaccine_general_system_resident_x"] == "449"
    assert settings["vaccine_general_system_resident_y"] == "2074"
    assert settings["vaccine_covid_system_resident_x"] == "1466"
    assert settings["vaccine_covid_system_resident_y"] == "2107"
