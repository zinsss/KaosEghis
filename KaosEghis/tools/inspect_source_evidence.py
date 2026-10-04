"""Explicit one-shot aggregate evidence only. No runtime reader or source rows."""
from datetime import date
from KaosEghis.core.eghis_db import run_verified_evidence_query, EghisEvidenceRejectedError
from KaosEghis.core.emr_read_queue import EmrReadSafetyError

ENCOUNTER_CAP = 10000
ORDER_CAP = 100000
REPORT_CAP = 256
TOKENS = {"NULL", "BLANK", "UNREVIEWED"}
PROC = ("10", "20", "25", "30", "40", "50")
FLAGS = ("Y", "N")
ORDER_TYPES = ("01", "02", "03", "04", "05", "06", "07", "08", "09")
DEPARTMENTS = ("LAB", "DRUG", "INJ", "XRAY", "BMD", "ECG", "PT")
SEX = ("M", "F", "O", "1", "2")
SCHEMA_FIELDS = {
    "h1opdin": {"recept_no", "ptnt_no", "clinic_ymd", "proc_gb", "hold_yn", "hold_opd"},
    "h2opd_doct_ord": {"recept_no", "ord_ymd", "ord_no", "ord_seq_no",
                       "ord_type", "proc_dept_cd", "dc_yn", "act_yn"},
    "hz_mst_ptnt": {"ptnt_no", "sex", "ageday"},
}
SUMMARY_FIELDS = {
    "encounters", "orders", "dated_orders", "no_order_encounters",
    "invalid_encounter_keys", "duplicate_encounter_keys",
    "invalid_order_keys", "duplicate_order_keys", "orders_other_date",
    "dated_orders_without_day_encounter", "sex_rows", "missing_patient_links",
}

SCHEMA_SQL = """
SELECT c.relname, a.attname, t.typname, a.attnotnull, c.relkind,
       has_table_privilege(c.oid, 'SELECT')
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped
  AND ((c.relname='h1opdin' AND a.attname=ANY(%(encounter_fields)s))
    OR (c.relname='h2opd_doct_ord' AND a.attname=ANY(%(order_fields)s))
    OR (c.relname='hz_mst_ptnt' AND a.attname=ANY(%(patient_fields)s)))
ORDER BY c.relname, a.attnum
LIMIT 33
"""

# Each CASE masks unreviewed values on the server, before they cross the boundary.
DAY_SQL = """
WITH h AS (
    SELECT recept_no, ptnt_no, proc_gb, hold_yn, hold_opd
    FROM public.h1opdin WHERE clinic_ymd=%(day)s
    LIMIT %(encounter_limit)s
), o AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no,
           ord_type, proc_dept_cd, dc_yn, act_yn
    FROM public.h2opd_doct_ord x
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no=x.recept_no)
    LIMIT %(order_limit)s
), dated AS (
    SELECT recept_no FROM public.h2opd_doct_ord WHERE ord_ymd=%(day)s
    LIMIT %(order_limit)s
), sexes AS (
    SELECT p.ptnt_no IS NOT NULL AS matched,
           CASE WHEN p.ptnt_no IS NULL THEN 'MISSING_LINK'
                WHEN p.sex IS NULL THEN 'NULL'
                WHEN p.sex::text='' THEN 'BLANK'
                WHEN p.sex::text=ANY(%(sex)s) THEN p.sex::text
                ELSE 'UNREVIEWED' END AS sex
    FROM h LEFT JOIN public.hz_mst_ptnt p ON p.ptnt_no=h.ptnt_no
    LIMIT %(encounter_limit)s
), reception_groups AS (
    SELECT CASE WHEN proc_gb IS NULL THEN 'NULL'
                WHEN proc_gb::text='' THEN 'BLANK'
                WHEN proc_gb::text=ANY(%(proc)s) THEN proc_gb::text
                ELSE 'UNREVIEWED' END AS code,
           CASE WHEN hold_yn IS NULL THEN 'NULL'
                WHEN hold_yn::text='' THEN 'BLANK'
                WHEN hold_yn::text=ANY(%(flags)s) THEN hold_yn::text
                ELSE 'UNREVIEWED' END AS hold,
           CASE WHEN hold_opd IS NULL THEN 'NULL'
                WHEN hold_opd::text='' THEN 'BLANK'
                WHEN hold_opd::text=ANY(%(flags)s) THEN hold_opd::text
                ELSE 'UNREVIEWED' END AS opd
    FROM h
), order_groups AS (
    SELECT CASE WHEN ord_type IS NULL THEN 'NULL'
                WHEN ord_type::text='' THEN 'BLANK'
                WHEN ord_type::text=ANY(%(types)s) THEN ord_type::text
                ELSE 'UNREVIEWED' END AS kind,
           CASE WHEN proc_dept_cd IS NULL THEN 'NULL'
                WHEN proc_dept_cd::text='' THEN 'BLANK'
                WHEN proc_dept_cd::text=ANY(%(departments)s) THEN proc_dept_cd::text
                ELSE 'UNREVIEWED' END AS department,
           CASE WHEN dc_yn IS NULL THEN 'NULL'
                WHEN dc_yn::text='' THEN 'BLANK'
                WHEN dc_yn::text=ANY(%(flags)s) THEN dc_yn::text
                ELSE 'UNREVIEWED' END AS dc,
           CASE WHEN act_yn IS NULL THEN 'NULL'
                WHEN act_yn::text='' THEN 'BLANK'
                WHEN act_yn::text=ANY(%(flags)s) THEN act_yn::text
                ELSE 'UNREVIEWED' END AS act
    FROM o
), summary AS (
    SELECT 'encounters' AS metric, count(*) AS n FROM h
    UNION ALL SELECT 'orders', count(*) FROM o
    UNION ALL SELECT 'dated_orders', count(*) FROM dated
    UNION ALL SELECT 'no_order_encounters', count(*) FROM h
        WHERE NOT EXISTS (SELECT 1 FROM o WHERE o.recept_no=h.recept_no)
    UNION ALL SELECT 'invalid_encounter_keys', count(*) FROM h
        WHERE recept_no IS NULL OR btrim(recept_no::text)=''
    UNION ALL SELECT 'duplicate_encounter_keys', count(*) FROM
        (SELECT recept_no FROM h GROUP BY recept_no HAVING count(*)>1) d
    UNION ALL SELECT 'invalid_order_keys', count(*) FROM o
        WHERE recept_no IS NULL OR btrim(recept_no::text)=''
           OR ord_ymd IS NULL OR btrim(ord_ymd::text)=''
           OR ord_no IS NULL OR btrim(ord_no::text)=''
           OR ord_seq_no IS NULL OR btrim(ord_seq_no::text)=''
    UNION ALL SELECT 'duplicate_order_keys', count(*) FROM
        (SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM o
         GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*)>1) d
    UNION ALL SELECT 'orders_other_date', count(*) FROM o
        WHERE ord_ymd IS NULL OR ord_ymd::text<>%(day)s
    UNION ALL SELECT 'dated_orders_without_day_encounter', count(*) FROM dated
        WHERE NOT EXISTS (SELECT 1 FROM h WHERE h.recept_no=dated.recept_no)
    UNION ALL SELECT 'sex_rows', count(*) FROM sexes
    UNION ALL SELECT 'missing_patient_links', count(*) FROM sexes WHERE NOT matched
)
SELECT 'summary' AS section, metric AS a, ''::text AS b, ''::text AS c,
       ''::text AS d, n FROM summary
UNION ALL SELECT 'reception', code, hold, opd, '', count(*)
    FROM reception_groups GROUP BY code, hold, opd
UNION ALL SELECT 'orders', kind, department, dc, act, count(*)
    FROM order_groups GROUP BY kind, department, dc, act
UNION ALL SELECT 'sex', sex, '', '', '', count(*) FROM sexes GROUP BY sex
ORDER BY 1, 2, 3, 4, 5
LIMIT 257
"""


class EvidenceRejected(ValueError):
    """Fixed reason only; provider text, source values and SQL are not retained."""


def _query_spec(operation, clinic_day):
    if operation == "schema":
        if clinic_day is not None:
            raise EvidenceRejected("invalid_scope")
        return SCHEMA_SQL, {
            "encounter_fields": sorted(SCHEMA_FIELDS["h1opdin"]),
            "order_fields": sorted(SCHEMA_FIELDS["h2opd_doct_ord"]),
            "patient_fields": sorted(SCHEMA_FIELDS["hz_mst_ptnt"]),
        }
    if operation != "day" or type(clinic_day) is not date:
        raise EvidenceRejected("invalid_scope")
    return DAY_SQL, {
        "day": clinic_day.strftime("%Y%m%d"),
        "encounter_limit": ENCOUNTER_CAP + 1, "order_limit": ORDER_CAP + 1,
        "proc": list(PROC), "flags": list(FLAGS), "types": list(ORDER_TYPES),
        "departments": list(DEPARTMENTS), "sex": list(SEX),
    }


def _schema_findings(rows):
    if not rows or len(rows) > 32:
        raise EvidenceRejected("schema_incomplete")
    seen = set()
    result = []
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != 6:
            raise EvidenceRejected("invalid_result")
        table, field, kind, required, relation, permitted = row
        if (type(table) is not str or table not in SCHEMA_FIELDS
                or type(field) is not str or field not in SCHEMA_FIELDS[table]
                or (table, field) in seen or kind not in {
                    "varchar", "bpchar", "text", "int2", "int4", "int8", "date",
                    "timestamp", "timestamptz", "numeric"}
                or type(required) is not bool or relation != "r" or permitted is not True):
            raise EvidenceRejected("schema_unverified")
        seen.add((table, field))
        result.append({"table": table, "field": field, "type": kind, "not_null": required})
    required = {(table, field) for table, names in SCHEMA_FIELDS.items()
                for field in names if field != "ageday"}
    if not required <= seen:
        raise EvidenceRejected("schema_incomplete")
    return result


def _day_findings(rows, expectation):
    if not rows or len(rows) > REPORT_CAP:
        raise EvidenceRejected("result_overflow_or_incomplete")
    summary, groups, seen = {}, {"reception": [], "orders": [], "sex": []}, set()
    for row in rows:
        if type(row) not in (tuple, list) or len(row) != 6:
            raise EvidenceRejected("invalid_result")
        section, a, b, c, d, count = row
        if (any(type(value) is not str for value in row[:5])
                or type(count) is not int or not 0 <= count <= ORDER_CAP + 1
                or tuple(row[:5]) in seen):
            raise EvidenceRejected("invalid_result")
        seen.add(tuple(row[:5]))
        if section == "summary":
            if a not in SUMMARY_FIELDS or (b, c, d) != ("", "", ""):
                raise EvidenceRejected("invalid_result")
            summary[a] = count
            continue
        allowed = {
            "reception": (set(PROC) | TOKENS, set(FLAGS) | TOKENS, set(FLAGS) | TOKENS, {""}),
            "orders": (set(ORDER_TYPES) | TOKENS, set(DEPARTMENTS) | TOKENS,
                       set(FLAGS) | TOKENS, set(FLAGS) | TOKENS),
            "sex": (set(SEX) | TOKENS | {"MISSING_LINK"}, {""}, {""}, {""}),
        }
        if section not in allowed or not count or any(
                value not in choices for value, choices in zip((a, b, c, d), allowed[section])):
            raise EvidenceRejected("invalid_result")
        groups[section].append({"values": [a, b, c, d], "count": count})
    if set(summary) != SUMMARY_FIELDS:
        raise EvidenceRejected("incomplete_result")
    if (summary["encounters"] > ENCOUNTER_CAP or summary["sex_rows"] > ENCOUNTER_CAP
            or summary["orders"] > ORDER_CAP or summary["dated_orders"] > ORDER_CAP):
        raise EvidenceRejected("source_overflow")
    if (sum(r["count"] for r in groups["reception"]) != summary["encounters"]
            or sum(r["count"] for r in groups["orders"]) != summary["orders"]
            or sum(r["count"] for r in groups["sex"]) != summary["sex_rows"]
            or summary["sex_rows"] != summary["encounters"]
            or summary["no_order_encounters"] > summary["encounters"]
            or summary["missing_patient_links"] > summary["encounters"]
            or summary["orders_other_date"] > summary["orders"]
            or summary["dated_orders_without_day_encounter"] > summary["dated_orders"]
            or summary["encounters"] - summary["no_order_encounters"] > summary["orders"]
            or summary["orders"] - summary["orders_other_date"] != (
                summary["dated_orders"] - summary["dated_orders_without_day_encounter"])
            or sum(r["count"] for r in groups["sex"] if r["values"][0] == "MISSING_LINK")
                != summary["missing_patient_links"]
            or any(summary[name] for name in (
                "invalid_encounter_keys", "duplicate_encounter_keys",
                "invalid_order_keys", "duplicate_order_keys"))):
        raise EvidenceRejected("inconsistent_result")
    if ((expectation == "empty" and any(summary[key] for key in
                                      ("encounters", "orders", "dated_orders")))
            or (expectation == "populated" and not summary["encounters"])):
        raise EvidenceRejected("operator_expectation_mismatch")
    return {"counts": summary, "groups": groups}


def inspect_evidence(connection_string, *, operation, clinic_day=None,
                     expectation=None, approved=False):
    """Only fixed reviewed operations; results are never authoritative snapshots."""
    proof = {"connection_opened": False, "readonly_verified": False,
             "cursor_closed": False, "connection_closed": False}
    report = {"status": "not_run", "authoritative_snapshot": False, "closure": proof}
    try:
        if approved is not True:
            raise EvidenceRejected("approval_required")
        if ((operation == "day" and expectation not in ("empty", "populated"))
                or (operation == "schema" and expectation is not None)):
            raise EvidenceRejected("invalid_scope")
        query, params = _query_spec(operation, clinic_day)
        rows = run_verified_evidence_query(connection_string, query, params=params, proof=proof)
        if not proof["cursor_closed"] or not proof["connection_closed"]:
            raise EvidenceRejected("cleanup_unverified")
        # No source result validation/aggregation occurs inside the connection slot.
        findings = (_schema_findings(rows) if operation == "schema"
                    else _day_findings(rows, expectation))
        report["findings"] = findings
        report["status"] = ("schema_observed" if operation == "schema"
                            else f"observed_{expectation}_scope")
    except (EvidenceRejected, EghisEvidenceRejectedError) as error:
        report["status"] = str(error)
    except EmrReadSafetyError:
        report["status"] = "reader_safety_stop"
    except Exception as error:
        report["status"] = {
            "57014": "query_timed_out", "42501": "permission_denied",
            "42703": "schema_mismatch", "42P01": "schema_mismatch",
        }.get(getattr(error, "pgcode", None), "read_failed")
    return report
