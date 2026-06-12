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


def test_items_repository_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        delete_item,
        get_item,
        list_items,
        update_item,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        item = create_item(connection, "Morning macro", "macro", True)
        assert item.id > 0
        assert item.name == "Morning macro"
        assert item.item_type == "macro"
        assert item.is_enabled is True

        assert len(list_items(connection, "macro")) == 1

        updated = update_item(connection, item.id, "Morning workflow", "workflow", False)
        assert updated is not None
        assert updated.name == "Morning workflow"
        assert updated.item_type == "workflow"
        assert updated.is_enabled is False

        assert get_item(connection, item.id) is not None
        assert delete_item(connection, item.id) is True
        assert get_item(connection, item.id) is None


def test_macro_steps_repository_crud_and_reorder(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_macro_step,
        delete_macro_step,
        list_macro_steps,
        reorder_macro_steps,
        update_macro_step,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        item = create_item(connection, "Check login", "macro", True)
        second = create_macro_step(
            connection,
            item.id,
            2,
            "wait_ms",
            value="250",
            timeout_seconds=0,
            retries=0,
        )
        first = create_macro_step(
            connection,
            item.id,
            1,
            "check_process",
            value="Eghis.exe",
            timeout_seconds=5,
            retries=1,
        )

        steps = list_macro_steps(connection, item.id)
        assert [step.id for step in steps] == [first.id, second.id]

        updated = update_macro_step(
            connection,
            second.id,
            3,
            "wait_ms",
            value="500",
            timeout_seconds=0,
            retries=0,
        )
        assert updated is not None
        assert updated.value == "500"

        reordered = reorder_macro_steps(connection, item.id)
        assert [step.step_order for step in reordered] == [1, 2]

        assert delete_macro_step(connection, first.id) is True
        assert len(list_macro_steps(connection, item.id)) == 1


def test_macro_dry_run_validation_reports_missing_target(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_macro_step,
        create_ui_target,
        validate_macro_dry_run,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        item = create_item(connection, "Read field", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "read_text_uia",
            target_id="missing.target",
        )
        assert validate_macro_dry_run(connection, item.id) == [
            "Step 1: target_id 'missing.target' is not registered."
        ]

        create_ui_target(connection, "missing.target")
        assert validate_macro_dry_run(connection, item.id) == []
