"""Controlled test-only storage evidence; no runtime importer or default reader."""

import hashlib
import math
from pathlib import Path
import re

from KaosEghis.core.eghis_db import EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError


ROOT = Path(__file__).parent / "fixtures"
CATALOG_QUERY = (ROOT / "source_order_storage_catalog_v1.sql").read_text(encoding="utf-8")
CATALOG_HASH = "51228a1824143b04761280d2ea6eb813b6c1c230ce38c19166af937389da0933"
INVENTORY_QUERY = (ROOT / "source_order_storage_inventory_v1.sql").read_text(encoding="utf-8")
INVENTORY_HASH = "6d78f3c379c8941bfd86d190c38608977d3df5199bc18505f937509883f14088"
ACCESS_QUERY = (ROOT / "source_order_storage_access_v1.sql").read_text(encoding="utf-8")
ACCESS_HASH = "2cf32cd7d263f149398a8c8211886bf6e5a2c280ea8dbfffc7fabdd4b884a8d3"
ACCESS_FIELDS = {"candidate_relations", "known_relations", "known_table_select", "known_any_column_select",
                 "other_relations", "other_table_select", "other_any_column_select", "other_reception_select",
                 "other_four_part_keys", "other_four_part_select", "other_code_select"}
NAME_PATTERN = r"^h[1-9][a-z_]{1,60}$"
TYPES = ("varchar", "bpchar", "text", "int2", "int4", "int8", "numeric", "date", "timestamp")
COLUMNS = ("recept_no", "ord_ymd", "ord_no", "ord_seq_no", "ord_cd")
PROOF_FIELDS = ("connection_opened", "readonly_verified", "cursor_closed", "connection_closed")
REASONS = frozenset({"invalid_result", "metadata_overflow", "metadata_unreviewed",
                     "source_scope_unverified", "cleanup_or_session_unverified"})


class StorageRejected(ValueError):
    """Fixed rejection reason, no provider or source text."""


def catalog_parameters():
    return {"schema": "public", "known_order": "h2opd_doct_ord", "candidate_limit": 65,
            "types": list(TYPES), "columns": list(COLUMNS), "name_pattern": NAME_PATTERN}


def validate_catalog(rows):
    if type(rows) not in (list, tuple) or not 4 <= len(rows) <= 67:
        raise StorageRejected("metadata_overflow")
    summaries = {}
    candidates = {}
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != 10:
            raise StorageRejected("invalid_result")
        section, name, kind, *tail = row
        types, selectable, count = tail[:5], tail[5], tail[6]
        if (type(section) is not str or type(name) is not str or type(kind) is not str
                or type(selectable) is not bool or type(count) is not int or count < 0):
            raise StorageRejected("invalid_result")
        if section == "summary":
            if (name not in {"candidate_relations", "unreviewed_names", "known_order_relations"}
                    or name in summaries or kind != "" or types != [""] * 5 or selectable):
                raise StorageRejected("invalid_result")
            summaries[name] = count
        elif section == "candidate":
            if name == "UNREVIEWED" or "UNREVIEWED" in types:
                raise StorageRejected("metadata_unreviewed")
            if (not re.fullmatch(NAME_PATTERN, name) or name in candidates or kind != "r"
                    or count != 1 or any(type(value) is not str or value not in (*TYPES, "MISSING") for value in types)
                    or types[0] == "MISSING" or types[2] == types[4] == "MISSING"):
                raise StorageRejected("invalid_result")
            candidates[name] = {**dict(zip(COLUMNS, types)), "selectable": selectable}
        else:
            raise StorageRejected("invalid_result")
    if set(summaries) != {"candidate_relations", "unreviewed_names", "known_order_relations"}:
        raise StorageRejected("invalid_result")
    if summaries["candidate_relations"] > 64:
        raise StorageRejected("metadata_overflow")
    if summaries["unreviewed_names"]:
        raise StorageRejected("metadata_unreviewed")
    if (summaries["candidate_relations"] != len(candidates)
            or summaries["known_order_relations"] != 1 or "h2opd_doct_ord" not in candidates):
        raise StorageRejected("source_scope_unverified")
    return {"candidate_count": len(candidates), "candidates": dict(sorted(candidates.items()))}


def inspect_catalog(query_runner, *, approved=False):
    return _inspect(query_runner, CATALOG_QUERY, CATALOG_HASH, validate_catalog, approved=approved)


def validate_inventory(rows):
    if type(rows) not in (list, tuple) or not 7 <= len(rows) <= 70:
        raise StorageRejected("metadata_overflow")
    counts, reviewed = {}, []
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != 10:
            raise StorageRejected("invalid_result")
        if row[0] == "summary" and row[1] in ("total_candidates", "omitted_names", "omitted_types"):
            if (row[1] in counts or tuple(row[2:8]) != ("",) * 6 or row[8] is not False
                    or type(row[9]) is not int or row[9] < 0):
                raise StorageRejected("invalid_result")
            counts[row[1]] = row[9]
        else:
            reviewed.append(row)
    if set(counts) != {"total_candidates", "omitted_names", "omitted_types"}:
        raise StorageRejected("invalid_result")
    if counts["total_candidates"] > 64:
        raise StorageRejected("metadata_overflow")
    findings = validate_catalog(reviewed)
    if counts["total_candidates"] != findings["candidate_count"] + counts["omitted_names"] + counts["omitted_types"]:
        raise StorageRejected("invalid_result")
    return {**findings, **counts, "inventory_complete": counts["omitted_names"] == counts["omitted_types"] == 0}


def inspect_inventory(query_runner, *, approved=False):
    return _inspect(query_runner, INVENTORY_QUERY, INVENTORY_HASH, validate_inventory, approved=approved)


def validate_access(rows):
    if type(rows) not in (list, tuple) or len(rows) != len(ACCESS_FIELDS):
        raise StorageRejected("invalid_result")
    counts = {}
    for row in rows:
        if (type(row) not in (list, tuple) or len(row) != 2 or type(row[0]) is not str
                or row[0] not in ACCESS_FIELDS or row[0] in counts
                or type(row[1]) is not int or row[1] < 0):
            raise StorageRejected("invalid_result")
        if row[1] > 64:
            raise StorageRejected("metadata_overflow")
        counts[row[0]] = row[1]
    c = counts
    if (c["known_relations"] != 1 or c["candidate_relations"] != c["other_relations"] + 1
            or not c["known_table_select"] <= c["known_any_column_select"] <= 1
            or not c["other_table_select"] <= c["other_reception_select"] <= c["other_any_column_select"] <= c["other_relations"]
            or not c["other_four_part_select"] <= c["other_four_part_keys"] <= c["other_relations"]
            or c["other_four_part_select"] > c["other_reception_select"]
            or c["other_code_select"] > c["other_any_column_select"]):
        raise StorageRejected("source_scope_unverified")
    return dict(sorted(counts.items()))


def inspect_access(query_runner, *, approved=False):
    params = {key: value for key, value in catalog_parameters().items()
              if key in {"schema", "columns", "candidate_limit", "known_order"}}
    return _inspect(query_runner, ACCESS_QUERY, ACCESS_HASH, validate_access, approved=approved, params=params)


def _inspect(query_runner, query, expected_hash, validator, *, approved, params=None):
    proof = dict.fromkeys(PROOF_FIELDS, False)
    report = {"status": "not_run", "authoritative_snapshot": False}
    try:
        if approved is not True:
            report["status"] = "approval_required"
        elif hashlib.sha256(query.encode("utf-8")).hexdigest() != expected_hash:
            report["status"] = "query_changed"
        else:
            rows = query_runner(query, params=catalog_parameters() if params is None else params, proof=proof)
            if not all(proof.get(key) is True for key in PROOF_FIELDS):
                raise StorageRejected("cleanup_or_session_unverified")
            findings = validator(rows)
            report.update(status="storage_metadata_observed", findings=findings)
    except StorageRejected as error:
        report["status"] = str(error) if str(error) in REASONS else "read_failed"
    except EghisEvidenceRejectedError as error:
        report["status"] = str(error) if str(error) in {
            "query_rejected", "session_unverified", "cursor_close_unverified",
        } else "read_failed"
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {"57014": "query_timed_out", "42501": "permission_denied",
                            "42703": "schema_mismatch", "42P01": "schema_mismatch"}.get(
                                getattr(error, "pgcode", None), "read_failed")
    report["closure"] = {key: proof.get(key) is True for key in PROOF_FIELDS}
    elapsed = proof.get("elapsed_seconds")
    if type(elapsed) in (int, float) and 0 <= elapsed <= 86400 and math.isfinite(elapsed):
        report["closure"]["elapsed_seconds"] = elapsed
    return report
