import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


DEFAULT_SETTINGS = {
    "eghis_process_name": "Eghis.exe",
    "eghis_executable_path": "",
    "eghis_window_title_contains": "Eghis",
    "kaosgdd_url": "https://kaosgdd.net",
    "credential_reference_name": "default",
    "eghis_db_connection_string": "",
    "eghis_db_image_study_query": "",
    "eghis_db_weekly_age_report_query": "",
    "kaospacs_api_base_url": "http://127.0.0.1:8060",
    "kaospacs_gateway_url": "http://127.0.0.1:8060",
    "kaospacs_web_admin_url": "http://192.168.0.200/admin/worklist",
    "kaospacs_gateway_api_token": "",
    "kaospacs_api_timeout_seconds": "5",
    "pacs_auto_poll_enabled": "false",
    "pacs_poll_interval_seconds": "60",
    "pacs_dry_run": "false",
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
    emr_target_profile_id: int | None
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
    patient_birth_date: str | None
    patient_sex: str | None
    chart_no: str | None
    study: str | None
    modality: str | None
    requested_at: str | None
    accession_or_order_id: str | None
    source: str
    error_message: str | None
    kaospacs_mwl_status: str
    kaospacs_mwl_last_synced_at: str | None
    kaospacs_mwl_error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PacsAuditEventRecord:
    id: int
    event_type: str
    worklist_item_id: int | None
    accession_or_order_id: str | None
    status_before: str | None
    status_after: str | None
    summary: str
    error_message: str | None
    created_at: str


@dataclass(frozen=True)
class EmrTargetProfileRecord:
    id: int
    name: str
    description: str | None
    is_enabled: bool
    is_default: bool
    process_name: str | None
    executable_path: str | None
    window_title_contains: str | None
    window_class: str | None
    root_automation_id: str | None
    main_window_automation_id: str | None
    login_window_automation_id: str | None
    patient_search_automation_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class EmrUiTargetRecord:
    id: int
    profile_id: int
    target_key: str
    label: str
    description: str | None
    automation_id: str | None
    control_type: str | None
    class_name: str | None
    name_match: str | None
    parent_target_key: str | None
    created_at: str
    updated_at: str


SUPPORTED_ITEM_TYPES = {"clipboard", "randomized_clipboard", "macro", "workflow"}
ALLOWED_MACRO_ACTIONS = {
    "focus_window",
    "wait_window",
    "wait_text_or_image",
    "click",
    "hotkey",
    "type_text",
    "paste_text",
    "preset_text",
    "delay_ms",
    # Legacy actions kept for existing saved definitions and older dry-run tests.
    "check_process",
    "wait_for_target",
    "read_text_uia",
    "type_text_keyboard",
    "type_text_clipboard",
    "set_text_uia",
    "mouse_click",
    "wait_ms",
}

LEGACY_PACS_WORKLIST_STATUS_ALIASES = {
    "done": "completed",
}
ALLOWED_PACS_WORKLIST_STATUS = {
    "active",
    "completed",
    "expired",
    "cancelled",
    "error",
}
ALLOWED_PACS_AUDIT_EVENT_TYPES = {
    "poll",
    "manual_insert",
    "manual_edit",
    "cancel_selected",
    "sync",
    "reconcile",
    "error",
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
            SELECT id, name, item_type, is_enabled, emr_target_profile_id, created_at, updated_at
            FROM items
            ORDER BY name
            """
        )
    else:
        rows = connection.execute(
            """
            SELECT id, name, item_type, is_enabled, emr_target_profile_id, created_at, updated_at
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
        SELECT id, name, item_type, is_enabled, emr_target_profile_id, created_at, updated_at
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
    emr_target_profile_id: int | None = None,
) -> ItemRecord:
    _validate_item_type(item_type)
    cursor = connection.execute(
        """
        INSERT INTO items (name, item_type, is_enabled, emr_target_profile_id)
        VALUES (?, ?, ?, ?)
        """,
        (name.strip(), item_type, int(is_enabled), emr_target_profile_id),
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
    emr_target_profile_id: int | None = None,
) -> ItemRecord | None:
    _validate_item_type(item_type)
    connection.execute(
        """
        UPDATE items
        SET name = ?,
            item_type = ?,
            is_enabled = ?,
            emr_target_profile_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name.strip(), item_type, int(is_enabled), emr_target_profile_id, item_id),
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
    patient_birth_date: str | None = None,
    patient_sex: str | None = None,
    chart_no: str | None = None,
    study: str | None = None,
    modality: str | None = None,
    requested_at: str | None = None,
    accession_or_order_id: str | None = None,
    source: str = "manual",
    error_message: str | None = None,
) -> PacsWorklistItemRecord:
    status = _normalize_pacs_worklist_status(status)
    _validate_pacs_worklist_status(status)
    cursor = connection.execute(
        """
        INSERT INTO pacs_worklist_items
            (status, patient_name, patient_birth_date, patient_sex, chart_no, study, modality, requested_at, accession_or_order_id, source, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            status,
            _blank_to_none(patient_name),
            _blank_to_none(patient_birth_date),
            _blank_to_none(patient_sex),
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
            SELECT id, status, patient_name, patient_birth_date, patient_sex, chart_no, study, modality, requested_at,
                   accession_or_order_id, source, error_message,
                   kaospacs_mwl_status, kaospacs_mwl_last_synced_at, kaospacs_mwl_error,
                   created_at, updated_at
            FROM pacs_worklist_items
            ORDER BY requested_at DESC, id DESC
            """
        )
    else:
        status = _normalize_pacs_worklist_status(status)
        _validate_pacs_worklist_status(status)
        rows = connection.execute(
            """
            SELECT id, status, patient_name, patient_birth_date, patient_sex, chart_no, study, modality, requested_at,
                   accession_or_order_id, source, error_message,
                   kaospacs_mwl_status, kaospacs_mwl_last_synced_at, kaospacs_mwl_error,
                   created_at, updated_at
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
        SELECT id, status, patient_name, patient_birth_date, patient_sex, chart_no, study, modality, requested_at,
               accession_or_order_id, source, error_message,
               kaospacs_mwl_status, kaospacs_mwl_last_synced_at, kaospacs_mwl_error,
               created_at, updated_at
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
    status = _normalize_pacs_worklist_status(status)
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


def update_pacs_worklist_item(
    connection: sqlite3.Connection,
    item_id: int,
    *,
    status: str,
    patient_name: str | None = None,
    patient_birth_date: str | None = None,
    patient_sex: str | None = None,
    chart_no: str | None = None,
    study: str | None = None,
    modality: str | None = None,
    requested_at: str | None = None,
    accession_or_order_id: str | None = None,
    source: str | None = None,
    error_message: str | None = None,
) -> PacsWorklistItemRecord | None:
    status = _normalize_pacs_worklist_status(status)
    _validate_pacs_worklist_status(status)
    current = get_pacs_worklist_item(connection, item_id)
    if current is None:
        return None

    connection.execute(
        """
        UPDATE pacs_worklist_items
        SET status = ?,
            patient_name = ?,
            patient_birth_date = ?,
            patient_sex = ?,
            chart_no = ?,
            study = ?,
            modality = ?,
            requested_at = ?,
            accession_or_order_id = ?,
            source = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            _blank_to_none(patient_name),
            _blank_to_none(patient_birth_date),
            _blank_to_none(patient_sex),
            _blank_to_none(chart_no),
            _blank_to_none(study),
            _blank_to_none(modality),
            _blank_to_none(requested_at),
            _blank_to_none(accession_or_order_id),
            _blank_to_none(source) or current.source,
            _blank_to_none(error_message),
            item_id,
        ),
    )
    connection.commit()
    return get_pacs_worklist_item(connection, item_id)


def update_pacs_worklist_sync_state(
    connection: sqlite3.Connection,
    item_id: int,
    *,
    kaospacs_mwl_status: str,
    kaospacs_mwl_last_synced_at: str | None = None,
    kaospacs_mwl_error: str | None = None,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE pacs_worklist_items
        SET kaospacs_mwl_status = ?,
            kaospacs_mwl_last_synced_at = ?,
            kaospacs_mwl_error = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            kaospacs_mwl_status,
            _blank_to_none(kaospacs_mwl_last_synced_at),
            _blank_to_none(kaospacs_mwl_error),
            item_id,
        ),
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


def create_pacs_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    worklist_item_id: int | None = None,
    accession_or_order_id: str | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    summary: str,
    error_message: str | None = None,
) -> PacsAuditEventRecord:
    _validate_pacs_audit_event_type(event_type)
    cursor = connection.execute(
        """
        INSERT INTO pacs_audit_events
            (
                event_type,
                worklist_item_id,
                accession_or_order_id,
                status_before,
                status_after,
                summary,
                error_message
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            worklist_item_id,
            _blank_to_none(accession_or_order_id),
            _blank_to_none(status_before),
            _blank_to_none(status_after),
            summary.strip(),
            _blank_to_none(error_message),
        ),
    )
    connection.commit()
    created = connection.execute(
        """
        SELECT id, event_type, worklist_item_id, accession_or_order_id, status_before,
               status_after, summary, error_message, created_at
        FROM pacs_audit_events
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    if created is None:
        raise RuntimeError("Failed to create PACS audit event.")
    return _pacs_audit_event_from_row(created)


def list_pacs_audit_events(
    connection: sqlite3.Connection,
    limit: int = 100,
    event_type: str | None = None,
) -> list[PacsAuditEventRecord]:
    if event_type is None:
        rows = connection.execute(
            """
            SELECT id, event_type, worklist_item_id, accession_or_order_id, status_before,
                   status_after, summary, error_message, created_at
            FROM pacs_audit_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    else:
        _validate_pacs_audit_event_type(event_type)
        rows = connection.execute(
            """
            SELECT id, event_type, worklist_item_id, accession_or_order_id, status_before,
                   status_after, summary, error_message, created_at
            FROM pacs_audit_events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (event_type, limit),
        )
    return [_pacs_audit_event_from_row(row) for row in rows]


def clear_pacs_audit_events(connection: sqlite3.Connection) -> int:
    cursor = connection.execute("DELETE FROM pacs_audit_events")
    connection.commit()
    return cursor.rowcount


def list_emr_target_profiles(
    connection: sqlite3.Connection,
) -> list[EmrTargetProfileRecord]:
    rows = connection.execute(
        """
        SELECT id, name, description, is_enabled, is_default, process_name,
               executable_path, window_title_contains, window_class,
               root_automation_id, main_window_automation_id,
               login_window_automation_id, patient_search_automation_id,
               created_at, updated_at
        FROM emr_target_profiles
        ORDER BY is_default DESC, is_enabled DESC, name
        """
    )
    return [_emr_target_profile_from_row(row) for row in rows]


def get_emr_target_profile(
    connection: sqlite3.Connection, profile_id: int
) -> EmrTargetProfileRecord | None:
    row = connection.execute(
        """
        SELECT id, name, description, is_enabled, is_default, process_name,
               executable_path, window_title_contains, window_class,
               root_automation_id, main_window_automation_id,
               login_window_automation_id, patient_search_automation_id,
               created_at, updated_at
        FROM emr_target_profiles
        WHERE id = ?
        """,
        (profile_id,),
    ).fetchone()
    if row is None:
        return None
    return _emr_target_profile_from_row(row)


def get_default_emr_target_profile(
    connection: sqlite3.Connection,
) -> EmrTargetProfileRecord | None:
    row = connection.execute(
        """
        SELECT id, name, description, is_enabled, is_default, process_name,
               executable_path, window_title_contains, window_class,
               root_automation_id, main_window_automation_id,
               login_window_automation_id, patient_search_automation_id,
               created_at, updated_at
        FROM emr_target_profiles
        WHERE is_default = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return _emr_target_profile_from_row(row)


def get_active_emr_target_profile(
    connection: sqlite3.Connection,
) -> EmrTargetProfileRecord | None:
    profile = get_default_emr_target_profile(connection)
    if profile is not None and profile.is_enabled:
        return profile
    row = connection.execute(
        """
        SELECT id, name, description, is_enabled, is_default, process_name,
               executable_path, window_title_contains, window_class,
               root_automation_id, main_window_automation_id,
               login_window_automation_id, patient_search_automation_id,
               created_at, updated_at
        FROM emr_target_profiles
        WHERE is_enabled = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return _emr_target_profile_from_row(row)


def create_emr_target_profile(
    connection: sqlite3.Connection,
    *,
    name: str,
    description: str | None = None,
    is_enabled: bool = True,
    is_default: bool = False,
    process_name: str | None = None,
    executable_path: str | None = None,
    window_title_contains: str | None = None,
    window_class: str | None = None,
    root_automation_id: str | None = None,
    main_window_automation_id: str | None = None,
    login_window_automation_id: str | None = None,
    patient_search_automation_id: str | None = None,
) -> EmrTargetProfileRecord:
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
            window_class,
            root_automation_id,
            main_window_automation_id,
            login_window_automation_id,
            patient_search_automation_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip(),
            _blank_to_none(description),
            int(is_enabled),
            int(is_default),
            _blank_to_none(process_name),
            _blank_to_none(executable_path),
            _blank_to_none(window_title_contains),
            _blank_to_none(window_class),
            _blank_to_none(root_automation_id),
            _blank_to_none(main_window_automation_id),
            _blank_to_none(login_window_automation_id),
            _blank_to_none(patient_search_automation_id),
        ),
    )
    if is_default:
        _set_default_profile_row(connection, cursor.lastrowid)
    else:
        _ensure_single_default_emr_profile(connection)
    connection.commit()
    created = get_emr_target_profile(connection, cursor.lastrowid)
    if created is None:
        raise RuntimeError("Failed to create EMR target profile.")
    return created


def update_emr_target_profile(
    connection: sqlite3.Connection,
    profile_id: int,
    *,
    name: str,
    description: str | None = None,
    is_enabled: bool = True,
    is_default: bool = False,
    process_name: str | None = None,
    executable_path: str | None = None,
    window_title_contains: str | None = None,
    window_class: str | None = None,
    root_automation_id: str | None = None,
    main_window_automation_id: str | None = None,
    login_window_automation_id: str | None = None,
    patient_search_automation_id: str | None = None,
) -> EmrTargetProfileRecord | None:
    current = get_emr_target_profile(connection, profile_id)
    if current is None:
        return None
    connection.execute(
        """
        UPDATE emr_target_profiles
        SET name = ?,
            description = ?,
            is_enabled = ?,
            is_default = ?,
            process_name = ?,
            executable_path = ?,
            window_title_contains = ?,
            window_class = ?,
            root_automation_id = ?,
            main_window_automation_id = ?,
            login_window_automation_id = ?,
            patient_search_automation_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            _blank_to_none(description),
            int(is_enabled),
            int(is_default),
            _blank_to_none(process_name),
            _blank_to_none(executable_path),
            _blank_to_none(window_title_contains),
            _blank_to_none(window_class),
            _blank_to_none(root_automation_id),
            _blank_to_none(main_window_automation_id),
            _blank_to_none(login_window_automation_id),
            _blank_to_none(patient_search_automation_id),
            profile_id,
        ),
    )
    if is_default:
        _set_default_profile_row(connection, profile_id)
    elif current.is_default:
        _set_default_profile_row(connection, profile_id)
    else:
        _ensure_single_default_emr_profile(connection)
    connection.commit()
    return get_emr_target_profile(connection, profile_id)


def delete_emr_target_profile(connection: sqlite3.Connection, profile_id: int) -> bool:
    current = get_emr_target_profile(connection, profile_id)
    if current is None:
        return False
    if current.is_default:
        replacement = connection.execute(
            """
            SELECT id
            FROM emr_target_profiles
            WHERE id != ? AND is_enabled = 1
            ORDER BY id
            LIMIT 1
            """,
            (profile_id,),
        ).fetchone()
        if replacement is None:
            raise ValueError("Cannot delete the only enabled default EMR target profile.")
        _set_default_profile_row(connection, replacement[0])
    connection.execute("DELETE FROM emr_ui_targets WHERE profile_id = ?", (profile_id,))
    cursor = connection.execute(
        "DELETE FROM emr_target_profiles WHERE id = ?",
        (profile_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def set_default_emr_target_profile(
    connection: sqlite3.Connection, profile_id: int
) -> EmrTargetProfileRecord | None:
    if get_emr_target_profile(connection, profile_id) is None:
        return None
    _set_default_profile_row(connection, profile_id)
    connection.commit()
    return get_emr_target_profile(connection, profile_id)


def list_emr_ui_targets(
    connection: sqlite3.Connection, profile_id: int
) -> list[EmrUiTargetRecord]:
    rows = connection.execute(
        """
        SELECT id, profile_id, target_key, label, description, automation_id,
               control_type, class_name, name_match, parent_target_key,
               created_at, updated_at
        FROM emr_ui_targets
        WHERE profile_id = ?
        ORDER BY target_key
        """,
        (profile_id,),
    )
    return [_emr_ui_target_from_row(row) for row in rows]


def get_emr_ui_target_by_key(
    connection: sqlite3.Connection,
    profile_id: int,
    target_key: str,
) -> EmrUiTargetRecord | None:
    row = connection.execute(
        """
        SELECT id, profile_id, target_key, label, description, automation_id,
               control_type, class_name, name_match, parent_target_key,
               created_at, updated_at
        FROM emr_ui_targets
        WHERE profile_id = ? AND target_key = ?
        """,
        (profile_id, target_key),
    ).fetchone()
    if row is None:
        return None
    return _emr_ui_target_from_row(row)


def get_emr_ui_target(
    connection: sqlite3.Connection, ui_target_id: int
) -> EmrUiTargetRecord | None:
    row = connection.execute(
        """
        SELECT id, profile_id, target_key, label, description, automation_id,
               control_type, class_name, name_match, parent_target_key,
               created_at, updated_at
        FROM emr_ui_targets
        WHERE id = ?
        """,
        (ui_target_id,),
    ).fetchone()
    if row is None:
        return None
    return _emr_ui_target_from_row(row)


def create_emr_ui_target(
    connection: sqlite3.Connection,
    *,
    profile_id: int,
    target_key: str,
    label: str,
    description: str | None = None,
    automation_id: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
    name_match: str | None = None,
    parent_target_key: str | None = None,
) -> EmrUiTargetRecord:
    cursor = connection.execute(
        """
        INSERT INTO emr_ui_targets (
            profile_id,
            target_key,
            label,
            description,
            automation_id,
            control_type,
            class_name,
            name_match,
            parent_target_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            target_key.strip(),
            label.strip(),
            _blank_to_none(description),
            _blank_to_none(automation_id),
            _blank_to_none(control_type),
            _blank_to_none(class_name),
            _blank_to_none(name_match),
            _blank_to_none(parent_target_key),
        ),
    )
    connection.commit()
    created = get_emr_ui_target(connection, cursor.lastrowid)
    if created is None:
        raise RuntimeError("Failed to create EMR UI target.")
    return created


def update_emr_ui_target(
    connection: sqlite3.Connection,
    ui_target_id: int,
    *,
    target_key: str,
    label: str,
    description: str | None = None,
    automation_id: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
    name_match: str | None = None,
    parent_target_key: str | None = None,
) -> EmrUiTargetRecord | None:
    connection.execute(
        """
        UPDATE emr_ui_targets
        SET target_key = ?,
            label = ?,
            description = ?,
            automation_id = ?,
            control_type = ?,
            class_name = ?,
            name_match = ?,
            parent_target_key = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            target_key.strip(),
            label.strip(),
            _blank_to_none(description),
            _blank_to_none(automation_id),
            _blank_to_none(control_type),
            _blank_to_none(class_name),
            _blank_to_none(name_match),
            _blank_to_none(parent_target_key),
            ui_target_id,
        ),
    )
    connection.commit()
    return get_emr_ui_target(connection, ui_target_id)


def delete_emr_ui_target(connection: sqlite3.Connection, ui_target_id: int) -> bool:
    cursor = connection.execute(
        "DELETE FROM emr_ui_targets WHERE id = ?",
        (ui_target_id,),
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
    item = get_item(connection, item_id)
    profile = resolve_macro_emr_target_profile(connection, item)
    for step in list_macro_steps(connection, item_id):
        if not step.target_id:
            continue
        if profile is not None and get_emr_ui_target_by_key(
            connection, profile.id, step.target_id
        ) is not None:
            continue
        if get_ui_target(connection, step.target_id) is not None:
            continue
        errors.append(
            f"Step {step.step_order}: target_id '{step.target_id}' is not registered."
        )
    return errors


def resolve_macro_emr_target_profile(
    connection: sqlite3.Connection,
    item: ItemRecord | None,
) -> EmrTargetProfileRecord | None:
    if item is None:
        return get_default_emr_target_profile(connection)
    if item.emr_target_profile_id is not None:
        profile = get_emr_target_profile(connection, item.emr_target_profile_id)
        if profile is not None:
            return profile
    return get_default_emr_target_profile(connection)


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
        emr_target_profile_id=row[4],
        created_at=row[5],
        updated_at=row[6],
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
        status=_normalize_pacs_worklist_status(row[1]),
        patient_name=row[2],
        patient_birth_date=row[3],
        patient_sex=row[4],
        chart_no=row[5],
        study=row[6],
        modality=row[7],
        requested_at=row[8],
        accession_or_order_id=row[9],
        source=row[10],
        error_message=row[11],
        kaospacs_mwl_status=row[12],
        kaospacs_mwl_last_synced_at=row[13],
        kaospacs_mwl_error=row[14],
        created_at=row[15],
        updated_at=row[16],
    )


def _pacs_audit_event_from_row(
    row: sqlite3.Row | tuple,
) -> PacsAuditEventRecord:
    return PacsAuditEventRecord(
        id=row[0],
        event_type=row[1],
        worklist_item_id=row[2],
        accession_or_order_id=row[3],
        status_before=row[4],
        status_after=row[5],
        summary=row[6],
        error_message=row[7],
        created_at=row[8],
    )


def _emr_target_profile_from_row(
    row: sqlite3.Row | tuple,
) -> EmrTargetProfileRecord:
    return EmrTargetProfileRecord(
        id=row[0],
        name=row[1],
        description=row[2],
        is_enabled=bool(row[3]),
        is_default=bool(row[4]),
        process_name=row[5],
        executable_path=row[6],
        window_title_contains=row[7],
        window_class=row[8],
        root_automation_id=row[9],
        main_window_automation_id=row[10],
        login_window_automation_id=row[11],
        patient_search_automation_id=row[12],
        created_at=row[13],
        updated_at=row[14],
    )


def _emr_ui_target_from_row(row: sqlite3.Row | tuple) -> EmrUiTargetRecord:
    return EmrUiTargetRecord(
        id=row[0],
        profile_id=row[1],
        target_key=row[2],
        label=row[3],
        description=row[4],
        automation_id=row[5],
        control_type=row[6],
        class_name=row[7],
        name_match=row[8],
        parent_target_key=row[9],
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


def _normalize_pacs_worklist_status(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    return LEGACY_PACS_WORKLIST_STATUS_ALIASES.get(normalized, normalized)


def _validate_pacs_audit_event_type(event_type: str) -> None:
    if event_type not in ALLOWED_PACS_AUDIT_EVENT_TYPES:
        raise ValueError(f"Unsupported PACS audit event type: {event_type}")


def _set_default_profile_row(connection: sqlite3.Connection, profile_id: int) -> None:
    connection.execute("UPDATE emr_target_profiles SET is_default = 0")
    connection.execute(
        """
        UPDATE emr_target_profiles
        SET is_default = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (profile_id,),
    )


def _ensure_single_default_emr_profile(connection: sqlite3.Connection) -> None:
    default_rows = connection.execute(
        "SELECT id FROM emr_target_profiles WHERE is_default = 1 ORDER BY id"
    ).fetchall()
    if default_rows:
        keep_id = default_rows[0][0]
        connection.execute(
            "UPDATE emr_target_profiles SET is_default = 0 WHERE is_default = 1 AND id != ?",
            (keep_id,),
        )
        return

    first_enabled = connection.execute(
        """
        SELECT id
        FROM emr_target_profiles
        WHERE is_enabled = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if first_enabled is not None:
        _set_default_profile_row(connection, first_enabled[0])
