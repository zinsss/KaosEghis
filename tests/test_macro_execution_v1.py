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


def test_type_text_can_send_enter_before_and_after_text(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    sent_keys: list[str] = []
    monkeypatch.setattr("pywinauto.keyboard.send_keys", sent_keys.append)

    result = MacroRunner()._run_type_text(
        MacroStep(
            action="type_text",
            value="hello",
            options={
                "text": "hello",
                "press_enter_before": True,
                "press_enter_after": True,
            },
        )
    )

    assert result.success is True
    assert result.message == "Pressed Enter, typed text, and pressed Enter."
    assert sent_keys == ["{ENTER}", "hello", "{ENTER}"]


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


def test_paste_text_dry_run_shows_enter_before_and_after(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Paste and submit", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "paste_text",
            value="hello",
            press_enter_before=True,
            press_enter_after=True,
        )

    monkeypatch.setattr(
        "pywinauto.keyboard.send_keys",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not send keys")
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert "paste_text value=hello enter_before=yes enter_after=yes" in result.message


def test_set_text_uia_dry_run_shows_step_without_os_input(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Set UIA Macro", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "set_text_uia",
            target_id="sx",
            value="hello",
            press_enter_before=True,
            press_enter_after=True,
        )

    monkeypatch.setattr(
        "pywinauto.keyboard.send_keys",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not send keys")
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert "set_text_uia target_id=sx value=hello enter_before=yes enter_after=yes" in result.message


def test_set_edit_text_dry_run_shows_step_without_os_input(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Set Edit Text Macro", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "set_edit_text",
            target_id="sx",
            value="hello",
            press_enter_before=True,
            press_enter_after=True,
        )

    monkeypatch.setattr(
        "pywinauto.keyboard.send_keys",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not send keys")
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=True)

    assert result.success is True
    assert "set_edit_text target_id=sx value=hello enter_before=yes enter_after=yes" in result.message


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


def test_set_text_uia_calls_value_pattern(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Set UIA Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "set_text_uia", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeValuePattern:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.CurrentIsReadOnly = False

        def SetValue(self, text: str) -> None:
            self.calls.append(text)

    class FakeElement:
        def __init__(self) -> None:
            self.iface_value = FakeValuePattern()

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.iface_value.calls == ["hello"]


def test_set_text_uia_returns_input_failed_when_value_pattern_is_unavailable(
    monkeypatch, tmp_path
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Set UIA Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "set_text_uia", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        @property
        def iface_value(self):
            raise RuntimeError("pattern missing")

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "input failed"


def test_set_edit_text_calls_element_set_edit_text(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Set Edit Text Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "set_edit_text", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.focus_calls = 0
            self.values: list[str] = []

        def set_focus(self) -> None:
            self.focus_calls += 1

        def set_edit_text(self, text: str) -> None:
            self.values.append(text)

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.focus_calls == 1
    assert fake_element.values == ["hello"]


def test_when_ready_uses_keyboard_focus_wait(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.core.wait_engine import WaitResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="symptom.text", automation_id="eghisRichTextBox")
        item = create_item(connection, "When Ready Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "when_ready", target_id="symptom.text", timeout_seconds=2.0)

    class FakeState:
        status = "green"
        message = "Connected and active"

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )

    def fake_wait(settings, target, condition, timeout_ms=0, poll_ms=0):
        captured["target_id"] = target.target_id
        captured["condition"] = getattr(condition, "value", condition)
        captured["timeout_ms"] = timeout_ms
        return WaitResult(
            success=True,
            message="Condition satisfied: keyboard_focus.",
            target_id=target.target_id,
            condition="keyboard_focus",
            elapsed_ms=50,
            attempts=1,
        )

    monkeypatch.setattr("KaosEghis.core.macro_runner.wait_for_target_condition", fake_wait)

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert captured["target_id"] == "symptom.text"
    assert captured["condition"] == "keyboard_focus"
    assert captured["timeout_ms"] == 2000


def test_when_ready_times_out_when_keyboard_focus_never_arrives(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.core.wait_engine import WaitResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="symptom.text", automation_id="eghisRichTextBox")
        item = create_item(connection, "When Ready Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "when_ready", target_id="symptom.text", timeout_seconds=1.0)

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.wait_for_target_condition",
        lambda settings, target, condition, timeout_ms=0, poll_ms=0: WaitResult(
            success=False,
            message="Timed out waiting for keyboard_focus.",
            target_id=target.target_id,
            condition="keyboard_focus",
            elapsed_ms=1000,
            attempts=10,
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "timeout"


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


def test_emr_parent_target_key_is_converted_to_parent_automation_scope(tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_emr_ui_target

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
            target_key="eghis_main",
            label="eghis",
            automation_id="MdiMain",
            name_match="이지스 전자차트 2.0",
        )
        child = create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="noclaim",
            label="청구안함",
            automation_id="chkInspTargetYn",
            control_type="CheckBox",
            class_name="WindowsForms10.Window.b.app.0.2bf8098_r6_ad1",
            name_match="청구안함",
            parent_target_key="eghis_main",
        )
        runner = MacroRunner(db_path)
        runtime_target = runner._runtime_target_from_emr_target(connection, child)

    assert runtime_target.target_id == "noclaim"
    assert runtime_target.parent_target_id is None
    assert runtime_target.parent_automation_id == "MdiMain"


def test_emr_profile_main_window_automation_id_is_used_as_runtime_scope(
    tmp_path,
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_emr_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Production",
            is_enabled=True,
            is_default=True,
            main_window_automation_id="H2OpdTreatment",
        )
        target = create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="noclaim",
            label="청구안함",
            automation_id="chkInspTargetYn",
            control_type="CheckBox",
            name_match="청구안함",
        )
        runner = MacroRunner(db_path)
        runtime_target = runner._runtime_target_from_emr_target(connection, target)

    assert runtime_target.parent_target_id is None
    assert runtime_target.parent_automation_id == "H2OpdTreatment"


def test_emr_profile_main_window_automation_id_overrides_generic_mdimain_scope(
    tmp_path,
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_emr_ui_target,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Production",
            is_enabled=True,
            is_default=True,
            main_window_automation_id="H2OpdTreatment",
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="eghis_main",
            label="eghis",
            automation_id="MdiMain",
            name_match="이지스 전자차트 2.0",
        )
        target = create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="noclaim",
            label="청구안함",
            automation_id="chkInspTargetYn",
            control_type="CheckBox",
            name_match="청구안함",
            parent_target_key="eghis_main",
        )
        runner = MacroRunner(db_path)
        runtime_target = runner._runtime_target_from_emr_target(connection, target)

    assert runtime_target.parent_automation_id == "H2OpdTreatment"


def test_emr_scope_automation_id_overrides_parent_key_and_profile_scope(
    tmp_path,
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_emr_target_profile,
        create_emr_ui_target,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Production",
            is_enabled=True,
            is_default=True,
            main_window_automation_id="H2OpdTreatment",
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="eghis_main",
            label="eghis",
            automation_id="MdiMain",
            name_match="이지스 전자차트 2.0",
        )
        target = create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="patient_name_row1",
            label="환자명 row 1",
            scope_automation_id="grdOpdList",
            automation_id=None,
            control_type="DataItem",
            name_match="환자명 row 1",
            parent_target_key="eghis_main",
        )
        runner = MacroRunner(db_path)
        runtime_target = runner._runtime_target_from_emr_target(connection, target)

    assert runtime_target.parent_automation_id == "grdOpdList"


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
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.time.sleep",
        lambda seconds: calls.append(("sleep", seconds)),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: calls.append(("send", keys)))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert calls == [
        ("copy", "hello there"),
        ("sleep", 0.05),
        ("send", "^v"),
        ("sleep", 0.15),
        ("restore", "hello there"),
    ]


def test_hotkey_normalizes_braced_sequences(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    sent_keys: list[str] = []
    monkeypatch.setattr("pywinauto.keyboard.send_keys", sent_keys.append)

    result = MacroRunner()._run_hotkey(
        MacroStep(action="hotkey", value="{ENTER},{ENTER}", options={"key": "{ENTER},{ENTER}"})
    )

    assert result.success is True
    assert sent_keys == ["{ENTER}", "{ENTER}"]

    sent_keys.clear()
    result = MacroRunner()._run_hotkey(
        MacroStep(action="hotkey", value="{ALT}{1}", options={"key": "{ALT}{1}"})
    )

    assert result.success is True
    assert sent_keys == ["%{1}"]


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


def test_paste_text_falls_back_to_direct_type_when_clipboard_copy_fails(
    monkeypatch, tmp_path
) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Fallback Paste Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "paste_text", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    events = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda _text: (_ for _ in ()).throw(RuntimeError("clipboard busy")),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: events.append(keys))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert events == ["hello"]


def test_paste_text_restore_failure_does_not_fail_macro(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Restore Failure Macro", "macro", True)
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
        lambda text: type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda _snapshot: (_ for _ in ()).throw(RuntimeError("restore failed")),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert result.message.startswith("Macro execution completed.")


def test_preset_text_can_resolve_saved_display_label(monkeypatch, tmp_path) -> None:
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
        item = create_item(connection, "Label Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "preset_text", value="Random Greeting (random)")
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
        lambda values: values[0],
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda text: copied.append(text) or type("Snapshot", (), {"text": text})(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.restore_clipboard",
        lambda _snapshot: None,
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert copied == ["alpha"]


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


def test_macros_page_splits_executable_and_non_executable_lists(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item
    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosPage

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_item(connection, "Real Macro", "macro", True)
        create_item(connection, "Template Macro", "macro", False)

    page = MacrosPage(db_path)

    assert page.executable_macros_table.rowCount() == 1
    assert page.non_executable_macros_table.rowCount() == 1
    assert page.executable_macros_table.item(0, 1).text() == "Real Macro"
    assert page.non_executable_macros_table.item(0, 1).text() == "Template Macro"


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
    assert dialog.press_enter_before.isEnabled() is False
    assert dialog.press_enter_after.isEnabled() is False
    assert not hasattr(dialog, "step_order")


def test_macro_step_dialog_includes_double_click_action(monkeypatch, tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QWidget

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroStepDialog

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    initialize_database(tmp_path / "KaosEghis.sqlite")

    parent = QWidget()
    dialog = MacroStepDialog(parent)

    assert dialog.action.findText("double_click") >= 0
    assert dialog.action.findText("select") >= 0


def test_select_uses_selection_interface_for_tab_target(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="tab.completed",
            name="완료(*)",
            control_type="TabItem",
        )
        item = create_item(connection, "Tab Select Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "select", target_id="tab.completed")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeSelectionItem:
        def __init__(self) -> None:
            self.select_calls = 0

        def Select(self) -> None:
            self.select_calls += 1

    selection_item = FakeSelectionItem()

    class _ElementInfo:
        control_type = "TabItem"

    class FakeElement:
        def __init__(self) -> None:
            self.element_info = _ElementInfo()
            self.iface_selection_item = selection_item

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert selection_item.select_calls == 1


def test_select_tab_falls_back_to_parent_tab_control_selection(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="tab.completed",
            name="완료(*)",
            control_type="TabItem",
        )
        item = create_item(connection, "Tab Parent Select Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "select", target_id="tab.completed")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeParentTab:
        def __init__(self) -> None:
            self.selected_names: list[str] = []

        def _select(self, name: str) -> None:
            self.selected_names.append(name)

    parent_tab = FakeParentTab()

    class _ElementInfo:
        control_type = "TabItem"
        name = "완료 (30)"

    class FakeElement:
        def __init__(self) -> None:
            self.element_info = _ElementInfo()
            self.iface_selection_item = None

        def parent(self):
            return parent_tab

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert parent_tab.selected_names == ["완료 (30)"]


def test_select_prefers_parent_scope_name_match_for_tab_like_target(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_emr_target_profile, create_emr_ui_target, create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = create_emr_target_profile(
            connection,
            name="Production",
            is_enabled=True,
            is_default=True,
            main_window_automation_id="H2OpdTreatment",
            patient_status_tab_automation_id="tabProc",
        )
        create_emr_ui_target(
            connection,
            profile_id=profile.id,
            target_key="donePt",
            label="완료목록",
            scope_automation_id="tabProc",
            name_match="prefix:완료 (",
        )
        item = create_item(connection, "click test", "macro", True, emr_target_profile_id=profile.id)
        create_macro_step(connection, item.id, 1, "focus_window")
        create_macro_step(connection, item.id, 2, "select", target_id="donePt")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeSelectionItem:
        def __init__(self) -> None:
            self.select_calls = 0

        def Select(self) -> None:
            self.select_calls += 1

    selection_item = FakeSelectionItem()

    class ChildInfo:
        name = "완료 (30)"
        control_type = "TabItem"

    class ChildElement:
        def __init__(self) -> None:
            self.element_info = ChildInfo()
            self.iface_selection_item = selection_item

    class ScopeElement:
        def children(self):
            return [ChildElement()]

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_scope_element",
        lambda _settings, _target: (ScopeElement(), "Parent found."),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (_ for _ in ()).throw(AssertionError("generic child resolution should not run first")),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert selection_item.select_calls == 1


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
    dialog.content.setPlainText(
        "first comment line 1\nfirst comment line 2\n---\n"
        "second comment line 1\nsecond comment line 2"
    )
    assert dialog.values()["item_type"] == "randomized_clipboard"
    assert dialog.values()["bodies"] == [
        "first comment line 1\nfirst comment line 2",
        "second comment line 1\nsecond comment line 2",
    ]


def test_format_current_date_macrotext_uses_korean_date_and_meridiem() -> None:
    from datetime import datetime

    from KaosEghis.ui.tabs.kaoseghis_tab import _format_current_date_macrotext

    morning = _format_current_date_macrotext(datetime(2026, 7, 22, 9, 30))
    afternoon = _format_current_date_macrotext(datetime(2026, 7, 22, 15, 45))

    assert morning == "2026년 07월 22일 오전"
    assert afternoon == "2026년 07월 22일 오후"


def test_macrotexts_page_includes_dynamic_current_date_row_and_copies_it(
    monkeypatch, tmp_path
) -> None:
    _app()

    from datetime import datetime

    from KaosEghis.db.database import initialize_database
    import KaosEghis.ui.tabs.kaoseghis_tab as kaoseghis_tab
    from KaosEghis.ui.tabs.kaoseghis_tab import MacroTextsPage

    copied: list[str] = []
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        kaoseghis_tab,
        "_format_current_date_macrotext",
        lambda now=None: "2026년 07월 22일 오후",
    )
    monkeypatch.setattr(
        kaoseghis_tab,
        "copy_text",
        lambda text: copied.append(text),
    )
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    page = MacroTextsPage(db_path)

    assert page.presets_table.item(0, 1).text() == "Current Date"
    assert page.presets_table.item(0, 2).text() == "Dynamic"

    page.presets_table.selectRow(0)
    page.copy_macrotext()

    assert copied == ["2026년 07월 22일 오후"]
    assert page.status_label.text() == "Copied current date to clipboard."


def test_macrotext_randomized_editor_uses_separator_and_ignores_empty_sections() -> None:
    _app()

    from types import SimpleNamespace

    from PySide6.QtWidgets import QWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import MacroTextDialog

    item = SimpleNamespace(name="Comments", item_type="randomized_clipboard")
    parent = QWidget()
    dialog = MacroTextDialog(parent, item, ["first\ncomment", "second\ncomment"])

    assert dialog.content.toPlainText() == "first\ncomment\n---\nsecond\ncomment"

    dialog.content.setPlainText("\n---\nfirst\ncomment\n---\n\n---\nsecond\n")
    assert dialog.values()["bodies"] == ["first\ncomment", "second"]


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
            "press_enter_before": True,
            "press_enter_after": True,
        },
    )

    assert dialog.press_enter_before.isEnabled() is True
    assert dialog.press_enter_before.isChecked() is True
    assert dialog.press_enter_after.isEnabled() is True
    assert dialog.press_enter_after.isChecked() is True
    assert dialog.values()["press_enter_before"] is True
    assert dialog.values()["press_enter_after"] is True

    dialog.wait_before_enabled.setChecked(True)
    dialog.wait_before_ms.setValue(150)

    values = dialog.values()
    assert values["wait_before_enabled"] is True
    assert values["wait_before_ms"] == 150


def test_macros_page_can_copy_selected_macro(monkeypatch, tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, list_items, list_macro_steps
    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosPage

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Original Macro", "macro", True)
        create_macro_step(
            connection,
            item.id,
            1,
            "type_text",
            value="hello",
            press_enter_before=True,
            press_enter_after=True,
        )

    page = MacrosPage(db_path)
    page.executable_macros_table.selectRow(0)
    page.copy_macro()

    with connect(db_path) as connection:
        macros = list_items(connection, "macro")
        copied = next(macro for macro in macros if macro.name == "Original Macro Copy")
        copied_steps = list_macro_steps(connection, copied.id)

    assert len(macros) == 2
    assert copied_steps[0].press_enter_before is True
    assert copied_steps[0].press_enter_after is True


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
            main_window_automation_id="H2OpdTreatment",
            prescription_grid_automation_id="tree처방_custom",
            symptom_grid_automation_id="grdSymp_custom",
            diagnosis_grid_automation_id="tree상병_custom",
            patient_list_grid_automation_id="grdOpdList_custom",
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
    assert captured_settings["eghis_main_window_automation_id"] == "H2OpdTreatment"
    assert captured_settings["eghis_prescription_grid_automation_id"] == "tree처방_custom"
    assert captured_settings["eghis_symptom_grid_automation_id"] == "grdSymp_custom"
    assert captured_settings["eghis_diagnosis_grid_automation_id"] == "tree상병_custom"
    assert captured_settings["eghis_patient_list_grid_automation_id"] == "grdOpdList_custom"


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


def test_click_prefers_physical_click_before_invoke(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="button.fast",
            automation_id="FastButton",
            control_type="Button",
        )
        item = create_item(connection, "Fast Click Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="button.fast")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.invoked = 0
            self.clicked_input = 0

        def invoke(self) -> None:
            self.invoked += 1

        def click_input(self) -> None:
            self.clicked_input += 1

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.invoked == 0
    assert fake_element.clicked_input == 1


def test_click_falls_back_to_click_input_when_fast_action_is_unavailable(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="checkbox.slow",
            automation_id="CheckSlow",
            control_type="CheckBox",
        )
        item = create_item(connection, "Fallback Click Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="checkbox.slow")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class _ElementInfo:
        control_type = "CheckBox"

    class FakeElement:
        def __init__(self) -> None:
            self.element_info = _ElementInfo()
            self.toggle_calls = 0
            self.click_input_calls = 0

        def toggle(self) -> None:
            self.toggle_calls += 1
            raise RuntimeError("toggle not supported")

        def click_input(self) -> None:
            self.click_input_calls += 1

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.toggle_calls == 0
    assert fake_element.click_input_calls == 1


def test_double_click_uses_double_click_input(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="row.patient",
            automation_id="PatientRow",
            control_type="DataItem",
        )
        item = create_item(connection, "Double Click Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "double_click", target_id="row.patient")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.double_click_input_calls = 0

        def double_click_input(self) -> None:
            self.double_click_input_calls += 1

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.double_click_input_calls == 1


def test_double_click_falls_back_to_double_click(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="row.patient",
            automation_id="PatientRow",
            control_type="DataItem",
        )
        item = create_item(connection, "Double Click Fallback Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "double_click", target_id="row.patient")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeElement:
        def __init__(self) -> None:
            self.double_click_calls = 0

        def double_click(self) -> None:
            self.double_click_calls += 1

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "resolved"),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.double_click_calls == 1


def test_click_targets_tabitem_by_header_area(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(
            connection,
            target_id="tab.completed",
            name="완료(*)",
            control_type="TabItem",
        )
        item = create_item(connection, "Tab Click Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "click", target_id="tab.completed")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class _Rect:
        left = 1988
        top = 194
        right = 2066
        bottom = 219

    class _ElementInfo:
        control_type = "TabItem"

    selection_item = None

    class FakeSelectionItem:
        def __init__(self) -> None:
            self.select_calls = 0

        def Select(self) -> None:
            self.select_calls += 1

    class FakeElement:
        def __init__(self) -> None:
            nonlocal selection_item
            self.element_info = _ElementInfo()
            self.iface_selection_item = FakeSelectionItem()
            selection_item = self.iface_selection_item

        def rectangle(self):
            return _Rect()

    clicked: list[tuple[int, int]] = []
    fake_mouse = SimpleNamespace(
        click=lambda *, button, coords: clicked.append(coords),
    )

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (FakeElement(), None, "resolved"),
    )
    monkeypatch.setitem(__import__("sys").modules, "pywinauto", SimpleNamespace(mouse=fake_mouse))

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert selection_item is not None
    assert selection_item.select_calls == 1
    assert clicked == []


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
    import sys

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
    events = []
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: events.append(keys))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert events == ["hello"]
