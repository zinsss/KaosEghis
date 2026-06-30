"""Sanitized PACS polling diagnostics for local operator troubleshooting.

This module is intentionally read-only against the Eghis DB and prints only
aggregate, non-PHI diagnostics so we can investigate polling gaps without
dumping raw EMR rows.
"""

from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
    run_readonly_query,
)
from KaosEghis.db.database import (
    connect,
    describe_database_path,
    get_database_path,
    initialize_database,
)
from KaosEghis.db.repositories import get_settings


_RECENT_MWL_QUERY = """
WITH recent_mwl AS (
    SELECT
        m.scheduled_modality,
        m.scheduled_proc_status,
        NULLIF(m.accession_no, '') AS accession_no,
        m.eghis_key,
        m.scheduled_proc_desc,
        m.requested_proc_desc,
        m.scheduled_dttm,
        m.imaging_request_dttm,
        m.trigger_dttm,
        m.replica_dttm
    FROM public.mwl AS m
    WHERE COALESCE(
        m.scheduled_dttm,
        m.imaging_request_dttm,
        m.trigger_dttm,
        m.replica_dttm
    ) >= NOW() - (%(days)s::text || ' days')::interval
)
SELECT
    COUNT(*) AS total_recent_mwl_rows,
    COUNT(*) FILTER (WHERE scheduled_modality = 'BMD') AS recent_bmd_modality_rows,
    COUNT(*) FILTER (WHERE scheduled_proc_status = '100') AS status_100_rows,
    COUNT(*) FILTER (WHERE accession_no IS NOT NULL) AS accession_present_rows,
    COUNT(*) FILTER (WHERE accession_no IS NULL) AS accession_empty_rows,
    COUNT(*) FILTER (WHERE NULLIF(TRIM(eghis_key), '') IS NOT NULL) AS eghis_key_present_rows,
    COUNT(*) FILTER (
        WHERE COALESCE(array_length(string_to_array(eghis_key, '_'), 1), 0) = 3
    ) AS eghis_key_tripartite_rows,
    COUNT(*) FILTER (
        WHERE NULLIF(TRIM(COALESCE(scheduled_proc_desc, requested_proc_desc, '')), '') IS NOT NULL
    ) AS study_present_rows,
    COUNT(*) FILTER (
        WHERE NULLIF(TRIM(COALESCE(scheduled_proc_desc, requested_proc_desc, '')), '') IS NULL
    ) AS study_empty_rows,
    COUNT(*) FILTER (WHERE scheduled_dttm IS NOT NULL) AS scheduled_dttm_present_rows,
    COUNT(*) FILTER (WHERE imaging_request_dttm IS NOT NULL) AS imaging_request_dttm_present_rows,
    COUNT(*) FILTER (WHERE trigger_dttm IS NOT NULL) AS trigger_dttm_present_rows,
    COUNT(*) FILTER (WHERE replica_dttm IS NOT NULL) AS replica_dttm_present_rows
FROM recent_mwl
""".strip()

_JOIN_SUMMARY_QUERY = """
WITH recent_mwl AS (
    SELECT
        m.scheduled_modality,
        m.scheduled_proc_status,
        m.eghis_key,
        o.recept_no,
        o.proc_dept_cd,
        o.ord_cd,
        o.dc_yn
    FROM public.mwl AS m
    LEFT JOIN public.h2opd_doct_ord AS o
        ON o.recept_no = split_part(m.eghis_key, '_', 1)
       AND CAST(o.ord_no AS text) = split_part(m.eghis_key, '_', 2)
       AND CAST(o.ord_seq_no AS text) = split_part(m.eghis_key, '_', 3)
    WHERE COALESCE(
        m.scheduled_dttm,
        m.imaging_request_dttm,
        m.trigger_dttm,
        m.replica_dttm
    ) >= NOW() - (%(days)s::text || ' days')::interval
)
SELECT
    COUNT(*) AS total_recent_mwl_rows,
    COUNT(*) FILTER (WHERE recept_no IS NOT NULL) AS join_success_count,
    COUNT(*) FILTER (WHERE recept_no IS NULL) AS join_failed_count,
    COUNT(*) FILTER (
        WHERE scheduled_modality = 'BMD' OR ord_cd = 'HC342'
    ) AS bmd_like_rows,
    COUNT(*) FILTER (
        WHERE (scheduled_modality = 'BMD' OR ord_cd = 'HC342')
          AND recept_no IS NULL
    ) AS bmd_like_rows_excluded_by_join,
    COUNT(*) FILTER (
        WHERE (scheduled_modality = 'BMD' OR ord_cd = 'HC342')
          AND scheduled_proc_status <> '100'
    ) AS bmd_like_rows_excluded_by_status,
    COUNT(*) FILTER (
        WHERE (scheduled_modality = 'BMD' OR ord_cd = 'HC342')
          AND recept_no IS NOT NULL
          AND COALESCE(proc_dept_cd, '') <> 'XRAY'
    ) AS bmd_like_rows_excluded_by_proc_dept,
    COUNT(*) FILTER (
        WHERE (scheduled_modality = 'BMD' OR ord_cd = 'HC342')
          AND recept_no IS NOT NULL
          AND scheduled_proc_status = '100'
          AND COALESCE(proc_dept_cd, '') = 'XRAY'
    ) AS bmd_like_rows_passing_current_filters
FROM recent_mwl
""".strip()

_DISTINCT_VALUES_QUERY = """
WITH recent_mwl AS (
    SELECT
        m.scheduled_modality,
        o.recept_no,
        o.proc_dept_cd,
        o.ord_cd,
        o.dc_yn
    FROM public.mwl AS m
    LEFT JOIN public.h2opd_doct_ord AS o
        ON o.recept_no = split_part(m.eghis_key, '_', 1)
       AND CAST(o.ord_no AS text) = split_part(m.eghis_key, '_', 2)
       AND CAST(o.ord_seq_no AS text) = split_part(m.eghis_key, '_', 3)
    WHERE COALESCE(
        m.scheduled_dttm,
        m.imaging_request_dttm,
        m.trigger_dttm,
        m.replica_dttm
    ) >= NOW() - (%(days)s::text || ' days')::interval
)
SELECT category, value, item_count
FROM (
    SELECT
        'proc_dept_cd' AS category,
        COALESCE(proc_dept_cd, '<NULL>') AS value,
        COUNT(*) AS item_count
    FROM recent_mwl
    WHERE recept_no IS NOT NULL
    GROUP BY COALESCE(proc_dept_cd, '<NULL>')

    UNION ALL

    SELECT
        'ord_cd' AS category,
        COALESCE(ord_cd, '<NULL>') AS value,
        COUNT(*) AS item_count
    FROM recent_mwl
    WHERE scheduled_modality = 'BMD' OR ord_cd = 'HC342'
    GROUP BY COALESCE(ord_cd, '<NULL>')

    UNION ALL

    SELECT
        'dc_yn' AS category,
        COALESCE(dc_yn, '<NULL>') AS value,
        COUNT(*) AS item_count
    FROM recent_mwl
    WHERE scheduled_modality = 'BMD' OR ord_cd = 'HC342'
    GROUP BY COALESCE(dc_yn, '<NULL>')
) grouped
ORDER BY category, item_count DESC, value
""".strip()


@dataclass(frozen=True)
class PacsPollDiagnosis:
    primary_reason: str
    recommendation: str


def load_app_settings(db_path: Path | None = None) -> dict[str, str]:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return get_settings(connection)


def run_debug_report(
    settings: dict[str, str],
    *,
    days: int = 7,
) -> dict[str, Any]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return {"status": "no_db_config"}

    recent_summary = _query_single_row(
        connection_string,
        _RECENT_MWL_QUERY,
        {"days": days},
    )
    join_summary = _query_single_row(
        connection_string,
        _JOIN_SUMMARY_QUERY,
        {"days": days},
    )
    distinct_rows = _query_rows(
        connection_string,
        _DISTINCT_VALUES_QUERY,
        {"days": days},
    )
    grouped_distincts = _group_distinct_values(distinct_rows)
    diagnosis = diagnose_bmd_exclusion(join_summary)

    return {
        "status": "ok",
        "recent_summary": recent_summary,
        "join_summary": join_summary,
        "distinct_values": grouped_distincts,
        "diagnosis": diagnosis,
    }


def diagnose_bmd_exclusion(join_summary: dict[str, Any]) -> PacsPollDiagnosis:
    bmd_like_rows = _as_int(join_summary.get("bmd_like_rows"))
    passing = _as_int(join_summary.get("bmd_like_rows_passing_current_filters"))
    excluded_by_proc_dept = _as_int(
        join_summary.get("bmd_like_rows_excluded_by_proc_dept")
    )
    excluded_by_status = _as_int(join_summary.get("bmd_like_rows_excluded_by_status"))
    excluded_by_join = _as_int(join_summary.get("bmd_like_rows_excluded_by_join"))

    if bmd_like_rows <= 0:
        return PacsPollDiagnosis(
            primary_reason="no recent BMD-like MWL rows found",
            recommendation=(
                "Check whether the test order reached public.mwl in the selected time window "
                "before changing the PACS polling query."
            ),
        )
    if passing > 0:
        return PacsPollDiagnosis(
            primary_reason="current query should already include at least one BMD-like row",
            recommendation=(
                "Inspect local SQLite duplicate/update handling next; the SQL filters do not appear "
                "to be the current blocker for recent BMD-like rows."
            ),
        )
    if excluded_by_proc_dept > 0:
        return PacsPollDiagnosis(
            primary_reason="BMD-like rows are excluded by o.proc_dept_cd = 'XRAY'",
            recommendation=(
                "Minimal safe query change: keep the current XRAY filter for standard imaging rows, "
                "but allow BMD rows when m.scheduled_modality = 'BMD' or o.ord_cd = 'HC342' even if "
                "proc_dept_cd differs."
            ),
        )
    if excluded_by_status > 0:
        return PacsPollDiagnosis(
            primary_reason="BMD-like rows are excluded by m.scheduled_proc_status = '100'",
            recommendation=(
                "Verify the observed BMD scheduled_proc_status values and consider a narrow configurable "
                "allowed-status list rather than broadening the query blindly."
            ),
        )
    if excluded_by_join > 0:
        return PacsPollDiagnosis(
            primary_reason="BMD-like rows are excluded because the mwl -> h2opd_doct_ord join fails",
            recommendation=(
                "Verify the eghis_key format and join keys first. Do not add a fallback join until a "
                "safe alternative is confirmed against real data."
            ),
        )
    return PacsPollDiagnosis(
        primary_reason="BMD-like rows are still missing for an undetermined reason",
        recommendation=(
            "Review recent sanitized aggregates and check whether requested_at, accession, or study "
            "fields are empty for the affected rows before changing the production query."
        ),
    )


def _query_single_row(
    connection_string: str,
    query: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    columns, rows = _run_query(connection_string, query, params)
    if not rows:
        return {}
    first = rows[0]
    return {columns[index]: first[index] for index in range(len(columns))}


def _query_rows(
    connection_string: str,
    query: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    columns, rows = _run_query(connection_string, query, params)
    return [
        {columns[index]: row[index] for index in range(len(columns))}
        for row in rows
    ]


def _run_query(
    connection_string: str,
    query: str,
    params: dict[str, Any],
) -> tuple[list[str], list[tuple | list | object]]:
    try:
        return run_readonly_query(connection_string, query % params)
    except EghisDbQueryRejectedError as exc:
        raise RuntimeError("query rejected by read-only safety gate") from exc
    except EghisDbUnavailableError as exc:
        raise RuntimeError("database adapter unavailable") from exc


def _group_distinct_values(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        category = str(row["category"])
        value = str(row["value"])
        count = _as_int(row["item_count"])
        grouped.setdefault(category, []).append(f"{value}={count}")
    return grouped


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="python -m KaosEghis.tools.debug_pacs_poll",
        description="Print sanitized PACS polling diagnostics for recent Eghis MWL rows.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Recent lookback window in days. Defaults to 7.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Optional local KaosEghis SQLite path to load PACS settings from.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        settings = load_app_settings(args.db_path)
        report = run_debug_report(settings, days=max(1, args.days))
    except RuntimeError as exc:
        print(f"PACS poll diagnostic failed: {exc}")
        return 1

    print("KaosEghis-pacs poll diagnostics")
    print(f"SQLite settings source: {describe_database_path(args.db_path or get_database_path())}")

    status = report["status"]
    if status == "no_db_config":
        print("Status: no Eghis DB connection string configured.")
        return 0

    recent_summary = report["recent_summary"]
    join_summary = report["join_summary"]
    distinct_values = report["distinct_values"]
    diagnosis: PacsPollDiagnosis = report["diagnosis"]

    print("")
    print("Recent MWL summary")
    for key in (
        "total_recent_mwl_rows",
        "recent_bmd_modality_rows",
        "status_100_rows",
        "accession_present_rows",
        "accession_empty_rows",
        "eghis_key_present_rows",
        "eghis_key_tripartite_rows",
        "study_present_rows",
        "study_empty_rows",
        "scheduled_dttm_present_rows",
        "imaging_request_dttm_present_rows",
        "trigger_dttm_present_rows",
        "replica_dttm_present_rows",
    ):
        print(f"- {key}: {_as_int(recent_summary.get(key))}")

    print("")
    print("Join and filter summary")
    for key in (
        "join_success_count",
        "join_failed_count",
        "bmd_like_rows",
        "bmd_like_rows_passing_current_filters",
        "bmd_like_rows_excluded_by_join",
        "bmd_like_rows_excluded_by_status",
        "bmd_like_rows_excluded_by_proc_dept",
    ):
        print(f"- {key}: {_as_int(join_summary.get(key))}")

    print("")
    print("Distinct values")
    for category in ("proc_dept_cd", "ord_cd", "dc_yn"):
        values = distinct_values.get(category, [])
        print(f"- {category}: {', '.join(values) if values else '<none>'}")

    print("")
    print("Diagnosis")
    print(f"- primary_reason: {diagnosis.primary_reason}")
    print(f"- recommendation: {diagnosis.recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
