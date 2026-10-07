"""Disabled production-shaped Reception day reader with injected query execution.

The caller must supply the existing serialized read-only query boundary. This
module never discovers credentials, imports settings, mounts runtime behavior, or
opens a connection by itself.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import math
from typing import Protocol
from unicodedata import category

from KaosEghis.core.reception_current_day_patients import (
    CLINIC_TIME_ZONE,
    MAX_FRESHNESS_SECONDS,
    CurrentDayPatient,
    CurrentDayPatientList,
    IncludedPatientState,
    PROJECTION_ID,
    PROVIDER_ID,
)


MAPPING_REVISION = "eghis-proc-gb-2026-10-07"
MAX_ROWS = 10_000
ROW_SENTINEL = MAX_ROWS + 1
MAX_RESULT_BYTES = 16 * 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 3.0
STATEMENT_TIMEOUT_SECONDS = 2.0
MAX_READ_SECONDS = 6.0
APPLICATION_NAME = "KaosEghis-reception-current-day"
TEXT_LIMIT = 128

RESULT_COLUMNS = (
    "row_kind",
    "extraction_status",
    "expected_data_rows",
    "source_clinic_day",
    "observed_at",
    "selection_id",
    "display_name",
    "source_status_code",
)

QUERY = """
WITH day_guard AS (
    SELECT CASE
        WHEN to_char(timezone('Asia/Seoul', statement_timestamp()), 'YYYYMMDD') = %(clinic_day)s
        THEN 1 ELSE 0 END AS matches,
        statement_timestamp() AS observed_at
),
source_rows AS (
    SELECT h.clinic_ymd,
           CAST(h.recept_no AS text) AS selection_id,
           CAST(h.ptnt_no AS text) AS patient_key,
           CAST(h.proc_gb AS text) AS source_status_code
    FROM public.h1opdin h
    WHERE h.clinic_ymd = %(clinic_day)s
      AND h.proc_gb IN ('30', '40')
      AND (SELECT matches FROM day_guard) = 1
),
distinct_facts AS (
    SELECT DISTINCT clinic_ymd, selection_id, patient_key, source_status_code
    FROM source_rows
),
limited AS (
    SELECT clinic_ymd, selection_id, patient_key, source_status_code
    FROM distinct_facts
    ORDER BY selection_id, patient_key, source_status_code
    LIMIT %(row_sentinel)s
),
encounters AS (
    SELECT clinic_ymd,
           selection_id,
           MIN(patient_key) AS patient_key,
           MIN(source_status_code) AS source_status_code,
           COUNT(*) AS encounter_matches
    FROM limited
    GROUP BY clinic_ymd, selection_id
),
joined AS (
    SELECT e.clinic_ymd,
           e.selection_id,
           e.source_status_code,
           e.encounter_matches,
           COUNT(p.ptnt_no) AS patient_matches,
           MIN(CAST(p.ptnt_nm AS text)) AS display_name
    FROM encounters e
    LEFT JOIN public.hz_mst_ptnt p
      ON CAST(p.ptnt_no AS text) = e.patient_key
    GROUP BY e.clinic_ymd, e.selection_id, e.source_status_code, e.encounter_matches
),
metrics AS (
    SELECT (SELECT matches FROM day_guard) AS day_matches,
           (SELECT COUNT(*) FROM limited) AS limited_rows,
           (SELECT COUNT(*) FROM joined) AS result_rows,
           (SELECT COUNT(*) FROM limited
             WHERE selection_id IS NULL OR trim(selection_id) = ''
                OR selection_id <> trim(selection_id)
                OR char_length(selection_id) > %(text_limit)s) AS invalid_identity_rows,
           (SELECT COUNT(*) FROM joined
             WHERE encounter_matches <> 1) AS duplicate_encounters,
           (SELECT COUNT(*) FROM joined
             WHERE patient_matches <> 1) AS patient_join_mismatches,
           (SELECT COUNT(*) FROM joined
             WHERE display_name IS NULL OR trim(display_name) = ''
                OR display_name <> trim(display_name)
                OR char_length(display_name) > %(text_limit)s) AS invalid_name_rows,
           (SELECT COALESCE(SUM(
                octet_length(COALESCE(selection_id, ''))
              + octet_length(COALESCE(display_name, ''))
              + octet_length(COALESCE(source_status_code, ''))
           ), 0) FROM joined) AS result_bytes
),
assessment AS (
    SELECT CASE
        WHEN day_matches <> 1 THEN 'day_mismatch'
        WHEN limited_rows > %(max_rows)s THEN 'row_overflow'
        WHEN invalid_identity_rows <> 0 THEN 'invalid_encounter_identity'
        WHEN duplicate_encounters <> 0 THEN 'duplicate_encounter'
        WHEN patient_join_mismatches <> 0 THEN 'patient_join_mismatch'
        WHEN invalid_name_rows <> 0 THEN 'invalid_display_name'
        WHEN result_bytes > %(max_result_bytes)s THEN 'byte_overflow'
        ELSE 'complete' END AS extraction_status,
        result_rows AS expected_data_rows
    FROM metrics
)
SELECT 'META' AS row_kind,
       a.extraction_status,
       a.expected_data_rows,
       %(clinic_day)s AS source_clinic_day,
       d.observed_at,
       CAST(NULL AS text) AS selection_id,
       CAST(NULL AS text) AS display_name,
       CAST(NULL AS text) AS source_status_code
FROM assessment a CROSS JOIN day_guard d
UNION ALL
SELECT 'DATA' AS row_kind,
       a.extraction_status,
       a.expected_data_rows,
       j.clinic_ymd AS source_clinic_day,
       d.observed_at,
       j.selection_id,
       j.display_name,
       j.source_status_code
FROM joined j CROSS JOIN assessment a CROSS JOIN day_guard d
WHERE a.extraction_status = 'complete'
ORDER BY row_kind DESC, selection_id
""".strip()


class ReceptionDayReadRejected(ValueError):
    """Fixed reason code only; never source values or provider messages."""


class SerializedQueryRunner(Protocol):
    def __call__(
        self,
        query: str,
        *,
        params: Mapping[str, object],
        connect_timeout_seconds: float,
        statement_timeout_seconds: float,
        application_name: str,
        timings: dict[str, float],
    ) -> tuple[Sequence[str], Sequence[Sequence[object]]]: ...


def _aware(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ReceptionDayReadRejected("invalid_result") from None
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ReceptionDayReadRejected("invalid_result")
    return value


def _text(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > TEXT_LIMIT
        or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise ReceptionDayReadRejected("invalid_result")
    return value


def _stage(timings: Mapping[str, object], name: str) -> float:
    value = timings.get(name)
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ReceptionDayReadRejected("cleanup_unverified")
    return float(value)


def _validate_cleanup(timings: Mapping[str, object]) -> None:
    names = (
        "connected",
        "session_ready",
        "timeout_set",
        "query_finished",
        "rows_fetched",
        "cursor_closed",
        "connection_closed",
    )
    stages = tuple(_stage(timings, name) for name in names)
    if stages != tuple(sorted(stages)) or stages[-1] > MAX_READ_SECONDS:
        raise ReceptionDayReadRejected("cleanup_unverified")


def _row_maps(
    columns: Sequence[str], rows: Sequence[Sequence[object]]
) -> tuple[dict[str, object], ...]:
    if tuple(columns) != RESULT_COLUMNS or not isinstance(rows, (tuple, list)):
        raise ReceptionDayReadRejected("invalid_result")
    if len(rows) > MAX_ROWS + 1:
        raise ReceptionDayReadRejected("row_overflow")
    mapped = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != len(RESULT_COLUMNS):
            raise ReceptionDayReadRejected("invalid_result")
        mapped.append(dict(zip(RESULT_COLUMNS, row)))
    return tuple(mapped)


@dataclass(frozen=True, slots=True, repr=False)
class BoundedReceptionDayProvider:
    """Unwired adapter over the shared serialized read-only query runner."""

    query_runner: SerializedQueryRunner = field(repr=False)
    freshness_limit: timedelta = timedelta(seconds=MAX_FRESHNESS_SECONDS)

    def __post_init__(self) -> None:
        if not callable(self.query_runner):
            raise ReceptionDayReadRejected("invalid_runner")
        if (
            type(self.freshness_limit) is not timedelta
            or self.freshness_limit <= timedelta(0)
            or self.freshness_limit > timedelta(seconds=MAX_FRESHNESS_SECONDS)
        ):
            raise ReceptionDayReadRejected("invalid_freshness")

    def __repr__(self) -> str:
        return "<BoundedReceptionDayProvider: redacted>"

    def read_current_day(self, now: datetime) -> CurrentDayPatientList:
        current_time = _aware(now)
        clinic_day = current_time.astimezone(CLINIC_TIME_ZONE).date()
        params = {
            "clinic_day": clinic_day.strftime("%Y%m%d"),
            "row_sentinel": ROW_SENTINEL,
            "max_rows": MAX_ROWS,
            "text_limit": TEXT_LIMIT,
            "max_result_bytes": MAX_RESULT_BYTES,
        }
        timings: dict[str, float] = {}
        try:
            columns, rows = self.query_runner(
                QUERY,
                params=params,
                connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
                statement_timeout_seconds=STATEMENT_TIMEOUT_SECONDS,
                application_name=APPLICATION_NAME,
                timings=timings,
            )
        except Exception:
            raise ReceptionDayReadRejected("source_unavailable") from None
        _validate_cleanup(timings)
        return self._validated_result(clinic_day, current_time, _row_maps(columns, rows))

    def _validated_result(
        self,
        clinic_day: date,
        current_time: datetime,
        rows: tuple[dict[str, object], ...],
    ) -> CurrentDayPatientList:
        meta = [row for row in rows if row["row_kind"] == "META"]
        data = [row for row in rows if row["row_kind"] == "DATA"]
        if len(meta) != 1 or len(meta) + len(data) != len(rows):
            raise ReceptionDayReadRejected("invalid_result")
        header = meta[0]
        if header["extraction_status"] != "complete":
            raise ReceptionDayReadRejected("source_scope_unverified")
        source_day = clinic_day.strftime("%Y%m%d")
        if (
            header["source_clinic_day"] != source_day
            or header["selection_id"] is not None
            or header["display_name"] is not None
            or header["source_status_code"] is not None
        ):
            raise ReceptionDayReadRejected("invalid_result")
        expected = header["expected_data_rows"]
        if type(expected) is not int or not 0 <= expected <= MAX_ROWS or expected != len(data):
            raise ReceptionDayReadRejected("invalid_result")
        observed_at = _aware(header["observed_at"])
        age = current_time.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)
        if age < timedelta(seconds=-30):
            raise ReceptionDayReadRejected("future_observation")
        if age > self.freshness_limit:
            raise ReceptionDayReadRejected("stale_read")

        unique: dict[str, CurrentDayPatient] = {}
        result_bytes = 0
        states = {
            "30": IncludedPatientState.CONSULTATION_COMPLETED,
            "40": IncludedPatientState.PAYMENT_COMPLETED,
        }
        for row in data:
            if (
                row["extraction_status"] != "complete"
                or row["expected_data_rows"] != expected
                or row["source_clinic_day"] != source_day
                or _aware(row["observed_at"]) != observed_at
            ):
                raise ReceptionDayReadRejected("invalid_result")
            selection_id = _text(row["selection_id"])
            display_name = _text(row["display_name"])
            code = row["source_status_code"]
            state = states.get(code)
            if state is None:
                raise ReceptionDayReadRejected("invalid_result")
            result_bytes += sum(
                len(value.encode("utf-8")) for value in (selection_id, display_name, code)
            )
            patient = CurrentDayPatient(selection_id, display_name, state)
            prior = unique.get(selection_id)
            if prior is not None and prior != patient:
                raise ReceptionDayReadRejected("conflicting_duplicate")
            unique[selection_id] = patient
        if result_bytes > MAX_RESULT_BYTES:
            raise ReceptionDayReadRejected("byte_overflow")
        return CurrentDayPatientList(
            PROVIDER_ID,
            PROJECTION_ID,
            clinic_day,
            observed_at,
            tuple(unique[key] for key in sorted(unique)),
        )
