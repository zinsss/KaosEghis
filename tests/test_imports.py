def test_core_modules_import() -> None:
    import KaosEghis.config
    import KaosEghis.core.clipboard_service
    import KaosEghis.core.credential_store
    import KaosEghis.core.emr_detector
    import KaosEghis.core.macro_models
    import KaosEghis.core.macro_runner
    import KaosEghis.core.safety_gate
    import KaosEghis.core.uia_inspector
    import KaosEghis.core.wait_engine
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
            parent_automation_id="TreatmentSymp",
            automation_id="UserNameBox",
            name="Username",
            control_type="Edit",
            class_name="RichEditD2DPT",
        )

        assert created.id > 0
        assert created.target_id == "login.username"
        assert created.parent_automation_id == "TreatmentSymp"
        assert created.automation_id == "UserNameBox"
        assert created.class_name == "RichEditD2DPT"
        assert len(list_ui_targets(connection)) == 1

        found = get_ui_target(connection, "login.username")
        assert found is not None
        assert found.parent_automation_id == "TreatmentSymp"
        assert found.name == "Username"
        assert found.class_name == "RichEditD2DPT"

        updated = update_ui_target(
            connection,
            target_id="login.username",
            parent_automation_id="TreatmentNote",
            automation_id="UserNameField",
            name="Login username",
            control_type="Edit",
            class_name="WindowsForms10.EDIT.app.0.141b42a_r8_ad1",
        )
        assert updated is not None
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
            SELECT target_id, automation_id, class_name, parent_automation_id
            FROM ui_targets
            """
        ).fetchone()

    assert "class_name" in columns
    assert "parent_automation_id" in columns
    assert row == ("existing.target", "eghisRichTextBox", None, None)


def test_items_repository_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_macro_step,
        create_item,
        delete_item,
        get_item,
        list_macro_steps,
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
        create_macro_step(connection, item.id, 1, "wait_ms", value="100")
        assert len(list_macro_steps(connection, item.id)) == 1
        assert delete_item(connection, item.id) is True
        assert get_item(connection, item.id) is None
        assert list_macro_steps(connection, item.id) == []


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
        1, "target.one", "TreatmentSymp", "AutoId", "Name", "Edit", None, "now"
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
    target = UiTargetRecord(1, "target.one", None, "AutoId", "Name", "Edit", None, "now")

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
    target = UiTargetRecord(1, "target.one", None, "AutoId", "Name", "Edit", None, "now")

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
