import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


DEFAULT_SETTINGS = {
    "eghis_process_name": "Eghis.exe",
    "eghis_window_title_contains": "Eghis",
    "kaosgdd_url": "https://kaosgdd.net",
    "credential_reference_name": "default",
}


@dataclass(frozen=True)
class UiTargetRecord:
    id: int
    target_id: str
    automation_id: str | None
    name: str | None
    control_type: str | None
    created_at: str


@dataclass(frozen=True)
class ItemRecord:
    id: int
    name: str
    item_type: str
    is_enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MacroStepRecord:
    id: int
    item_id: int
    step_order: int
    action: str
    target_id: str | None
    value: str | None
    timeout_seconds: float
    retries: int


SUPPORTED_ITEM_TYPES = {"clipboard", "randomized_clipboard", "macro", "workflow"}
ALLOWED_MACRO_ACTIONS = {
    "check_process",
    "wait_for_target",
    "read_text_uia",
    "type_text_keyboard",
    "type_text_clipboard",
    "set_text_uia",
    "mouse_click",
    "wait_ms",
}


def get_settings(connection: sqlite3.Connection) -> dict[str, str]:
    rows: Iterable[tuple[str, str]] = connection.execute(
        "SELECT key, value FROM app_settings"
    )
    return DEFAULT_SETTINGS | dict(rows)


def set_setting(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )


def set_settings(connection: sqlite3.Connection, settings: dict[str, str]) -> None:
    for key, value in settings.items():
        set_setting(connection, key, value)
    connection.commit()


def list_items(connection: sqlite3.Connection, item_type: str | None = None) -> list[ItemRecord]:
    if item_type is None:
        rows = connection.execute(
            """
            SELECT id, name, item_type, is_enabled, created_at, updated_at
            FROM items
            ORDER BY name
            """
        )
    else:
        rows = connection.execute(
            """
            SELECT id, name, item_type, is_enabled, created_at, updated_at
            FROM items
            WHERE item_type = ?
            ORDER BY name
            """,
            (item_type,),
        )
    return [_item_from_row(row) for row in rows]


def get_item(connection: sqlite3.Connection, item_id: int) -> ItemRecord | None:
    row = connection.execute(
        """
        SELECT id, name, item_type, is_enabled, created_at, updated_at
        FROM items
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return _item_from_row(row)


def create_item(
    connection: sqlite3.Connection,
    name: str,
    item_type: str,
    is_enabled: bool = True,
) -> ItemRecord:
    _validate_item_type(item_type)
    cursor = connection.execute(
        """
        INSERT INTO items (name, item_type, is_enabled)
        VALUES (?, ?, ?)
        """,
        (name.strip(), item_type, int(is_enabled)),
    )
    connection.commit()
    created = get_item(connection, cursor.lastrowid)
    if created is None:
        raise RuntimeError("Failed to create item.")
    return created


def update_item(
    connection: sqlite3.Connection,
    item_id: int,
    name: str,
    item_type: str,
    is_enabled: bool,
) -> ItemRecord | None:
    _validate_item_type(item_type)
    connection.execute(
        """
        UPDATE items
        SET name = ?,
            item_type = ?,
            is_enabled = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name.strip(), item_type, int(is_enabled), item_id),
    )
    connection.commit()
    return get_item(connection, item_id)


def delete_item(connection: sqlite3.Connection, item_id: int) -> bool:
    delete_macro_steps_for_item(connection, item_id)
    cursor = connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
    connection.commit()
    return cursor.rowcount > 0


def list_macro_steps(connection: sqlite3.Connection, item_id: int) -> list[MacroStepRecord]:
    rows = connection.execute(
        """
        SELECT id, item_id, step_order, action, target_id, value, timeout_seconds, retries
        FROM macro_steps
        WHERE item_id = ?
        ORDER BY step_order, id
        """,
        (item_id,),
    )
    return [_macro_step_from_row(row) for row in rows]


def get_macro_step(connection: sqlite3.Connection, step_id: int) -> MacroStepRecord | None:
    return _get_macro_step_by_id(connection, step_id)


def create_macro_step(
    connection: sqlite3.Connection,
    item_id: int,
    step_order: int,
    action: str,
    target_id: str | None = None,
    value: str | None = None,
    timeout_seconds: float = 5.0,
    retries: int = 0,
) -> MacroStepRecord:
    _validate_macro_action(action)
    cursor = connection.execute(
        """
        INSERT INTO macro_steps
            (item_id, step_order, action, target_id, value, timeout_seconds, retries)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            step_order,
            action,
            _blank_to_none(target_id),
            _blank_to_none(value),
            timeout_seconds,
            retries,
        ),
    )
    connection.commit()
    created = _get_macro_step_by_id(connection, cursor.lastrowid)
    if created is None:
        raise RuntimeError("Failed to create macro step.")
    return created


def update_macro_step(
    connection: sqlite3.Connection,
    step_id: int,
    step_order: int,
    action: str,
    target_id: str | None = None,
    value: str | None = None,
    timeout_seconds: float = 5.0,
    retries: int = 0,
) -> MacroStepRecord | None:
    _validate_macro_action(action)
    connection.execute(
        """
        UPDATE macro_steps
        SET step_order = ?,
            action = ?,
            target_id = ?,
            value = ?,
            timeout_seconds = ?,
            retries = ?
        WHERE id = ?
        """,
        (
            step_order,
            action,
            _blank_to_none(target_id),
            _blank_to_none(value),
            timeout_seconds,
            retries,
            step_id,
        ),
    )
    connection.commit()
    return _get_macro_step_by_id(connection, step_id)


def delete_macro_step(connection: sqlite3.Connection, step_id: int) -> bool:
    cursor = connection.execute("DELETE FROM macro_steps WHERE id = ?", (step_id,))
    connection.commit()
    return cursor.rowcount > 0


def delete_macro_steps_for_item(connection: sqlite3.Connection, item_id: int) -> int:
    cursor = connection.execute("DELETE FROM macro_steps WHERE item_id = ?", (item_id,))
    connection.commit()
    return cursor.rowcount


def reorder_macro_steps(connection: sqlite3.Connection, item_id: int) -> list[MacroStepRecord]:
    steps = list_macro_steps(connection, item_id)
    for index, step in enumerate(steps, start=1):
        connection.execute(
            "UPDATE macro_steps SET step_order = ? WHERE id = ?",
            (index, step.id),
        )
    connection.commit()
    return list_macro_steps(connection, item_id)


def validate_macro_dry_run(connection: sqlite3.Connection, item_id: int) -> list[str]:
    errors: list[str] = []
    for step in list_macro_steps(connection, item_id):
        if step.target_id and get_ui_target(connection, step.target_id) is None:
            errors.append(
                f"Step {step.step_order}: target_id '{step.target_id}' is not registered."
            )
    return errors


def list_ui_targets(connection: sqlite3.Connection) -> list[UiTargetRecord]:
    rows = connection.execute(
        """
        SELECT id, target_id, automation_id, name, control_type, created_at
        FROM ui_targets
        ORDER BY target_id
        """
    )
    return [_ui_target_from_row(row) for row in rows]


def get_ui_target(connection: sqlite3.Connection, target_id: str) -> UiTargetRecord | None:
    row = connection.execute(
        """
        SELECT id, target_id, automation_id, name, control_type, created_at
        FROM ui_targets
        WHERE target_id = ?
        """,
        (target_id,),
    ).fetchone()
    if row is None:
        return None
    return _ui_target_from_row(row)


def create_ui_target(
    connection: sqlite3.Connection,
    target_id: str,
    automation_id: str | None = None,
    name: str | None = None,
    control_type: str | None = None,
) -> UiTargetRecord:
    connection.execute(
        """
        INSERT INTO ui_targets (target_id, automation_id, name, control_type)
        VALUES (?, ?, ?, ?)
        """,
        (
            target_id.strip(),
            _blank_to_none(automation_id),
            _blank_to_none(name),
            _blank_to_none(control_type),
        ),
    )
    connection.commit()
    created = get_ui_target(connection, target_id.strip())
    if created is None:
        raise RuntimeError("Failed to create UI target.")
    return created


def update_ui_target(
    connection: sqlite3.Connection,
    target_id: str,
    automation_id: str | None = None,
    name: str | None = None,
    control_type: str | None = None,
) -> UiTargetRecord | None:
    connection.execute(
        """
        UPDATE ui_targets
        SET automation_id = ?,
            name = ?,
            control_type = ?
        WHERE target_id = ?
        """,
        (
            _blank_to_none(automation_id),
            _blank_to_none(name),
            _blank_to_none(control_type),
            target_id,
        ),
    )
    connection.commit()
    return get_ui_target(connection, target_id)


def delete_ui_target(connection: sqlite3.Connection, target_id: str) -> bool:
    cursor = connection.execute(
        "DELETE FROM ui_targets WHERE target_id = ?",
        (target_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def _ui_target_from_row(row: sqlite3.Row | tuple) -> UiTargetRecord:
    return UiTargetRecord(
        id=row[0],
        target_id=row[1],
        automation_id=row[2],
        name=row[3],
        control_type=row[4],
        created_at=row[5],
    )


def _item_from_row(row: sqlite3.Row | tuple) -> ItemRecord:
    return ItemRecord(
        id=row[0],
        name=row[1],
        item_type=row[2],
        is_enabled=bool(row[3]),
        created_at=row[4],
        updated_at=row[5],
    )


def _macro_step_from_row(row: sqlite3.Row | tuple) -> MacroStepRecord:
    return MacroStepRecord(
        id=row[0],
        item_id=row[1],
        step_order=row[2],
        action=row[3],
        target_id=row[4],
        value=row[5],
        timeout_seconds=row[6],
        retries=row[7],
    )


def _get_macro_step_by_id(
    connection: sqlite3.Connection, step_id: int
) -> MacroStepRecord | None:
    row = connection.execute(
        """
        SELECT id, item_id, step_order, action, target_id, value, timeout_seconds, retries
        FROM macro_steps
        WHERE id = ?
        """,
        (step_id,),
    ).fetchone()
    if row is None:
        return None
    return _macro_step_from_row(row)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_item_type(item_type: str) -> None:
    if item_type not in SUPPORTED_ITEM_TYPES:
        raise ValueError(f"Unsupported item_type: {item_type}")


def _validate_macro_action(action: str) -> None:
    if action not in ALLOWED_MACRO_ACTIONS:
        raise ValueError(f"Unsupported macro action: {action}")
