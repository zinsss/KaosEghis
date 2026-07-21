from collections.abc import Iterator
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path

from KaosEghis.db.repositories import get_settings


APP_DIR_NAME = "KaosEghis"
DATA_DIR_ENV_VAR = "KAOSEGHIS_DATA_DIR"


def get_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV_VAR, "").strip()
    if override:
        data_dir = Path(override).expanduser()
    else:
        data_dir = _default_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    return get_data_dir() / "KaosEghis.sqlite"


def describe_database_path(path: Path | None = None) -> str:
    db_path = path or get_database_path()
    return str(db_path.resolve())


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
        _migrate_items(connection)
        _migrate_macro_steps(connection)
        _migrate_ui_targets_columns(connection)
        _migrate_pacs_worklist(connection)
        _migrate_pacs_audit_events(connection)
        _migrate_emr_target_profiles(connection)
        _migrate_emr_ui_targets(connection)
        _seed_default_emr_target_profile(connection)
        connection.commit()


def _default_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data).expanduser() / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


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


def _migrate_items(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(items)").fetchall()
    }
    if "emr_target_profile_id" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN emr_target_profile_id INTEGER")
    if "launcher_section" not in columns:
        connection.execute(
            "ALTER TABLE items ADD COLUMN launcher_section TEXT NOT NULL DEFAULT 'Macro'"
        )
    if "launcher_position" not in columns:
        connection.execute(
            "ALTER TABLE items ADD COLUMN launcher_position INTEGER NOT NULL DEFAULT 0"
        )
    connection.execute(
        """
        UPDATE items
        SET launcher_section = CASE
            WHEN item_type IN ('clipboard', 'randomized_clipboard') THEN 'Comments'
            WHEN launcher_section = 'Medical Documents' THEN 'Comments'
            WHEN launcher_section = 'Eghis' THEN 'Macro'
            WHEN launcher_section = 'ETC' THEN 'Favorite'
            ELSE launcher_section
        END
        WHERE item_type IN ('clipboard', 'randomized_clipboard')
           OR launcher_section IN ('Medical Documents', 'Eghis', 'ETC')
        """
    )
    _normalize_launcher_positions(connection)


def _migrate_macro_steps(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(macro_steps)").fetchall()
    }
    if "press_enter_before" not in columns:
        connection.execute(
            "ALTER TABLE macro_steps "
            "ADD COLUMN press_enter_before INTEGER NOT NULL DEFAULT 0"
        )
    if "press_enter_after" not in columns:
        connection.execute(
            "ALTER TABLE macro_steps "
            "ADD COLUMN press_enter_after INTEGER NOT NULL DEFAULT 0"
        )
    if "wait_before_enabled" not in columns:
        connection.execute(
            "ALTER TABLE macro_steps "
            "ADD COLUMN wait_before_enabled INTEGER NOT NULL DEFAULT 0"
        )
    if "wait_before_ms" not in columns:
        connection.execute(
            "ALTER TABLE macro_steps "
            "ADD COLUMN wait_before_ms INTEGER NOT NULL DEFAULT 100"
        )


def _normalize_launcher_positions(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT id, COALESCE(launcher_section, 'Macro')
        FROM items
        WHERE item_type IN ('macro', 'clipboard', 'randomized_clipboard')
        ORDER BY COALESCE(launcher_section, 'Macro'), launcher_position, id
        """
    ).fetchall()
    positions_by_section: dict[str, int] = {}
    for item_id, launcher_section in rows:
        section = launcher_section or "Macro"
        positions_by_section[section] = positions_by_section.get(section, 0) + 1
        connection.execute(
            """
            UPDATE items
            SET launcher_section = ?,
                launcher_position = ?
            WHERE id = ?
            """,
            (section, positions_by_section[section], item_id),
        )


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
    if "patient_birth_date" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN patient_birth_date TEXT"
        )
    if "patient_sex" not in columns:
        connection.execute(
            "ALTER TABLE pacs_worklist_items ADD COLUMN patient_sex TEXT"
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
    if _pacs_worklist_status_schema_needs_rebuild(connection):
        _rebuild_pacs_worklist_status_schema(connection)


def _pacs_worklist_status_schema_needs_rebuild(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type='table' AND name='pacs_worklist_items'
        """
    ).fetchone()
    if row is None or row[0] is None:
        return False
    sql = str(row[0]).lower()
    return (
        "status in ('active', 'completed', 'expired', 'cancelled', 'error')" not in sql
        or "'done'" in sql
    )


def _rebuild_pacs_worklist_status_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE pacs_worklist_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'expired', 'cancelled', 'error')),
            patient_name TEXT,
            patient_birth_date TEXT,
            patient_sex TEXT,
            chart_no TEXT,
            study TEXT,
            modality TEXT,
            requested_at TEXT,
            accession_or_order_id TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            error_message TEXT,
            kaospacs_mwl_status TEXT NOT NULL DEFAULT 'not_sent',
            kaospacs_mwl_last_synced_at TEXT,
            kaospacs_mwl_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO pacs_worklist_items_new (
            id,
            status,
            patient_name,
            patient_birth_date,
            patient_sex,
            chart_no,
            study,
            modality,
            requested_at,
            accession_or_order_id,
            source,
            error_message,
            kaospacs_mwl_status,
            kaospacs_mwl_last_synced_at,
            kaospacs_mwl_error,
            created_at,
            updated_at
        )
        SELECT
            id,
            CASE
                WHEN lower(status) = 'done' THEN 'completed'
                ELSE lower(status)
            END,
            patient_name,
            patient_birth_date,
            patient_sex,
            chart_no,
            study,
            modality,
            requested_at,
            accession_or_order_id,
            source,
            error_message,
            kaospacs_mwl_status,
            kaospacs_mwl_last_synced_at,
            kaospacs_mwl_error,
            created_at,
            updated_at
        FROM pacs_worklist_items
        """
    )
    connection.execute("DROP TABLE pacs_worklist_items")
    connection.execute("ALTER TABLE pacs_worklist_items_new RENAME TO pacs_worklist_items")


def _migrate_pacs_audit_events(connection: sqlite3.Connection) -> None:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name='pacs_audit_events'
        """
    ).fetchone()
    if table_exists:
        return

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pacs_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            worklist_item_id INTEGER,
            accession_or_order_id TEXT,
            status_before TEXT,
            status_after TEXT,
            summary TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migrate_emr_target_profiles(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(emr_target_profiles)"
        ).fetchall()
    }
    if not columns:
        return
    if "description" not in columns:
        connection.execute(
            "ALTER TABLE emr_target_profiles ADD COLUMN description TEXT"
        )
    if "is_enabled" not in columns:
        connection.execute(
            "ALTER TABLE emr_target_profiles ADD COLUMN is_enabled INTEGER NOT NULL DEFAULT 1"
        )
    if "is_default" not in columns:
        connection.execute(
            "ALTER TABLE emr_target_profiles ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0"
        )
    for name in (
        "process_name",
        "executable_path",
        "window_title_contains",
        "window_class",
        "root_automation_id",
        "main_window_automation_id",
        "login_window_automation_id",
        "patient_search_automation_id",
    ):
        if name not in columns:
            connection.execute(
                f"ALTER TABLE emr_target_profiles ADD COLUMN {name} TEXT"
            )
    if "updated_at" not in columns:
        connection.execute(
            "ALTER TABLE emr_target_profiles ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_target_profiles_name ON emr_target_profiles(name)"
    )


def _migrate_emr_ui_targets(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(emr_ui_targets)").fetchall()
    }
    if not columns:
        return
    for name in (
        "description",
        "scope_automation_id",
        "automation_id",
        "control_type",
        "class_name",
        "name_match",
        "parent_target_key",
        "ancestor_path",
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE emr_ui_targets ADD COLUMN {name} TEXT")
    if "updated_at" not in columns:
        connection.execute(
            "ALTER TABLE emr_ui_targets ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_ui_targets_profile_target_key ON emr_ui_targets(profile_id, target_key)"
    )


def _seed_default_emr_target_profile(connection: sqlite3.Connection) -> None:
    existing = connection.execute(
        "SELECT COUNT(*) FROM emr_target_profiles"
    ).fetchone()
    if existing is None or existing[0] > 0:
        return

    settings = get_settings(connection)
    connection.execute(
        """
        INSERT INTO emr_target_profiles (
            name,
            description,
            is_enabled,
            is_default,
            process_name,
            executable_path,
            window_title_contains
        )
        VALUES (?, ?, 1, 1, ?, ?, ?)
        """,
        (
            "eGHIS Production",
            "Seeded from current KaosEghis settings.",
            settings.get("eghis_process_name", "").strip() or None,
            settings.get("eghis_executable_path", "").strip() or None,
            settings.get("eghis_window_title_contains", "").strip() or None,
        ),
    )
