from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
from pathlib import Path


APP_DIR_NAME = "KaosEghis"


def get_data_dir() -> Path:
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    return get_data_dir() / "KaosEghis.sqlite"


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = path or get_database_path()
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(path: Path | None = None) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with connect(path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _migrate_ui_targets_columns(connection)
        _migrate_pacs_worklist(connection)
        connection.commit()


def _migrate_ui_targets_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(ui_targets)").fetchall()
    }
    if "class_name" not in columns:
        connection.execute("ALTER TABLE ui_targets ADD COLUMN class_name TEXT")
    if "parent_automation_id" not in columns:
        connection.execute("ALTER TABLE ui_targets ADD COLUMN parent_automation_id TEXT")
    if "parent_target_id" not in columns:
        connection.execute("ALTER TABLE ui_targets ADD COLUMN parent_target_id TEXT")


def _migrate_pacs_worklist(connection: sqlite3.Connection) -> None:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name='pacs_worklist_items'
        """
    ).fetchone()
    if not table_exists:
        return

    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(pacs_worklist_items)").fetchall()
    }
    if "error_message" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN error_message TEXT"
        )
    if "source" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'"
        )
    if "status" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )
    if "updated_at" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
    if "kaospacs_mwl_status" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN kaospacs_mwl_status TEXT NOT NULL DEFAULT 'not_sent'"
        )
    if "kaospacs_mwl_last_synced_at" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN kaospacs_mwl_last_synced_at TEXT"
        )
    if "kaospacs_mwl_error" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN kaospacs_mwl_error TEXT"
        )
