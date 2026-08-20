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
    is_launcher_exposed INTEGER NOT NULL DEFAULT 1,
    emr_target_profile_id INTEGER,
    launcher_section TEXT NOT NULL DEFAULT 'Macro',
    launcher_position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emr_target_profile_id) REFERENCES emr_target_profiles(id)
);

CREATE TABLE IF NOT EXISTS launcher_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    launcher_section TEXT NOT NULL DEFAULT 'Macro',
    launcher_position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS launcher_collection_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    macro_item_id INTEGER NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES launcher_collections(id),
    FOREIGN KEY (macro_item_id) REFERENCES items(id)
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
    press_enter_before INTEGER NOT NULL DEFAULT 0,
    press_enter_after INTEGER NOT NULL DEFAULT 0,
    wait_before_enabled INTEGER NOT NULL DEFAULT 0,
    wait_before_ms INTEGER NOT NULL DEFAULT 100,
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

CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    macro_item_id INTEGER NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 0,
    schedule_time TEXT NOT NULL,
    weekdays TEXT NOT NULL DEFAULT '0,1,2,3,4',
    missed_run_policy TEXT NOT NULL DEFAULT 'skip'
        CHECK (missed_run_policy IN ('skip', 'prompt')),
    next_run_at TEXT,
    last_run_at TEXT,
    last_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (macro_item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_due
    ON scheduler_jobs(is_enabled, next_run_at);

CREATE TABLE IF NOT EXISTS scheduler_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    macro_item_id INTEGER NOT NULL,
    trigger TEXT NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
    scheduled_for TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    status TEXT NOT NULL,
    executed_steps INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES scheduler_jobs(id),
    FOREIGN KEY (macro_item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_scheduler_runs_job_created
    ON scheduler_runs(job_id, created_at DESC);

CREATE TABLE IF NOT EXISTS socl_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL CHECK (domain IN ('subjective', 'objective')),
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, name)
);

CREATE TABLE IF NOT EXISTS socl_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    render_text TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, label),
    FOREIGN KEY (collection_id) REFERENCES socl_collections(id)
);

CREATE INDEX IF NOT EXISTS idx_socl_collections_domain_order
    ON socl_collections(domain, sort_order, id);

CREATE INDEX IF NOT EXISTS idx_socl_findings_collection_order
    ON socl_findings(collection_id, sort_order, id);

CREATE TABLE IF NOT EXISTS socl_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
    patient_status_tab_automation_id TEXT,
    login_window_automation_id TEXT,
    patient_search_automation_id TEXT,
    prescription_grid_automation_id TEXT,
    symptom_grid_automation_id TEXT,
    diagnosis_grid_automation_id TEXT,
    patient_list_grid_automation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emr_ui_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    target_key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    scope_automation_id TEXT,
    automation_id TEXT,
    control_type TEXT,
    class_name TEXT,
    name_match TEXT,
    parent_target_key TEXT,
    ancestor_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES emr_target_profiles(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_target_profiles_name
    ON emr_target_profiles(name);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emr_ui_targets_profile_target_key
    ON emr_ui_targets(profile_id, target_key);

CREATE TABLE IF NOT EXISTS vaccine_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT,
    chart_note_template TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
);

CREATE TABLE IF NOT EXISTS vaccine_program_seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program TEXT NOT NULL CHECK (program IN ('influenza', 'covid')),
    season_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    daily_cap INTEGER NOT NULL DEFAULT 100 CHECK (daily_cap >= 0),
    schedule_json TEXT NOT NULL DEFAULT '{}',
    age_groups_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (program, season_name)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vaccine_program_seasons_one_active
    ON vaccine_program_seasons(program)
    WHERE is_active = 1;
