import sqlite3
from collections.abc import Iterable


DEFAULT_SETTINGS = {
    "eghis_process_name": "Eghis.exe",
    "eghis_window_title_contains": "Eghis",
    "kaosgdd_url": "https://kaosgdd.net",
    "credential_reference_name": "default",
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
