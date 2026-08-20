import json
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_vaccine_season_table_is_created_and_legacy_settings_are_seeded(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import list_vaccine_program_seasons

    db_path = tmp_path / "KaosEghis.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (
                "vaccine_schedule_rules_json",
                json.dumps(
                    {
                        "influenza": {
                            "season_name": "2028-2029",
                            "program_enabled": True,
                            "elderly_75_plus_start": "2028-10-01",
                            "daily_cap": 88,
                        },
                        "covid": {
                            "season_name": "2028-2029",
                            "program_enabled": False,
                            "program_start": "2028-10-01",
                            "daily_cap": 40,
                        },
                    }
                ),
            ),
        )
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (
                "vaccine_age_groups_json",
                json.dumps(
                    [
                        {
                            "key": "elderly_75_plus",
                            "label": "Elderly 75+",
                            "vaccine": "influenza",
                            "birth_date_from": "19000101",
                            "birth_date_to": "19531231",
                        }
                    ]
                ),
            ),
        )
        connection.commit()

    initialize_database(db_path)
    with connect(db_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'vaccine_program_seasons'"
        ).fetchone()
        influenza = list_vaccine_program_seasons(connection, "influenza")
        covid = list_vaccine_program_seasons(connection, "covid")

    assert table is not None
    assert len(influenza) == 1
    assert influenza[0].season_name == "2028-2029"
    assert influenza[0].is_active is True
    assert influenza[0].daily_cap == 88
    assert influenza[0].age_groups[0]["key"] == "elderly_75_plus"
    assert len(covid) == 1
    assert covid[0].is_active is False


def test_vaccine_season_crud_and_next_year_duplication(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_program_season,
        delete_vaccine_program_season,
        duplicate_vaccine_program_season,
        get_active_vaccine_program_season,
        list_vaccine_program_seasons,
        update_vaccine_program_season,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        created = create_vaccine_program_season(
            connection,
            program="influenza",
            season_name="2030-2031",
            daily_cap=95,
            schedule={
                "elderly_75_plus_start": "2030-10-01",
                "elderly_program_end": "2031-04-30",
            },
            age_groups=[
                {
                    "key": "elderly_75_plus",
                    "label": "Elderly 75+",
                    "birth_date_from": "1900-01-01",
                    "birth_date_to": "1955-12-31",
                }
            ],
            is_active=True,
        )
        duplicate = duplicate_vaccine_program_season(connection, created.id)
        active_before = get_active_vaccine_program_season(connection, "influenza")
        activated = update_vaccine_program_season(
            connection,
            duplicate.id,
            season_name=duplicate.season_name,
            daily_cap=duplicate.daily_cap,
            schedule=duplicate.schedule,
            age_groups=duplicate.age_groups,
            is_active=True,
        )
        active_after = get_active_vaccine_program_season(connection, "influenza")
        deleted = delete_vaccine_program_season(connection, created.id)
        listed = list_vaccine_program_seasons(connection, "influenza")

    assert duplicate.season_name == "2031-2032"
    assert duplicate.is_active is False
    assert duplicate.schedule["elderly_75_plus_start"] == "2031-10-01"
    assert duplicate.schedule["elderly_program_end"] == "2032-04-30"
    assert duplicate.age_groups[0]["birth_date_to"] == "1956-12-31"
    assert active_before is not None and active_before.id == created.id
    assert activated is not None and activated.is_active is True
    assert active_after is not None and active_after.id == duplicate.id
    assert sum(season.is_active for season in listed) == 1
    assert deleted is True


def test_active_vaccine_seasons_sync_to_eligibility_settings(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_program_season,
        get_settings,
        sync_active_vaccine_seasons_to_settings,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_vaccine_program_season(
            connection,
            program="influenza",
            season_name="2032-2033",
            daily_cap=77,
            schedule={"elderly_75_plus_start": "2032-10-01"},
            age_groups=[
                {
                    "key": "elderly_75_plus",
                    "label": "Elderly 75+",
                    "birth_date_from": "1900-01-01",
                    "birth_date_to": "1957-12-31",
                }
            ],
            is_active=True,
        )
        sync_active_vaccine_seasons_to_settings(connection)
        settings = get_settings(connection)

    schedules = json.loads(settings["vaccine_schedule_rules_json"])
    groups = json.loads(settings["vaccine_age_groups_json"])
    assert schedules["influenza"]["season_name"] == "2032-2033"
    assert schedules["influenza"]["program_enabled"] is True
    assert settings["vaccine_influenza_daily_cap"] == "77"
    assert [group["key"] for group in groups if group["vaccine"] == "influenza"] == [
        "elderly_75_plus"
    ]


def test_vaccine_settings_page_has_separate_multi_year_editors(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)

    assert page.tabs.count() == 2
    assert page.tabs.tabText(0) == "Influenza schedules"
    assert page.tabs.tabText(1) == "COVID schedules"
    assert page.influenza_editor.season_combo.count() == 1
    assert page.covid_editor.season_combo.count() == 1
    assert page.influenza_editor.duplicate_button.text() == "Duplicate next season"


def test_structured_influenza_editor_saves_active_season(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_active_vaccine_program_season
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    editor = page.influenza_editor
    editor.season_name_input.setText("2026-2027")
    editor.daily_cap_input.setValue(100)
    editor.active_check.setChecked(True)
    for key, date_input in editor.date_inputs.items():
        date_input.set_value("2027-04-30" if key.endswith("end") else "2026-09-01")
    ranges = {
        "elderly_75_plus": ("1900-01-01", "1951-12-31"),
        "elderly_70_74": ("1952-01-01", "1956-12-31"),
        "elderly_65_69": ("1957-01-01", "1961-12-31"),
        "child_two_dose": ("2020-01-01", "2026-08-31"),
    }
    for key, (lower, upper) in editor.birth_inputs.items():
        lower.set_value(ranges[key][0])
        upper.set_value(ranges[key][1])

    assert editor.save_season() is True

    with connect(db_path) as connection:
        active = get_active_vaccine_program_season(connection, "influenza")
    assert active is not None
    assert active.season_name == "2026-2027"
    assert active.daily_cap == 100
    assert active.schedule["program_enabled"] is True


def test_active_season_requires_complete_dates_and_birth_ranges(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_settings_page import VaccineSettingsPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineSettingsPage(db_path)
    editor = page.influenza_editor
    editor.active_check.setChecked(True)

    assert editor.save_season() is False
    assert "Complete all" in editor.status_label.text()
    assert "before activating" in editor.status_label.text()
