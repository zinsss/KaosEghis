"""One-shot metadata evidence only; no default connection or runtime importer."""

import hashlib
from pathlib import Path

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


ROOT = Path(__file__).parent / "fixtures"
QUERIES = {name: (ROOT / filename).read_text(encoding="utf-8") for name, filename in (
    ("views", "source_view_dependencies_v1.sql"),
    ("privileges", "source_privileges_v1.sql"),
)}
HASHES = {
    "views": "606b07c562cdd5d7349424cae728fccabd5cfe402e721f411374835b04626582",
    "privileges": "7b4ad2bcaedfb489dc8a7401f748ddccda25eca995d494f70183aba205772795",
}
VIEW_FIELDS = {
    "relations": 2, "ordinary_relations": 2, "scope_view_links": 64,
    "reception_views": 64, "order_views": 64, "unique_views": 64,
    "shared_views": 64, "ordinary_views": 64, "materialized_views": 64,
    "relation_links": 128, "reception_relation_links": 64,
    "order_relation_links": 64, "other_ordinary_relation_links": 128,
    "other_view_relation_links": 128, "other_materialized_relation_links": 128,
    "other_relation_links": 128, "routine_links": 128,
}
PRIVILEGE_FIELDS = {
    "relations": 2, "ordinary_relations": 2, "own_roles": 1,
    "superuser_roles": 1, "role_admin_roles": 1, "database_admin_roles": 1,
    "inherit_roles": 1, "reachable_roles": 64, "reachable_privileged_roles": 64,
    "selectable_relations": 2, "nonselect_relations": 2,
    "nonselect_column_relations": 2, "owner_role_relations": 2,
    "schemas": 1, "usable_schemas": 1, "writable_schemas": 1,
    "definer_routines": 128, "executable_definer_routines": 128,
}
FIELDS = {"views": VIEW_FIELDS, "privileges": PRIVILEGE_FIELDS}
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")


class MetadataRejected(ValueError):
    """Fixed reason only, never source/provider text."""


def parameters(operation):
    params = {"schema": "public", "reception_table": "h1opdin",
              "order_table": "h2opd_doct_ord"}
    if operation == "privileges":
        params.update(table_nonselect="INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER",
                      column_nonselect="INSERT,UPDATE,REFERENCES", schema_nonselect="CREATE")
    return params


def validate_rows(operation, rows):
    bounds = FIELDS[operation]
    if type(rows) not in (list, tuple) or len(rows) != len(bounds):
        raise MetadataRejected("report_overflow_or_incomplete")
    result = {}
    for row in rows:
        if (type(row) not in (tuple, list) or len(row) != 2
                or type(row[0]) is not str or row[0] not in bounds or row[0] in result
                or type(row[1]) is not int or row[1] < 0):
            raise MetadataRejected("invalid_result")
        if row[1] > bounds[row[0]]:
            raise MetadataRejected("metadata_overflow")
        result[row[0]] = row[1]
    if result["relations"] != 2 or result["ordinary_relations"] != 2:
        raise MetadataRejected("source_scope_unverified")
    if operation == "views":
        valid = (
            result["scope_view_links"] == result["reception_views"] + result["order_views"]
            == result["unique_views"] + result["shared_views"]
            and result["shared_views"] <= min(result["reception_views"], result["order_views"])
            and result["unique_views"] == result["ordinary_views"] + result["materialized_views"]
            and result["relation_links"] == sum(result[key] for key in (
                "reception_relation_links", "order_relation_links", "other_ordinary_relation_links",
                "other_view_relation_links", "other_materialized_relation_links", "other_relation_links",
            ))
            and result["reception_relation_links"] == result["reception_views"]
            and result["order_relation_links"] == result["order_views"]
            and (result["unique_views"] > 0 or result["relation_links"] == result["routine_links"] == 0)
        )
    else:
        valid = (result["own_roles"] == result["schemas"] == 1
                 and result["reachable_roles"] >= 1
                 and result["reachable_privileged_roles"] <= result["reachable_roles"]
                 and result["executable_definer_routines"] <= result["definer_routines"])
    if not valid:
        raise MetadataRejected("inconsistent_result")
    return result


def inspect_metadata(operation, query_runner, *, approved=False):
    proof = dict.fromkeys(PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False, "closure": proof}
    if approved is not True:
        report["status"] = "approval_required"
        return report
    if type(operation) is not str or operation not in QUERIES:
        report["status"] = "invalid_operation"
        return report
    query = QUERIES[operation]
    if hashlib.sha256(query.encode("utf-8")).hexdigest() != HASHES[operation]:
        report["status"] = "query_changed"
        return report
    try:
        rows = query_runner(query, params=parameters(operation), proof=proof)
        if not all(proof[key] is True for key in PROOF_FIELDS):
            raise MetadataRejected("cleanup_or_session_unverified")
        report["findings"] = validate_rows(operation, rows)
        report["status"] = "metadata_observed"
    except MetadataRejected as error:
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
