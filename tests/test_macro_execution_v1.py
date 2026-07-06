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


def test_press_action_supports_ordered_sequences(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Press Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "press", value="{F2}>>^a>>{ENTER}")

    class FakeState:
        status = "green"
        message = "Connected and active"

    sent: list[str] = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: sent.append(keys))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert sent == ["{F2}", "^a", "{ENTER}"]


def test_coordinate_click_uses_mouse_click(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Coordinate Click", "macro", True)
        create_macro_step(connection, item.id, 1, "click", value="499,113")

    class FakeState:
        status = "green"
        message = "Connected and active"

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setitem(
        sys.modules,
        "pywinauto",
        type(
            "Pwa",
            (),
            {
                "mouse": type(
                    "Mouse",
                    (),
                    {"click": staticmethod(lambda coords: calls.append(coords))},
                )()
            },
        )(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert calls == [(499, 113)]


def test_is_ready_uia_checks_found_visible_enabled(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.core.uia_inspector import UiaInspectionResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Ready Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "is_ready_uia", target_id="sx")

    class FakeState:
        status = "green"
        message = "Connected and active"

    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.inspect_target_readonly",
        lambda _settings, _target: UiaInspectionResult(
            found=True,
            message="Target found",
            target_id="sx",
            parent_target_id=None,
            parent_automation_id=None,
            parent_found=None,
            automation_id="SymptomBox",
            name=None,
            control_type="Edit",
            class_name=None,
            found_name="Field",
            found_control_type="Edit",
            found_class_name=None,
            is_enabled=True,
            is_visible=True,
            text_value=None,
        ),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True


def test_copy_text_and_last_text_placeholder(monkeypatch, tmp_path) -> None:
    import sys

    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Copy Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "copy_text", value="random:alpha||beta")
        create_macro_step(connection, item.id, 2, "paste_text", value="{{last_text}}")

    class FakeState:
        status = "green"
        message = "Connected and active"

    copied: list[str] = []
    sent: list[str] = []
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
        sys.modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda keys: sent.append(keys))})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert copied == ["beta", "beta"]
    assert sent == ["^v"]


def test_set_text_uses_value_pattern_when_available(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step, create_ui_target

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_ui_target(connection, target_id="sx", automation_id="SymptomBox")
        item = create_item(connection, "Set Text Macro", "macro", True)
        create_macro_step(connection, item.id, 1, "set_text", target_id="sx", value="hello")

    class FakeState:
        status = "green"
        message = "Connected and active"

    class FakeValue:
        CurrentIsReadOnly = False

        def __init__(self) -> None:
            self.values: list[str] = []

        def SetValue(self, text: str) -> None:
            self.values.append(text)

    class FakeElement:
        def __init__(self) -> None:
            self.iface_value = FakeValue()

    fake_element = FakeElement()
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.resolve_target_element",
        lambda _settings, _target: (fake_element, None, "Target resolved."),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert fake_element.iface_value.values == ["hello"]


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


def test_focus_window_step_does_not_repeat_connector_check_within_same_run(
    monkeypatch, tmp_path
) -> None:
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, create_macro_step

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        item = create_item(connection, "Fast F1", "macro", True)
        create_macro_step(connection, item.id, 1, "focus_window")
        create_macro_step(connection, item.id, 2, "hotkey", value="{F1}")

    class FakeState:
        status = "green"
        message = "Connected and active"

    ready_calls = []
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: ready_calls.append("ready") or FakeState(),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pywinauto.keyboard",
        type("Keyboard", (), {"send_keys": staticmethod(lambda _keys: None)})(),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is True
    assert ready_calls == ["ready"]


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
