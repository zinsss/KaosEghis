"""Test-only aggregate order-coverage proposal, never an authoritative snapshot.

Requires the trusted shared verified reader and an aware clock. No CLI, driver,
credentials, runtime importer, clinical filtering or delivery is added.
"""

from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


QUERY = (Path(__file__).parent / "fixtures" / "source_order_coverage_v1.sql").read_text(encoding="utf-8")
QUERY_SHA256 = "d608ae8ca3e477b1719f67f7ad2ff8a539bafae64aa8d27b795009300611c53c"
KST = timezone(timedelta(hours=9))
ENCOUNTER_CAP = 10000
ORDER_CAP = 100000
BOUNDS = {
    "current_day_matches": 1,
    **dict.fromkeys(("encounters", "encounters_with_orders", "encounters_without_orders",
                     "invalid_encounter_keys", "duplicate_encounter_keys"), ENCOUNTER_CAP),
    **dict.fromkeys(("linked_orders", "dated_orders", "linked_orders_on_day", "linked_orders_off_day",
                     "dated_orders_with_day_encounter", "dated_orders_without_day_encounter",
                     "linked_invalid_keys", "dated_invalid_keys", "linked_duplicate_keys",
                     "dated_duplicate_keys", "linked_three_part_multi_date_keys"), ORDER_CAP),
}
REVIEW_METRICS = (
    "invalid_encounter_keys", "duplicate_encounter_keys", "linked_orders_off_day",
    "dated_orders_without_day_encounter", "linked_invalid_keys", "dated_invalid_keys",
    "linked_duplicate_keys", "dated_duplicate_keys", "linked_three_part_multi_date_keys",
)
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")
REASONS = frozenset({
    "invalid_scope", "current_day_changed", "report_overflow_or_incomplete", "invalid_result",
    "source_overflow", "inconsistent_result", "cleanup_or_session_unverified",
})


class CoverageRejected(ValueError):
    """Fixed reason only; no source values or provider error text."""


def parameters(clinic_day):
    return {"day": clinic_day.strftime("%Y%m%d"), "encounter_limit": ENCOUNTER_CAP + 1,
            "order_limit": ORDER_CAP + 1}


def _check_day(clinic_day, now):
    if type(clinic_day) is not date or not callable(now):
        raise CoverageRejected("invalid_scope")
    instant = now()
    if type(instant) is not datetime or instant.tzinfo is None or instant.utcoffset() is None:
        raise CoverageRejected("invalid_scope")
    if instant.astimezone(KST).date() != clinic_day:
        raise CoverageRejected("current_day_changed")


def validate_rows(rows):
    if type(rows) not in (list, tuple) or len(rows) != len(BOUNDS):
        raise CoverageRejected("report_overflow_or_incomplete")
    counts = {}
    for row in rows:
        if (type(row) not in (tuple, list) or len(row) != 2
                or type(row[0]) is not str or row[0] not in BOUNDS or row[0] in counts
                or type(row[1]) is not int or row[1] < 0):
            raise CoverageRejected("invalid_result")
        if row[1] > BOUNDS[row[0]]:
            raise CoverageRejected("source_overflow")
        counts[row[0]] = row[1]
    if counts["current_day_matches"] != 1:
        raise CoverageRejected("current_day_changed")
    c = counts
    valid = (
        c["encounters_with_orders"] + c["encounters_without_orders"] == c["encounters"]
        and c["linked_orders_on_day"] + c["linked_orders_off_day"] == c["linked_orders"]
        and c["dated_orders_with_day_encounter"] + c["dated_orders_without_day_encounter"] == c["dated_orders"]
        and c["linked_orders_on_day"] == c["dated_orders_with_day_encounter"]
        and (c["encounters_with_orders"] == 0) == (c["linked_orders"] == 0)
        and c["invalid_encounter_keys"] <= c["encounters"]
        and c["duplicate_encounter_keys"] <= c["encounters"] // 2
        and c["linked_invalid_keys"] <= c["linked_orders"]
        and c["dated_invalid_keys"] <= c["dated_orders"]
        and c["linked_duplicate_keys"] <= c["linked_orders"] // 2
        and c["dated_duplicate_keys"] <= c["dated_orders"] // 2
        and c["linked_three_part_multi_date_keys"] <= c["linked_orders"] // 2
        and c["linked_three_part_multi_date_keys"] <= c["linked_orders_off_day"]
    )
    if not c["duplicate_encounter_keys"]:
        valid = valid and c["encounters_with_orders"] <= c["linked_orders"]
    if c["linked_orders_off_day"] == c["dated_orders_without_day_encounter"] == 0:
        valid = (valid and c["linked_invalid_keys"] == c["dated_invalid_keys"]
                 and c["linked_duplicate_keys"] == c["dated_duplicate_keys"])
    if not valid:
        raise CoverageRejected("inconsistent_result")
    return {"counts": dict(sorted(counts.items())),
            "review_required": [key for key in REVIEW_METRICS if counts[key] > 0]}


def inspect_coverage(query_runner, *, clinic_day, now, approved=False):
    proof = dict.fromkeys(PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        elif hashlib.sha256(QUERY.encode("utf-8")).hexdigest() != QUERY_SHA256:
            report["status"] = "query_changed"
        else:
            _check_day(clinic_day, now)
            rows = query_runner(QUERY, params=parameters(clinic_day), proof=proof)
            if not all(proof.get(key) is True for key in PROOF_FIELDS):
                raise CoverageRejected("cleanup_or_session_unverified")
            _check_day(clinic_day, now)
            findings = validate_rows(rows)
            _check_day(clinic_day, now)
            status = "coverage_anomalies_observed" if findings["review_required"] else "order_counts_observed"
            report.update(status=status, findings=findings)
    except CoverageRejected as error:
        report["status"] = str(error) if str(error) in REASONS else "read_failed"
    except EghisEvidenceRejectedError as error:
        report["status"] = (str(error) if str(error) in {
            "query_rejected", "session_unverified", "cursor_close_unverified",
        } else "read_failed")
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {
            "57014": "query_timed_out", "42501": "permission_denied",
            "42703": "schema_mismatch", "42P01": "schema_mismatch",
        }.get(getattr(error, "pgcode", None), "read_failed")
    report["closure"] = {key: proof.get(key) is True for key in PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and 0 <= elapsed <= 86400 and math.isfinite(elapsed):
        report["closure"]["elapsed_seconds"] = elapsed
    return report
