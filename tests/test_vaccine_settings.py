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
