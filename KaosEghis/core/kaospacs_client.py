from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib import error, request

from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    PacsWorklistItemRecord,
    get_settings,
    list_pacs_worklist_items,
    update_pacs_worklist_sync_state,
)
from KaosEghis.core.kaospacs_gateway_client import get_imaging_worklist


@dataclass(frozen=True)
class KaosPacsSyncResult:
    sent: int
    cancelled: int
    errors: int
    skipped: int
    message: str | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class KaosPacsReconcileResult:
    completed: int
    expired: int
    skipped: int
    errors: int
    message: str | None = None
    dry_run: bool = False


def check_kaospacs_health(settings: dict[str, str]) -> bool:
    payload = _request_json(settings, "GET", "/health")
    return bool(payload)


def fetch_kaospacs_worklist(settings: dict[str, str]) -> dict:
    return _request_json(settings, "GET", "/worklist")


def push_kaospacs_worklist(settings: dict[str, str], entries: list[dict]) -> dict:
    return _request_json(settings, "POST", "/orders/upsert", {"entries": entries})


def cancel_kaospacs_order(settings: dict[str, str], accession_number: str) -> dict:
    return _request_json(
        settings,
        "POST",
        "/orders/cancel",
        {"AccessionNumber": accession_number},
    )


def sync_local_worklist_to_kaospacs(
    settings: dict[str, str],
    db_path: Path | None = None,
) -> KaosPacsSyncResult:
    initialize_database(db_path)
    db_file = db_path or get_database_path()
    sent = 0
    cancelled = 0
    errors = 0
    skipped = 0

    with connect(db_file) as connection:
        items = list_pacs_worklist_items(connection)

    active_entries: list[dict] = []
    active_items: list[PacsWorklistItemRecord] = []
    cancelled_items: list[PacsWorklistItemRecord] = []
    dry_run = _is_pacs_dry_run(settings)

    for item in items:
        if not item.accession_or_order_id:
            skipped += 1
            continue
        if item.status == "active":
            active_entries.append(_build_kaospacs_entry(item))
            active_items.append(item)
        elif item.status == "cancelled":
            # Business cancellation originates on the KaosEghis side. KaosPACS
            # receives that truth through the explicit cancel endpoint and must
            # not infer it from downstream imaging lifecycle state.
            if item.kaospacs_mwl_status == "sent":
                cancelled_items.append(item)
            else:
                skipped += 1

    if dry_run:
        return KaosPacsSyncResult(
            sent=len(active_items),
            cancelled=len(cancelled_items),
            errors=errors,
            skipped=skipped,
            dry_run=True,
        )

    if active_entries:
        try:
            push_kaospacs_worklist(settings, active_entries)
            synced_at = _utc_now_text()
            with connect(db_file) as connection:
                for item in active_items:
                    update_pacs_worklist_sync_state(
                        connection,
                        item.id,
                        kaospacs_mwl_status="sent",
                        kaospacs_mwl_last_synced_at=synced_at,
                        kaospacs_mwl_error=None,
                    )
            sent = len(active_items)
        except RuntimeError as exc:
            with connect(db_file) as connection:
                for item in active_items:
                    update_pacs_worklist_sync_state(
                        connection,
                        item.id,
                        kaospacs_mwl_status="error",
                        kaospacs_mwl_error=str(exc),
                    )
            errors += len(active_items)

    for item in cancelled_items:
        try:
            cancel_kaospacs_order(settings, item.accession_or_order_id or "")
            with connect(db_file) as connection:
                update_pacs_worklist_sync_state(
                    connection,
                    item.id,
                    kaospacs_mwl_status="cancelled",
                    kaospacs_mwl_last_synced_at=_utc_now_text(),
                    kaospacs_mwl_error=None,
                )
            cancelled += 1
        except RuntimeError as exc:
            with connect(db_file) as connection:
                update_pacs_worklist_sync_state(
                    connection,
                    item.id,
                    kaospacs_mwl_status="error",
                    kaospacs_mwl_error=str(exc),
                )
            errors += 1

    return KaosPacsSyncResult(
        sent=sent,
        cancelled=cancelled,
        errors=errors,
        skipped=skipped,
        dry_run=False,
    )


def reconcile_kaospacs_worklist_to_local(
    settings: dict[str, str],
    db_path: Path | None = None,
) -> KaosPacsReconcileResult:
    initialize_database(db_path)
    db_file = db_path or get_database_path()
    completed = 0
    expired = 0
    skipped = 0
    errors = 0

    try:
        entries = fetch_kaospacs_reconcile_entries(settings)
    except RuntimeError as exc:
        return KaosPacsReconcileResult(
            completed=0,
            expired=0,
            skipped=0,
            errors=1,
            message=str(exc),
            dry_run=_is_pacs_dry_run(settings),
        )

    dry_run = _is_pacs_dry_run(settings)
    with connect(db_file) as connection:
        items = list_pacs_worklist_items(connection)
        item_by_identifier = _index_local_items(items)

        for entry in entries:
            if not isinstance(entry, dict):
                skipped += 1
                continue

            local_item = _match_local_item(item_by_identifier, entry)
            if local_item is None:
                skipped += 1
                continue

            # Architectural ownership:
            # - KaosEghis-PACS owns business cancellation.
            # - KaosPACS owns imaging completion and expiry.
            # Reconciliation therefore accepts only Completed/Expired from KaosPACS
            # and never infers local Cancelled from remote imaging state.
            if local_item.status in {"completed", "expired", "cancelled"}:
                skipped += 1
                continue

            remote_status = _reconciliation_status(entry)
            if remote_status == "completed":
                if local_item.status != "completed":
                    if dry_run:
                        completed += 1
                    elif _update_local_status_for_reconciliation(connection, local_item.id, "completed"):
                        completed += 1
                    else:
                        errors += 1
                else:
                    skipped += 1
            elif remote_status == "expired":
                if local_item.status != "expired":
                    if dry_run:
                        expired += 1
                    elif _update_local_status_for_reconciliation(connection, local_item.id, "expired"):
                        expired += 1
                    else:
                        errors += 1
                else:
                    skipped += 1
            else:
                skipped += 1

    return KaosPacsReconcileResult(
        completed=completed,
        expired=expired,
        skipped=skipped,
        errors=errors,
        dry_run=dry_run,
    )


def fetch_kaospacs_reconcile_entries(settings: dict[str, str]) -> list[dict]:
    gateway_url = (settings.get("kaospacs_gateway_url") or "").strip()
    if gateway_url:
        return get_imaging_worklist(settings)

    payload = fetch_kaospacs_worklist(settings)
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        raise RuntimeError("invalid worklist payload")
    return [entry for entry in entries if isinstance(entry, dict)]


def _build_kaospacs_entry(item: PacsWorklistItemRecord) -> dict[str, str]:
    accession_number = item.accession_or_order_id or ""
    requested_date, requested_time = _split_date_time(item.requested_at)
    modality = item.modality or ""
    return {
        "PatientName": item.patient_name or "",
        "PatientID": item.chart_no or "",
        "AccessionNumber": accession_number,
        "RequestedProcedureID": accession_number,
        "ScheduledProcedureStepID": accession_number,
        "RequestedProcedureDescription": item.study or "",
        "ScheduledProcedureStepDescription": item.study or "",
        "Modality": modality,
        "ScheduledStationAETitle": _scheduled_station_ae_title(modality),
        "ScheduledProcedureStepStartDate": requested_date,
        "ScheduledProcedureStepStartTime": requested_time,
    }


def _scheduled_station_ae_title(modality: str) -> str:
    if modality == "BMD":
        return "BMD"
    return "INNOVISION"


def _split_date_time(value: str | None) -> tuple[str, str]:
    if not value:
        return "", ""
    normalized = value.strip().replace("T", " ")
    if " " not in normalized:
        return normalized.replace("-", ""), ""
    date_part, time_part = normalized.split(" ", 1)
    return date_part.replace("-", ""), time_part.replace(":", "")


def _index_local_items(
    items: list[PacsWorklistItemRecord],
) -> dict[str, PacsWorklistItemRecord]:
    index: dict[str, PacsWorklistItemRecord] = {}
    for item in items:
        if not item.accession_or_order_id:
            continue
        index[item.accession_or_order_id] = item
    return index


def _match_local_item(
    item_by_identifier: dict[str, PacsWorklistItemRecord],
    entry: dict,
) -> PacsWorklistItemRecord | None:
    for key in ("AccessionNumber", "RequestedProcedureID", "ScheduledProcedureStepID"):
        value = _text(entry.get(key))
        if value and value in item_by_identifier:
            return item_by_identifier[value]
    return None


def _reconciliation_status(entry: dict) -> str | None:
    status = _text(entry.get("state") or entry.get("Status")).lower()
    completed_at = _text(entry.get("CompletedAt"))
    expired_at = _text(entry.get("ExpiredAt"))

    if status == "expired" or expired_at:
        return "expired"
    if status == "completed":
        return "completed"
    if completed_at:
        return "completed"
    return None


def _update_local_status_for_reconciliation(
    connection,
    item_id: int,
    status: str,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE pacs_worklist_items
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, item_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _request_json(
    settings: dict[str, str],
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    base_url = (settings.get("kaospacs_api_base_url") or "http://127.0.0.1:8055").strip().rstrip("/")
    timeout_seconds = float(settings.get("kaospacs_api_timeout_seconds") or "5")
    data = None
    headers = {"Accept": "application/json; charset=utf-8"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    http_request = request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except (error.HTTPError, error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc
    if not body:
        return {}
    return json.loads(body)


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_pacs_dry_run(settings: dict[str, str]) -> bool:
    return (settings.get("pacs_dry_run") or "").strip().lower() == "true"
