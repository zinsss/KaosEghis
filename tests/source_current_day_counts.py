"""Review-only aggregate proposal. No CLI, credentials or runtime importer.

The trusted caller supplies the shared verified reader and an aware clock. This
is not a source snapshot, production filter or approved live operation.
"""

from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


QUERY = (Path(__file__).parent / "fixtures" / "source_current_day_counts_v1.sql").read_text(
    encoding="utf-8",
)
QUERY_SHA256 = "6f510ed7ca47f9c01c1f692b7b92fee52c3dbcceca0e4b693c8cb0bf832069c8"
KST = timezone(timedelta(hours=9))
ENCOUNTER_CAP = 10000
CODES = ("10", "20", "25", "30", "40", "50")
FLAGS = ("Y", "N")
MASKS = ("NULL", "BLANK", "UNREVIEWED")
PRESENCE = ("WITH_ORDERS", "WITHOUT_ORDERS")
SUMMARY_FIELDS = ("current_day_matches", "encounters", "invalid_encounter_keys",
                  "duplicate_encounter_keys")
REPORT_CAP = len(SUMMARY_FIELDS) + (len(CODES) + len(MASKS)) * (len(FLAGS) + len(MASKS)) * 2
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")
REASONS = frozenset({
    "invalid_scope", "current_day_changed", "report_overflow_or_incomplete",
    "invalid_result", "incomplete_result", "inconsistent_result", "source_overflow",
    "encounter_keys_unverified", "cleanup_or_session_unverified",
})


class CountsRejected(ValueError):
    """Fixed reason only; never echo input or provider diagnostics."""


def parameters(clinic_day):
    return {"day": clinic_day.strftime("%Y%m%d"), "encounter_limit": ENCOUNTER_CAP + 1,
            "codes": list(CODES), "flags": list(FLAGS)}


def _check_day(clinic_day, now):
    if type(clinic_day) is not date or not callable(now):
        raise CountsRejected("invalid_scope")
    instant = now()
    if type(instant) is not datetime or instant.tzinfo is None or instant.utcoffset() is None:
        raise CountsRejected("invalid_scope")
    if instant.astimezone(KST).date() != clinic_day:
        raise CountsRejected("current_day_changed")


def validate_rows(rows):
    if type(rows) not in (list, tuple) or not 4 <= len(rows) <= REPORT_CAP:
        raise CountsRejected("report_overflow_or_incomplete")
    summary, buckets = {}, {}
    for row in rows:
        if (type(row) not in (tuple, list) or len(row) != 5
                or any(type(value) is not str for value in row[:4])
                or type(row[4]) is not int or row[4] < 0):
            raise CountsRejected("invalid_result")
        section, code, hold, presence, count = row
        if count > ENCOUNTER_CAP:
            raise CountsRejected("source_overflow")
        if section == "summary" and code in SUMMARY_FIELDS and hold == presence == "":
            if code in summary:
                raise CountsRejected("invalid_result")
            summary[code] = count
        elif (section == "bucket" and code in CODES + MASKS and hold in FLAGS + MASKS
              and presence in PRESENCE and count > 0):
            key = (code, hold, presence)
            if key in buckets:
                raise CountsRejected("invalid_result")
            buckets[key] = count
        else:
            raise CountsRejected("invalid_result")
    if set(summary) != set(SUMMARY_FIELDS):
        raise CountsRejected("incomplete_result")
    if summary["current_day_matches"] == 0:
        raise CountsRejected("current_day_changed")
    if summary["current_day_matches"] != 1 or sum(buckets.values()) != summary["encounters"]:
        raise CountsRejected("inconsistent_result")
    if summary["invalid_encounter_keys"] or summary["duplicate_encounter_keys"]:
        raise CountsRejected("encounter_keys_unverified")
    return {
        "counts": {"encounters": summary["encounters"], **{
            presence.lower(): sum(count for key, count in buckets.items() if key[2] == presence)
            for presence in PRESENCE
        }},
        "buckets": [{"code": code, "hold_yn": hold, "order_presence": presence, "count": count}
                    for (code, hold, presence), count in sorted(buckets.items())],
    }


def inspect_counts(query_runner, *, clinic_day, now, approved=False):
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
                raise CountsRejected("cleanup_or_session_unverified")
            _check_day(clinic_day, now)
            findings = validate_rows(rows)
            _check_day(clinic_day, now)
            report.update(status="counts_observed", findings=findings)
    except CountsRejected as error:
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
    # Copy only allowlisted proof fields, even when an injected reader fails.
    report["closure"] = {key: proof.get(key) is True for key in PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and 0 <= elapsed <= 86400 and math.isfinite(elapsed):
        report["closure"]["elapsed_seconds"] = elapsed
    return report
