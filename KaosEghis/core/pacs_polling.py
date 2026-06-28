"""Read-only polling adapters for local PACS worklist bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import create_pacs_worklist_item

_CANONICAL_ALIASES = {
    "patient_name": ["patient_name", "PatientName", "PATIENT_NAME", "pname", "수진자명"],
    "chart_no": [
        "chart_no",
        "ChartNo",
        "CHART_NO",
        "patient_id",
        "patient_no",
        "등록번호",
        "차트번호",
    ],
    "study": ["study", "Study", "STUDY", "exam_name", "order_name", "검사명", "처방명"],
    "modality": ["modality", "Modality", "MODALITY", "modality_code", "검사구분"],
    "requested_at": [
        "requested_at",
        "RequestedAt",
        "order_datetime",
        "order_date",
        "처방일시",
        "처방일자",
    ],
    "accession_or_order_id": [
        "accession_or_order_id",
        "accession",
        "accession_no",
        "order_id",
        "order_no",
        "처방ID",
        "처방번호",
    ],
}
_WRITE_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|EXEC|CALL)\b",
    re.IGNORECASE,
)
_DEFAULT_IMAGE_ORDER_QUERY = """
SELECT
    CASE
        WHEN ord.dc_yn = 'Y' THEN 'cancelled'
        ELSE 'active'
    END AS status,
    ord.ptnt_nm AS patient_name,
    ord.ptnt_no AS patient_id,
    ord.proc_nm AS order_name,
    ord.proc_cd AS modality_code,
    ord.ordr_dtime AS order_datetime,
    COALESCE(NULLIF(m.accession_no, ''), m.eghis_key) AS accession_or_order_id,
    m.eghis_key,
    ord.dc_yn
FROM public.mwl AS m
JOIN public.h2opd_doct_ord AS ord
    ON split_part(m.eghis_key, '_', 1) = ord.recept_no
   AND split_part(m.eghis_key, '_', 2) = ord.ord_no
   AND split_part(m.eghis_key, '_', 3) = ord.ord_seq_no
WHERE ord.scheduled_proc_status = '100'
  AND ord.proc_dept_cd = 'XRAY'
  AND ord.ordr_dtime::date = CURRENT_DATE
ORDER BY ord.ordr_dtime DESC
""".strip()


@dataclass(frozen=True)
class PollResult:
    inserted: int
    updated: int
    skipped: int
    message: str | None = None


class PollingUnavailableError(RuntimeError):
    """Raised when the optional Eghis DB adapter is not available."""


class QueryRejectedError(RuntimeError):
    """Raised when operator-configured SQL fails the read-only safety gate."""


def poll_image_orders(settings: dict[str, str]) -> list[dict[str, str | None]]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return []

    return _poll_image_orders_from_db(settings)


def poll_eghis_image_orders_into_local_worklist(
    settings: dict[str, str],
    db_path: Path | None = None,
    poller: Callable[[dict[str, str]], list[dict[str, str | None]]] | None = None,
) -> PollResult:
    if not (settings.get("eghis_db_connection_string") or "").strip():
        return PollResult(inserted=0, updated=0, skipped=0)

    initialize_database(db_path)
    try:
        orders = (poller or poll_image_orders)(settings)
    except QueryRejectedError:
        return PollResult(inserted=0, updated=0, skipped=0, message="query rejected")
    except PollingUnavailableError:
        return PollResult(inserted=0, updated=0, skipped=0, message="unavailable")
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
                SELECT id, status
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

            if status == "cancelled":
                skipped += 1
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


def _poll_image_orders_from_db(
    settings: dict[str, str],
) -> list[dict[str, str | None]]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    query = _resolve_image_study_query(settings)
    if not connection_string or not query:
        return []
    if _WRITE_SQL_PATTERN.search(query):
        raise QueryRejectedError("Configured SQL was rejected by the read-only safety gate.")

    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PollingUnavailableError("psycopg2 is not installed.") from exc

    # KaosEghis-pacs reads Eghis DB as an EMR-side adapter and writes only to the
    # local KaosEghis SQLite worklist. It does not push to KaosPACS in this PR.
    connection = psycopg2.connect(connection_string)

    try:
        try:
            connection.set_session(readonly=True, autocommit=True)
        except Exception:
            connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            column_names = [column[0] for column in cursor.description or []]
            rows = cursor.fetchall()
        finally:
            close_cursor = getattr(cursor, "close", None)
            if callable(close_cursor):
                close_cursor()
    finally:
        close_connection = getattr(connection, "close", None)
        if callable(close_connection):
            close_connection()

    return [_map_db_row_to_order(column_names, row) for row in rows]


def _map_db_row_to_order(
    column_names: list[str], row: tuple | list | object
) -> dict[str, str | None]:
    row_map = {column_names[index]: row[index] for index in range(len(column_names))}
    order: dict[str, str | None] = {
        "status": "active",
        "patient_name": None,
        "chart_no": None,
        "study": None,
        "modality": None,
        "requested_at": None,
        "accession_or_order_id": None,
        "source": "eghis-db",
    }

    # Store only the minimum local worklist fields. Ignore any extra DB columns so
    # resident ID, DOB, sex, phone, address, diagnosis, EMR notes, and raw rows do
    # not enter KaosEghis local SQLite through this adapter.
    order["status"] = _stringify(_lookup_alias(row_map, ["status"])) or "active"
    for key in (
        "patient_name",
        "chart_no",
        "study",
        "modality",
        "requested_at",
        "accession_or_order_id",
    ):
        order[key] = _stringify(_lookup_alias(row_map, _CANONICAL_ALIASES[key]))
    return order


def _lookup_alias(
    row_map: dict[str, object], aliases: list[str]
) -> object | None:
    normalized = {str(key).lower(): value for key, value in row_map.items()}
    for alias in aliases:
        if alias in row_map:
            return row_map[alias]
        lowered = alias.lower()
        if lowered in normalized:
            return normalized[lowered]
    return None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _stringify(value: object | None) -> str | None:
    if value is None:
        return None
    return _blank_to_none(str(value))


def _resolve_image_study_query(settings: dict[str, str]) -> str:
    configured = (settings.get("eghis_db_image_study_query") or "").strip()
    if configured:
        return configured
    return _DEFAULT_IMAGE_ORDER_QUERY
