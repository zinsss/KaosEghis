from collections.abc import Iterator
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path

from KaosEghis.db.repositories import get_settings


APP_DIR_NAME = "KaosEghis"
DATA_DIR_ENV_VAR = "KAOSEGHIS_DATA_DIR"

VACCINE_EMR_TARGET_DEFAULTS = (
    (
        "vaccine.patient_chart_no",
        "Vaccine patient chart No",
        "txt환자번호",
    ),
    (
        "vaccine.patient_resident_id",
        "Vaccine patient resident No",
        "txt주민번호",
    ),
    (
        "vaccine.patient_name",
        "Vaccine patient name",
        "txt환자명",
    ),
    (
        "vaccine.patient_sex_age",
        "Vaccine patient sex and age",
        "lblSexAge",
    ),
    (
        "vaccine.patient_birth_date",
        "Vaccine patient date of birth",
        "dateEdit1",
    ),
    (
        "vaccine.patient_phone",
        "Vaccine patient telephone",
        "txt휴대폰",
    ),
    (
        "vaccine.patient_telephone",
        "Vaccine patient secondary telephone",
        "txt전화",
    ),
    (
        "vaccine.patient_address",
        "Vaccine patient address",
        "txt주소",
    ),
)

EGHIS_SHUTDOWN_TARGET_DEFAULTS = (
    {
        "target_key": "shutdown.lock_password",
        "label": "eGHIS inactivity-lock password",
        "description": "Password-only field for the verified eGHIS inactivity lock.",
        "automation_id": "TxtPW",
        "control_type": "Edit",
        "name_match": None,
        "ancestor_path": (
            '[{"name":"로그인 안내","control_type":"Window"},'
            '{"name":"이지스 전자차트 2.0","control_type":"Window"}]'
        ),
    },
    {
        "target_key": "shutdown.close_yes",
        "label": "eGHIS close confirmation",
        "description": "First Yes button that confirms closing eGHIS.",
        "automation_id": None,
        "control_type": "Button",
        "name_match": "예(Y)",
        "ancestor_path": (
            '[{"name":"확인","control_type":"Window"},'
            '{"name":"이지스 전자차트 2.0","control_type":"Window"}]'
        ),
    },
    {
        "target_key": "shutdown.backup_yes",
        "label": "eGHIS database backup confirmation",
        "description": "Second Yes button that confirms the eGHIS database backup.",
        "automation_id": None,
        "control_type": "Button",
        "name_match": "예(Y)",
        "ancestor_path": '[{"name":"확인","control_type":"Window"}]',
    },
    {
        "target_key": "shutdown.power_off_after_backup",
        "label": "Power off after eGHIS backup",
        "description": "Checkbox that powers off the workstation after backup completes.",
        "automation_id": "chkShutDown",
        "control_type": "CheckBox",
        "name_match": "백업 완료 후 PC를 자동 종료 합니다.",
        "ancestor_path": '[{"name":"이지스 백업","control_type":"Window"}]',
    },
)


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
def connect(
    path: Path | None = None,
    *,
    timeout: float = 5.0,
) -> Iterator[sqlite3.Connection]:
    db_path = path or get_database_path()
    connection = sqlite3.connect(db_path, timeout=timeout)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(path: Path | None = None) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with connect(path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _migrate_items(connection)
        _migrate_launcher_collections(connection)
        _migrate_macro_steps(connection)
        _migrate_ui_targets_columns(connection)
        _migrate_pacs_worklist(connection)
        _migrate_pacs_audit_events(connection)
        _migrate_emr_target_profiles(connection)
        _migrate_emr_ui_targets(connection)
        _migrate_unstable_patient_number_selectors(connection)
        _migrate_vaccine_tables(connection)
        _seed_default_emr_target_profile(connection)
        _seed_vaccine_emr_targets(connection)
        _seed_eghis_shutdown_targets(connection)
        _seed_default_socl_vocabulary(connection)
        _seed_default_vaccine_types(connection)
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
    if "is_launcher_exposed" not in columns:
        connection.execute(
            "ALTER TABLE items "
            "ADD COLUMN is_launcher_exposed INTEGER NOT NULL DEFAULT 1"
        )
    connection.execute(
        """
        UPDATE items
        SET launcher_section = CASE
            WHEN item_type IN ('clipboard', 'randomized_clipboard') THEN 'Comments'
            WHEN launcher_section = 'Medical Documents' THEN 'Comments'
            WHEN launcher_section = 'Eghis' THEN 'Macro'
            WHEN item_type = 'macro' AND launcher_section IN ('ETC', 'Favorite') THEN 'Macro'
            WHEN launcher_section IN ('ETC', 'Favorite') THEN 'Actions'
            WHEN item_type = 'macro' AND launcher_section = 'Actions' THEN 'Macro'
            ELSE launcher_section
        END
        WHERE item_type IN ('clipboard', 'randomized_clipboard')
           OR launcher_section IN ('Medical Documents', 'Eghis', 'ETC', 'Favorite', 'Actions')
        """
    )
    _normalize_launcher_positions(connection)


def _migrate_launcher_collections(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS launcher_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            launcher_section TEXT NOT NULL DEFAULT 'Macro',
            launcher_position INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS launcher_collection_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            macro_item_id INTEGER NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (collection_id) REFERENCES launcher_collections(id),
            FOREIGN KEY (macro_item_id) REFERENCES items(id)
        )
        """
    )
    connection.execute(
        """
        UPDATE launcher_collections
        SET launcher_section = CASE
            WHEN launcher_section = 'Medical Documents' THEN 'Comments'
            WHEN launcher_section = 'Eghis' THEN 'Macro'
            WHEN launcher_section IN ('ETC', 'Favorite', 'Actions') THEN 'Macro'
            ELSE launcher_section
        END
        WHERE launcher_section IN ('Medical Documents', 'Eghis', 'ETC', 'Favorite', 'Actions')
        """
    )


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
    connection.execute(
        """
        UPDATE macro_steps
        SET action = 'click'
        WHERE action = 'mouse_click'
        """
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
        "patient_status_tab_automation_id",
        "login_window_automation_id",
        "patient_search_automation_id",
        "prescription_grid_automation_id",
        "symptom_grid_automation_id",
        "diagnosis_grid_automation_id",
        "patient_list_grid_automation_id",
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


def _migrate_vaccine_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vaccine_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT,
            chart_note_template TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vaccine_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaccine_type_id INTEGER,
            vaccine_type_name TEXT NOT NULL,
            patient_chart_no TEXT,
            patient_resident_id TEXT,
            patient_name TEXT,
            patient_sex TEXT,
            patient_age TEXT,
            patient_phone TEXT,
            patient_address TEXT,
            status TEXT NOT NULL DEFAULT 'prepared',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vaccine_type_id) REFERENCES vaccine_types(id)
        )
        """
    )


def _seed_default_vaccine_types(connection: sqlite3.Connection) -> None:
    count_row = connection.execute(
        "SELECT COUNT(*) FROM vaccine_types"
    ).fetchone()
    if count_row is not None and int(count_row[0] or 0) > 0:
        return
    connection.executemany(
        """
        INSERT INTO vaccine_types (name, code, chart_note_template, is_active, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ("Influenza", "flu", "인플루엔자 예방접종 시행함.", 1, 1),
            ("COVID-19", "covid", "코로나19 예방접종 시행함.", 1, 2),
        ),
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


def _migrate_unstable_patient_number_selectors(
    connection: sqlite3.Connection,
) -> None:
    for key in (
        "eghis_patient_alert_chart_automation_id",
        "eghis_patient_alert_chart_name",
    ):
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is not None and str(row[0] or "").strip().isdigit():
            connection.execute(
                "UPDATE app_settings SET value = '', updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                (key,),
            )

    rows = connection.execute(
        """
        SELECT id, automation_id, name_match
        FROM emr_ui_targets
        WHERE target_key = 'vaccine.patient_chart_no'
        """
    ).fetchall()
    for target_id, automation_id, name_match in rows:
        updates: list[str] = []
        if str(automation_id or "").strip().isdigit():
            updates.append("automation_id = NULL")
        if str(name_match or "").strip().isdigit():
            updates.append("name_match = NULL")
        if updates:
            connection.execute(
                f"UPDATE emr_ui_targets SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (target_id,),
            )


def _seed_default_emr_target_profile(connection: sqlite3.Connection) -> None:
    existing = connection.execute(
        "SELECT COUNT(*) FROM emr_target_profiles"
    ).fetchone()
    if existing is None:
        return
    if existing[0] > 0:
        return

    settings = get_settings(connection)
    cursor = connection.execute(
        """
        INSERT INTO emr_target_profiles (
            name,
            description,
            is_enabled,
            is_default,
            process_name,
            executable_path,
            window_title_contains,
            patient_status_tab_automation_id,
            prescription_grid_automation_id,
            symptom_grid_automation_id,
            diagnosis_grid_automation_id,
            patient_list_grid_automation_id
        )
        VALUES (?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "eGHIS Production",
            "Seeded from current KaosEghis settings.",
            settings.get("eghis_process_name", "").strip() or None,
            settings.get("eghis_executable_path", "").strip() or None,
            settings.get("eghis_window_title_contains", "").strip() or None,
            settings.get("eghis_patient_status_tab_automation_id", "").strip() or "tabProc",
            "tree처방",
            "grdSymp",
            "tree상병",
            "grdOpdList",
        ),
    )


def _seed_vaccine_emr_targets(connection: sqlite3.Connection) -> None:
    profile_ids = connection.execute(
        "SELECT id FROM emr_target_profiles ORDER BY id"
    ).fetchall()
    for (profile_id,) in profile_ids:
        connection.executemany(
            """
            INSERT INTO emr_ui_targets (
                profile_id,
                target_key,
                label,
                automation_id
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id, target_key) DO UPDATE SET
                automation_id = excluded.automation_id,
                updated_at = CURRENT_TIMESTAMP
            WHERE emr_ui_targets.automation_id IS NULL
              AND emr_ui_targets.name_match IS NULL
              AND emr_ui_targets.scope_automation_id IS NULL
              AND emr_ui_targets.parent_target_key IS NULL
              AND emr_ui_targets.ancestor_path IS NULL
            """,
            (
                (profile_id, target_key, label, automation_id)
                for target_key, label, automation_id in VACCINE_EMR_TARGET_DEFAULTS
            ),
        )


def _seed_eghis_shutdown_targets(connection: sqlite3.Connection) -> None:
    profile_ids = connection.execute(
        "SELECT id FROM emr_target_profiles ORDER BY id"
    ).fetchall()
    for (profile_id,) in profile_ids:
        connection.executemany(
            """
            INSERT INTO emr_ui_targets (
                profile_id,
                target_key,
                label,
                description,
                automation_id,
                control_type,
                name_match,
                ancestor_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_id, target_key) DO UPDATE SET
                automation_id = excluded.automation_id,
                control_type = excluded.control_type,
                name_match = excluded.name_match,
                ancestor_path = excluded.ancestor_path,
                updated_at = CURRENT_TIMESTAMP
            WHERE emr_ui_targets.automation_id IS NULL
              AND emr_ui_targets.name_match IS NULL
              AND emr_ui_targets.scope_automation_id IS NULL
              AND emr_ui_targets.parent_target_key IS NULL
              AND emr_ui_targets.ancestor_path IS NULL
              AND emr_ui_targets.control_type IS NULL
              AND emr_ui_targets.class_name IS NULL
            """,
            (
                (
                    profile_id,
                    target["target_key"],
                    target["label"],
                    target["description"],
                    target["automation_id"],
                    target["control_type"],
                    target["name_match"],
                    target["ancestor_path"],
                )
                for target in EGHIS_SHUTDOWN_TARGET_DEFAULTS
            ),
        )


def _seed_default_socl_vocabulary(connection: sqlite3.Connection) -> None:
    from KaosEghis.db.socl_defaults import (
        SOCL_CATALOG_VERSION,
        SOCL_DEFAULT_COLLECTIONS,
    )

    marker = connection.execute(
        "SELECT value FROM socl_metadata WHERE key = 'default_catalog_version'"
    ).fetchone()
    if marker is not None:
        return

    count_row = connection.execute("SELECT COUNT(*) FROM socl_collections").fetchone()
    if count_row is not None and int(count_row[0]) == 0:
        for collection_order, (domain, name, findings) in enumerate(
            SOCL_DEFAULT_COLLECTIONS,
            start=1,
        ):
            cursor = connection.execute(
                """
                INSERT INTO socl_collections (domain, name, sort_order)
                VALUES (?, ?, ?)
                """,
                (domain, name, collection_order),
            )
            for finding_order, label in enumerate(findings, start=1):
                connection.execute(
                    """
                    INSERT INTO socl_findings (
                        collection_id, label, render_text, sort_order
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (cursor.lastrowid, label, label, finding_order),
                )

    connection.execute(
        """
        INSERT INTO socl_metadata (key, value)
        VALUES ('default_catalog_version', ?)
        """,
        (SOCL_CATALOG_VERSION,),
    )
