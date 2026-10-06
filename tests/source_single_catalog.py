"""One explicitly approved visit's standard catalog fields, not a historical reader."""

from datetime import date, datetime
import hashlib
import math
from pathlib import Path
import re
import unicodedata

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError
from tests.source_named_order import KST, PROOF_FIELDS

QUERY = (Path(__file__).parent / "fixtures" / "source_single_catalog_v1.sql").read_text(encoding="utf-8")
QUERY_SHA256 = "df5e23c2596a16000c3ca754a8c024b59b6e15db94410ad2d09b0aab20c050e8"
APPROVED_VISIT_DAY = date(2026, 10, 6)
APPROVED_READ_DAY = date(2026, 10, 7)
REASONS = {"invalid_scope", "approved_window_changed", "query_changed", "invalid_result",
           "single_order_scope_unconfirmed", "catalog_text_withheld", "cleanup_or_session_unverified"}


class CatalogRejected(ValueError):
    """Fixed reason, never provider text or identifying input."""


def check_scope(clinic_day, chart_no, now):
    if (type(clinic_day) is not date or clinic_day != APPROVED_VISIT_DAY
            or type(chart_no) is not str or re.fullmatch(r"[0-9]{1,12}", chart_no) is None
            or not callable(now)):
        raise CatalogRejected("invalid_scope")
    instant = now()
    if type(instant) is not datetime or instant.tzinfo is None or instant.utcoffset() is None:
        raise CatalogRejected("invalid_scope")
    if instant.astimezone(KST).date() != APPROVED_READ_DAY:
        raise CatalogRejected("approved_window_changed")


def validate_rows(rows):
    if type(rows) not in (tuple, list) or len(rows) != 1 or type(rows[0]) not in (tuple, list) or len(rows[0]) != 7:
        raise CatalogRejected("invalid_result")
    encounters, orders, invalid, off_day, withheld, code, name = rows[0]
    if any(type(n) is not int or not 0 <= n <= 2 for n in rows[0][:5]):
        raise CatalogRejected("invalid_result")
    if (encounters, orders, invalid, off_day) != (1, 1, 0, 0):
        raise CatalogRejected("single_order_scope_unconfirmed")
    if withheld:
        raise CatalogRejected("catalog_text_withheld")
    for value, cap in ((code, 64), (name, 256)):
        if value is None:
            continue
        if (type(value) is not str or len(value) > cap
                or any(unicodedata.category(c).startswith("C") for c in value)
                or re.search(r"[0-9]{6}[- ]?[1-8][0-9]{6}|01[016789][- ]?[0-9]{3,4}[- ]?[0-9]{4}", value)):
            raise CatalogRejected("catalog_text_withheld")
    return {"code": code, "name": name}


def inspect_catalog(query_runner, *, clinic_day, chart_no, now, approved=False):
    proof = dict.fromkeys(PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        else:
            check_scope(clinic_day, chart_no, now)
            if hashlib.sha256(QUERY.encode("utf-8")).hexdigest() != QUERY_SHA256:
                raise CatalogRejected("query_changed")
            rows = query_runner(QUERY, params={"day": clinic_day.strftime("%Y%m%d"), "chart_no": chart_no,
                                              "read_day": APPROVED_READ_DAY.strftime("%Y%m%d")}, proof=proof)
            if not all(proof.get(key) is True for key in PROOF_FIELDS):
                raise CatalogRejected("cleanup_or_session_unverified")
            check_scope(clinic_day, chart_no, now)
            catalog = validate_rows(rows)
            check_scope(clinic_day, chart_no, now)
            report.update(status="single_catalog_observed", catalog=catalog)
    except CatalogRejected as error:
        report["status"] = str(error) if str(error) in REASONS else "read_failed"
    except EghisEvidenceRejectedError as error:
        report["status"] = str(error) if str(error) in {"query_rejected", "session_unverified", "cursor_close_unverified"} else "read_failed"
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {"57014": "query_timed_out", "42501": "permission_denied",
                            "42703": "schema_mismatch", "42P01": "schema_mismatch"}.get(getattr(error, "pgcode", None), "read_failed")
    report["closure"] = {key: proof.get(key) is True for key in PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and 0 <= elapsed <= 86400 and math.isfinite(elapsed):
        report["closure"]["elapsed_seconds"] = elapsed
    return report
