"""Review-only metadata proposal; no CLI, DSN, driver or runtime importer.

The caller must supply the shared bounded reader. Tests supply its mocked-driver
version. A future one-shot live invocation needs separate operator approval.
"""

import hashlib
from pathlib import Path

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


QUERY = (Path(__file__).parent / "fixtures" / "source_structure_v1.sql").read_text(
    encoding="utf-8",
)
QUERY_SHA256 = "b4541a09068dc41c76f3d32a871d8f2fae4efdeae219c4135c8ad267a5adf1c2"
SCOPES = ("receptions", "orders")
METRICS = (
    "parent_links", "child_links", "outgoing_foreign_keys", "incoming_foreign_keys",
    "dependent_views", "dependent_materialized_views",
)
KINDS = frozenset({"r", "p", "v", "m", "f"})
REPORT_CAP = 16
RELATIONSHIP_CAP = 64


class StructureRejected(ValueError):
    """Fixed review reason; never source text or provider diagnostics."""


def parameters():
    return {"schema": "public", "reception_table": "h1opdin",
            "order_table": "h2opd_doct_ord"}


def validate_rows(rows):
    if type(rows) not in (list, tuple) or not rows or len(rows) > REPORT_CAP:
        raise StructureRejected("report_overflow_or_incomplete")
    summary, relations, links = {}, {}, {}
    seen = set()
    for row in rows:
        if (type(row) not in (list, tuple) or len(row) != 4
                or any(type(value) is not str for value in row[:3])
                or type(row[3]) is not int or not 0 <= row[3] <= RELATIONSHIP_CAP + 1
                or tuple(row[:3]) in seen):
            raise StructureRejected("invalid_result")
        seen.add(tuple(row[:3]))
        section, scope, detail, count = row
        if section == "summary" and scope in {"relations", "relationships"} and detail == "":
            summary[scope] = count
        elif section == "relation" and scope in SCOPES:
            if detail not in KINDS or count != 1 or scope in relations:
                raise StructureRejected("relation_scope_unverified")
            relations[scope] = detail
        elif section == "links" and scope in SCOPES and detail in METRICS:
            links[scope, detail] = count
        else:
            raise StructureRejected("invalid_result")
    if (set(summary) != {"relations", "relationships"} or set(relations) != set(SCOPES)
            or set(links) != {(scope, metric) for scope in SCOPES for metric in METRICS}):
        raise StructureRejected("incomplete_result")
    if summary["relationships"] > RELATIONSHIP_CAP:
        raise StructureRejected("relationship_overflow")
    if summary["relations"] != 2 or sum(links.values()) != summary["relationships"]:
        raise StructureRejected("inconsistent_result")
    return {"relationship_count": summary["relationships"], "relations": {
        scope: {"kind": relations[scope], **{metric: links[scope, metric] for metric in METRICS}}
        for scope in SCOPES}}


def inspect_structure(query_runner, *, approved=False):
    proof = {"connection_opened": False, "readonly_verified": False,
             "cursor_closed": False, "connection_closed": False}
    report = {"status": "not_run", "authoritative_snapshot": False, "closure": proof}
    if approved is not True:
        report["status"] = "approval_required"
        return report
    if hashlib.sha256(QUERY.encode("utf-8")).hexdigest() != QUERY_SHA256:
        report["status"] = "query_changed"
        return report
    try:
        rows = query_runner(QUERY, params=parameters(), proof=proof)
        if not all(proof[key] is True for key in (
            "connection_opened", "readonly_verified", "cursor_closed", "connection_closed",
        )):
            raise StructureRejected("cleanup_or_session_unverified")
        report["findings"] = validate_rows(rows)
        report["status"] = "structure_observed"
    except StructureRejected as error:
        report["status"] = str(error)
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
    return report
