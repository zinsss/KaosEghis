"""Test-only display-source evidence; catalog metadata is not clinical meaning."""

from pathlib import Path
import re

from tests import source_order_storage as storage
from tests import source_single_catalog as singleton
from tests.source_named_order import CONFIRMED_CODE, ORDER_NAME


METADATA_QUERY = (Path(__file__).parent / "fixtures" / "source_order_display_columns_v1.sql").read_text(encoding="utf-8")
METADATA_HASH = "ab37138970de6c60406f5a4d34acd7400dc572fe0fe8b144eaca1c263a4a1f59"
IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"
CANDIDATE_PATTERN = r"(ord|user|medfee|code|name|_cd$|_nm$)"
EXCLUDED = ("hold_opd", "ptnt_nm", "patient_name")
TYPES = storage.TYPES + ("bool", "float4", "float8", "timestamptz")
MATCH_QUERY = (Path(__file__).parent / "fixtures" / "source_order_display_match_v1.sql").read_text(encoding="utf-8")
MATCH_HASH = "2ad618c051b8035e80ed4fd014d691bb4ee4243732af4c330ff01f27da864f31"


def metadata_parameters():
    return {"schema": "public", "table": "h2opd_doct_ord", "identifier_pattern": IDENTIFIER_PATTERN,
            "candidate_pattern": CANDIDATE_PATTERN, "types": list(TYPES), "excluded": list(EXCLUDED)}


def validate_metadata(rows):
    if type(rows) not in (list, tuple) or not 2 <= len(rows) <= 130:
        raise storage.StorageRejected("metadata_overflow")
    summary, columns = {}, {}
    for row in rows:
        if (type(row) not in (list, tuple) or len(row) != 6
                or any(type(s) is not str for s in row[:3])
                or type(row[3]) is not bool or type(row[4]) is not bool
                or type(row[5]) is not int or row[5] < 0):
            raise storage.StorageRejected("invalid_result")
        section, name, kind, nullable, selectable, n = row
        if section == "summary":
            if name not in {"relations", "columns"} or name in summary or kind != "" or nullable or selectable:
                raise storage.StorageRejected("invalid_result")
            summary[name] = n
        elif section == "column":
            if (not re.fullmatch(IDENTIFIER_PATTERN, name) or not re.search(CANDIDATE_PATTERN, name)
                    or name in EXCLUDED or kind not in TYPES + ("OTHER_TYPE",)):
                raise storage.StorageRejected("metadata_unreviewed")
            if name in columns or n != 1:
                raise storage.StorageRejected("invalid_result")
            columns[name] = {"type": kind, "nullable": nullable, "selectable": selectable}
        else:
            raise storage.StorageRejected("invalid_result")
    if set(summary) != {"relations", "columns"}:
        raise storage.StorageRejected("invalid_result")
    if summary["columns"] > 128:
        raise storage.StorageRejected("metadata_overflow")
    if summary["relations"] != 1 or summary["columns"] != len(columns):
        raise storage.StorageRejected("source_scope_unverified")
    return {"candidate_columns": dict(sorted(columns.items())), "count": len(columns)}


def inspect_metadata(query_runner, *, approved=False):
    return storage._inspect(query_runner, METADATA_QUERY, METADATA_HASH, validate_metadata,
                            approved=approved, params=metadata_parameters())


def validate_match(rows):
    if (type(rows) not in (list, tuple) or len(rows) != 1
            or type(rows[0]) not in (tuple, list) or len(rows[0]) != 6
            or any(type(n) is not int or not 0 <= n <= 2 for n in rows[0])):
        raise storage.StorageRejected("invalid_result")
    encounters, orders, invalid, off_day, code_matches, name_matches = rows[0]
    if (encounters, orders, invalid, off_day) != (1, 1, 0, 0):
        raise storage.StorageRejected("source_scope_unverified")
    if code_matches > 1 or name_matches > 1:
        raise storage.StorageRejected("invalid_result")
    return {"single_visit_order_confirmed": True,
            "expected_user_code_matches": code_matches, "expected_user_name_matches": name_matches}


def inspect_match(query_runner, *, clinic_day, chart_no, now, approved=False):
    try:
        if approved is not True:
            return {"status": "approval_required", "authoritative_snapshot": False,
                    "closure": dict.fromkeys(storage.PROOF_FIELDS, False)}
        singleton.check_scope(clinic_day, chart_no, now)
    except singleton.CatalogRejected as error:
        return {"status": str(error) if str(error) in singleton.REASONS else "invalid_scope",
                "authoritative_snapshot": False, "closure": dict.fromkeys(storage.PROOF_FIELDS, False)}
    except Exception:
        return {"status": "invalid_scope", "authoritative_snapshot": False,
                "closure": dict.fromkeys(storage.PROOF_FIELDS, False)}

    def after_close(rows):
        try:
            singleton.check_scope(clinic_day, chart_no, now)
            findings = validate_match(rows)
            singleton.check_scope(clinic_day, chart_no, now)
            return findings
        except singleton.CatalogRejected:
            raise storage.StorageRejected("source_scope_unverified") from None

    params = {"day": clinic_day.strftime("%Y%m%d"), "chart_no": chart_no,
              "read_day": singleton.APPROVED_READ_DAY.strftime("%Y%m%d"),
              "expected_code": CONFIRMED_CODE, "expected_name": ORDER_NAME}
    report = storage._inspect(query_runner, MATCH_QUERY, MATCH_HASH, after_close,
                              approved=True, params=params)
    if report["status"] == "storage_metadata_observed":
        facts = report["findings"]
        report["status"] = ("display_pair_matched" if facts["expected_user_code_matches"]
                            == facts["expected_user_name_matches"] == 1 else "display_pair_not_matched")
    return report
