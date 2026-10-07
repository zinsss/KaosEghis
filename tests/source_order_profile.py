"""One-shot, aggregate-only performance inspection; no runtime or credentials."""

import hashlib
import json
import math

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError
from tests import source_order_coverage as coverage


PREFIX = "EXPLAIN (ANALYZE TRUE, BUFFERS TRUE, FORMAT JSON)\n"
BLOCKS = (
    "Shared Hit Blocks", "Shared Read Blocks", "Shared Dirtied Blocks", "Shared Written Blocks",
    "Local Hit Blocks", "Local Read Blocks", "Local Dirtied Blocks", "Local Written Blocks",
    "Temp Read Blocks", "Temp Written Blocks",
)
SCANS = ("Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan", "Bitmap Index Scan")


class ProfileRejected(ValueError):
    """Fixed reason, never plan text, predicates or source values."""


def _number(value, *, integer=False):
    if (type(value) not in ((int,) if integer else (int, float))
            or not 0 <= value <= 10**12 or not math.isfinite(value)):
        raise ProfileRejected("invalid_profile")
    return value


def summarize_plan(rows):
    if type(rows) not in (list, tuple) or len(rows) != 1:
        raise ProfileRejected("invalid_profile")
    if type(rows[0]) not in (list, tuple) or len(rows[0]) != 1:
        raise ProfileRejected("invalid_profile")
    plan = rows[0][0]
    if type(plan) is str:
        if len(plan) > 2_000_000:
            raise ProfileRejected("invalid_profile")
        try:
            plan = json.loads(plan)
        except (ValueError, RecursionError):
            raise ProfileRejected("invalid_profile") from None
    if type(plan) is not list or len(plan) != 1 or type(plan[0]) is not dict:
        raise ProfileRejected("invalid_profile")
    top = plan[0]
    root = top.get("Plan")
    if type(root) is not dict or root.get("Node Type") != "Limit":
        raise ProfileRejected("invalid_profile")
    if root.get("Actual Rows") != len(coverage.BOUNDS) or root.get("Actual Loops") != 1:
        raise ProfileRejected("invalid_profile")
    runtime = top.get("Execution Time", top.get("Total Runtime"))
    result = {"server_execution_ms": _number(runtime),
              "root_execution_ms": _number(root.get("Actual Total Time")),
              "buffers": {key: _number(root.get(key), integer=True) for key in BLOCKS}}
    scans = dict.fromkeys(SCANS, 0)
    stack, visited = [root], set()
    while stack:
        node = stack.pop()
        if type(node) is not dict or id(node) in visited or len(visited) >= 1000:
            raise ProfileRejected("invalid_profile")
        visited.add(id(node))
        kind = node.get("Node Type")
        if type(kind) is str and kind in scans:
            scans[kind] += 1
        children = node.get("Plans", [])
        if type(children) is not list or len(children) > 1000:
            raise ProfileRejected("invalid_profile")
        stack.extend(children)
    result["scan_node_counts"] = scans
    return result


def inspect_profile(query_runner, *, clinic_day, now, approved=False):
    proof = dict.fromkeys(coverage.PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        elif hashlib.sha256(coverage.QUERY.encode("utf-8")).hexdigest() != coverage.QUERY_SHA256:
            report["status"] = "query_changed"
        else:
            coverage._check_day(clinic_day, now)
            rows = query_runner(PREFIX + coverage.QUERY,
                                params=coverage.parameters(clinic_day), proof=proof)
            if not all(proof.get(key) is True for key in coverage.PROOF_FIELDS):
                raise ProfileRejected("cleanup_or_session_unverified")
            coverage._check_day(clinic_day, now)
            findings = summarize_plan(rows)
            coverage._check_day(clinic_day, now)
            report.update(status="profile_observed", findings=findings)
    except ProfileRejected as error:
        report["status"] = (str(error) if str(error) in {
            "invalid_profile", "cleanup_or_session_unverified",
        } else "profile_failed")
    except coverage.CoverageRejected:
        report["status"] = "current_day_unverified"
    except EghisEvidenceRejectedError:
        report["status"] = "session_or_query_rejected"
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {"57014": "query_timed_out", "42501": "permission_denied"}.get(
            getattr(error, "pgcode", None), "profile_failed")
    report["closure"] = {key: proof.get(key) is True for key in coverage.PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 86400:
        report["closure"]["elapsed_seconds"] = elapsed
    return report
