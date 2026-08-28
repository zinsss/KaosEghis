from __future__ import annotations

import sqlite3

from KaosEghis.db.repositories import (
    ItemRecord,
    create_item,
    create_macro_step,
    delete_item,
    get_default_emr_target_profile,
    list_items,
)


END_OF_DAY_MACRO_NAME = "eGHIS End-of-Day Backup and Power Off"
END_OF_DAY_CREDENTIAL_REFERENCE = "eGhis EMR"
LOCK_PASSWORD_TARGET_KEY = "shutdown.lock_password"
CLOSE_CONFIRM_TARGET_KEY = "shutdown.close_yes"
POWER_OFF_CHECKBOX_TARGET_KEY = "shutdown.power_off_after_backup"


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
        return existing, False

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
    steps = (
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
    try:
        for step_order, action, target_id, value, timeout_seconds in steps:
            create_macro_step(
                connection,
                macro.id,
                step_order,
                action,
                target_id,
                value,
                timeout_seconds,
                0,
            )
    except Exception:
        delete_item(connection, macro.id)
        raise
    return macro, True
