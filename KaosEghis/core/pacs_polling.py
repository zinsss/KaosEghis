"""Read-only polling adapters for local PACS worklist bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import create_pacs_worklist_item


@dataclass(frozen=True)
class PollResult:
    inserted: int
    updated: int
    skipped: int


def poll_image_orders(settings: dict[str, str]) -> list[dict[str, str | None]]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return []

    # Read-only scaffold: safe placeholder data until real DB integration is added.
    query = (settings.get("eghis_db_image_study_query") or "").strip()
    if query:
        return []

    return [
        {
            "status": "active",
            "patient_name": "Sample Patient",
            "chart_no": "CH-0001",
            "study": "Sample study",
            "modality": "XR",
            "requested_at": "2026-01-01T00:00:00",
            "accession_or_order_id": "KPE-ORDER-001",
            "source": "eghis-poll-mock",
        }
    ]


def poll_eghis_image_orders_into_local_worklist(
    settings: dict[str, str],
    db_path: Path | None = None,
) -> PollResult:
    if not (settings.get("eghis_db_connection_string") or "").strip():
        return PollResult(inserted=0, updated=0, skipped=0)

    initialize_database(db_path)
    orders = poll_image_orders(settings)
    inserted = 0
    updated = 0
    skipped = 0

    if not orders:
        return PollResult(inserted=0, updated=0, skipped=0)

    db_file = db_path or get_database_path()
    with connect(db_file) as connection:
        for order in orders:
            accession_or_order_id = _blank_to_none(order.get("accession_or_order_id"))
            status = _blank_to_none(order.get("status")) or "active"

            if not accession_or_order_id:
                skipped += 1
                continue

            existing = connection.execute(
                """
                SELECT id
                FROM pacs_worklist_items
                WHERE accession_or_order_id = ?
                """,
                (accession_or_order_id,),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    """
                    UPDATE pacs_worklist_items
                    SET status = ?,
                        patient_name = ?,
                        chart_no = ?,
                        study = ?,
                        modality = ?,
                        requested_at = ?,
                        source = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        status,
                        _blank_to_none(order.get("patient_name")),
                        _blank_to_none(order.get("chart_no")),
                        _blank_to_none(order.get("study")),
                        _blank_to_none(order.get("modality")),
                        _blank_to_none(order.get("requested_at")),
                        _blank_to_none(order.get("source")) or "eghis-poll",
                        existing[0],
                    ),
                )
                updated += 1
                continue

            create_pacs_worklist_item(
                connection,
                status=status,
                patient_name=order.get("patient_name"),
                chart_no=order.get("chart_no"),
                study=order.get("study"),
                modality=order.get("modality"),
                requested_at=order.get("requested_at"),
                accession_or_order_id=accession_or_order_id,
                source=_blank_to_none(order.get("source")) or "eghis-poll",
            )
            inserted += 1
        connection.commit()

    return PollResult(inserted=inserted, updated=updated, skipped=skipped)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
