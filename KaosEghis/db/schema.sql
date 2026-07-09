CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    item_type TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    emr_target_profile_id INTEGER,
    launcher_section TEXT NOT NULL DEFAULT 'Eghis',
    launcher_position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emr_target_profile_id) REFERENCES emr_target_profiles(id)
);

CREATE TABLE IF NOT EXISTS clipboard_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS ui_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL UNIQUE,
    parent_target_id TEXT,
    parent_automation_id TEXT,
    automation_id TEXT,
    name TEXT,
    control_type TEXT,
    class_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS macro_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT,
    value TEXT,
    timeout_seconds REAL NOT NULL DEFAULT 5,
    retries INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS macro_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    status TEXT NOT NULL,
    message TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    schedule_expression TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 0,
    next_run_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS pacs_worklist_items (
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
);

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
);

CREATE TABLE IF NOT EXISTS emr_target_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    process_name TEXT,
    executable_path TEXT,
    window_title_contains TEXT,
    window_class TEXT,
    root_automation_id TEXT,
    main_window_automation_id TEXT,
    login_window_automation_id TEXT,
    patient_search_automation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emr_ui_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    target_key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    automation_id TEXT,
    control_type TEXT,
    class_name TEXT,
    name_match TEXT,
    parent_target_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES emr_target_profiles(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_target_profiles_name
    ON emr_target_profiles(name);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_ui_targets_profile_target_key
    ON emr_ui_targets(profile_id, target_key);
