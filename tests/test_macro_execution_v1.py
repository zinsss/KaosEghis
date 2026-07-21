import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_macro_dry_run_does_not_call_os_input_functions(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Dry Run Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "hotkey", value="^a")
        create_macro_step(connection, item.id, 2, "paste_text", value="hello")

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda _text: (_ for _ in ()).throw(AssertionError("copy_text should not be called")),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert result.executed_steps == 2
    assert "No actions executed." in result.message
    assert "hotkey" in result.message
    assert "paste_text" in result.message


def test_type_text_can_send_enter_after_text(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    sent_keys: list[str] = []
    monkeypatch.setattr("pywinauto.keyboard.send_keys", sent_keys.append)

    result = MacroRunner()._run_type_text(
        MacroStep(
            action="type_text",
            value="hello",
            options={"text": "hello", "press_enter_after": True},
        )
    )

    assert result.success is True
    assert result.message == "Typed text and pressed Enter."
    assert sent_keys == ["hello", "{ENTER}"]


def test_type_text_without_enter_option_does_not_send_enter(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    sent_keys: list[str] = []
    monkeypatch.setattr("pywinauto.keyboard.send_keys", sent_keys.append)

    result = MacroRunner()._run_type_text(
        MacroStep(action="type_text", value="hello", options={"text": "hello"})
    )

    assert result.success is True
    assert sent_keys == ["hello"]


def test_type_text_dry_run_shows_enter_option_without_input(
    monkeypatch, tmp_path
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Type and submit", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "type_text",
            value="hello",
            press_enter_after=True,
            wait_before_enabled=True,
            wait_before_ms=125,
        )

    monkeypatch.setattr(
        "pywinauto.keyboard.send_keys",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not send keys")
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert "type_text value=hello enter_after=yes" in result.message
    assert "wait_before=125ms" in result.message


def test_step_wait_runs_before_actual_action(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroRunResult, MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    class FakeState:
        status = "green"
        message = "Connected"

    events: list[str] = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "pywinauto.keyboard.send_keys",
        lambda key: events.append(f"key:{key}"),
    )

    runner = MacroRunner()

    def fake_wait(milliseconds, *, success_message=None):
        events.append(f"wait:{milliseconds}")
        return MacroRunResult(True, success_message or "waited", 1, None)

    monkeypatch.setattr(runner, "_wait_milliseconds", fake_wait)

    result = runner.run(
        [
            MacroStep(
                action="hotkey",
                value="^a",
                options={
                    "key": "^a",
                    "wait_before_enabled": True,
                    "wait_before_ms": 25,
                },
            )
        ],
        dry_run=False,
        settings={},
    )

    assert result.success is True
    assert result.executed_steps == 1
    assert events == ["wait:25", "key:^a"]


def test_disabled_macro_cannot_run_real_execution(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Disabled Macro", "macro", False)

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: (_ for _ in ()).throw(AssertionError("connector should not run")),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "Macro execution blocked: macro is disabled."


def test_paste_text_with_target_requires_resolved_target(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Paste Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "target not found"


def test_paste_text_focuses_resolved_target_before_paste(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Paste Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.focused = False

        def set_focus(self) -> None:
            self.focused = True

    events = []
    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "Target resolved."),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: events.append(("copy", text)) or type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda snapshot: events.append(("restore", snapshot.text)),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: events.append(("send", keys)))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.focused is True
    assert events[:2] == [("copy", "hello"), ("send", "^v")]


def test_reuses_resolved_target_within_single_macro_run(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Cached Target Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", target_id="sx", value="hello")
        create_macro_step(connection, item.id, 2, "click", target_id="sx")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.focused = 0
            self.clicked = 0

        def set_focus(self) -> None:
            self.focused += 1

        def click_input(self) -> None:
            self.clicked += 1

    events = []
    fake_element = FakeElement()
    resolve_calls = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: resolve_calls.append(_target.target_id) or (fake_element, None, "Target resolved."),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: events.append(("copy", text)) or type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda snapshot: events.append(("restore", snapshot.text)),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: events.append(("send", keys)))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert resolve_calls == ["sx"]
    assert fake_element.focused == 1
    assert fake_element.clicked == 1


def test_emr_profile_target_resolution_still_works_with_cache_enabled(
    monkeypatch, tmp_path
) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_emr_ui_target,
        create_item,
        create_macro_step,
        create_ui_target,
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
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="symptom.text",
            label="Symptom Text",
            automation_id="ProfileSymptomBox",
            control_type="Edit",
            class_name="ProfileClass",
        )
        create_ui_target(
            connection,
            target_id="symptom.text",
            automation_id="LegacySymptomBox",
            control_type="Edit",
            class_name="LegacyClass",
        )
        item = create_item(connection, "Profile Cache Macro", "macro", True, profile.id)
        create_macro_step(connection, item.id, 1, "paste_text", target_id="symptom.text", value="hello")
        create_macro_step(connection, item.id, 2, "click", target_id="symptom.text")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def set_focus(self) -> None:
            return None

        def click_input(self) -> None:
            return None

    resolved_automation_ids = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: resolved_automation_ids.append(_target.automation_id)
        or (FakeElement(), None, "Target resolved."),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda _snapshot: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert resolved_automation_ids == ["ProfileSymptomBox"]
    assert "Resolved targets: 1" in result.message
    assert "Cache hits: 1" in result.message
    assert "Cache misses: 1" in result.message


def test_macro_stops_on_failed_step(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_models import MacroRunResult
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Stop On Failure", "macro", True)
        create_macro_step(connection, item.id, 1, "delay_ms", value="0")
        create_macro_step(connection, item.id, 2, "wait_text_or_image", value="todo")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )

    runner = MacroRunner(db_path)
    result = runner.execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.executed_steps == 1
    assert result.failed_step == 2
    assert result.message == "unsupported action"


def test_preset_text_resolves_clipboard_item(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        preset = create_item(connection, "Greeting", "clipboard", True)
        connection.execute(
            "INSERT INTO clipboard_variants (item_id, label, body) VALUES (?, ?, ?)",
            (preset.id, "default", "hello there"),
        )
        item = create_item(connection, "Preset Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "preset_text", value=str(preset.id))
        connection.commit()

    class FakeState:
        status = "green"
        message = "Connected and active"

    calls = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: calls.append(("copy", text)) or type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda snapshot: calls.append(("restore", snapshot.text)),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: calls.append(("send", keys)))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert ("copy", "hello there") in calls
    assert ("send", "^v") in calls


def test_randomized_preset_selects_one_option(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        preset = create_item(connection, "Random Greeting", "randomized_clipboard", True)
        connection.execute(
            "INSERT INTO clipboard_variants (item_id, label, body) VALUES (?, ?, ?)",
            (preset.id, "one", "alpha"),
        )
        connection.execute(
            "INSERT INTO clipboard_variants (item_id, label, body) VALUES (?, ?, ?)",
            (preset.id, "two", "beta"),
        )
        item = create_item(connection, "Random Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "preset_text", value=str(preset.id))
        connection.commit()

    class FakeState:
        status = "green"
        message = "Connected and active"

    copied = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.random.choice",
        lambda values: values[1],
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: copied.append(text) or type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda _snapshot: None,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert copied == ["beta"]


def test_delay_ms_is_represented_in_dry_run(tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Delay Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "delay_ms", value="250")

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert "delay_ms value=250 (dry run only)" in result.message
    assert "Resolved targets: 0" in result.message
    assert "Cache hits: 0" in result.message
    assert "Cache misses: 0" in result.message


def test_cache_clears_between_macro_runs(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Repeat Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="sx")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def click_input(self) -> None:
            return None

    resolve_calls = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: resolve_calls.append(_target.target_id) or (FakeElement(), None, "Target resolved."),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    runner = MacroRunner(db_path)
    first = runner.execute_macro(item.id, dry_run=False)
    second = runner.execute_macro(item.id, dry_run=False)

    assert first.success is True
    assert second.success is True
    assert resolve_calls == ["sx", "sx"]


def test_cache_clears_after_failed_target_resolution(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Retry Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="sx", retries=1)

    class FakeState:
        status = "green"
        message = "Connected and active"

    attempts = []

    def fake_resolve(_settings, _target):
        attempts.append(_target.target_id)
        return None, None, "window not available"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        fake_resolve,
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    runner = MacroRunner(db_path)
    result = runner.execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "window not ready"
    assert attempts == ["sx", "sx"]
    assert runner._resolved_target_cache == {}


def test_cached_connection_check_called_once_per_run_when_possible(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Fast Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", target_id="sx", value="hello")
        create_macro_step(connection, item.id, 2, "click", target_id="sx")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def set_focus(self) -> None:
            return None

        def click_input(self) -> None:
            return None

    ready_calls = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: ready_calls.append("ready") or FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "Target resolved."),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda _snapshot: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert ready_calls == ["ready"]


def test_no_target_handles_saved_in_sqlite(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        worklist_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(macro_runs)")
        }
        ui_target_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ui_targets)")
        }

    assert "resolved_handle" not in worklist_columns
    assert "element_handle" not in worklist_columns
    assert "resolved_handle" not in ui_target_columns
    assert "element_handle" not in ui_target_columns


def test_macros_page_has_dry_run_and_run_selected_macro_buttons() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosPage

    page = MacrosPage()

    assert page.dry_run_button.text() == "Dry run"
    assert page.run_macro_button.text() == "Run selected macro"


def test_new_macro_editor_seeds_focus_window_step(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    parent = QWidget()
    dialog = MacroEditorDialog(parent)

    assert dialog.steps_table.rowCount() == 1
    assert dialog.steps_table.item(0, 1).text() == "focus_window"


def test_macro_editor_reorders_complete_steps_by_drag_order(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QAbstractItemView, QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    parent = QWidget()
    dialog = MacroEditorDialog(parent)
    dialog._append_step(
        {
            "step_order": 2,
            "action": "hotkey",
            "target_id": "",
            "value": "^a",
            "timeout_seconds": 5.0,
            "retries": 0,
            "wait_before_enabled": True,
            "wait_before_ms": 25,
        }
    )
    dialog._append_step(
        {
            "step_order": 3,
            "action": "click",
            "target_id": "submit",
            "value": "",
            "timeout_seconds": 5.0,
            "retries": 0,
            "wait_before_enabled": True,
            "wait_before_ms": 40,
        }
    )

    assert (
        dialog.steps_table.dragDropMode()
        == QAbstractItemView.DragDropMode.InternalMove
    )

    dialog.steps_table.move_row(2, 0)
    steps = dialog.values()["steps"]

    assert [step["action"] for step in steps] == ["click", "focus_window", "hotkey"]
    assert [step["step_order"] for step in steps] == [1, 2, 3]
    assert steps[0]["wait_before_enabled"] is True
    assert steps[0]["wait_before_ms"] == 40
    assert steps[2]["wait_before_enabled"] is True
    assert steps[2]["wait_before_ms"] == 25


def test_new_macro_step_dialog_defaults_to_focus_window(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    parent = QWidget()
    dialog = MacroStepDialog(parent)

    assert dialog.action.currentText() == "focus_window"
    assert dialog.press_enter_after.isEnabled() is False
    assert not hasattr(dialog, "step_order")


def test_macro_step_dialog_selects_saved_macrotext(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, replace_clipboard_variants
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        preset = create_item(connection, "Referral comment", "clipboard", True)
        replace_clipboard_variants(connection, preset.id, ["text"])

    parent = QWidget()
    dialog = MacroStepDialog(
        parent,
        {
            "step_order": 1,
            "action": "preset_text",
            "target_id": "",
            "value": str(preset.id),
            "timeout_seconds": 5.0,
            "retries": 0,
        },
        db_path=db_path,
    )

    assert dialog.preset_text.currentData() == preset.id
    assert "Referral comment" in dialog.preset_text.currentText()
    assert dialog.values()["value"] == str(preset.id)
    assert dialog.value.isVisible() is False


def test_macrotext_dialog_supports_simple_and_randomized_content() -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import MacroTextDialog

    parent = QWidget()
    dialog = MacroTextDialog(parent)
    dialog.name.setText("Comment")
    dialog.content.setPlainText("first line\nsecond line")

    assert dialog.values() == {
        "name": "Comment",
        "item_type": "clipboard",
        "bodies": ["first line\nsecond line"],
    }

    dialog.randomized.setChecked(True)
    assert dialog.values()["item_type"] == "randomized_clipboard"
    assert dialog.values()["bodies"] == ["first line", "second line"]


def test_macro_step_dialog_offers_enter_after_for_type_text(
    monkeypatch, tmp_path
) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    parent = QWidget()
    dialog = MacroStepDialog(
        parent,
        {
            "step_order": 1,
            "action": "type_text",
            "target_id": "",
            "value": "hello",
            "timeout_seconds": 5.0,
            "retries": 0,
            "press_enter_after": True,
        },
    )

    assert dialog.press_enter_after.isEnabled() is True
    assert dialog.press_enter_after.isChecked() is True
    assert dialog.values()["press_enter_after"] is True

    dialog.wait_before_enabled.setChecked(True)
    dialog.wait_before_ms.setValue(150)

    values = dialog.values()
    assert values["wait_before_enabled"] is True
    assert values["wait_before_ms"] == 150


def test_macro_runner_requires_manual_connection_before_real_run(tmp_path) -> None:
    from KaosEghis.core.eghis_connector import clear_cached_eghis_state
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    clear_cached_eghis_state()
    with connect(db_path) as connection:
        item = create_item(connection, "Reconnect Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "focus_window")

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.executed_steps == 0
    assert result.message == "Application not connected. Connect manually and retry."


def test_macro_runner_uses_selected_profile_for_connection_settings(
    monkeypatch, tmp_path
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Notepad",
            is_enabled=True,
            is_default=False,
            process_name="notepad.exe",
            executable_path="C:\\Windows\\System32\\notepad.exe",
            window_title_contains="Notepad",
        )
        item = create_item(connection, "Profile Macro", "macro", True, profile.id)
        create_macro_step(connection, item.id, 1, "focus_window")

    captured_settings: dict[str, str] = {}

    class FakeState:
        status = "green"
        message = "Connected and active"

    def fake_ready(settings):
        captured_settings.update(settings)
        return FakeState()

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        fake_ready,
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert captured_settings["eghis_process_name"] == "notepad.exe"
    assert captured_settings["eghis_window_title_contains"] == "Notepad"
    assert captured_settings["eghis_executable_path"] == "C:\\Windows\\System32\\notepad.exe"


def test_app_startup_does_not_execute_macro(monkeypatch, tmp_path) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.tabs.kaoseghis_tab as kaoseghis_tab
    from KaosEghis.ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(
        kaoseghis_tab.MacroRunner,
        "execute_macro",
        lambda self, item_id, dry_run=False, settings=None: calls.append((item_id, dry_run)),
    )

    window = MainWindow()

    assert window is not None
    assert calls == []


def test_click_failure_is_sanitized(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="button.ok", automation_id="OkButton")
        item = create_item(connection, "Click Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="button.ok")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def click_input(self) -> None:
            raise RuntimeError("low-level click failure")

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "raw internals"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "input failed"


def test_target_resolution_failure_is_sanitized(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="button.ok", automation_id="OkButton")
        item = create_item(connection, "Resolve Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="button.ok")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (None, None, "ElementAmbiguousError: raw internals"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "target not found"


def test_hotkey_failure_is_sanitized(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Hotkey Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "hotkey", value="^a")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: (_ for _ in ()).throw(RuntimeError("raw send_keys failure")))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "input failed"


def test_clipboard_failures_are_sanitized(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Paste Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda _text: (_ for _ in ()).throw(RuntimeError("raw clipboard failure")),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "clipboard failed"
