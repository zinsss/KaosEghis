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
            automation_id="PatientSearchBox",
            control_type="Edit",
            class_name="WindowsForms10.Edit",
            name_match="Patient Search",
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
    assert "target_key=patient.search" in result.message
    assert "label=Patient Search" in result.message
    assert "automation_id=PatientSearchBox" in result.message


def test_dry_run_reports_unresolved_target(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_item, create_macro_step

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
        macro = create_item(connection, "Unresolved Macro", "macro", True, profile.id)
        create_macro_step(
            connection,
            macro.id,
            1,
            "wait_for_target",
            target_id="missing.target",
        )

    result = MacroRunner(db_path).execute_macro(macro.id, dry_run=True)

    assert result.success is True
    assert "warning: unresolved target_key 'missing.target'" in result.message
    assert "Review warnings before real execution." in result.message


def test_dry_run_warns_on_disabled_profile(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_item

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Disabled EMR",
            is_enabled=False,
            is_default=False,
        )
        macro = create_item(connection, "Disabled Profile Macro", "macro", True, profile.id)

    result = MacroRunner(db_path).execute_macro(macro.id, dry_run=True)

    assert result.success is True
    assert "Warning: EMR target profile 'Disabled EMR' is disabled." in result.message


def test_dry_run_warns_when_no_default_profile(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        connection.execute("UPDATE emr_target_profiles SET is_default = 0")
        connection.commit()
        macro = create_item(connection, "No Default Macro", "macro", True, None)

    result = MacroRunner(db_path).execute_macro(macro.id, dry_run=True)

    assert result.success is True
    assert "Warning: No default EMR target profile is configured." in result.message


def test_target_selector_refreshes_when_profile_changes(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_emr_ui_target
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_emr_target_profile(
            connection,
            name="Profile One",
            is_enabled=True,
            is_default=False,
        )
        second = create_emr_target_profile(
            connection,
            name="Profile Two",
            is_enabled=True,
            is_default=False,
        )
        create_emr_ui_target(
            connection,
            profile_id=first.id,
            target_key="patient.search",
            label="Patient Search",
        )
        create_emr_ui_target(
            connection,
            profile_id=second.id,
            target_key="symptom.text",
            label="Symptom Text",
        )

    parent = QWidget()
    dialog = MacroEditorDialog(parent)
    dialog.emr_profile.setCurrentIndex(dialog.emr_profile.findData(first.id))
    assert "patient.search" in dialog.available_target_keys()
    assert "symptom.text" not in dialog.available_target_keys()

    dialog.emr_profile.setCurrentIndex(dialog.emr_profile.findData(second.id))
    assert "patient.search" not in dialog.available_target_keys()
    assert "symptom.text" in dialog.available_target_keys()


def test_non_target_action_allows_blank_target(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    parent = QWidget()
    dialog = MacroStepDialog(parent)
    dialog.action.setCurrentText("hotkey")

    assert dialog.target_id.isEnabled() is False
    assert dialog.target_id.currentText() == ""


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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
