"""Explicit one-row evidence only; never a runtime reader or source mapping."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from tests import source_order_storage as storage


QUERY = (Path(__file__).parent / "fixtures" / "source_order_grid_numeric_match_v1.sql").read_text(encoding="utf-8")
QUERY_HASH = "7fcceeffe55f539aa7e952a2112bd61d183acf64508fb881b2484d3d917e5db3"
KST = ZoneInfo("Asia/Seoul")
EXACT_TYPES = {"numeric", "smallint", "integer", "bigint"}


@dataclass(frozen=True, repr=False)
class GridSample:
    owner: tuple
    chart_no: str
    code: str
    name: str
    daily: Decimal
    frequency: Decimal
    days: Decimal

    def __repr__(self):
        return "<GridSample: redacted>"


def parse_display_number(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,8})?", value) is None:
        raise storage.StorageRejected("source_scope_unverified")
    return Decimal(value)


def validate_sample(sample):
    if type(sample) is not GridSample or type(sample.owner) is not tuple or not sample.owner:
        raise storage.StorageRejected("source_scope_unverified")
    if type(sample.chart_no) is not str or re.fullmatch(r"[0-9]{1,20}", sample.chart_no) is None:
        raise storage.StorageRejected("source_scope_unverified")
    for text, cap in ((sample.code, 128), (sample.name, 256)):
        if type(text) is not str or not text.strip() or len(text) > cap or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in text):
            raise storage.StorageRejected("source_scope_unverified")
    for value in (sample.daily, sample.frequency, sample.days):
        if (type(value) is not Decimal or not value.is_finite() or value < 0 or value >= Decimal("100000000")
                or value.as_tuple().exponent < -8 or len(value.as_tuple().digits) > 16):
            raise storage.StorageRejected("source_scope_unverified")
    # Equal examples cannot distinguish column mappings from each other.
    if len({sample.daily, sample.frequency, sample.days}) != 3:
        raise storage.StorageRejected("source_scope_unverified")


def check_day(day, now):
    value = now()
    if (type(day) is not date or type(value) is not datetime or value.utcoffset() is None
            or value.astimezone(KST).date() != day):
        raise storage.StorageRejected("source_scope_unverified")


def validate_result(rows):
    if (type(rows) not in (list, tuple) or len(rows) != 1 or type(rows[0]) not in (list, tuple)
            or len(rows[0]) != 10 or any(type(n) is not int or not 0 <= n <= 2 for n in rows[0][:7])):
        raise storage.StorageRejected("invalid_result")
    row = rows[0]
    if tuple(row[:4]) != (1, 1, 0, 0):
        raise storage.StorageRejected("source_scope_unverified")
    if any(n > 1 for n in row[4:7]):
        raise storage.StorageRejected("invalid_result")
    if any(type(kind) is not str or kind not in EXACT_TYPES for kind in row[7:]):
        raise storage.StorageRejected("metadata_unreviewed")
    return {"unique_current_day_match": True,
            "daily_equals_qty": row[4] == 1, "frequency_equals_divide": row[5] == 1,
            "days_equals_days": row[6] == 1,
            "source_types": dict(zip(("qty", "divide", "days"), row[7:]))}


def inspect(query_runner, sample_reader, *, clinic_day, now, approved=False):
    if approved is not True:
        return {"status": "approval_required", "authoritative_snapshot": False,
                "closure": dict.fromkeys(storage.PROOF_FIELDS, False)}
    try:
        check_day(clinic_day, now)
        before = sample_reader()
        validate_sample(before)
        check_day(clinic_day, now)
    except Exception:
        return {"status": "ui_or_day_scope_unverified", "authoritative_snapshot": False,
                "closure": dict.fromkeys(storage.PROOF_FIELDS, False)}

    def after_close(rows):
        check_day(clinic_day, now)
        after = sample_reader()
        validate_sample(after)
        if before != after:
            raise storage.StorageRejected("source_scope_unverified")
        findings = validate_result(rows)
        check_day(clinic_day, now)
        return findings

    params = {"day": clinic_day.strftime("%Y%m%d"), "chart_no": before.chart_no,
              "code": before.code, "name": before.name, "daily": before.daily,
              "frequency": before.frequency, "days": before.days}
    report = storage._inspect(query_runner, QUERY, QUERY_HASH, after_close,
                              approved=True, params=params)
    if report["status"] == "storage_metadata_observed":
        flags = ("daily_equals_qty", "frequency_equals_divide", "days_equals_days")
        report["status"] = ("one_row_numeric_match" if all(report["findings"][k] for k in flags)
                            else "numeric_mapping_not_matched")
    return report
