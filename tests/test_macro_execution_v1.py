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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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


def test_macros_page_has_dry_run_and_run_selected_macro_buttons() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosPage

    page = MacrosPage()

    assert page.dry_run_button.text() == "Dry run"
    assert page.run_macro_button.text() == "Run selected macro"


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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
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
        "KaosEghis.core.macro_runner.ensure_ready_for_macro",
        lambda _settings: FakeState(),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.copy_text",
        lambda _text: (_ for _ in ()).throw(RuntimeError("raw clipboard failure")),
    )

    result = MacroRunner(db_path).execute_macro(item.id, dry_run=False)

    assert result.success is False
    assert result.message == "clipboard failed"
