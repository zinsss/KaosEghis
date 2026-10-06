"""Test-only exact catalog-name observation; not a source snapshot or runtime reader."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path
import re

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


QUERY = (Path(__file__).parent / "fixtures" / "source_named_order_v1.sql").read_text(encoding="utf-8")
QUERY_SHA256 = "c1ec4286191ce2b766df5a922619e008583558ab6f10bf6fc050739af78f01e6"
ORDER_NAME = "\uad6d\uac00\uc811\uc885 \ub3c5\uac10"
CODE_QUERY = (Path(__file__).parent / "fixtures" / "source_named_order_code_v1.sql").read_text(encoding="utf-8")
CODE_QUERY_SHA256 = "87c78f2d7c8be948546503bc690be71ca0c98f6ebb6761619b5f51e3000aa25f"
CONFIRMED_CODE = "\uad6d\uac00\uc811\uc885\ub3c5\uac10"
NAME_MATCHES = ("COMPACT_NAME", "SPACED_NAME", "NULL_NAME", "OTHER_NAME")
KST = timezone(timedelta(hours=9))
ENCOUNTER_CAP, ORDER_CAP, BUCKET_CAP = 10000, 1000, 32
CODE_PATTERN = r"^[A-Za-z0-9_.@#*-]{1,32}$"
TYPES = ("01", "02", "03", "04", "05", "06", "07", "08", "09")
DEPARTMENTS = ("LAB", "DRUG", "INJ", "XRAY", "BMD", "ECG", "PT")
FLAGS = ("Y", "N")
MASKS = ("NULL", "BLANK", "UNREVIEWED")
BOUNDS = {
    "current_day_matches": 1,
    **dict.fromkeys(("encounters_in_scope", "invalid_encounter_keys", "duplicate_encounter_keys"), ENCOUNTER_CAP),
    **dict.fromkeys(("matched_orders", "matched_encounters", "invalid_order_keys", "duplicate_order_keys"), ORDER_CAP),
}
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")
REASONS = frozenset({
    "invalid_scope", "current_day_changed", "report_overflow_or_incomplete", "invalid_result",
    "source_overflow", "inconsistent_result", "keys_unverified", "catalog_code_unreviewed",
    "cleanup_or_session_unverified", "query_changed",
})


class NamedOrderRejected(ValueError):
    """Fixed reason only; no provider text or source values."""


def parameters(clinic_day, *, by_code=False, compact_name=False):
    params = {"day": clinic_day.strftime("%Y%m%d"),
              "encounter_limit": ENCOUNTER_CAP + 1, "order_limit": ORDER_CAP + 1,
              "types": list(TYPES), "departments": list(DEPARTMENTS), "flags": list(FLAGS)}
    if by_code:
        params.update(order_code=CONFIRMED_CODE, compact_name=CONFIRMED_CODE, spaced_name=ORDER_NAME)
    else:
        params.update(order_name=CONFIRMED_CODE if compact_name else ORDER_NAME, code_pattern=CODE_PATTERN)
    return params


def _check_day(clinic_day, now):
    if type(clinic_day) is not date or not callable(now):
        raise NamedOrderRejected("invalid_scope")
    instant = now()
    if type(instant) is not datetime or instant.tzinfo is None or instant.utcoffset() is None:
        raise NamedOrderRejected("invalid_scope")
    if instant.astimezone(KST).date() != clinic_day:
        raise NamedOrderRejected("current_day_changed")


def validate_rows(rows, *, by_code=False):
    if type(rows) not in (list, tuple) or not len(BOUNDS) <= len(rows) <= len(BOUNDS) + BUCKET_CAP:
        raise NamedOrderRejected("report_overflow_or_incomplete")
    counts, buckets = {}, {}
    for row in rows:
        if (type(row) not in (list, tuple) or len(row) != 8
                or type(row[-1]) is not int or row[-1] < 0):
            raise NamedOrderRejected("invalid_result")
        section, metric, code, kind, department, dc, act, n = row
        if section == "summary":
            if (type(metric) is not str or metric not in BOUNDS or metric in counts
                    or (code, kind, department, dc, act) != ("",) * 5):
                raise NamedOrderRejected("invalid_result")
            if n > BOUNDS[metric]:
                raise NamedOrderRejected("source_overflow")
            counts[metric] = n
        elif section == "bucket" and (metric in NAME_MATCHES if by_code else metric == ""):
            if by_code and code != "CONFIRMED_CODE":
                raise NamedOrderRejected("catalog_code_unreviewed")
            if not by_code and (type(code) is not str or re.fullmatch(CODE_PATTERN, code) is None):
                raise NamedOrderRejected("catalog_code_unreviewed")
            if (kind not in TYPES + MASKS or department not in DEPARTMENTS + MASKS
                    or dc not in FLAGS + MASKS or act not in FLAGS + MASKS or n == 0):
                raise NamedOrderRejected("invalid_result")
            if n > ORDER_CAP:
                raise NamedOrderRejected("source_overflow")
            key = (code, kind, department, dc, act, metric)
            if key in buckets:
                raise NamedOrderRejected("invalid_result")
            buckets[key] = n
        else:
            raise NamedOrderRejected("invalid_result")
    if set(counts) != set(BOUNDS):
        raise NamedOrderRejected("report_overflow_or_incomplete")
    if counts["current_day_matches"] != 1:
        raise NamedOrderRejected("current_day_changed")
    if any(counts[key] for key in ("invalid_encounter_keys", "duplicate_encounter_keys",
                                   "invalid_order_keys", "duplicate_order_keys")):
        raise NamedOrderRejected("keys_unverified")
    if (sum(buckets.values()) != counts["matched_orders"]
            or counts["matched_encounters"] > min(counts["matched_orders"], counts["encounters_in_scope"])
            or (counts["matched_encounters"] == 0) != (counts["matched_orders"] == 0)):
        raise NamedOrderRejected("inconsistent_result")
    findings = []
    for (code, kind, department, dc, act, name_match), n in sorted(buckets.items()):
        bucket = dict(zip(("catalog_code", "order_type", "department", "dc_yn", "act_yn", "count"),
                          (CONFIRMED_CODE if by_code else code, kind, department, dc, act, n)))
        if by_code:
            bucket["catalog_name_match"] = name_match
        findings.append(bucket)
    return {"counts": dict(sorted(counts.items())), "buckets": findings}


def inspect_named_order(query_runner, *, clinic_day, now, approved=False, by_code=False, compact_name=False):
    proof = dict.fromkeys(PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        else:
            if type(by_code) is not bool or type(compact_name) is not bool or (by_code and compact_name):
                raise NamedOrderRejected("invalid_scope")
            query, digest = (CODE_QUERY, CODE_QUERY_SHA256) if by_code else (QUERY, QUERY_SHA256)
            if hashlib.sha256(query.encode("utf-8")).hexdigest() != digest:
                raise NamedOrderRejected("query_changed")
            _check_day(clinic_day, now)
            rows = query_runner(query, params=parameters(clinic_day, by_code=by_code, compact_name=compact_name), proof=proof)
            if not all(proof.get(key) is True for key in PROOF_FIELDS):
                raise NamedOrderRejected("cleanup_or_session_unverified")
            _check_day(clinic_day, now)
            findings = validate_rows(rows, by_code=True) if by_code else validate_rows(rows)
            _check_day(clinic_day, now)
            status = "named_order_observed" if findings["counts"]["matched_orders"] else "named_order_not_found"
            report.update(status=status, findings=findings)
    except NamedOrderRejected as error:
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
