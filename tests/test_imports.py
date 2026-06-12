def test_core_modules_import() -> None:
    import KaosEghis.config
    import KaosEghis.core.clipboard_service
    import KaosEghis.core.credential_store
    import KaosEghis.core.emr_detector
    import KaosEghis.core.macro_models
    import KaosEghis.core.macro_runner
    import KaosEghis.core.safety_gate
    import KaosEghis.db.database
    import KaosEghis.db.repositories


def test_settings_repository_can_save_and_load(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "eghis_process_name": "Example.exe",
                "eghis_window_title_contains": "Example",
                "kaosgdd_url": "https://kaosgdd.net",
                "credential_reference_name": "test-reference",
            },
        )
        settings = get_settings(connection)

    assert settings["eghis_process_name"] == "Example.exe"
    assert settings["eghis_window_title_contains"] == "Example"
    assert settings["credential_reference_name"] == "test-reference"


def test_detector_and_clipboard_imports() -> None:
    from KaosEghis.core import clipboard_service, emr_detector

    assert callable(emr_detector.check_process_running)
    assert callable(emr_detector.find_window_by_title_contains)
    assert callable(emr_detector.get_active_window_title)
    assert callable(emr_detector.is_target_window_active)
    assert callable(clipboard_service.copy_text)


def test_ui_targets_repository_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_ui_target,
        delete_ui_target,
        get_ui_target,
        list_ui_targets,
        update_ui_target,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        created = create_ui_target(
            connection,
            target_id="login.username",
            automation_id="UserNameBox",
            name="Username",
            control_type="Edit",
        )

        assert created.id > 0
        assert created.target_id == "login.username"
        assert created.automation_id == "UserNameBox"
        assert len(list_ui_targets(connection)) == 1

        found = get_ui_target(connection, "login.username")
        assert found is not None
        assert found.name == "Username"

        updated = update_ui_target(
            connection,
            target_id="login.username",
            automation_id="UserNameField",
            name="Login username",
            control_type="Edit",
        )
        assert updated is not None
        assert updated.automation_id == "UserNameField"
        assert updated.name == "Login username"

        assert delete_ui_target(connection, "login.username") is True
        assert get_ui_target(connection, "login.username") is None
        assert list_ui_targets(connection) == []
