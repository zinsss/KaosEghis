import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_vaccine_tables_and_seed_types_are_created(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, list_vaccine_types

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        vaccine_types = list_vaccine_types(connection)
        settings = get_settings(connection)

    assert "vaccine_types" in tables
    assert "vaccine_records" in tables
    assert [entry.name for entry in vaccine_types[:2]] == ["Influenza", "COVID-19"]
    assert '"influenza"' in settings["vaccine_schedule_rules_json"]
    assert '"elderly_75_plus"' in settings["vaccine_age_groups_json"]


def test_vaccine_type_and_record_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        create_vaccine_type,
        delete_vaccine_record,
        delete_vaccine_type,
        get_vaccine_record,
        list_vaccine_records,
        list_vaccine_types,
        reorder_vaccine_types,
        update_vaccine_record,
        update_vaccine_type,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        vaccine_type = create_vaccine_type(
            connection,
            name="Tdap",
            code="tdap",
            chart_note_template="Tdap 시행함.",
        )
        updated_type = update_vaccine_type(
            connection,
            vaccine_type.id,
            name="Tdap Updated",
            code="tdap2",
            chart_note_template="Tdap updated.",
            is_active=False,
        )
        ordered = reorder_vaccine_types(
            connection,
            [entry.id for entry in reversed(list_vaccine_types(connection))],
        )
        record = create_vaccine_record(
            connection,
            vaccine_type_id=vaccine_type.id,
            vaccine_type_name="Tdap Updated",
            patient_chart_no="2735",
            patient_resident_id="700101-1234567",
            patient_name="홍길동",
            patient_sex="M",
            patient_age="56",
            patient_phone="010-1111-2222",
            patient_address="Seoul",
        )
        updated_record = update_vaccine_record(
            connection,
            record.id,
            vaccine_type_id=vaccine_type.id,
            vaccine_type_name="Tdap Updated",
            patient_chart_no="2735",
            patient_resident_id="700101-1234567",
            patient_name="김민수",
            patient_sex="M",
            patient_age="57",
            patient_phone="010-3333-4444",
            patient_address="Busan",
            status="prepared",
        )
        listed_records = list_vaccine_records(connection)
        fetched_record = get_vaccine_record(connection, record.id)
        deleted_record = delete_vaccine_record(connection, record.id)
        deleted_type = delete_vaccine_type(connection, vaccine_type.id)

    assert updated_type is not None
    assert updated_type.name == "Tdap Updated"
    assert updated_type.is_active is False
    assert ordered
    assert updated_record is not None
    assert updated_record.patient_name == "김민수"
    assert fetched_record is not None
    assert fetched_record.patient_phone == "010-3333-4444"
    assert listed_records
    assert deleted_record is True
    assert deleted_type is True


def test_vaccine_tab_fetches_patient_context_from_emr_targets(tmp_path, monkeypatch) -> None:
    _app()

    from types import SimpleNamespace

    from KaosEghis.core.uia_inspector import UiaInspectionResult
    from KaosEghis.db.database import initialize_database
    import KaosEghis.ui.tabs.vaccine_tab as vaccine_tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    class _Profile:
        id = 1
        process_name = "eGhis.exe"
        window_title_contains = "이지스 전자차트 2.0"
        executable_path = r"C:\eghis\eGhis.exe"
        main_window_automation_id = "MdiMain"
        patient_status_tab_automation_id = "tabProc"
        prescription_grid_automation_id = "tree처방"
        symptom_grid_automation_id = "grdSymp"
        diagnosis_grid_automation_id = "tree상병"
        patient_list_grid_automation_id = "grdOpdList"

    target_values = {
        "vaccine.patient_chart_no": "2735",
        "vaccine.patient_resident_id": "700101-1234567",
        "vaccine.patient_name": "홍길동",
        "vaccine.patient_sex": "M",
        "vaccine.patient_age": "56",
        "vaccine.patient_phone": "010-1111-2222",
        "vaccine.patient_address": "Seoul",
    }

    monkeypatch.setattr(
        vaccine_tab_module,
        "get_active_emr_target_profile",
        lambda connection: _Profile(),
    )
    monkeypatch.setattr(vaccine_tab_module, "get_settings", lambda connection: {})
    monkeypatch.setattr(
        vaccine_tab_module,
        "get_emr_ui_target_by_key",
        lambda connection, profile_id, target_key: SimpleNamespace(
            target_id=target_key,
            parent_target_id=None,
            parent_automation_id=None,
            automation_id="auto",
            name=None,
            control_type="Edit",
            class_name=None,
        ),
    )
    monkeypatch.setattr(
        vaccine_tab_module,
        "inspect_target_readonly",
        lambda settings, target: UiaInspectionResult(
            found=True,
            message="ok",
            target_id=target.target_id,
            parent_target_id=None,
            parent_automation_id=None,
            parent_found=None,
            automation_id="auto",
            name=None,
            control_type="Edit",
            class_name=None,
            found_name=None,
            found_control_type="Edit",
            found_class_name=None,
            is_enabled=True,
            is_visible=True,
            text_value=target_values[target.target_id],
            has_keyboard_focus=True,
        ),
    )

    page = vaccine_tab_module.VaccineTab(db_path)

    assert page.fetch_current_patient_from_emr() is True
    assert page.patient_name_input.text() == "홍길동"
    assert page.patient_resident_id_input.text() == "700101-1234567"
    assert page.patient_phone_input.text() == "010-1111-2222"


def test_today_vaccine_counts_use_only_today_rows(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        get_today_vaccine_counts,
        list_vaccine_types,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        vaccine_types = {entry.name: entry for entry in list_vaccine_types(connection)}
        flu_type = vaccine_types["Influenza"]
        covid_type = vaccine_types["COVID-19"]
        flu_record = create_vaccine_record(
            connection,
            vaccine_type_id=flu_type.id,
            vaccine_type_name=flu_type.name,
            patient_name="홍길동",
        )
        covid_record = create_vaccine_record(
            connection,
            vaccine_type_id=covid_type.id,
            vaccine_type_name=covid_type.name,
            patient_name="김민수",
        )
        connection.execute(
            "UPDATE vaccine_records SET created_at = '2026-08-09 08:00:00' WHERE id = ?",
            (flu_record.id,),
        )
        connection.execute(
            "UPDATE vaccine_records SET created_at = '2026-08-10 08:00:00' WHERE id = ?",
            (covid_record.id,),
        )
        connection.commit()
        counts = get_today_vaccine_counts(connection, "2026-08-10")

    assert counts == {"flu": 0, "covid": 1}


def test_vaccine_tab_uses_single_structured_program_settings(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineTab(db_path)

    settings_page = page.settings_page
    assert settings_page.tabs.tabText(0) == "Influenza schedule"
    assert settings_page.tabs.tabText(1) == "COVID schedule"
    assert not hasattr(settings_page.influenza_editor, "season_combo")
    assert not hasattr(settings_page.influenza_editor, "duplicate_button")


def test_vaccine_tab_uses_three_internal_pages(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineTab(db_path)

    assert page.TOP_PAGES == ["Main", "DB", "Settings"]
    assert page.stacked_widget.count() == 3
    assert set(page.nav_buttons) == {"Main", "DB", "Settings"}


def test_vaccine_tab_db_buckets_split_records_by_type(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_vaccine_record, create_vaccine_type
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_vaccine_record(
            connection,
            vaccine_type_id=None,
            vaccine_type_name="Influenza",
            patient_name="홍길동",
        )
        create_vaccine_record(
            connection,
            vaccine_type_id=None,
            vaccine_type_name="COVID-19",
            patient_name="김민수",
        )
        tdap = create_vaccine_type(connection, name="Tdap", code="tdap")
        create_vaccine_record(
            connection,
            vaccine_type_id=tdap.id,
            vaccine_type_name="Tdap",
            patient_name="박지훈",
        )

    page = VaccineTab(db_path)

    assert page.flu_records_table.rowCount() == 1
    assert page.covid_records_table.rowCount() == 1
    assert page.general_records_table.rowCount() == 1
