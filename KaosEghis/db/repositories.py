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


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
