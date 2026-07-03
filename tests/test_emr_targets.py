import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_emr_profile_tables_are_created(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "emr_target_profiles" in tables
    assert "emr_ui_targets" in tables


def test_default_profile_is_seeded_from_existing_settings(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_default_emr_target_profile

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
            ("eghis_process_name", "SeededEghis.exe"),
        )
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            ("eghis_window_title_contains", "Seeded Eghis"),
        )
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            ("credential_reference_name", "super-secret-ref"),
        )
        connection.commit()

    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = get_default_emr_target_profile(connection)
        row = connection.execute(
            """
            SELECT name, description, process_name, window_title_contains
            FROM emr_target_profiles
            WHERE is_default = 1
            """
        ).fetchone()

    assert profile is not None
    assert profile.name == "eGHIS Production"
    assert profile.process_name == "SeededEghis.exe"
    assert profile.window_title_contains == "Seeded Eghis"
    assert "super-secret-ref" not in row


def test_emr_target_profile_crud_and_single_default(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        get_active_emr_target_profile,
        get_emr_target_profile,
        list_emr_target_profiles,
        set_default_emr_target_profile,
        update_emr_target_profile,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        seeded = get_active_emr_target_profile(connection)
        assert seeded is not None

        created = create_emr_target_profile(
            connection,
            name="Training EMR",
            description="Training profile",
            is_enabled=True,
            is_default=True,
            process_name="Training.exe",
            window_title_contains="Training Window",
        )
        updated = update_emr_target_profile(
            connection,
            created.id,
            name="Training EMR Updated",
            description="Updated profile",
            is_enabled=True,
            is_default=True,
            process_name="TrainingUpdated.exe",
            window_title_contains="Training Updated",
        )
        set_default_emr_target_profile(connection, seeded.id)
        profiles = list_emr_target_profiles(connection)
        defaults = [profile for profile in profiles if profile.is_default]
        fetched = get_emr_target_profile(connection, created.id)

    assert updated is not None
    assert updated.name == "Training EMR Updated"
    assert updated.process_name == "TrainingUpdated.exe"
    assert fetched is not None
    assert fetched.name == "Training EMR Updated"
    assert len(defaults) == 1
    assert defaults[0].id == seeded.id


def test_deleting_default_profile_promotes_another_enabled_profile(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        delete_emr_target_profile,
        get_default_emr_target_profile,
        list_emr_target_profiles,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        original_default = get_default_emr_target_profile(connection)
        assert original_default is not None
        replacement = create_emr_target_profile(
            connection,
            name="Alternate EMR",
            is_enabled=True,
            is_default=False,
        )
        deleted = delete_emr_target_profile(connection, original_default.id)
        new_default = get_default_emr_target_profile(connection)
        remaining_ids = {profile.id for profile in list_emr_target_profiles(connection)}

    assert deleted is True
    assert new_default is not None
    assert new_default.id == replacement.id
    assert original_default.id not in remaining_ids


def test_deleting_only_default_profile_is_blocked(tmp_path) -> None:
    import pytest

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        delete_emr_target_profile,
        get_default_emr_target_profile,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        default_profile = get_default_emr_target_profile(connection)
        assert default_profile is not None
        with pytest.raises(ValueError):
            delete_emr_target_profile(connection, default_profile.id)


def test_emr_ui_target_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_ui_target,
        get_default_emr_target_profile,
        list_emr_ui_targets,
        update_emr_ui_target,
        delete_emr_ui_target,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = get_default_emr_target_profile(connection)
        assert profile is not None
        target = create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="patient.search",
            label="Patient Search",
            automation_id="SearchBox",
            control_type="Edit",
            parent_target_key="main.window",
            ancestor_hint_path='[{"name":"진료실","control_type":"Window"}]',
        )
        updated = update_emr_ui_target(
            connection,
            target.id,
            target_key="patient.search",
            label="Patient Search Updated",
            automation_id="SearchBoxUpdated",
            control_type="Edit",
            class_name="WindowsForms10.Edit",
            parent_target_key="main.window",
            ancestor_hint_path='[{"name":"Tools","control_type":"ToolBar"}]',
        )
        listed = list_emr_ui_targets(connection, profile.id)
        deleted = delete_emr_ui_target(connection, target.id)
        after_delete = list_emr_ui_targets(connection, profile.id)

    assert updated is not None
    assert updated.label == "Patient Search Updated"
    assert listed[0].automation_id == "SearchBoxUpdated"
    assert listed[0].ancestor_hint_path == '[{"name":"Tools","control_type":"ToolBar"}]'
    assert deleted is True
    assert after_delete == []


def test_emr_ui_target_migration_adds_ancestor_hint_path(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE emr_target_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE emr_ui_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                target_key TEXT NOT NULL,
                label TEXT NOT NULL,
                parent_target_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.commit()

    initialize_database(db_path)
    with connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(emr_ui_targets)")
        }

    assert "ancestor_hint_path" in columns


def test_emr_targets_page_instantiates_and_shows_default_profile(tmp_path, monkeypatch) -> None:
    _app()

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    page = EmrTargetsPage(db_path)

    assert page.profile_list.count() >= 1
    assert page.name_input.text() == "eGHIS Production"
    assert page.default_status_label.text() == "[default]"


def test_emr_targets_page_connection_toggle_updates_status(
    tmp_path, monkeypatch
) -> None:
    _app()

    from KaosEghis.core.eghis_connector import clear_cached_eghis_state
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage

    class FakeState:
        status = "green"
        pid = 1234
        exe_path = "C:\\Mcc\\Clinic\\eGhis.exe"
        process_name = "eGhis.exe"
        message = "Connected and active"

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    clear_cached_eghis_state()
    monkeypatch.setattr(
        "KaosEghis.ui.tabs.emr_targets_page.refresh_cached_eghis_state",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.ui.tabs.emr_targets_page.get_cached_eghis_state",
        lambda: FakeState(),
    )

    page = EmrTargetsPage(db_path)
    page.connection_toggle.click()

    assert page.connection_toggle.isChecked() is True
    assert "Connected and active" in page.connection_status_label.text()


def test_emr_targets_page_shows_connected_message_for_inactive_cached_app(
    tmp_path, monkeypatch
) -> None:
    _app()

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage

    class FakeState:
        status = "yellow"
        pid = 1234
        exe_path = "C:\\eghis\\eghisEmr\\eGhis.exe"
        process_name = "eGhis.exe"
        message = "Connected - will focus on run"

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    monkeypatch.setattr(
        "KaosEghis.ui.tabs.emr_targets_page.get_cached_eghis_state",
        lambda: FakeState(),
    )

    page = EmrTargetsPage(db_path)
    page.refresh_view()

    assert page.connection_toggle.isChecked() is True
    assert "will be focused when a macro runs" in page.connection_status_label.text()
