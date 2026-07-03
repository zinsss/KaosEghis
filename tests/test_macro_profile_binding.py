import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_macro_can_bind_to_emr_profile(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_item,
        get_item,
        list_items,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        macro = create_item(
            connection,
            "Bound Macro",
            "macro",
            True,
            profile.id,
        )
        fetched = get_item(connection, macro.id)
        listed = list_items(connection, "macro")

    assert fetched is not None
    assert fetched.emr_target_profile_id == profile.id
    assert listed[0].emr_target_profile_id == profile.id


def test_null_macro_profile_falls_back_to_default(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_item,
        get_default_emr_target_profile,
        get_item,
        resolve_macro_emr_target_profile,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        macro = create_item(connection, "Fallback Macro", "macro", True, None)
        item = get_item(connection, macro.id)
        default_profile = get_default_emr_target_profile(connection)
        resolved_profile = resolve_macro_emr_target_profile(connection, item)

    assert default_profile is not None
    assert item is not None
    assert item.emr_target_profile_id is None
    assert resolved_profile is not None
    assert resolved_profile.id == default_profile.id


def test_target_selector_lists_profile_ui_targets(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_emr_ui_target
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="patient.search",
            label="Patient Search",
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="symptom.text",
            label="Symptom Text",
        )

    parent = QWidget()
    dialog = MacroStepDialog(parent, profile_id=profile.id)
    options = [dialog.target_id.itemText(index) for index in range(dialog.target_id.count())]

    assert "patient.search" in options
    assert "symptom.text" in options


def test_dry_run_shows_selected_profile(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_emr_ui_target,
        create_item,
        create_macro_step,
    )

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="patient.search",
            label="Patient Search",
        )
        macro = create_item(connection, "Profile Dry Run", "macro", True, profile.id)
        create_macro_step(
            connection,
            macro.id,
            1,
            "wait_for_target",
            target_id="patient.search",
        )

    result = MacroRunner(db_path).execute_macro(macro.id, dry_run=True)

    assert result.success is True
    assert "Profile: Training EMR" in result.message
    assert "target_id=patient.search" in result.message


def test_macros_page_shows_selected_emr_profile(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_item
    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosPage

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        create_item(connection, "Profiled Macro", "macro", True, profile.id)

    page = MacrosPage(db_path)

    assert page.macros_table.item(0, 2).text() == "Training EMR"


def test_macro_execution_behavior_unchanged_with_bound_profile(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Training EMR",
            is_enabled=True,
            is_default=False,
        )
        macro = create_item(connection, "Hotkey Macro", "macro", True, profile.id)
        create_macro_step(connection, macro.id, 1, "hotkey", value="^a")

    class FakeState:
        status = "green"
        message = "Connected and active"

    calls: list[str] = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type(
            "Keyboard",
            (),
            {"send_keys": staticmethod(lambda keys: calls.append(keys))},
        )(),
    )

    result = MacroRunner(db_path).execute_macro(macro.id, dry_run=False)

    assert result.success is True
    assert calls == ["^a"]


def test_launcher_positions_persist(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, list_launcher_items, set_launcher_positions

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "Macro A", "macro", True)
        second = create_item(connection, "Macro B", "macro", True)
        set_launcher_positions(
            connection,
            [
                (second.id, "Medical Documents", 0),
                (first.id, "Eghis", 1),
            ],
        )
        items = list_launcher_items(connection)

    assert [(item.id, item.launcher_category, item.launcher_order) for item in items] == [
        (first.id, "Eghis", 1),
        (second.id, "Medical Documents", 0),
    ]


def test_launcher_page_shows_three_macro_columns(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    page = LauncherPage(tmp_path / "KaosEghis.sqlite")

    assert list(page._lists.keys()) == ["Eghis", "Medical Documents", "ETC"]
