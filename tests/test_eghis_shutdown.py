from __future__ import annotations

from types import SimpleNamespace


def _runtime_target(target_id: str, automation_id: str):
    from KaosEghis.db.repositories import UiTargetRecord

    return UiTargetRecord(
        id=1,
        target_id=target_id,
        parent_target_id=None,
        parent_automation_id=None,
        automation_id=automation_id,
        name=None,
        control_type="Edit",
        class_name=None,
        created_at="2026-09-02T00:00:00",
    )


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
        "delay_ms",
        "hotkey",
        "delay_ms",
        "confirm_eghis_backup",
        "delay_ms",
        "confirm_eghis_backup",
        "delay_ms",
        "check_eghis_shutdown_after_backup",
    ]
    assert [step.target_id for step in steps] == [
        "shutdown.lock_password",
        None,
        None,
        None,
        "shutdown.close_yes",
        None,
        "shutdown.backup_yes",
        None,
        "shutdown.power_off_after_backup",
    ]
    assert steps[0].value == "eGhis EMR"
    assert steps[2].value == "{ALT}{F4}"
    assert [steps[index].value for index in (1, 3, 5, 7)] == [
        "1000",
        "1000",
        "1000",
        "2000",
    ]


def test_legacy_single_confirmation_macro_is_corrected_and_disabled(tmp_path) -> None:
    from KaosEghis.core.eghis_shutdown import (
        END_OF_DAY_CREDENTIAL_REFERENCE,
        END_OF_DAY_MACRO_NAME,
        LOCK_PASSWORD_TARGET_KEY,
        POWER_OFF_CHECKBOX_TARGET_KEY,
        create_eghis_end_of_day_macro,
    )
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_item,
        create_macro_step,
        get_default_emr_target_profile,
        list_macro_steps,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        profile = get_default_emr_target_profile(connection)
        assert profile is not None
        macro = create_item(
            connection,
            END_OF_DAY_MACRO_NAME,
            "macro",
            is_enabled=True,
            emr_target_profile_id=profile.id,
            is_launcher_exposed=False,
        )
        legacy_steps = (
            (1, "unlock_eghis", LOCK_PASSWORD_TARGET_KEY, END_OF_DAY_CREDENTIAL_REFERENCE, 10.0),
            (2, "focus_window", None, None, 5.0),
            (3, "delay_ms", None, "1000", 5.0),
            (4, "hotkey", None, "{ALT}{F4}", 5.0),
            (5, "confirm_eghis_backup", "shutdown.close_yes", None, 10.0),
            (
                6,
                "check_eghis_shutdown_after_backup",
                POWER_OFF_CHECKBOX_TARGET_KEY,
                None,
                30.0,
            ),
        )
        for order, action, target_id, value, timeout in legacy_steps:
            create_macro_step(
                connection,
                macro.id,
                order,
                action,
                target_id,
                value,
                timeout,
                0,
            )

        corrected, changed = create_eghis_end_of_day_macro(connection)
        steps = list_macro_steps(connection, corrected.id)

    assert changed is True
    assert corrected.is_enabled is False
    assert len(steps) == 9
    assert steps[4].target_id == "shutdown.close_yes"
    assert steps[6].target_id == "shutdown.backup_yes"


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


def test_named_window_resolver_uses_exact_title_and_process_scope() -> None:
    from KaosEghis.core import uia_inspector

    class FakeElement:
        def __init__(self, automation_id: str) -> None:
            self.element_info = SimpleNamespace(
                automation_id=automation_id,
                name="",
                control_type="Edit",
                class_name="WindowsForms10.Edit",
                handle=600,
            )

    class FakeWindow:
        def __init__(self, title: str, elements: list[FakeElement]) -> None:
            self._title = title
            self._elements = elements

        def window_text(self) -> str:
            return self._title

        def descendants(self) -> list[FakeElement]:
            return self._elements

    calls: list[tuple[str, int]] = []
    target_element = FakeElement("chkShutDown")

    class FakeDesktop:
        def __init__(self, *, backend: str) -> None:
            self.backend = backend

        def windows(self, *, process: int) -> list[FakeWindow]:
            calls.append((self.backend, process))
            return [
                FakeWindow("Other window", [target_element]),
                FakeWindow("이지스 백업", [target_element]),
            ]

    resolved, message = (
        uia_inspector.resolve_target_element_in_named_top_level_window(
            _runtime_target("shutdown.power_off_after_backup", "chkShutDown"),
            "이지스 백업",
            process_id=721,
            desktop_type=FakeDesktop,
        )
    )

    assert resolved is target_element
    assert calls == [("uia", 721)]
    assert "trusted window" in message


def test_power_off_target_may_fall_back_to_exact_backup_window(
    tmp_path,
    monkeypatch,
) -> None:
    import contextlib

    from KaosEghis.core import macro_runner
    from KaosEghis.core.eghis_shutdown import POWER_OFF_CHECKBOX_TARGET_KEY
    from KaosEghis.core.macro_runner import MacroRunner

    target_record = _runtime_target(POWER_OFF_CHECKBOX_TARGET_KEY, "chkShutDown")
    backup_checkbox = object()
    named_calls: list[tuple[str, int | None]] = []
    runner = MacroRunner(tmp_path / "runner.sqlite")
    monkeypatch.setattr(macro_runner, "connect", lambda _path: contextlib.nullcontext(object()))
    monkeypatch.setattr(
        runner,
        "_load_runtime_target_record",
        lambda _connection, _target_id: (target_record, (1, "target", None)),
    )
    monkeypatch.setattr(
        macro_runner,
        "resolve_target_element_in_cached_process",
        lambda _target: (None, "not found"),
    )

    def resolve_named(target, title, *, process_id=None, desktop_type=None):
        assert target is target_record
        named_calls.append((title, process_id))
        return backup_checkbox, "found"

    monkeypatch.setattr(
        macro_runner,
        "resolve_target_element_in_named_top_level_window",
        resolve_named,
    )

    resolved, message = runner._resolve_process_target(POWER_OFF_CHECKBOX_TARGET_KEY)

    assert resolved is backup_checkbox
    assert named_calls == [("이지스 백업", None)]
    assert "connected eGHIS process" in message


def test_non_backup_target_never_uses_cross_process_window_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    import contextlib

    from KaosEghis.core import macro_runner
    from KaosEghis.core.macro_runner import MacroRunner

    target_record = _runtime_target("shutdown.close_yes", "CloseYes")
    runner = MacroRunner(tmp_path / "runner.sqlite")
    monkeypatch.setattr(macro_runner, "connect", lambda _path: contextlib.nullcontext(object()))
    monkeypatch.setattr(
        runner,
        "_load_runtime_target_record",
        lambda _connection, _target_id: (target_record, (1, "target", None)),
    )
    monkeypatch.setattr(
        macro_runner,
        "resolve_target_element_in_cached_process",
        lambda _target: (None, "not found"),
    )
    monkeypatch.setattr(
        macro_runner,
        "resolve_target_element_in_named_top_level_window",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Only the backup checkbox may use cross-process lookup.")
        ),
    )

    resolved, message = runner._resolve_process_target("shutdown.close_yes")

    assert resolved is None
    assert message == "target not found"


def test_shutdown_preflight_reports_disabled_macro_without_exposing_secret(
    tmp_path,
    monkeypatch,
) -> None:
    from KaosEghis.core import eghis_shutdown
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_scheduler_job

    db_path = tmp_path / "preflight.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro, _created = eghis_shutdown.create_eghis_end_of_day_macro(connection)
        create_scheduler_job(
            connection,
            "End of day",
            macro.id,
            "20:30",
            (0, 1, 2, 3, 4),
            is_enabled=True,
            next_run_at="2026-09-02T20:30:00",
        )

    monkeypatch.setattr(
        eghis_shutdown,
        "get_cached_eghis_state",
        lambda: SimpleNamespace(
            status="green",
            pid=721,
            window_handle=12345,
        ),
    )
    monkeypatch.setattr(eghis_shutdown, "has_unlocked_credential", lambda _name: True)
    monkeypatch.setattr(
        eghis_shutdown,
        "_inspect_shutdown_target_readonly",
        lambda target_key, target, cached_pid: eghis_shutdown.ShutdownTargetDiagnostic(
            target_key=target_key,
            configured=target is not None,
            visible=False,
            owner_pid=None,
            ownership="unknown",
            message=f"pid={cached_pid}",
        ),
    )

    result = eghis_shutdown.inspect_eghis_shutdown_preflight(db_path)
    output = eghis_shutdown.format_eghis_shutdown_preflight(result)

    assert result.macro_found is True
    assert result.macro_enabled is False
    assert result.enabled_schedule_count == 1
    assert result.next_run_at == "2026-09-02T20:30:00"
    assert result.emr_connected is True
    assert result.credential_available is True
    assert "Macro: disabled" in output
    assert "BLOCKED" in output
    assert "test-lock-password" not in output
    assert "No windows were opened and no input was sent." in output


def test_shutdown_preflight_scopes_only_backup_checkbox_outside_cached_pid(
    monkeypatch,
) -> None:
    from KaosEghis.core import eghis_shutdown
    from KaosEghis.db.repositories import EmrUiTargetRecord

    calls: list[tuple[str, int | None]] = []

    def target(target_key: str, window_name: str) -> EmrUiTargetRecord:
        return EmrUiTargetRecord(
            id=1,
            profile_id=1,
            target_key=target_key,
            label=target_key,
            description=None,
            scope_automation_id=None,
            automation_id="Target",
            control_type="Button",
            class_name=None,
            name_match=None,
            parent_target_key=None,
            created_at="2026-09-02T00:00:00",
            updated_at="2026-09-02T00:00:00",
            ancestor_path=(
                '[{"name": "'
                + window_name
                + '", "control_type": "Window"}]'
            ),
        )

    def resolve(_target, title, *, process_id=None, desktop_type=None):
        calls.append((title, process_id))
        return None, "not open"

    monkeypatch.setattr(
        eghis_shutdown,
        "resolve_target_element_in_named_top_level_window",
        resolve,
    )

    eghis_shutdown._inspect_shutdown_target_readonly(
        eghis_shutdown.CLOSE_CONFIRM_TARGET_KEY,
        target(eghis_shutdown.CLOSE_CONFIRM_TARGET_KEY, "확인"),
        721,
    )
    eghis_shutdown._inspect_shutdown_target_readonly(
        eghis_shutdown.POWER_OFF_CHECKBOX_TARGET_KEY,
        target(eghis_shutdown.POWER_OFF_CHECKBOX_TARGET_KEY, "이지스 백업"),
        721,
    )

    assert calls == [("확인", 721), ("이지스 백업", None)]


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
    assert result.executed_steps == 9
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
