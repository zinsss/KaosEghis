from __future__ import annotations

from dataclasses import dataclass
import re

from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
    run_readonly_query,
)


class PatientContextNotFoundError(RuntimeError):
    pass


class PatientContextAmbiguousError(RuntimeError):
    pass


class PatientContextSourceUnavailableError(RuntimeError):
    pass


class InvalidPatientIdError(ValueError):
    pass


_PATIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class PatientContextRecord:
    chart_no: str
    patient_name: str
    patient_birth_date: str
    patient_sex: str
    source: str = "egHis"
    confidence: str = "exact"


def get_patient_context(settings: dict[str, str], chart_no: str) -> PatientContextRecord:
    normalized_chart_no = normalize_patient_id(chart_no)

    connection_string = (settings.get("eghis_db_connection_string") or "").strip()
    if not connection_string:
        raise PatientContextSourceUnavailableError("Eghis DB is not configured.")

    query = _build_patient_context_query(normalized_chart_no)
    try:
        column_names, rows = run_readonly_query(connection_string, query)
    except (EghisDbUnavailableError, EghisDbQueryRejectedError, Exception) as exc:
        if isinstance(exc, (PatientContextNotFoundError, PatientContextAmbiguousError)):
            raise
        raise PatientContextSourceUnavailableError("Patient context source unavailable.") from exc

    if not rows:
        raise PatientContextNotFoundError("Patient not found.")
    if len(rows) > 1:
        raise PatientContextAmbiguousError("Multiple patient rows matched the chart number.")

    row_map = dict(zip(column_names, rows[0]))
    return PatientContextRecord(
        chart_no=normalized_chart_no,
        patient_name=_normalize_text(row_map.get("patient_name")),
        patient_birth_date=_normalize_birth_date(row_map.get("patient_birth_date")),
        patient_sex=_normalize_sex(row_map.get("patient_sex")),
    )


def normalize_patient_id(chart_no: str) -> str:
    normalized = str(chart_no or "").strip()
    if not _PATIENT_ID_PATTERN.fullmatch(normalized):
        raise InvalidPatientIdError("Invalid patient ID.")
    return normalized


def _build_patient_context_query(chart_no: str) -> str:
    escaped_chart_no = chart_no.replace("'", "''")
    return f"""
SELECT
    ptnt_no AS chart_no,
    ptnt_nm AS patient_name,
    birth_ymd AS patient_birth_date,
    sex AS patient_sex
FROM public.hz_mst_ptnt
WHERE ptnt_no = '{escaped_chart_no}'
ORDER BY ptnt_no
LIMIT 2
""".strip()


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_birth_date(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def _normalize_sex(value: object) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"M", "MALE", "1", "남", "남성"}:
        return "M"
    if normalized in {"F", "FEMALE", "2", "여", "여성"}:
        return "F"
    if normalized:
        return "O"
    return ""
