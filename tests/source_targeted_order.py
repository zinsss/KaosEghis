"""Test-only current-day aggregate probe; caller-supplied identity is never reported."""

import hashlib
import math
from pathlib import Path
import re

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError
from tests import source_named_order as base


QUERY = (Path(__file__).parent / "fixtures" / "source_targeted_order_v1.sql").read_text(encoding="utf-8")
QUERY_SHA256 = "21021162c560696540142a8f0407e2c850a1dc8c9012999746baed71c10d828d"
BOUNDS = {"current_day_matches": 1,
          **dict.fromkeys(("day_encounters", "invalid_encounter_keys", "duplicate_encounter_keys"), 10),
          **dict.fromkeys(("linked_orders", "orders_on_day", "orders_off_day", "compact_name_matches",
                           "spaced_name_matches", "exact_code_matches", "invalid_order_keys", "duplicate_order_keys"), 1000)}


def validate_rows(rows):
    if type(rows) not in (tuple, list) or len(rows) != len(BOUNDS):
        raise base.NamedOrderRejected("report_overflow_or_incomplete")
    counts = {}
    for row in rows:
        if (type(row) not in (tuple, list) or len(row) != 2 or type(row[0]) is not str
                or row[0] not in BOUNDS or row[0] in counts or type(row[1]) is not int or row[1] < 0):
            raise base.NamedOrderRejected("invalid_result")
        if row[1] > BOUNDS[row[0]]:
            raise base.NamedOrderRejected("source_overflow")
        counts[row[0]] = row[1]
    if counts["current_day_matches"] != 1:
        raise base.NamedOrderRejected("current_day_changed")
    if any(counts[k] for k in ("invalid_encounter_keys", "duplicate_encounter_keys", "invalid_order_keys", "duplicate_order_keys")):
        raise base.NamedOrderRejected("keys_unverified")
    if (counts["orders_on_day"] + counts["orders_off_day"] != counts["linked_orders"]
            or (counts["day_encounters"] == 0 and counts["linked_orders"] > 0)
            or counts["compact_name_matches"] + counts["spaced_name_matches"] > counts["linked_orders"]
            or counts["exact_code_matches"] > counts["linked_orders"]):
        raise base.NamedOrderRejected("inconsistent_result")
    return dict(sorted(counts.items()))


def inspect_target(query_runner, *, chart_no, clinic_day, now, approved=False):
    proof = dict.fromkeys(base.PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        else:
            if type(chart_no) is not str or re.fullmatch(r"[0-9]{1,12}", chart_no) is None:
                raise base.NamedOrderRejected("invalid_scope")
            if hashlib.sha256(QUERY.encode("utf-8")).hexdigest() != QUERY_SHA256:
                raise base.NamedOrderRejected("query_changed")
            base._check_day(clinic_day, now)
            params = {"day": clinic_day.strftime("%Y%m%d"), "chart_no": chart_no,
                      "compact_name": base.CONFIRMED_CODE, "spaced_name": base.ORDER_NAME,
                      "encounter_limit": 11, "order_limit": 1001}
            rows = query_runner(QUERY, params=params, proof=proof)
            if not all(proof.get(key) is True for key in base.PROOF_FIELDS):
                raise base.NamedOrderRejected("cleanup_or_session_unverified")
            base._check_day(clinic_day, now)
            counts = validate_rows(rows)
            base._check_day(clinic_day, now)
            report.update(status="target_day_counts_observed", counts=counts)
    except base.NamedOrderRejected as error:
        report["status"] = str(error) if str(error) in base.REASONS else "read_failed"
    except EghisEvidenceRejectedError as error:
        report["status"] = str(error) if str(error) in {"query_rejected", "session_unverified", "cursor_close_unverified"} else "read_failed"
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {"57014": "query_timed_out", "42501": "permission_denied",
                            "42703": "schema_mismatch", "42P01": "schema_mismatch"}.get(getattr(error, "pgcode", None), "read_failed")
    report["closure"] = {key: proof.get(key) is True for key in base.PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and 0 <= elapsed <= 86400 and math.isfinite(elapsed):
        report["closure"]["elapsed_seconds"] = elapsed
    return report
