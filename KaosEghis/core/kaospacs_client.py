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


@dataclass(frozen=True)
class KaosPacsSyncResult:
    sent: int
    cancelled: int
    errors: int
    skipped: int
    message: str | None = None


def check_kaospacs_health(settings: dict[str, str]) -> bool:
    payload = _request_json(settings, "GET", "/health")
    return bool(payload)


def fetch_kaospacs_worklist(settings: dict[str, str]) -> dict:
    return _request_json(settings, "GET", "/worklist")


def push_kaospacs_worklist(settings: dict[str, str], entries: list[dict]) -> dict:
    return _request_json(settings, "PUT", "/worklist", {"entries": entries})


def complete_kaospacs_order(settings: dict[str, str], accession_number: str) -> dict:
    return _request_json(
        settings,
        "POST",
        "/worklist/complete",
        {"AccessionNumber": accession_number},
    )


def cancel_kaospacs_order(settings: dict[str, str], accession_number: str) -> dict:
    return _request_json(
        settings,
        "POST",
        "/worklist/cancel",
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

    for item in items:
        if not item.accession_or_order_id:
            skipped += 1
            continue
        if item.status == "active":
            active_entries.append(_build_kaospacs_entry(item))
            active_items.append(item)
        elif item.status == "cancelled":
            if item.kaospacs_mwl_status == "sent":
                cancelled_items.append(item)
            else:
                skipped += 1

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
    )


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


def _request_json(
    settings: dict[str, str],
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    base_url = (settings.get("kaospacs_api_base_url") or "http://127.0.0.1:8055").strip().rstrip("/")
    timeout_seconds = float(settings.get("kaospacs_api_timeout_seconds") or "5")
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
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
