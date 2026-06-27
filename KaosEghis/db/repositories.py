import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


DEFAULT_SETTINGS = {
    "eghis_process_name": "Eghis.exe",
    "eghis_window_title_contains": "Eghis",
    "kaosgdd_url": "https://kaosgdd.net",
    "credential_reference_name": "default",
    "eghis_db_connection_string": "",
    "eghis_db_image_study_query": "",
}


@dataclass(frozen=True)
class UiTargetRecord:
    id: int
    target_id: str
    parent_target_id: str | None
    parent_automation_id: str | None
    automation_id: str | None
    name: str | None
    control_type: str | None
    class_name: str | None
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


@dataclass(frozen=True)
class PacsWorklistItemRecord:
    id: int
    status: str
    patient_name: str | None
    chart_no: str | None
    study: str | None
    modality: str | None
    requested_at: str | None
    accession_or_order_id: str | None
    source: str
    error_message: str | None
    created_at: str
    updated_at: str


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

ALLOWED_PACS_WORKLIST_STATUS = {"active", "done", "cancelled", "error"}


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


def create_pacs_worklist_item(
    connection: sqlite3.Connection,
    *,
    status: str,
    patient_name: str | None = None,
    chart_no: str | None = None,
    study: str | None = None,
    modality: str | None = None,
    requested_at: str | None = None,
    accession_or_order_id: str | None = None,
    source: str = "manual",
    error_message: str | None = None,
) -> PacsWorklistItemRecord:
    _validate_pacs_worklist_status(status)
    cursor = connection.execute(
        """
        INSERT INTO pacs_worklist_items
            (status, patient_name, chart_no, study, modality, requested_at, accession_or_order_id, source, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            status,
            _blank_to_none(patient_name),
            _blank_to_none(chart_no),
            _blank_to_none(study),
            _blank_to_none(modality),
            _blank_to_none(requested_at),
            _blank_to_none(accession_or_order_id),
            _blank_to_none(source) or "manual",
            _blank_to_none(error_message),
        ),
    )
    connection.commit()
    created = get_pacs_worklist_item(connection, cursor.lastrowid)
    if created is None:
        raise RuntimeError("Failed to create PACS worklist item.")
    return created


def list_pacs_worklist_items(
    connection: sqlite3.Connection,
    status: str | None = None,
) -> list[PacsWorklistItemRecord]:
    if status is None:
        rows = connection.execute(
            """
            SELECT id, status, patient_name, chart_no, study, modality, requested_at,
                   accession_or_order_id, source, error_message, created_at, updated_at
            FROM pacs_worklist_items
            ORDER BY requested_at DESC, id DESC
            """
        )
    else:
        _validate_pacs_worklist_status(status)
        rows = connection.execute(
            """
            SELECT id, status, patient_name, chart_no, study, modality, requested_at,
                   accession_or_order_id, source, error_message, created_at, updated_at
            FROM pacs_worklist_items
            WHERE status = ?
            ORDER BY requested_at DESC, id DESC
            """,
            (status,),
        )
    return [_pacs_worklist_item_from_row(row) for row in rows]


def get_pacs_worklist_item(
    connection: sqlite3.Connection, item_id: int
) -> PacsWorklistItemRecord | None:
    row = connection.execute(
        """
        SELECT id, status, patient_name, chart_no, study, modality, requested_at,
               accession_or_order_id, source, error_message, created_at, updated_at
        FROM pacs_worklist_items
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return _pacs_worklist_item_from_row(row)


def update_pacs_worklist_status(
    connection: sqlite3.Connection,
    item_id: int,
    status: str,
    error_message: str | None = None,
) -> bool:
    _validate_pacs_worklist_status(status)
    cursor = connection.execute(
        """
        UPDATE pacs_worklist_items
        SET status = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, _blank_to_none(error_message), item_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def delete_pacs_worklist_item(connection: sqlite3.Connection, item_id: int) -> bool:
    cursor = connection.execute(
        "DELETE FROM pacs_worklist_items WHERE id = ?",
        (item_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


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
        SELECT id, target_id, parent_target_id, parent_automation_id, automation_id,
               name, control_type, class_name, created_at
        FROM ui_targets
        ORDER BY target_id
        """
    )
    return [_ui_target_from_row(row) for row in rows]


def get_ui_target(connection: sqlite3.Connection, target_id: str) -> UiTargetRecord | None:
    row = connection.execute(
        """
        SELECT id, target_id, parent_target_id, parent_automation_id, automation_id,
               name, control_type, class_name, created_at
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
    parent_target_id: str | None = None,
    parent_automation_id: str | None = None,
    automation_id: str | None = None,
    name: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
) -> UiTargetRecord:
    connection.execute(
        """
        INSERT INTO ui_targets
            (
                target_id,
                parent_target_id,
                parent_automation_id,
                automation_id,
                name,
                control_type,
                class_name
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target_id.strip(),
            _blank_to_none(parent_target_id),
            _blank_to_none(parent_automation_id),
            _blank_to_none(automation_id),
            _blank_to_none(name),
            _blank_to_none(control_type),
            _blank_to_none(class_name),
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
    parent_target_id: str | None = None,
    parent_automation_id: str | None = None,
    automation_id: str | None = None,
    name: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
) -> UiTargetRecord | None:
    connection.execute(
        """
        UPDATE ui_targets
        SET parent_target_id = ?,
            parent_automation_id = ?,
            automation_id = ?,
            name = ?,
            control_type = ?,
            class_name = ?
        WHERE target_id = ?
        """,
        (
            _blank_to_none(parent_target_id),
            _blank_to_none(parent_automation_id),
            _blank_to_none(automation_id),
            _blank_to_none(name),
            _blank_to_none(control_type),
            _blank_to_none(class_name),
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
        parent_target_id=row[2],
        parent_automation_id=row[3],
        automation_id=row[4],
        name=row[5],
        control_type=row[6],
        class_name=row[7],
        created_at=row[8],
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


def _pacs_worklist_item_from_row(
    row: sqlite3.Row | tuple,
) -> PacsWorklistItemRecord:
    return PacsWorklistItemRecord(
        id=row[0],
        status=row[1],
        patient_name=row[2],
        chart_no=row[3],
        study=row[4],
        modality=row[5],
        requested_at=row[6],
        accession_or_order_id=row[7],
        source=row[8],
        error_message=row[9],
        created_at=row[10],
        updated_at=row[11],
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


def _validate_pacs_worklist_status(status: str) -> None:
    if status not in ALLOWED_PACS_WORKLIST_STATUS:
        raise ValueError(f"Unsupported PACS worklist status: {status}")
