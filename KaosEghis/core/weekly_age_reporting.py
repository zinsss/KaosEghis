"""Weekly age-group practice-count reporting against the Eghis PostgreSQL database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
    run_readonly_query,
)

AGE_GROUP_ORDER = [
    "~0",
    "1-6",
    "7-12",
    "13-18",
    "19-49",
    "50-64",
    "65 over",
]


@dataclass(frozen=True)
class WeeklyAgeRow:
    age_group: str
    visit_count: int
    patient_count: int


class WeeklyAgeReportingUnavailableError(RuntimeError):
    """Raised when the reporting adapter is unavailable."""


def iso_week_range(year: int, iso_week: int) -> tuple[str, str]:
    try:
        start_date = date.fromisocalendar(year, iso_week, 1)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO week: {year}-W{iso_week:02d}") from exc
    end_date = start_date + timedelta(days=6)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def expand_week_range(year: int, start_week: int, end_week: int) -> tuple[str, str]:
    if end_week < start_week:
        raise ValueError("End week must be greater than or equal to start week.")
    start_ymd, _ = iso_week_range(year, start_week)
    _, end_ymd = iso_week_range(year, end_week)
    return start_ymd, end_ymd


def build_weekly_age_report_query(start_ymd: str, end_ymd: str) -> str:
    return f"""
WITH visit_base AS (
    SELECT
        h.ptnt_no,
        EXTRACT(
            YEAR FROM age(
                to_date(h.clinic_ymd, 'YYYYMMDD'),
                to_date(p.birth_ymd, 'YYYYMMDD')
            )
        )::int AS age_years
    FROM public.h1opdin h
    JOIN public.hz_mst_ptnt p
      ON p.ptnt_no = h.ptnt_no
    WHERE h.clinic_ymd BETWEEN '{start_ymd}' AND '{end_ymd}'
      AND h.proc_gb IN ('30', '40')
      AND p.birth_ymd ~ '^[0-9]{{8}}$'
),
bucketed_visits AS (
    SELECT
        CASE
            WHEN age_years <= 0 THEN '~0'
            WHEN age_years BETWEEN 1 AND 6 THEN '1-6'
            WHEN age_years BETWEEN 7 AND 12 THEN '7-12'
            WHEN age_years BETWEEN 13 AND 18 THEN '13-18'
            WHEN age_years BETWEEN 19 AND 49 THEN '19-49'
            WHEN age_years BETWEEN 50 AND 64 THEN '50-64'
            ELSE '65 over'
        END AS age_group,
        COUNT(*)::int AS visit_count,
        COUNT(DISTINCT ptnt_no)::int AS patient_count
    FROM visit_base
    GROUP BY 1
)
SELECT
    age_group,
    visit_count,
    patient_count
FROM bucketed_visits
ORDER BY
    CASE age_group
        WHEN '~0' THEN 1
        WHEN '1-6' THEN 2
        WHEN '7-12' THEN 3
        WHEN '13-18' THEN 4
        WHEN '19-49' THEN 5
        WHEN '50-64' THEN 6
        ELSE 7
    END
""".strip()


def fetch_weekly_age_report(
    settings: dict[str, str],
    *,
    year: int,
    start_week: int,
    end_week: int | None = None,
) -> list[WeeklyAgeRow]:
    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        return []

    resolved_end_week = start_week if end_week is None else end_week
    start_ymd, end_ymd = expand_week_range(year, start_week, resolved_end_week)
    query = build_weekly_age_report_query(start_ymd, end_ymd)

    try:
        column_names, rows = run_readonly_query(connection_string, query)
    except (EghisDbQueryRejectedError, EghisDbUnavailableError) as exc:
        raise WeeklyAgeReportingUnavailableError(str(exc)) from exc

    return [_map_weekly_age_row(column_names, row) for row in rows]


def _map_weekly_age_row(
    column_names: list[str], row: tuple | list | object
) -> WeeklyAgeRow:
    row_map = {column_names[index]: row[index] for index in range(len(column_names))}
    return WeeklyAgeRow(
        age_group=str(row_map.get("age_group") or "").strip(),
        visit_count=int(row_map.get("visit_count") or 0),
        patient_count=int(row_map.get("patient_count") or 0),
    )
