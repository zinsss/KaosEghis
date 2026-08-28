from __future__ import annotations

import sqlite3

from KaosEghis.db.repositories import (
    ItemRecord,
    create_item,
    create_macro_step,
    delete_macro_steps_for_item,
    delete_item,
    get_default_emr_target_profile,
    list_macro_steps,
    list_items,
    update_item,
)


END_OF_DAY_MACRO_NAME = "eGHIS End-of-Day Backup and Power Off"
END_OF_DAY_CREDENTIAL_REFERENCE = "eGhis EMR"
LOCK_PASSWORD_TARGET_KEY = "shutdown.lock_password"
CLOSE_CONFIRM_TARGET_KEY = "shutdown.close_yes"
BACKUP_CONFIRM_TARGET_KEY = "shutdown.backup_yes"
POWER_OFF_CHECKBOX_TARGET_KEY = "shutdown.power_off_after_backup"

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
