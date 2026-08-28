from __future__ import annotations

from datetime import date
from itertools import groupby
import re


_ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class DateFormatValidationError(ValueError):
    """Raised when a compact-date input contains an invalid date token."""


def format_dates_korean_compact(value: str) -> str:
    """Format comma-separated ISO dates using compact Korean year/month groups."""

    if not value.strip():
        return ""

    parsed_dates: set[date] = set()
    for raw_token in value.split(","):
        token = raw_token.strip()
        if not _ISO_DATE_PATTERN.fullmatch(token):
            raise DateFormatValidationError(
                "Invalid date input. Use YYYY-MM-DD separated by commas."
            )
        try:
            parsed_dates.add(date.fromisoformat(token))
        except ValueError as error:
            raise DateFormatValidationError(
                "Invalid date input. Use valid YYYY-MM-DD dates."
            ) from error

    output_parts: list[str] = []
    sorted_dates = sorted(parsed_dates)
    for year, year_group in groupby(sorted_dates, key=lambda item: item.year):
        year_dates = list(year_group)
        first_month = True
        for month, month_group in groupby(year_dates, key=lambda item: item.month):
            days = ",".join(str(item.day) for item in month_group)
            year_prefix = f"{year}년" if first_month else ""
            output_parts.append(f"{year_prefix}{month}월{days}일")
            first_month = False

    return " ".join(output_parts)
