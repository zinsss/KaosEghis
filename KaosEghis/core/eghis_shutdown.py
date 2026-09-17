from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from KaosEghis.core.eghis_connector import get_cached_eghis_state
from KaosEghis.core.pw_runtime import has_unlocked_credential
from KaosEghis.core.uia_inspector import (
    resolve_target_element_in_named_top_level_window,
)
from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    EmrUiTargetRecord,
    ItemRecord,
    UiTargetRecord,
    create_item,
    create_macro_step,
    delete_macro_steps_for_item,
    delete_item,
    get_default_emr_target_profile,
    get_emr_target_profile,
    get_emr_ui_target_by_key,
    list_macro_steps,
    list_items,
    list_scheduler_jobs,
    update_item,
)


END_OF_DAY_MACRO_NAME = "eGHIS End-of-Day Backup and Power Off"
END_OF_DAY_CREDENTIAL_REFERENCE = "eGhis EMR"
LOCK_PASSWORD_TARGET_KEY = "shutdown.lock_password"
CLOSE_CONFIRM_TARGET_KEY = "shutdown.close_yes"
BACKUP_CONFIRM_TARGET_KEY = "shutdown.backup_yes"
POWER_OFF_CHECKBOX_TARGET_KEY = "shutdown.power_off_after_backup"
POWER_OFF_WINDOW_TITLE = "이지스 백업"
SHUTDOWN_TARGET_KEYS = (
    LOCK_PASSWORD_TARGET_KEY,
    CLOSE_CONFIRM_TARGET_KEY,
    BACKUP_CONFIRM_TARGET_KEY,
    POWER_OFF_CHECKBOX_TARGET_KEY,
)


def resolve_native_confirmation_target(
    target: UiTargetRecord,
    window_title: str,
    process_id: int,
) -> tuple[object | None, str]:
    """Read a unique, focusable WinForms confirmation button without activating it."""

    if (
        target.target_id not in {CLOSE_CONFIRM_TARGET_KEY, BACKUP_CONFIRM_TARGET_KEY}
        or target.control_type != "Button"
        or target.automation_id or target.parent_automation_id or target.parent_target_id
        or not target.name or not window_title or process_id <= 0
        or target.name.casefold().startswith(("re:", "regex:", "contains:", "prefix:"))
        or "*" in target.name
    ):
        return None, "target not found"
    # This fallback supports the captured single-modal scope only. More detailed
    # configured ancestors/Automation IDs must still be resolved by UIA.
    try:
        nodes = json.loads(target.ancestor_path or "[]")
    except (TypeError, ValueError):
        return None, "target not found"
    if nodes != [{"name": window_title, "control_type": "Window"}]:
        return None, "target not found"
    try:
        import win32con
        import win32gui
        import win32process
        from pywinauto import Desktop

        windows: list[int] = []

        def collect_window(handle, _extra):
            if (
                win32gui.IsWindowVisible(handle)
                and win32gui.IsWindowEnabled(handle)
                and win32gui.GetWindowText(handle).strip() == window_title
                and win32process.GetWindowThreadProcessId(handle)[1] == process_id
            ):
                windows.append(handle)

        win32gui.EnumWindows(collect_window, None)
        if len(windows) > 1:
            return None, "confirmation target ambiguous"
        if not windows:
            return None, "target not found"
        matches: list[int] = []

        def caption(text: str) -> str:
            return text.replace("&&", "\0").replace("&", "").replace("\0", "&").strip().casefold()

        def collect_button(handle, _extra):
            native_class = win32gui.GetClassName(handle)
            if (
                win32gui.IsWindowVisible(handle)
                and win32gui.IsWindowEnabled(handle)
                and win32process.GetWindowThreadProcessId(handle)[1] == process_id
                and caption(win32gui.GetWindowText(handle)) == caption(target.name)
                and (not target.class_name or native_class == target.class_name)
                and (
                    native_class == "Button"
                    or native_class.startswith(("WindowsForms10.BUTTON.", "WindowsForms10.Window."))
                )
                and win32gui.GetWindowLong(handle, win32con.GWL_STYLE) & win32con.WS_TABSTOP
            ):
                matches.append(handle)

        win32gui.EnumChildWindows(windows[0], collect_button, None)
        if len(matches) > 1:
            return None, "confirmation target ambiguous"
        if len(matches) == 1:
            element = Desktop(backend="win32").window(handle=matches[0]).wrapper_object()
            return element, "Confirmation button found in connected eGHIS dialog."
    except Exception:
        pass
    return None, "target not found"


@dataclass(frozen=True)
class ShutdownTargetDiagnostic:
    target_key: str
    configured: bool
    visible: bool
    owner_pid: int | None
    ownership: str
    message: str


@dataclass(frozen=True)
class ShutdownPreflightResult:
    macro_found: bool
    macro_enabled: bool
    enabled_schedule_count: int
    next_run_at: str | None
    emr_connected: bool
    credential_available: bool
    targets: tuple[ShutdownTargetDiagnostic, ...]


def inspect_eghis_shutdown_preflight(
    db_path: Path | None = None,
) -> ShutdownPreflightResult:
    """Inspect shutdown configuration and currently visible targets without input."""

    effective_path = db_path or get_database_path()
    initialize_database(effective_path)
    with connect(effective_path) as connection:
        macro = next(
            (
                item
                for item in list_items(connection, "macro")
                if item.name == END_OF_DAY_MACRO_NAME
            ),
            None,
        )
        jobs = [
            job
            for job in list_scheduler_jobs(connection)
            if macro is not None and job.macro_item_id == macro.id and job.is_enabled
        ]
        profile = get_default_emr_target_profile(connection)
        if macro is not None and macro.emr_target_profile_id is not None:
            profile = get_emr_target_profile(connection, macro.emr_target_profile_id)
        configured_targets = {
            target_key: (
                get_emr_ui_target_by_key(connection, profile.id, target_key)
                if profile is not None
                else None
            )
            for target_key in SHUTDOWN_TARGET_KEYS
        }

    state = get_cached_eghis_state()
    cached_pid = getattr(state, "pid", None)
    emr_connected = bool(
        state is not None
        and getattr(state, "status", "") in {"green", "yellow"}
        and cached_pid is not None
        and getattr(state, "window_handle", None) is not None
    )
    diagnostics = tuple(
        _inspect_shutdown_target_readonly(target_key, target, cached_pid)
        for target_key, target in configured_targets.items()
    )
    return ShutdownPreflightResult(
        macro_found=macro is not None,
        macro_enabled=bool(macro is not None and macro.is_enabled),
        enabled_schedule_count=len(jobs),
        next_run_at=min((job.next_run_at for job in jobs if job.next_run_at), default=None),
        emr_connected=emr_connected,
        credential_available=has_unlocked_credential(END_OF_DAY_CREDENTIAL_REFERENCE),
        targets=diagnostics,
    )


def format_eghis_shutdown_preflight(result: ShutdownPreflightResult) -> str:
    lines = [
        "End-of-day shutdown preflight (read-only)",
        f"Macro: {'missing' if not result.macro_found else 'enabled' if result.macro_enabled else 'disabled'}",
        f"Enabled schedules: {result.enabled_schedule_count}",
        f"Next run: {result.next_run_at or 'none'}",
        f"EMR connection: {'connected' if result.emr_connected else 'not connected'}",
        f"Credential: {'available' if result.credential_available else 'unavailable'}",
        "Visible targets:",
    ]
    for target in result.targets:
        if not target.configured:
            status = "not configured"
        elif not target.visible:
            status = "not currently open"
        else:
            status = f"visible ({target.ownership})"
        lines.append(f"- {target.target_key}: {status}")
    if not result.macro_enabled:
        lines.append("BLOCKED: the shutdown macro is not executable.")
    lines.append("Staged confirmation/backup targets are expected to be absent before shutdown.")
    lines.append("No windows were opened and no input was sent.")
    return "\n".join(lines)


def _inspect_shutdown_target_readonly(
    target_key: str,
    target: EmrUiTargetRecord | None,
    cached_pid: int | None,
) -> ShutdownTargetDiagnostic:
    if target is None:
        return ShutdownTargetDiagnostic(
            target_key,
            False,
            False,
            None,
            "unknown",
            "Target is not configured.",
        )
    runtime_target = _shutdown_runtime_target(target)
    window_title = _first_ancestor_window_name(target.ancestor_path)
    search_pid = None if target_key == POWER_OFF_CHECKBOX_TARGET_KEY else cached_pid
    if not window_title or (search_pid is None and target_key != POWER_OFF_CHECKBOX_TARGET_KEY):
        return ShutdownTargetDiagnostic(
            target_key,
            True,
            False,
            None,
            "unknown",
            "Target window is not currently inspectable.",
        )
    element, message = resolve_target_element_in_named_top_level_window(
        runtime_target,
        window_title,
        process_id=search_pid,
    )
    owner_pid = _element_process_id(element) if element is not None else None
    ownership = (
        "cached eGHIS process"
        if owner_pid is not None and cached_pid is not None and owner_pid == cached_pid
        else "separate process"
        if owner_pid is not None
        else "unknown process"
    )
    return ShutdownTargetDiagnostic(
        target_key,
        True,
        element is not None,
        owner_pid,
        ownership,
        message,
    )


def _shutdown_runtime_target(target: EmrUiTargetRecord) -> UiTargetRecord:
    return UiTargetRecord(
        id=target.id,
        target_id=target.target_key,
        parent_target_id=None,
        parent_automation_id=target.scope_automation_id,
        automation_id=target.automation_id,
        name=target.name_match,
        control_type=target.control_type,
        class_name=target.class_name,
        created_at=target.created_at,
        ancestor_path=target.ancestor_path,
    )


def _first_ancestor_window_name(ancestor_path: str | None) -> str | None:
    if not ancestor_path:
        return None
    try:
        nodes = json.loads(ancestor_path)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name", "") or "").strip()
        control_type = str(node.get("control_type", "") or "").strip().casefold()
        if name and control_type == "window":
            return name
    return None


def _element_process_id(element) -> int | None:
    if element is None:
        return None
    value = getattr(getattr(element, "element_info", None), "process_id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

END_OF_DAY_STEP_DEFINITIONS = (
    (1, "unlock_eghis", LOCK_PASSWORD_TARGET_KEY, END_OF_DAY_CREDENTIAL_REFERENCE, 10.0),
    (2, "delay_ms", None, "1000", 5.0),
    (3, "hotkey", None, "{ALT}{F4}", 5.0),
    (4, "delay_ms", None, "1000", 5.0),
    (5, "confirm_eghis_backup", CLOSE_CONFIRM_TARGET_KEY, None, 10.0),
    (6, "delay_ms", None, "1000", 5.0),
    (7, "confirm_eghis_backup", BACKUP_CONFIRM_TARGET_KEY, None, 10.0),
    (8, "delay_ms", None, "2000", 5.0),
    (
        9,
        "check_eghis_shutdown_after_backup",
        POWER_OFF_CHECKBOX_TARGET_KEY,
        None,
        30.0,
    ),
)

_LEGACY_SINGLE_CONFIRMATION_STEPS = (
    (1, "unlock_eghis", LOCK_PASSWORD_TARGET_KEY, END_OF_DAY_CREDENTIAL_REFERENCE, 10.0),
    (2, "focus_window", None, None, 5.0),
    (3, "delay_ms", None, "1000", 5.0),
    (4, "hotkey", None, "{ALT}{F4}", 5.0),
    (5, "confirm_eghis_backup", CLOSE_CONFIRM_TARGET_KEY, None, 10.0),
    (
        6,
        "check_eghis_shutdown_after_backup",
        POWER_OFF_CHECKBOX_TARGET_KEY,
        None,
        30.0,
    ),
)


def create_eghis_end_of_day_macro(
    connection: sqlite3.Connection,
) -> tuple[ItemRecord, bool]:
    """Create the disabled reviewed sequence once, without creating a schedule."""

    existing = next(
        (
            item
            for item in list_items(connection, "macro")
            if item.name == END_OF_DAY_MACRO_NAME
        ),
        None,
    )
    if existing is not None:
        if _macro_step_signature(connection, existing.id) != _LEGACY_SINGLE_CONFIRMATION_STEPS:
            return existing, False
        delete_macro_steps_for_item(connection, existing.id)
        _create_steps(connection, existing.id)
        updated = update_item(
            connection,
            existing.id,
            existing.name,
            existing.item_type,
            False,
            emr_target_profile_id=existing.emr_target_profile_id,
            launcher_section=existing.launcher_section,
            is_launcher_exposed=existing.is_launcher_exposed,
        )
        if updated is None:
            raise RuntimeError("Failed to update end-of-day macro.")
        return updated, True

    profile = get_default_emr_target_profile(connection)
    if profile is None:
        raise ValueError("A default EMR target profile is required.")

    macro = create_item(
        connection,
        END_OF_DAY_MACRO_NAME,
        "macro",
        is_enabled=False,
        emr_target_profile_id=profile.id,
        launcher_section="action",
        is_launcher_exposed=False,
    )
    try:
        _create_steps(connection, macro.id)
    except Exception:
        delete_item(connection, macro.id)
        raise
    return macro, True


def _create_steps(connection: sqlite3.Connection, item_id: int) -> None:
    for step_order, action, target_id, value, timeout_seconds in END_OF_DAY_STEP_DEFINITIONS:
        create_macro_step(
            connection,
            item_id,
            step_order,
            action,
            target_id,
            value,
            timeout_seconds,
            0,
        )


def _macro_step_signature(
    connection: sqlite3.Connection,
    item_id: int,
) -> tuple[tuple[int, str, str | None, str | None, float], ...]:
    return tuple(
        (
            step.step_order,
            step.action,
            step.target_id,
            step.value,
            step.timeout_seconds,
        )
        for step in list_macro_steps(connection, item_id)
    )
