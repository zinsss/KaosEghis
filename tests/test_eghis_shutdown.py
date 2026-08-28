from __future__ import annotations

from types import SimpleNamespace


def test_end_of_day_macro_is_disabled_hidden_and_idempotent(tmp_path) -> None:
    from KaosEghis.core.eghis_shutdown import create_eghis_end_of_day_macro
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import list_items, list_macro_steps

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro, created = create_eghis_end_of_day_macro(connection)
        same_macro, created_again = create_eghis_end_of_day_macro(connection)
        steps = list_macro_steps(connection, macro.id)
        matching = [
            item
            for item in list_items(connection, "macro")
            if item.name == macro.name
        ]

    assert created is True
    assert created_again is False
    assert same_macro.id == macro.id
    assert macro.is_enabled is False
    assert macro.is_launcher_exposed is False
    assert macro.emr_target_profile_id is not None
    assert len(matching) == 1
    assert [step.action for step in steps] == [
        "unlock_eghis",
        "focus_window",
        "delay_ms",
        "hotkey",
        "confirm_eghis_backup",
        "check_eghis_shutdown_after_backup",
    ]
    assert [step.target_id for step in steps] == [
        "shutdown.lock_password",
        None,
        None,
        None,
        "shutdown.close_yes",
        "shutdown.power_off_after_backup",
    ]
    assert steps[0].value == "eGhis EMR"
    assert steps[3].value == "{ALT}{F4}"


def test_process_scoped_resolver_searches_connected_process_windows(monkeypatch) -> None:
    from KaosEghis.core import uia_inspector
    from KaosEghis.db.repositories import UiTargetRecord

    class FakeElement:
        def __init__(self, automation_id: str, handle: int) -> None:
            self.handle = handle
            self.element_info = SimpleNamespace(
                automation_id=automation_id,
                name="",
                control_type="Edit",
                class_name="WindowsForms10.Edit",
                handle=handle,
            )

    class FakeWindow:
        def __init__(self, descendants: list[FakeElement]) -> None:
            self._descendants = descendants

        def descendants(self) -> list[FakeElement]:
            return self._descendants

    calls: list[tuple[str, int]] = []
    target_element = FakeElement("TxtPW", 502)

    class FakeDesktop:
        def __init__(self, *, backend: str) -> None:
            self.backend = backend

        def windows(self, *, process: int) -> list[FakeWindow]:
            calls.append((self.backend, process))
            return [FakeWindow([target_element])]

    monkeypatch.setattr(
        uia_inspector,
        "get_cached_eghis_state",
        lambda: SimpleNamespace(pid=917),
    )
    target = UiTargetRecord(
        id=1,
        target_id="shutdown.lock_password",
        parent_target_id=None,
        parent_automation_id=None,
        automation_id="TxtPW",
        name=None,
        control_type="Edit",
        class_name=None,
        created_at="2026-08-28T00:00:00",
    )

    resolved, message = uia_inspector.resolve_target_element_in_cached_process(
        target,
        desktop_type=FakeDesktop,
    )

    assert resolved is target_element
    assert calls == [("uia", 917)]
    assert "connected application process" in message


def test_end_of_day_macro_dry_run_never_reads_password_or_sends_input(
    tmp_path,
    monkeypatch,
) -> None:
    from KaosEghis.core.eghis_shutdown import create_eghis_end_of_day_macro
    from KaosEghis.core.macro_runner import MacroRunner
    from KaosEghis.db.database import connect, initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro, _created = create_eghis_end_of_day_macro(connection)

    def fail_password_lookup(_service_name: str) -> str | None:
        raise AssertionError("Dry run must not read a credential.")

    monkeypatch.setattr(
        MacroRunner,
        "_send_keys",
        staticmethod(lambda _value: (_ for _ in ()).throw(
            AssertionError("Dry run must not send keys.")
        )),
    )

    result = MacroRunner(
        db_path,
        password_provider=fail_password_lookup,
    ).execute_macro(macro.id, dry_run=True)

    assert result.success is True
    assert result.executed_steps == 6
    assert "credential_reference=eGhis EMR" in result.message
    assert "password never displayed" in result.message
    assert "test-lock-password" not in result.message
    assert "No actions executed." in result.message


def test_unlock_eghis_uses_vault_password_only_after_target_resolves(
    monkeypatch,
) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    target = object()
    resolutions = iter([(target, "found"), (None, "not found")])
    password_requests: list[str] = []
    typed_values: list[str] = []
    runner = MacroRunner(
        password_provider=lambda name: (
            password_requests.append(name) or "test-lock-password"
        )
    )
    monkeypatch.setattr(runner, "_resolve_process_target", lambda _key: next(resolutions))
    monkeypatch.setattr(runner, "_focus_target_element", lambda _target: (True, "focused"))
    monkeypatch.setattr(
        runner,
        "_type_secret_and_submit",
        lambda value: typed_values.append(value) or True,
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: SimpleNamespace(status="green", message="ready"),
    )

    result = runner._run_unlock_eghis(
        MacroStep(
            action="unlock_eghis",
            target_id="shutdown.lock_password",
            value="eGhis EMR",
            timeout_seconds=0.5,
        ),
        {},
    )

    assert result.success is True
    assert password_requests == ["eGhis EMR"]
    assert typed_values == ["test-lock-password"]
    assert "test-lock-password" not in result.message


def test_unlock_eghis_blocks_without_unlocked_credential(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    runner = MacroRunner(password_provider=lambda _name: None)
    monkeypatch.setattr(
        runner,
        "_resolve_process_target",
        lambda _key: (object(), "found"),
    )
    monkeypatch.setattr(
        runner,
        "_type_secret_and_submit",
        lambda _value: (_ for _ in ()).throw(
            AssertionError("A missing credential must block before typing.")
        ),
    )

    result = runner._run_unlock_eghis(
        MacroStep(
            action="unlock_eghis",
            target_id="shutdown.lock_password",
            value="eGhis EMR",
        ),
        {},
    )

    assert result.success is False
    assert result.message == "credential unavailable"


def test_absent_lock_target_requires_normal_eghis_readiness(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    password_requests: list[str] = []
    runner = MacroRunner(
        password_provider=lambda name: password_requests.append(name) or "unused"
    )
    monkeypatch.setattr(
        runner,
        "_resolve_process_target",
        lambda _key: (None, "target not found"),
    )
    monkeypatch.setattr(
        "KaosEghis.core.macro_runner.ensure_cached_connection_ready",
        lambda _settings: SimpleNamespace(status="green", message="ready"),
    )

    result = runner._run_unlock_eghis(
        MacroStep(
            action="unlock_eghis",
            target_id="shutdown.lock_password",
            value="eGhis EMR",
        ),
        {},
    )

    assert result.success is True
    assert "already unlocked" in result.message
    assert password_requests == []


def test_close_confirmation_activates_only_resolved_target(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    target = object()
    activated: list[object] = []
    runner = MacroRunner()
    monkeypatch.setattr(
        runner,
        "_wait_for_process_target",
        lambda _step: (target, "found"),
    )
    monkeypatch.setattr(
        runner,
        "_activate_target_element",
        lambda value: activated.append(value) or True,
    )

    result = runner._run_confirm_eghis_backup(
        MacroStep(
            action="confirm_eghis_backup",
            target_id="shutdown.close_yes",
        )
    )

    assert result.success is True
    assert activated == [target]


def test_backup_power_off_checkbox_is_not_toggled_when_already_checked(
    monkeypatch,
) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    target = object()
    runner = MacroRunner()
    monkeypatch.setattr(
        runner,
        "_wait_for_process_target",
        lambda _step: (target, "found"),
    )
    monkeypatch.setattr(runner, "_checkbox_checked_state", lambda _target: True)
    monkeypatch.setattr(
        runner,
        "_activate_target_element",
        lambda _target: (_ for _ in ()).throw(
            AssertionError("An already checked option must not be toggled.")
        ),
    )

    result = runner._run_check_eghis_shutdown_after_backup(
        MacroStep(
            action="check_eghis_shutdown_after_backup",
            target_id="shutdown.power_off_after_backup",
        )
    )

    assert result.success is True
    assert "already selected" in result.message


def test_backup_power_off_checkbox_is_checked_and_verified(monkeypatch) -> None:
    from KaosEghis.core.macro_models import MacroStep
    from KaosEghis.core.macro_runner import MacroRunner

    target = object()
    states = iter([False, True])
    activated: list[object] = []
    runner = MacroRunner()
    monkeypatch.setattr(
        runner,
        "_wait_for_process_target",
        lambda _step: (target, "found"),
    )
    monkeypatch.setattr(runner, "_checkbox_checked_state", lambda _target: next(states))
    monkeypatch.setattr(
        runner,
        "_activate_target_element",
        lambda value: activated.append(value) or True,
    )
    monkeypatch.setattr("KaosEghis.core.macro_runner.time.sleep", lambda _seconds: None)

    result = runner._run_check_eghis_shutdown_after_backup(
        MacroStep(
            action="check_eghis_shutdown_after_backup",
            target_id="shutdown.power_off_after_backup",
        )
    )

    assert result.success is True
    assert activated == [target]
