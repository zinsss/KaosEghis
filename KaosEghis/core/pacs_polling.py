"""Read-only polling adapters for local PACS worklist bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Callable

from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    create_pacs_audit_event,
    create_pacs_worklist_item,
    list_pacs_worklist_items,
    update_pacs_worklist_status,
)
from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
    run_readonly_query,
)

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
_DEFAULT_IMAGE_ORDER_QUERY = """
SELECT
    CASE
        WHEN COALESCE(o.dc_yn, 'N') = 'Y' THEN 'cancelled'
        ELSE 'active'
    END AS status,
    m.patient_name AS patient_name,
    m.patient_id AS patient_id,
    COALESCE(m.scheduled_proc_desc, m.requested_proc_desc) AS study,
    CASE
        WHEN m.scheduled_modality = 'BMD' OR o.ord_cd = 'HC342' THEN 'BMD'
        WHEN m.scheduled_modality = 'DR' THEN 'CR'
        ELSE m.scheduled_modality
    END AS modality,
    COALESCE(
        m.scheduled_dttm,
        m.imaging_request_dttm,
        m.trigger_dttm,
        m.replica_dttm
    ) AS requested_at,
    COALESCE(NULLIF(m.accession_no, ''), m.eghis_key) AS accession_or_order_id,
    m.eghis_key,
    o.dc_yn
FROM public.mwl AS m
JOIN public.h2opd_doct_ord AS o
    ON o.recept_no = split_part(m.eghis_key, '_', 1)
   AND CAST(o.ord_no AS text) = split_part(m.eghis_key, '_', 2)
   AND CAST(o.ord_seq_no AS text) = split_part(m.eghis_key, '_', 3)
WHERE o.proc_dept_cd = 'XRAY'
  AND (
      m.scheduled_proc_status = '100'
      OR COALESCE(o.dc_yn, 'N') = 'Y'
  )
ORDER BY COALESCE(
    m.scheduled_dttm,
    m.imaging_request_dttm,
    m.trigger_dttm,
    m.replica_dttm
) DESC
""".strip()


@dataclass(frozen=True)
class PollResult:
    inserted: int
    updated: int
    skipped: int
    removed_active: int = 0
    message: str | None = None


class PollingUnavailableError(RuntimeError):
    """Raised when the optional Eghis DB adapter is not available."""


class QueryRejectedError(RuntimeError):
    """Raised when operator-configured SQL fails the read-only safety gate."""


def poll_image_orders(
    settings: dict[str, str],
    selected_date: date | str | None = None,
) -> list[dict[str, str | None]]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return []

    return _poll_image_orders_from_db(settings, selected_date=selected_date)


def poll_eghis_image_orders_into_local_worklist(
    settings: dict[str, str],
    db_path: Path | None = None,
    poller: Callable[[dict[str, str]], list[dict[str, str | None]]] | None = None,
    selected_date: date | str | None = None,
) -> PollResult:
    if not (settings.get("eghis_db_connection_string") or "").strip():
        return PollResult(inserted=0, updated=0, skipped=0)

    initialize_database(db_path)
    try:
        if poller is None:
            orders = poll_image_orders(settings, selected_date=selected_date)
        else:
            orders = poller(settings)
    except QueryRejectedError:
        return PollResult(inserted=0, updated=0, skipped=0, message="query rejected")
    except PollingUnavailableError:
        return PollResult(inserted=0, updated=0, skipped=0, message="unavailable")
    inserted = 0
    updated = 0
    skipped = 0
    removed_active = 0

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

        selected_ymd = _normalize_selected_ymd(selected_date)
        if selected_ymd is not None:
            local_active_items = [
                item
                for item in list_pacs_worklist_items(connection, "active")
                if _requested_at_matches_ymd(item.requested_at, selected_ymd)
                and _is_eghis_polled_row(item.source)
                and _blank_to_none(item.accession_or_order_id) is not None
            ]
            existing_mwl_ids = _fetch_existing_mwl_order_ids(
                settings,
                selected_ymd,
                [
                    item.accession_or_order_id
                    for item in local_active_items
                    if item.accession_or_order_id is not None
                ],
            )
            if existing_mwl_ids is not None:
                for item in local_active_items:
                    accession = _blank_to_none(item.accession_or_order_id)
                    if accession is None or accession in existing_mwl_ids:
                        continue
                    if update_pacs_worklist_status(
                        connection,
                        item.id,
                        "cancelled",
                        "order removed from eGHIS MWL",
                    ):
                        create_pacs_audit_event(
                            connection,
                            event_type="poll",
                            worklist_item_id=item.id,
                            status_before="active",
                            status_after="cancelled",
                            summary="active order removed from eGHIS MWL -> marked cancelled",
                        )
                        removed_active += 1
        connection.commit()

    return PollResult(
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        removed_active=removed_active,
    )


def _poll_image_orders_from_db(
    settings: dict[str, str],
    *,
    selected_date: date | str | None = None,
) -> list[dict[str, str | None]]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    query = _resolve_image_study_query(settings, selected_date=selected_date)
    if not connection_string or not query:
        return []

    try:
        # KaosEghis-pacs reads Eghis DB as an EMR-side adapter and writes only to the
        # local KaosEghis SQLite worklist. It does not push to KaosPACS in this PR.
        column_names, rows = run_readonly_query(connection_string, query)
    except EghisDbQueryRejectedError as exc:
        raise QueryRejectedError(str(exc)) from exc
    except EghisDbUnavailableError as exc:
        raise PollingUnavailableError(str(exc)) from exc

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


def _resolve_image_study_query(
    settings: dict[str, str],
    *,
    selected_date: date | str | None = None,
) -> str:
    configured = (settings.get("eghis_db_image_study_query") or "").strip()
    if configured:
        return configured
    return _build_default_image_order_query(selected_date)


def _build_default_image_order_query(
    selected_date: date | str | None = None,
) -> str:
    selected_ymd = _normalize_selected_ymd(selected_date)
    if selected_ymd is None:
        return _DEFAULT_IMAGE_ORDER_QUERY

    anchor_date_sql = f"""
  AND substring(
      regexp_replace(
          COALESCE(
              m.scheduled_dttm,
              m.imaging_request_dttm,
              m.trigger_dttm,
              m.replica_dttm,
              ''
          )::text,
          '[^0-9]',
          '',
          'g'
      )
      FROM 1 FOR 8
  ) = '{selected_ymd}'
""".rstrip()
    return _DEFAULT_IMAGE_ORDER_QUERY.replace(
        "ORDER BY COALESCE(",
        f"{anchor_date_sql}\nORDER BY COALESCE(",
        1,
    )


def _normalize_selected_ymd(selected_date: date | str | None) -> str | None:
    if selected_date is None:
        return None
    if isinstance(selected_date, date):
        return selected_date.strftime("%Y%m%d")
    digits = re.sub(r"[^0-9]", "", str(selected_date))
    if len(digits) < 8:
        return None
    return digits[:8]


def _requested_at_matches_ymd(requested_at: str | None, selected_ymd: str) -> bool:
    if requested_at is None:
        return False
    digits = re.sub(r"[^0-9]", "", requested_at)
    if len(digits) < 8:
        return False
    return digits[:8] == selected_ymd


def _is_eghis_polled_row(source: str | None) -> bool:
    normalized = (source or "").strip().lower()
    return normalized in {"eghis-db", "eghis-poll"}


def _fetch_existing_mwl_order_ids(
    settings: dict[str, str],
    selected_ymd: str,
    accession_or_order_ids: list[str],
) -> set[str] | None:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return set()

    normalized_ids = [
        accession
        for accession in (_blank_to_none(value) for value in accession_or_order_ids)
        if accession is not None
    ]
    if not normalized_ids:
        return set()

    in_clause = ", ".join(_sql_quote(accession) for accession in normalized_ids)
    query = f"""
SELECT DISTINCT
    COALESCE(NULLIF(m.accession_no, ''), m.eghis_key) AS accession_or_order_id
FROM public.mwl AS m
WHERE substring(
        regexp_replace(
            COALESCE(
                m.scheduled_dttm,
                m.imaging_request_dttm,
                m.trigger_dttm,
                m.replica_dttm,
                ''
            )::text,
            '[^0-9]',
            '',
            'g'
        )
        FROM 1 FOR 8
    ) = '{selected_ymd}'
  AND COALESCE(NULLIF(m.accession_no, ''), m.eghis_key) IN ({in_clause})
""".strip()

    try:
        column_names, rows = run_readonly_query(connection_string, query)
    except (EghisDbQueryRejectedError, EghisDbUnavailableError):
        return None

    if not rows:
        return set()
    column_index = 0
    if column_names:
        for index, name in enumerate(column_names):
            if str(name).lower() == "accession_or_order_id":
                column_index = index
                break
    return {
        value
        for value in (_stringify(row[column_index]) for row in rows)
        if value is not None
    }


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
