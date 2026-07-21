def test_core_modules_import() -> None:
    import KaosEghis.config
    import KaosEghis.core.clipboard_service
    import KaosEghis.core.credential_store
    import KaosEghis.core.kaospacs_client
    import KaosEghis.core.pacs_polling
    import KaosEghis.core.eghis_connector
    import KaosEghis.core.emr_detector
    import KaosEghis.core.eghis_key_paste_test
    import KaosEghis.core.macro_models
    import KaosEghis.core.macro_runner
    import KaosEghis.core.paste_test
    import KaosEghis.core.scan_service
    import KaosEghis.core.safety_gate
    import KaosEghis.core.uia_inspector
    import KaosEghis.core.wait_engine
    import KaosEghis.core.write_test
    import KaosEghis.db.database
    import KaosEghis.db.repositories
    import KaosEghis.ui.main_window
    import KaosEghis.ui.tabs.eghis_assist_tab
    import KaosEghis.ui.tabs.kaoseghis_tab
    import KaosEghis.ui.tabs.scan_tab


def test_nord_theme_includes_complete_scrollbar_styling() -> None:
    from KaosEghis.ui.theme import nord_stylesheet

    stylesheet = nord_stylesheet().casefold()

    assert "#2e3440" in stylesheet
    assert "#88c0d0" in stylesheet
    assert "qscrollbar:vertical" in stylesheet
    assert "qscrollbar:horizontal" in stylesheet
    assert "qscrollbar::handle:vertical:hover" in stylesheet
    assert "qscrollbar::handle:horizontal:pressed" in stylesheet
    assert "#1e1e2e" not in stylesheet
    assert "#cba6f7" not in stylesheet


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
    from KaosEghis.core import (
        clipboard_service,
        eghis_key_paste_test,
        emr_detector,
        paste_test,
        write_test,
    )

    assert callable(emr_detector.check_process_running)
    assert callable(emr_detector.detect_eghis_connection)
    assert callable(emr_detector.find_matching_processes)
    assert callable(emr_detector.find_window_by_title_contains)
    assert callable(emr_detector.find_matching_window_titles)
    assert callable(emr_detector.get_active_window_title)
    assert callable(emr_detector.is_target_window_active)
    assert callable(
        eghis_key_paste_test.paste_to_eghis_field_by_function_key_for_test
    )
    assert callable(clipboard_service.copy_text)
    assert callable(paste_test.paste_text_to_target_for_test)
    assert callable(write_test.set_value_to_target_for_test)
    assert callable(write_test.set_edit_text_to_target_for_test)


def test_clipboard_service_retries_until_text_is_applied(monkeypatch) -> None:
    import KaosEghis.core.clipboard_service as clipboard_service

    events: list[str] = []
    state = {"text": "old", "calls": 0}

    def fake_read() -> str:
        return state["text"]

    def fake_write(value: str) -> None:
        state["calls"] += 1
        events.append(f"set:{state['calls']}")
        if state["calls"] >= 3:
            state["text"] = value

    monkeypatch.setattr(clipboard_service, "_read_clipboard_text", fake_read)
    monkeypatch.setattr(clipboard_service, "_write_clipboard_text", fake_write)
    monkeypatch.setattr(
        clipboard_service.time,
        "sleep",
        lambda seconds: events.append(f"sleep:{seconds}"),
    )

    snapshot = clipboard_service.copy_text("hello")

    assert snapshot.text == "old"
    assert state["text"] == "hello"
    assert state["calls"] == 3
    assert events == [
        "set:1",
        "sleep:0.05",
        "set:2",
        "sleep:0.05",
        "set:3",
    ]


def test_clipboard_service_raises_when_clipboard_stays_busy(monkeypatch) -> None:
    import pytest
    import KaosEghis.core.clipboard_service as clipboard_service
    monkeypatch.setattr(clipboard_service, "_read_clipboard_text", lambda: "old")
    monkeypatch.setattr(clipboard_service, "_write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(
        clipboard_service.time,
        "sleep",
        lambda _seconds: None,
    )

    with pytest.raises(RuntimeError, match="Clipboard is busy."):
        clipboard_service.copy_text("hello")


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
            parent_target_id="login",
            parent_automation_id="TreatmentSymp",
            automation_id="UserNameBox",
            name="Username",
            control_type="Edit",
            class_name="RichEditD2DPT",
        )

        assert created.id > 0
        assert created.target_id == "login.username"
        assert created.parent_target_id == "login"
        assert created.parent_automation_id == "TreatmentSymp"
        assert created.automation_id == "UserNameBox"
        assert created.class_name == "RichEditD2DPT"
        assert len(list_ui_targets(connection)) == 1

        found = get_ui_target(connection, "login.username")
        assert found is not None
        assert found.parent_target_id == "login"
        assert found.parent_automation_id == "TreatmentSymp"
        assert found.name == "Username"
        assert found.class_name == "RichEditD2DPT"

        updated = update_ui_target(
            connection,
            target_id="login.username",
            parent_target_id="session.login",
            parent_automation_id="TreatmentNote",
            automation_id="UserNameField",
            name="Login username",
            control_type="Edit",
            class_name="WindowsForms10.EDIT.app.0.141b42a_r8_ad1",
        )
        assert updated is not None
        assert updated.parent_target_id == "session.login"
        assert updated.parent_automation_id == "TreatmentNote"
        assert updated.automation_id == "UserNameField"
        assert updated.name == "Login username"
        assert updated.class_name == "WindowsForms10.EDIT.app.0.141b42a_r8_ad1"

        assert delete_ui_target(connection, "login.username") is True
        assert get_ui_target(connection, "login.username") is None
        assert list_ui_targets(connection) == []


def test_database_migration_adds_ui_target_optional_columns(tmp_path) -> None:
    import sqlite3

    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE ui_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id TEXT NOT NULL UNIQUE,
                automation_id TEXT,
                name TEXT,
                control_type TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO ui_targets (target_id, automation_id, name, control_type)
            VALUES ('existing.target', 'eghisRichTextBox', 'Existing', 'Edit');
            """
        )

    initialize_database(db_path)

    with connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ui_targets)")
        }
        row = connection.execute(
            """
            SELECT target_id, automation_id, class_name, parent_automation_id, parent_target_id
            FROM ui_targets
            """
        ).fetchone()

    assert "class_name" in columns
    assert "parent_automation_id" in columns
    assert "parent_target_id" in columns
    assert row == ("existing.target", "eghisRichTextBox", None, None, None)


def test_items_repository_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_macro_step,
        create_item,
        delete_item,
        get_item,
        list_launcher_items,
        list_clipboard_variants,
        list_macro_steps,
        list_items,
        update_item_launcher_placement,
        replace_clipboard_variants,
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
        assert item.launcher_section == "Macro"
        assert item.launcher_position == 1

        assert len(list_items(connection, "macro")) == 1

        updated = update_item(connection, item.id, "Morning workflow", "workflow", False)
        assert updated is not None
        assert updated.name == "Morning workflow"
        assert updated.item_type == "workflow"
        assert updated.is_enabled is False
        assert updated.launcher_section == "Macro"

        assert get_item(connection, item.id) is not None
        create_macro_step(connection, item.id, 1, "wait_ms", value="100")
        assert len(list_macro_steps(connection, item.id)) == 1
        assert delete_item(connection, item.id) is True
        assert get_item(connection, item.id) is None
        assert list_macro_steps(connection, item.id) == []

        first = create_item(connection, "Alpha", "macro", True)
        second = create_item(connection, "Beta", "macro", True)
        moved = update_item_launcher_placement(
            connection,
            second.id,
            "Comments",
            1,
        )
        assert moved is not None
        assert moved.launcher_section == "Comments"
        launcher_items = list_launcher_items(connection, "Comments")
        assert [item.id for item in launcher_items] == [second.id]
        assert get_item(connection, first.id).launcher_section == "Macro"

        macrotext = create_item(connection, "Comment", "clipboard", True)
        assert macrotext.launcher_section == "Comments"
        assert replace_clipboard_variants(
            connection, macrotext.id, ["First line\nSecond line"]
        ) == 1
        variants = list_clipboard_variants(connection, macrotext.id)
        assert [variant.body for variant in variants] == ["First line\nSecond line"]
        assert macrotext.id in [
            item.id for item in list_launcher_items(connection, "Comments")
        ]


def test_launcher_section_migration_preserves_legacy_items(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, get_item

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        document = create_item(connection, "Legacy document", "macro", True)
        eghis = create_item(connection, "Legacy Eghis", "macro", True)
        etc = create_item(connection, "Legacy ETC", "macro", True)
        connection.executemany(
            "UPDATE items SET launcher_section = ? WHERE id = ?",
            [
                ("Medical Documents", document.id),
                ("Eghis", eghis.id),
                ("ETC", etc.id),
            ],
        )
        connection.commit()

    initialize_database(db_path)

    with connect(db_path) as connection:
        migrated_document = get_item(connection, document.id)
        migrated_eghis = get_item(connection, eghis.id)
        migrated_etc = get_item(connection, etc.id)
    assert migrated_document is not None
    assert migrated_document.launcher_section == "Comments"
    assert migrated_eghis is not None
    assert migrated_eghis.launcher_section == "Macro"
    assert migrated_etc is not None
    assert migrated_etc.launcher_section == "Favorite"


def test_macro_steps_repository_crud_and_reorder(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_macro_step,
        delete_macro_step,
        delete_macro_steps_for_item,
        get_macro_step,
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
        assert get_macro_step(connection, second.id) is not None

        reordered = reorder_macro_steps(connection, item.id)
        assert [step.step_order for step in reordered] == [1, 2]

        assert delete_macro_step(connection, first.id) is True
        assert len(list_macro_steps(connection, item.id)) == 1
        assert delete_macro_steps_for_item(connection, item.id) == 1
        assert list_macro_steps(connection, item.id) == []


def test_macro_step_press_enter_after_is_persisted(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_macro_step,
        update_macro_step,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        item = create_item(connection, "Submit text", "macro", True)
        step = create_macro_step(
            connection,
            item.id,
            1,
            "type_text",
            value="hello",
            press_enter_after=True,
            wait_before_enabled=True,
            wait_before_ms=250,
        )
        assert step.press_enter_after is True
        assert step.wait_before_enabled is True
        assert step.wait_before_ms == 250

        updated = update_macro_step(
            connection,
            step.id,
            1,
            "type_text",
            value="hello again",
            press_enter_after=False,
            wait_before_enabled=False,
            wait_before_ms=125,
        )
        assert updated is not None
        assert updated.press_enter_after is False
        assert updated.wait_before_enabled is False
        assert updated.wait_before_ms == 125


def test_macro_step_migration_adds_press_enter_after(tmp_path) -> None:
    import sqlite3

    from KaosEghis.db.database import initialize_database

    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE macro_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id TEXT,
                value TEXT,
                timeout_seconds REAL NOT NULL DEFAULT 5,
                retries INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(macro_steps)")
        }
        assert "press_enter_after" in columns
        assert columns["press_enter_after"][4] == "0"
        assert columns["wait_before_enabled"][4] == "0"
        assert columns["wait_before_ms"][4] == "100"


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


def test_uia_inspection_result_construction() -> None:
    from KaosEghis.core.uia_inspector import UiaInspectionResult

    result = UiaInspectionResult(
        found=False,
        message="not found",
        target_id="target.one",
        parent_target_id="symptom",
        parent_automation_id="TreatmentSymp",
        parent_found=True,
        automation_id="AutoId",
        name="Name",
        control_type="Edit",
        class_name="RichEditD2DPT",
        found_name=None,
        found_control_type=None,
        found_class_name=None,
        is_enabled=None,
        is_visible=None,
        text_value=None,
    )

    assert result.found is False
    assert result.target_id == "target.one"
    assert result.message == "not found"


def test_inspect_target_readonly_reports_missing_pywinauto(monkeypatch) -> None:
    import sys

    from KaosEghis.core.uia_inspector import inspect_target_readonly
    from KaosEghis.db.repositories import UiTargetRecord

    monkeypatch.setitem(sys.modules, "pywinauto", None)
    target = UiTargetRecord(
        1, "target.one", None, "TreatmentSymp", "AutoId", "Name", "Edit", None, "now"
    )

    result = inspect_target_readonly({"eghis_window_title_contains": "Eghis"}, target)

    assert result.found is False
    assert result.target_id == "target.one"
    assert "pywinauto" in result.message


def test_wait_result_construction() -> None:
    from KaosEghis.core.wait_engine import WaitResult

    result = WaitResult(
        success=True,
        message="done",
        target_id="target.one",
        condition="exists",
        elapsed_ms=12,
        attempts=2,
    )

    assert result.success is True
    assert result.condition == "exists"
    assert result.attempts == 2


def test_wait_condition_evaluation() -> None:
    from KaosEghis.core.uia_inspector import UiaInspectionResult
    from KaosEghis.core.wait_engine import is_condition_satisfied

    inspection = UiaInspectionResult(
        found=True,
        message="found",
        target_id="target.one",
        parent_target_id=None,
        parent_automation_id=None,
        parent_found=None,
        automation_id=None,
        name=None,
        control_type=None,
        class_name=None,
        found_name="Field",
        found_control_type="Edit",
        found_class_name=None,
        is_enabled=True,
        is_visible=True,
        text_value="value",
    )

    assert is_condition_satisfied(inspection, "exists") is True
    assert is_condition_satisfied(inspection, "visible") is True
    assert is_condition_satisfied(inspection, "enabled") is True
    assert is_condition_satisfied(inspection, "text_non_empty") is True


def test_wait_for_target_condition_timeout(monkeypatch) -> None:
    from KaosEghis.core import wait_engine
    from KaosEghis.core.uia_inspector import UiaInspectionResult
    from KaosEghis.db.repositories import UiTargetRecord

    def inspect(_settings, target):
        return UiaInspectionResult(
            found=False,
            message="not found",
            target_id=target.target_id,
            parent_target_id=target.parent_target_id,
            parent_automation_id=target.parent_automation_id,
            parent_found=None,
            automation_id=target.automation_id,
            name=target.name,
            control_type=target.control_type,
            class_name=target.class_name,
            found_name=None,
            found_control_type=None,
            found_class_name=None,
            is_enabled=None,
            is_visible=None,
            text_value=None,
        )

    monkeypatch.setattr(wait_engine, "inspect_target_readonly", inspect)
    target = UiTargetRecord(
        1, "target.one", None, None, "AutoId", "Name", "Edit", None, "now"
    )

    result = wait_engine.wait_for_target_condition(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "exists",
        timeout_ms=1,
        poll_ms=1,
    )

    assert result.success is False
    assert result.target_id == "target.one"
    assert result.condition == "exists"
    assert result.attempts >= 1
    assert "Timed out" in result.message


def test_wait_for_target_condition_success(monkeypatch) -> None:
    from KaosEghis.core import wait_engine
    from KaosEghis.core.uia_inspector import UiaInspectionResult
    from KaosEghis.db.repositories import UiTargetRecord

    def inspect(_settings, target):
        return UiaInspectionResult(
            found=True,
            message="found",
            target_id=target.target_id,
            parent_target_id=target.parent_target_id,
            parent_automation_id=target.parent_automation_id,
            parent_found=None,
            automation_id=target.automation_id,
            name=target.name,
            control_type=target.control_type,
            class_name=target.class_name,
            found_name="Name",
            found_control_type="Edit",
            found_class_name=None,
            is_enabled=True,
            is_visible=True,
            text_value="ready",
        )

    monkeypatch.setattr(wait_engine, "inspect_target_readonly", inspect)
    target = UiTargetRecord(
        1, "target.one", None, None, "AutoId", "Name", "Edit", None, "now"
    )

    result = wait_engine.wait_for_target_condition(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "visible",
        timeout_ms=5000,
        poll_ms=200,
    )

    assert result.success is True
    assert result.condition == "visible"
    assert result.attempts == 1


def test_paste_test_rejects_empty_text() -> None:
    from KaosEghis.core.paste_test import paste_text_to_target_for_test
    from KaosEghis.db.repositories import UiTargetRecord

    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = paste_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "   ",
    )

    assert result.success is False
    assert result.focused is None
    assert result.clipboard_restored is False
    assert "empty" in result.message


def test_paste_test_returns_failure_when_target_unresolved(monkeypatch) -> None:
    import KaosEghis.core.paste_test as paste_test

    from KaosEghis.db.repositories import UiTargetRecord

    calls: list[str] = []

    def fake_resolve(_settings, _target):
        calls.append("resolve")
        return None, None, "UI target 'symptom.text' was not found."

    monkeypatch.setattr(paste_test, "resolve_target_element", fake_resolve)
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = paste_test.paste_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert calls == ["resolve"]
    assert result.success is False
    assert result.focused is None
    assert "not found" in result.message


def test_paste_test_restores_clipboard_on_keyboard_failure(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.paste_test as paste_test

    from KaosEghis.db.repositories import UiTargetRecord

    class FakeElement:
        def set_focus(self) -> None:
            return None

    restored: list[str] = []

    monkeypatch.setattr(
        paste_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    monkeypatch.setattr(
        paste_test,
        "copy_text",
        lambda text: SimpleNamespace(text=text, previous="old"),
    )
    monkeypatch.setattr(
        paste_test,
        "restore_clipboard",
        lambda _snapshot: restored.append("restored"),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        SimpleNamespace(send_keys=lambda _keys: (_ for _ in ()).throw(RuntimeError("boom"))),
    )

    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )
    result = paste_test.paste_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert result.focused is True
    assert result.clipboard_restored is True
    assert restored == ["restored"]
    assert "failed" in result.message


def test_paste_test_pastes_only_after_unique_resolution(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.paste_test as paste_test

    from KaosEghis.db.repositories import UiTargetRecord

    class FakeElement:
        def set_focus(self) -> None:
            return None

    calls: list[str] = []

    def fake_resolve(_settings, _target):
        calls.append("resolve")
        return FakeElement(), None, "Target found."

    monkeypatch.setattr(paste_test, "resolve_target_element", fake_resolve)
    monkeypatch.setattr(
        paste_test,
        "copy_text",
        lambda text: calls.append(f"copy:{text}") or SimpleNamespace(text=text),
    )
    monkeypatch.setattr(
        paste_test,
        "restore_clipboard",
        lambda _snapshot: calls.append("restore"),
    )
    monkeypatch.setattr(
        paste_test.time,
        "sleep",
        lambda seconds: calls.append(f"sleep:{seconds}"),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        SimpleNamespace(send_keys=lambda keys: calls.append(f"send:{keys}")),
    )

    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )
    result = paste_test.paste_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is True
    assert result.focused is True
    assert result.clipboard_restored is True
    assert calls == ["resolve", "copy:hello", "send:^v", "sleep:0.15", "restore"]


def test_set_value_test_rejects_empty_text() -> None:
    from KaosEghis.core.write_test import set_value_to_target_for_test
    from KaosEghis.db.repositories import UiTargetRecord

    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        " ",
    )

    assert result.success is False
    assert result.method == "set_value"
    assert "empty" in result.message


def test_set_value_test_fails_if_target_unresolved(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (None, None, "UI target was not found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert "not found" in result.message


def test_set_value_test_calls_iface_value_set_value(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    calls: list[str] = []

    class FakeValuePattern:
        CurrentIsReadOnly = False

        def SetValue(self, text: str) -> None:
            calls.append(text)

    class FakeElement:
        iface_value = FakeValuePattern()

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is True
    assert calls == ["hello"]


def test_set_value_test_fails_cleanly_if_value_pattern_missing(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    class FakeElement:
        pass

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert "ValuePattern" in result.message


def test_set_value_test_fails_cleanly_if_iface_value_access_raises(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    class FakeElement:
        @property
        def iface_value(self):
            raise RuntimeError("pattern unavailable")

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert "ValuePattern is not available" in result.message
    assert "pattern unavailable" in result.message


def test_set_value_test_fails_cleanly_if_readonly(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    class FakeValuePattern:
        CurrentIsReadOnly = True

    class FakeElement:
        iface_value = FakeValuePattern()

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_value_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert "read-only" in result.message


def test_set_edit_text_test_rejects_empty_text() -> None:
    from KaosEghis.core.write_test import set_edit_text_to_target_for_test
    from KaosEghis.db.repositories import UiTargetRecord

    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = set_edit_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "",
    )

    assert result.success is False
    assert result.method == "set_edit_text"
    assert "empty" in result.message


def test_set_edit_text_test_fails_if_target_unresolved(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (None, None, "UI target was not found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_edit_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is False
    assert "not found" in result.message


def test_set_edit_text_test_calls_element_set_edit_text(monkeypatch) -> None:
    import KaosEghis.core.write_test as write_test

    from KaosEghis.db.repositories import UiTargetRecord

    calls: list[str] = []

    class FakeElement:
        def set_focus(self) -> None:
            calls.append("focus")

        def set_edit_text(self, text: str) -> None:
            calls.append(text)

    monkeypatch.setattr(
        write_test,
        "resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target found."),
    )
    target = UiTargetRecord(
        1, "symptom.text", "symptom", None, "eghisRichTextBox", None, "Edit", None, "now"
    )

    result = write_test.set_edit_text_to_target_for_test(
        {"eghis_window_title_contains": "Eghis"},
        target,
        "hello",
    )

    assert result.success is True
    assert result.focused is True
    assert calls == ["focus", "hello"]


def test_function_key_paste_test_rejects_empty_text() -> None:
    from KaosEghis.core.eghis_key_paste_test import (
        paste_to_eghis_field_by_function_key_for_test,
    )

    result = paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Symptom",
        "F1",
        "   ",
    )

    assert result.success is False
    assert result.text_length == 3
    assert result.key_sent is False
    assert result.paste_sent is False
    assert "empty" in result.message


def test_function_key_paste_test_rejects_invalid_function_key() -> None:
    from KaosEghis.core.eghis_key_paste_test import (
        paste_to_eghis_field_by_function_key_for_test,
    )

    result = paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Symptom",
        "F9",
        "hello",
    )

    assert result.success is False
    assert result.key_sent is False
    assert "not supported" in result.message


def test_function_key_paste_test_rejects_invalid_destination() -> None:
    from KaosEghis.core.eghis_key_paste_test import (
        paste_to_eghis_field_by_function_key_for_test,
    )

    result = paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Billing",
        "F1",
        "hello",
    )

    assert result.success is False
    assert result.key_sent is False
    assert "Destination 'Billing'" in result.message


def test_function_key_paste_test_rejects_empty_title_setting() -> None:
    from KaosEghis.core.eghis_key_paste_test import (
        paste_to_eghis_field_by_function_key_for_test,
    )

    result = paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "   "},
        "Symptom",
        "F1",
        "hello",
    )

    assert result.success is False
    assert result.eghis_active is False
    assert "title setting is empty" in result.message


def test_function_key_paste_test_rejects_when_eghis_inactive(monkeypatch) -> None:
    import KaosEghis.core.eghis_key_paste_test as eghis_key_paste_test

    monkeypatch.setattr(
        eghis_key_paste_test,
        "is_target_window_active",
        lambda _title: False,
    )

    result = eghis_key_paste_test.paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Symptom",
        "F1",
        "hello",
    )

    assert result.success is False
    assert result.eghis_active is False
    assert "not active" in result.message


def test_function_key_paste_test_sends_function_key_before_ctrl_v(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.eghis_key_paste_test as eghis_key_paste_test

    calls: list[str] = []

    monkeypatch.setattr(
        eghis_key_paste_test,
        "is_target_window_active",
        lambda _title: True,
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "copy_text",
        lambda text: calls.append(f"copy:{text}") or SimpleNamespace(text=text),
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "restore_clipboard",
        lambda _snapshot: calls.append("restore"),
    )
    monkeypatch.setattr(
        eghis_key_paste_test.time,
        "sleep",
        lambda seconds: calls.append(f"sleep:{seconds}"),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        SimpleNamespace(send_keys=lambda keys: calls.append(f"send:{keys}")),
    )

    result = eghis_key_paste_test.paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Symptom",
        "F1",
        "hello",
    )

    assert result.success is True
    assert result.key_sent is True
    assert result.paste_sent is True
    assert result.clipboard_restored is True
    assert calls == [
        "copy:hello",
        "send:{F1}",
        "sleep:0.3",
        "send:^v",
        "sleep:0.15",
        "restore",
    ]


def test_function_key_paste_test_restores_clipboard_after_success(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.eghis_key_paste_test as eghis_key_paste_test

    restored: list[str] = []

    monkeypatch.setattr(
        eghis_key_paste_test,
        "is_target_window_active",
        lambda _title: True,
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "copy_text",
        lambda text: SimpleNamespace(text=text),
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "restore_clipboard",
        lambda _snapshot: restored.append("restored"),
    )
    monkeypatch.setattr(eghis_key_paste_test.time, "sleep", lambda _seconds: None)
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        SimpleNamespace(send_keys=lambda _keys: None),
    )

    result = eghis_key_paste_test.paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Orders",
        "F3",
        "hello",
    )

    assert result.success is True
    assert result.clipboard_restored is True
    assert restored == ["restored"]


def test_function_key_paste_test_restores_clipboard_after_send_failure(
    monkeypatch,
) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.eghis_key_paste_test as eghis_key_paste_test

    restored: list[str] = []
    calls: list[str] = []

    def send_keys(keys: str) -> None:
        calls.append(keys)
        if keys == "^v":
            raise RuntimeError("paste failed")

    monkeypatch.setattr(
        eghis_key_paste_test,
        "is_target_window_active",
        lambda _title: True,
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "copy_text",
        lambda text: SimpleNamespace(text=text),
    )
    monkeypatch.setattr(
        eghis_key_paste_test,
        "restore_clipboard",
        lambda _snapshot: restored.append("restored"),
    )
    monkeypatch.setattr(eghis_key_paste_test.time, "sleep", lambda _seconds: None)
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        SimpleNamespace(send_keys=send_keys),
    )

    result = eghis_key_paste_test.paste_to_eghis_field_by_function_key_for_test(
        {"eghis_window_title_contains": "Eghis"},
        "Diagnosis",
        "F2",
        "hello",
    )

    assert result.success is False
    assert result.key_sent is True
    assert result.paste_sent is False
    assert result.clipboard_restored is True
    assert calls == ["{F2}", "^v"]
    assert restored == ["restored"]


def test_process_detection_matches_executable_stem_and_cmdline(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.emr_detector as emr_detector

    class FakePsutil:
        AccessDenied = RuntimeError
        NoSuchProcess = RuntimeError

        @staticmethod
        def process_iter(_attrs):
            return [
                SimpleNamespace(
                    info={
                        "name": "EGHIS Launcher.exe",
                        "exe": r"C:\\Program Files\\Eghis\\EGHIS Launcher.exe",
                        "cmdline": [r"C:\\Program Files\\Eghis\\EGHIS Launcher.exe"],
                    }
                ),
                SimpleNamespace(
                    info={
                        "name": "Other.exe",
                        "exe": r"C:\\Program Files\\Other\\Other.exe",
                        "cmdline": [r"C:\\Program Files\\Other\\Other.exe"],
                    }
                ),
            ]

    monkeypatch.setitem(sys.modules, "psutil", FakePsutil)

    matches = emr_detector.find_matching_processes("Eghis.exe")

    assert matches == ["EGHIS Launcher.exe"]
    assert emr_detector.check_process_running("Eghis.exe") is True




def test_discover_eghis_returns_red_when_process_window_missing(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    monkeypatch.setattr(connector, "_discover_process_info", lambda _name: None)
    monkeypatch.setattr(connector, "_discover_window_info", lambda _title: None)
    monkeypatch.setattr(connector, "_foreground_handle_matches", lambda _handle: False)

    state = connector.discover_eghis({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.message == "Eghis not found"


def test_discover_eghis_returns_yellow_when_found_but_not_active(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    monkeypatch.setattr(connector, "_discover_process_info", lambda _name: {"process_name": "Eghis.exe", "pid": 12, "exe_path": "C:/Eghis.exe"})
    monkeypatch.setattr(connector, "_discover_window_info", lambda _title: {"window_title": "Eghis EMR", "window_handle": 55})
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_foreground_handle_matches", lambda _handle: False)
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:00:00")

    state = connector.discover_eghis({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "yellow"
    assert state.window_owner_pid == 12
    assert state.message == "Eghis found but not active"


def test_discover_eghis_returns_green_when_found_and_active(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    monkeypatch.setattr(connector, "_discover_process_info", lambda _name: {"process_name": "Eghis.exe", "pid": 12, "exe_path": "C:/Eghis.exe"})
    monkeypatch.setattr(connector, "_discover_window_info", lambda _title: {"window_title": "Eghis EMR", "window_handle": 55})
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_foreground_handle_matches", lambda _handle: True)
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:00:00")

    state = connector.discover_eghis({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "green"
    assert state.window_owner_pid == 12
    assert state.message == "Connected and active"




def test_discover_eghis_blocks_when_window_owner_pid_differs(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    monkeypatch.setattr(connector, "_discover_process_info", lambda _name: {"process_name": "Eghis.exe", "pid": 12, "exe_path": "C:/Eghis.exe"})
    monkeypatch.setattr(connector, "_discover_window_info", lambda _title: {"window_title": "Eghis EMR", "window_handle": 55})
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 99)
    monkeypatch.setattr(connector, "_foreground_handle_matches", lambda _handle: True)
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:00:00")

    state = connector.discover_eghis({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.window_owner_pid == 99
    assert state.message == "window process mismatch"


def test_discover_eghis_prefers_exact_process_match_over_partial_helper_process(
    monkeypatch,
) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.eghis_connector as connector

    class FakePsutil:
        @staticmethod
        def process_iter(_attrs):
            return [
                SimpleNamespace(
                    info={
                        "pid": 10,
                        "name": "eGhis.Forms.exe",
                        "exe": r"C:\\eghis\\eghisEmr\\eGhis.Forms.exe",
                        "cmdline": [r"C:\\eghis\\eghisEmr\\eGhis.Forms.exe"],
                    }
                ),
                SimpleNamespace(
                    info={
                        "pid": 20,
                        "name": "eGhis.exe",
                        "exe": r"C:\\eghis\\eghisEmr\\eGhis.exe",
                        "cmdline": [r"C:\\eghis\\eghisEmr\\eGhis.exe"],
                    }
                ),
            ]

    monkeypatch.setitem(sys.modules, "psutil", FakePsutil)
    monkeypatch.setattr(
        connector,
        "_discover_window_info",
        lambda _title: {"window_title": "Eghis EMR", "window_handle": 55},
    )
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 20)
    monkeypatch.setattr(connector, "_foreground_handle_matches", lambda _handle: True)
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-30T16:05:00")

    state = connector.discover_eghis(
        {
            "eghis_process_name": "Eghis.exe",
            "eghis_window_title_contains": "Eghis",
        }
    )

    assert state.status == "green"
    assert state.pid == 20
    assert state.window_owner_pid == 20
    assert state.process_name == "eGhis.exe"
    assert state.message == "Connected and active"


def test_manual_cached_connection_revalidates_after_ttl_without_reconnect(
    monkeypatch,
) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState(
        "green",
        True,
        "Eghis.exe",
        12,
        "C:/Eghis.exe",
        True,
        "Eghis EMR",
        55,
        12,
        True,
        "2026-06-19T12:00:00",
        "Connected and active",
    )
    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: True)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(
        connector, "_process_identity_matches_state", lambda _state, _settings: True
    )
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(
        connector, "_has_blocking_modal_dialog", lambda _state, _settings: False
    )
    monkeypatch.setattr(
        connector,
        "_get_foreground_window_info",
        lambda: {"window_handle": 55, "window_title": "Eghis EMR"},
    )
    monkeypatch.setattr(
        connector,
        "_focus_and_confirm_window",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("already-foreground window should not be refocused")
        ),
    )
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:01:00")

    state = connector.ensure_cached_connection_ready(
        {
            "eghis_process_name": "Eghis.exe",
            "eghis_window_title_contains": "Eghis",
        }
    )

    assert state.status == "green"
    assert state.last_seen_at == "2026-06-19T12:01:00"
    assert state.message == "Connected and active"


def test_manual_cached_connection_refocuses_on_each_later_macro_run(
    monkeypatch,
) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState(
        "green",
        True,
        "Eghis.exe",
        12,
        "C:/Eghis.exe",
        True,
        "Eghis EMR",
        55,
        12,
        True,
        "2026-06-19T12:00:00",
        "Connected and active",
    )
    foreground = {"window_handle": 999, "window_title": "KaosEghis"}
    focus_calls: list[int] = []

    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(
        connector, "_process_identity_matches_state", lambda _state, _settings: True
    )
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(
        connector, "_has_blocking_modal_dialog", lambda _state, _settings: False
    )
    monkeypatch.setattr(
        connector, "_get_foreground_window_info", lambda: dict(foreground)
    )

    def focus_and_confirm(window_handle, _state, _settings):
        focus_calls.append(window_handle)
        foreground.update(window_handle=55, window_title="Eghis EMR")
        return True, "Connected and active"

    monkeypatch.setattr(connector, "_focus_and_confirm_window", focus_and_confirm)
    settings = {
        "eghis_process_name": "Eghis.exe",
        "eghis_window_title_contains": "Eghis",
    }

    first = connector.ensure_cached_connection_ready(settings)
    foreground.update(window_handle=999, window_title="KaosEghis")
    second = connector.ensure_cached_connection_ready(settings)

    assert first.status == "green"
    assert second.status == "green"
    assert focus_calls == [55, 55]


def test_ensure_ready_for_macro_uses_cached_state_but_still_confirms_focus(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:00", "cached")
    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: False)
    calls = []
    monkeypatch.setattr(connector, "_focus_window_handle", lambda _hwnd: calls.append("focus") or True)
    monkeypatch.setattr(connector, "_get_foreground_window_info", lambda: {"window_handle": 55, "window_title": "Eghis EMR"})
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:01:00")

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert calls == ["focus"]
    assert state.status == "green"
    assert state.message == "Connected and active"


def test_ensure_ready_for_macro_rediscover_once_if_cached_hwnd_stale(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    stale = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 1, 12, False, "2026-06-19T12:00:00", "stale")
    fresh = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:02", "fresh")
    monkeypatch.setattr(connector, "_CACHED_STATE", stale)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda hwnd: hwnd == 55)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda hwnd: 12 if hwnd == 55 else 777)
    calls = []
    monkeypatch.setattr(connector, "refresh_cached_eghis_state", lambda _settings: calls.append("refresh") or fresh)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: False)
    monkeypatch.setattr(connector, "_focus_window_handle", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_foreground_window_info", lambda: {"window_handle": 55, "window_title": "Eghis EMR"})
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:01:00")

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert calls == ["refresh"]
    assert state.status == "green"


def test_ensure_ready_for_macro_blocks_when_rediscovery_fails(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    stale = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 1, 12, False, "2026-06-19T12:00:00", "stale")
    failed = connector.EghisConnectorState("red", False, None, None, None, False, None, None, None, False, None, "Eghis not found")
    monkeypatch.setattr(connector, "_CACHED_STATE", stale)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: True)
    monkeypatch.setattr(connector, "refresh_cached_eghis_state", lambda _settings: failed)

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.message == "rediscovery failed"


def test_ensure_ready_for_macro_blocks_when_modal_dialog_present(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:00", "cached")
    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: True)

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.message == "modal/popup detected"


def test_ensure_ready_for_macro_blocks_on_wrong_foreground_after_focus(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:00", "cached")
    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: False)
    monkeypatch.setattr(connector, "_focus_window_handle", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_foreground_window_info", lambda: {"window_handle": 999, "window_title": "Other app"})
    monkeypatch.setattr(connector, "_foreground_looks_like_modal", lambda _fg, _state, _settings: False)

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.message == "foreground mismatch"


def test_ensure_ready_for_macro_retries_focus_before_succeeding(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    cached = connector.EghisConnectorState(
        "yellow",
        True,
        "Eghis.exe",
        12,
        "C:/Eghis.exe",
        True,
        "Eghis EMR",
        55,
        12,
        False,
        "2026-06-19T12:00:00",
        "cached",
    )
    monkeypatch.setattr(connector, "_CACHED_STATE", cached)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda _hwnd: 12)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: False)
    monkeypatch.setattr(connector, "_focus_window_handle", lambda _hwnd: True)
    monkeypatch.setattr(connector.time, "sleep", lambda _seconds: None)

    foreground_sequence = iter(
        [
            {"window_handle": 99, "window_title": "Other"},
            {"window_handle": 55, "window_title": "Eghis EMR"},
            {"window_handle": 55, "window_title": "Eghis EMR"},
        ]
    )
    monkeypatch.setattr(
        connector,
        "_get_foreground_window_info",
        lambda: next(foreground_sequence),
    )

    state = connector.ensure_ready_for_macro(
        {"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"}
    )

    assert state.status == "green"
    assert state.message == "Connected and active"




def test_cached_state_with_changed_window_owner_pid_forces_rediscovery(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    stale = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 54, 12, False, "2026-06-19T12:00:00", "cached")
    fresh = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:02", "fresh")
    monkeypatch.setattr(connector, "_CACHED_STATE", stale)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: False)
    monkeypatch.setattr(connector, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(connector, "_window_handle_is_valid", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_window_owner_pid", lambda hwnd: 99 if hwnd == 54 else 12)
    calls = []
    monkeypatch.setattr(connector, "refresh_cached_eghis_state", lambda _settings: calls.append("refresh") or fresh)
    monkeypatch.setattr(connector, "_process_identity_matches_state", lambda _state, _settings: True)
    monkeypatch.setattr(connector, "_has_blocking_modal_dialog", lambda _state, _settings: False)
    monkeypatch.setattr(connector, "_focus_window_handle", lambda _hwnd: True)
    monkeypatch.setattr(connector, "_get_foreground_window_info", lambda: {"window_handle": 55, "window_title": "Eghis EMR"})
    monkeypatch.setattr(connector, "_timestamp_now", lambda: "2026-06-19T12:01:00")

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert calls == ["refresh"]
    assert state.status == "green"


def test_rediscovery_with_window_owner_pid_mismatch_blocks(monkeypatch) -> None:
    import KaosEghis.core.eghis_connector as connector

    stale = connector.EghisConnectorState("yellow", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 12, False, "2026-06-19T12:00:00", "cached")
    mismatch = connector.EghisConnectorState("red", True, "Eghis.exe", 12, "C:/Eghis.exe", True, "Eghis EMR", 55, 99, False, "2026-06-19T12:00:02", "window process mismatch")
    monkeypatch.setattr(connector, "_CACHED_STATE", stale)
    monkeypatch.setattr(connector, "_is_state_stale", lambda _state: True)
    monkeypatch.setattr(connector, "refresh_cached_eghis_state", lambda _settings: mismatch)

    state = connector.ensure_ready_for_macro({"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert state.status == "red"
    assert state.message == "window process mismatch"

def test_macro_runner_blocks_real_execution_without_green_connector(monkeypatch) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    import KaosEghis.core.macro_runner as macro_runner

    class FakeState:
        status = "red"
        message = "Eghis not running"

    monkeypatch.setattr(
        macro_runner,
        "ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    result = MacroRunner().run([], dry_run=False, settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert result.success is False
    assert result.message == "Eghis not running"


def test_macro_runner_runs_wait_key_and_paste_text(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroStep

    events = []
    clock = [0.0]

    class FakeState:
        status = "green"
        message = "Connected and active"

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        events.append(("sleep", seconds))
        clock[0] += seconds

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    monkeypatch.setattr(macro_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(macro_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(macro_runner, "copy_text", lambda text: events.append(("copy", text)) or SimpleNamespace(text=text))
    monkeypatch.setattr(macro_runner, "restore_clipboard", lambda snapshot: events.append(("restore", snapshot.text)))
    monkeypatch.setitem(sys.modules, "pywinauto.keyboard", SimpleNamespace(send_keys=lambda keys: events.append(("send", keys))))

    runner = macro_runner.MacroRunner()
    steps = [
        MacroStep(action="wait", options={"ms": 250}),
        MacroStep(action="key", options={"key": "{ENTER}"}),
        MacroStep(action="paste_text", options={"text": "hello"}),
    ]

    result = runner.run(steps, dry_run=False, settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"})

    assert result.success is True
    assert result.executed_steps == 3
    enter_index = events.index(("send", "{ENTER}"))
    wait_events = [seconds for kind, seconds in events[:enter_index] if kind == "sleep"]
    assert wait_events
    assert max(wait_events) <= 0.05
    assert abs(sum(wait_events) - 0.25) < 0.001
    assert events[enter_index:] == [
        ("send", "{ENTER}"),
        ("copy", "hello"),
        ("sleep", 0.05),
        ("send", "^v"),
        ("sleep", 0.15),
        ("restore", "hello"),
    ]


def test_macro_runner_blocks_invalid_action(monkeypatch) -> None:
    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroStep

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    result = macro_runner.MacroRunner().run(
        [MacroStep(action="unknown", options={})],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "unsupported action"


def test_macro_runner_stops_on_first_failed_step(monkeypatch) -> None:
    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroRunResult, MacroStep

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    runner = macro_runner.MacroRunner()
    monkeypatch.setattr(
        runner,
        "_execute_step",
        lambda step: MacroRunResult(True, "ok", 1) if runner._action_name(step) == "wait" else MacroRunResult(False, "key action failed: boom", 0),
    )

    result = runner.run(
        [MacroStep(action="wait", options={"ms": 1}), MacroStep(action="key", options={"key": "A"}), MacroStep(action="paste_text", options={"text": "never"})],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )

    assert result.success is False
    assert result.executed_steps == 1
    assert result.message == "input failed"


def test_macro_runner_cancellation_during_wait_stops_execution(monkeypatch) -> None:
    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroStep

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    runner = macro_runner.MacroRunner()
    clock = [0.0]
    sleeps = []

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
        runner.cancel()

    monkeypatch.setattr(macro_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(macro_runner.time, "sleep", fake_sleep)

    result = runner.run(
        [MacroStep(action="wait", options={"ms": 200}), MacroStep(action="key", options={"key": "A"})],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "Macro execution canceled."
    assert sleeps
    assert max(sleeps) <= 0.05
    assert sum(sleeps) < 0.2


def test_macro_runner_resets_cancellation_state_between_runs(monkeypatch) -> None:
    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroStep

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    runner = macro_runner.MacroRunner()
    clock = [0.0]
    call_count = [0]

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        call_count[0] += 1
        clock[0] += seconds
        if call_count[0] == 1:
            runner.cancel()

    monkeypatch.setattr(macro_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(macro_runner.time, "sleep", fake_sleep)

    first = runner.run(
        [MacroStep(action="wait", options={"ms": 200})],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )
    second = runner.run(
        [MacroStep(action="wait", options={"ms": 0})],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )

    assert first.success is False
    assert first.message == "Macro execution canceled."
    assert second.success is True
    assert second.executed_steps == 1


def test_macro_runner_cancellation_during_wait_keeps_prior_completed_steps(monkeypatch) -> None:
    import KaosEghis.core.macro_runner as macro_runner
    from KaosEghis.core.macro_models import MacroStep

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(macro_runner, "ensure_cached_connection_ready", lambda _settings: FakeState())
    runner = macro_runner.MacroRunner()
    clock = [0.0]
    sleep_calls = [0]

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        sleep_calls[0] += 1
        clock[0] += seconds
        if sleep_calls[0] == 1:
            return
        runner.cancel()

    monkeypatch.setattr(macro_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(macro_runner.time, "sleep", fake_sleep)

    result = runner.run(
        [
            MacroStep(action="wait", options={"ms": 0}),
            MacroStep(action="wait", options={"ms": 200}),
            MacroStep(action="key", options={"key": "A"}),
        ],
        dry_run=False,
        settings={"eghis_process_name": "Eghis.exe", "eghis_window_title_contains": "Eghis"},
    )

    assert result.success is False
    assert result.executed_steps == 1
    assert result.message == "Macro execution canceled."

def test_window_detection_falls_back_to_pywinauto_when_pygetwindow_empty(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import KaosEghis.core.emr_detector as emr_detector

    class FakeDesktop:
        def __init__(self, backend: str) -> None:
            self.backend = backend

        def windows(self) -> list:
            return [
                SimpleNamespace(window_text=lambda: ""),
                SimpleNamespace(window_text=lambda: "Eghis EMR - Chart"),
            ]

    monkeypatch.setitem(
        sys.modules,
        "pygetwindow",
        SimpleNamespace(getAllTitles=lambda: []),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto",
        SimpleNamespace(Desktop=FakeDesktop),
    )

    titles = emr_detector.find_matching_window_titles("Eghis")

    assert titles == ["Eghis EMR - Chart"]
    assert emr_detector.find_window_by_title_contains("Eghis") is True


def test_detect_eghis_connection_reports_setting_mismatch_details(monkeypatch) -> None:
    import KaosEghis.core.emr_detector as emr_detector

    monkeypatch.setattr(
        emr_detector,
        "find_matching_processes",
        lambda _process_name: [],
    )
    monkeypatch.setattr(
        emr_detector,
        "find_matching_window_titles",
        lambda _title_fragment: ["Eghis EMR - Chart"],
    )

    status = emr_detector.detect_eghis_connection("Eghis.exe", "Eghis")

    assert status.connected is False
    assert status.process_running is False
    assert status.window_found is True
    assert "process name setting did not match" in status.message


def test_uia_target_matching_uses_automation_id_and_class_name() -> None:
    from types import SimpleNamespace

    from KaosEghis.core.uia_inspector import _find_target_element
    from KaosEghis.db.repositories import UiTargetRecord

    def element(automation_id: str, class_name: str):
        return SimpleNamespace(
            element_info=SimpleNamespace(
                automation_id=automation_id,
                name="Shared",
                control_type="Edit",
                class_name=class_name,
            )
        )

    target = UiTargetRecord(
        1,
        "prescription.note",
        None,
        None,
        "eghisRichTextBox",
        None,
        None,
        "RichEditD2DPT",
        "now",
    )

    match, message = _find_target_element(
        [
            element("eghisRichTextBox", "WindowsForms10.RichEdit20W.app"),
            element("eghisRichTextBox", "RichEditD2DPT"),
        ],
        target,
    )

    assert match is not None
    assert message == "Target found."


def test_inspect_target_readonly_scopes_lookup_to_parent(monkeypatch) -> None:
    from KaosEghis.core.uia_inspector import inspect_target_readonly
    from KaosEghis.db.repositories import UiTargetRecord

    child_outside_parent = _FakeElement("eghisRichTextBox", class_name="WrongScope")
    child_inside_parent = _FakeElement("eghisRichTextBox", class_name="RichEditD2DPT")
    parent = _FakeElement("TreatmentSymp", children=[child_inside_parent])
    window = _FakeWindow("Eghis", [parent, child_outside_parent])
    _install_fake_pywinauto(monkeypatch, [window])

    target = UiTargetRecord(
        1,
        "prescription.note",
        None,
        "TreatmentSymp",
        "eghisRichTextBox",
        None,
        None,
        "RichEditD2DPT",
        "now",
    )

    result = inspect_target_readonly({"eghis_window_title_contains": "Eghis"}, target)

    assert result.found is True
    assert result.parent_found is True
    assert result.found_class_name == "RichEditD2DPT"
    assert window.descendants_calls == 0
    assert parent.descendants_calls == 1


def test_inspect_target_readonly_without_parent_still_uses_window_lookup(
    monkeypatch,
) -> None:
    from KaosEghis.core.uia_inspector import inspect_target_readonly
    from KaosEghis.db.repositories import UiTargetRecord

    child = _FakeElement("eghisRichTextBox", class_name="RichEditD2DPT")
    window = _FakeWindow("Eghis", [child])
    _install_fake_pywinauto(monkeypatch, [window])

    target = UiTargetRecord(
        1,
        "prescription.note",
        None,
        None,
        "eghisRichTextBox",
        None,
        None,
        "RichEditD2DPT",
        "now",
    )

    result = inspect_target_readonly({"eghis_window_title_contains": "Eghis"}, target)

    assert result.found is True
    assert result.parent_found is None
    assert result.found_class_name == "RichEditD2DPT"
    assert window.descendants_calls == 1


def test_inspect_target_readonly_reports_missing_parent(monkeypatch) -> None:
    from KaosEghis.core.uia_inspector import inspect_target_readonly
    from KaosEghis.db.repositories import UiTargetRecord

    window = _FakeWindow("Eghis", [_FakeElement("OtherPane")])
    _install_fake_pywinauto(monkeypatch, [window])

    target = UiTargetRecord(
        1,
        "prescription.note",
        None,
        "TreatmentSymp",
        "eghisRichTextBox",
        None,
        None,
        "RichEditD2DPT",
        "now",
    )

    result = inspect_target_readonly({"eghis_window_title_contains": "Eghis"}, target)

    assert result.found is False
    assert result.parent_found is False
    assert "Parent automation_id 'TreatmentSymp'" in result.message
    assert "was not found" in result.message
    assert window.descendants_calls == 0


def test_inspect_target_readonly_reports_multiple_parent_matches(monkeypatch) -> None:
    from KaosEghis.core.uia_inspector import inspect_target_readonly
    from KaosEghis.db.repositories import UiTargetRecord

    window = _FakeWindow(
        "Eghis",
        [_FakeElement("TreatmentSymp"), _FakeElement("TreatmentSymp")],
    )
    _install_fake_pywinauto(monkeypatch, [window])

    target = UiTargetRecord(
        1,
        "prescription.note",
        None,
        "TreatmentSymp",
        "eghisRichTextBox",
        None,
        None,
        "RichEditD2DPT",
        "now",
    )

    result = inspect_target_readonly({"eghis_window_title_contains": "Eghis"}, target)

    assert result.found is False
    assert result.parent_found is False
    assert "matched 2 elements" in result.message
    assert window.descendants_calls == 0


def test_inspect_target_readonly_uses_parent_target_id(monkeypatch, tmp_path) -> None:
    import KaosEghis.core.uia_inspector as inspector

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_ui_target, get_ui_target

    child_inside_parent = _FakeElement("eghisRichTextBox", class_name="SharedClass")
    child_outside_parent = _FakeElement("eghisRichTextBox", class_name="SharedClass")
    parent = _FakeElement(
        "TreatmentSymp",
        control_type="Pane",
        class_name="WindowsForms10.Window.8.app.0.2bf8098_r6_ad1",
        children=[child_inside_parent],
    )
    window = _FakeWindow("Eghis", [parent, child_outside_parent])
    _install_fake_pywinauto(monkeypatch, [window])

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="symptom",
            automation_id="TreatmentSymp",
            control_type="Pane",
            class_name="WindowsForms10.Window.8.app.0.2bf8098_r6_ad1",
        )
        create_ui_target(
            connection,
            target_id="symptom.text",
            parent_target_id="symptom",
            automation_id="eghisRichTextBox",
            control_type="Edit",
            class_name="SharedClass",
        )
        target = get_ui_target(connection, "symptom.text")

    assert target is not None

    monkeypatch.setattr(inspector, "connect", lambda: connect(db_path))

    result = inspector.inspect_target_readonly(
        {"eghis_window_title_contains": "Eghis"}, target
    )

    assert result.found is True
    assert result.parent_found is True
    assert result.parent_target_id == "symptom"
    assert result.found_class_name == "SharedClass"
    assert window.descendants_calls == 1
    assert parent.descendants_calls == 1


class _FakeElementInfo:
    def __init__(
        self,
        automation_id: str,
        name: str | None = None,
        control_type: str | None = None,
        class_name: str | None = None,
    ) -> None:
        self.automation_id = automation_id
        self.name = name
        self.control_type = control_type
        self.class_name = class_name


class _FakeElement:
    def __init__(
        self,
        automation_id: str,
        name: str | None = None,
        control_type: str | None = "Edit",
        class_name: str | None = None,
        children: list | None = None,
    ) -> None:
        self.element_info = _FakeElementInfo(
            automation_id,
            name=name,
            control_type=control_type,
            class_name=class_name,
        )
        self._children = children or []
        self.descendants_calls = 0

    def descendants(self) -> list:
        self.descendants_calls += 1
        return self._children

    def is_enabled(self) -> bool:
        return True

    def is_visible(self) -> bool:
        return True


class _FakeWindow:
    def __init__(self, title: str, children: list) -> None:
        self._title = title
        self._children = children
        self.descendants_calls = 0

    def window_text(self) -> str:
        return self._title

    def descendants(self) -> list:
        self.descendants_calls += 1
        return self._children

    def child_window(self, auto_id: str):
        matches = [
            child
            for child in self._children
            if child.element_info.automation_id == auto_id
        ]
        return _FakeChildLookup(matches)


class _FakeChildLookup:
    def __init__(self, matches: list) -> None:
        self._matches = matches

    def wrapper_object(self):
        if not self._matches:
            raise _FakeElementNotFoundError()
        if len(self._matches) > 1:
            raise _FakeElementAmbiguousError(len(self._matches))
        return self._matches[0]


class _FakeElementNotFoundError(Exception):
    pass


class _FakeElementAmbiguousError(Exception):
    def __init__(self, match_count: int) -> None:
        super().__init__(f"matched {match_count} elements")
        self.match_count = match_count


def _install_fake_pywinauto(monkeypatch, windows: list) -> None:
    from types import SimpleNamespace

    class FakeDesktop:
        def __init__(self, backend: str) -> None:
            self.backend = backend

        def windows(self) -> list:
            return windows

    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto",
        SimpleNamespace(Desktop=FakeDesktop),
    )
