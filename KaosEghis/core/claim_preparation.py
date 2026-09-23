from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re


class ClaimPreviewError(ValueError):
    """An incomplete or unsafe claim-screen read, never an empty history."""


@dataclass(frozen=True)
class ClaimHistory:
    month: date
    weeks: tuple[int, ...]
    available_weeks: tuple[int, ...]
    captured_at: datetime
    connection: tuple[int, int]


@dataclass(frozen=True)
class ClaimPlanPart:
    start: date
    end: date
    latest_week: int | None
    next_week: int | None
    status: str
    captured_at: datetime | None = None

    @property
    def month(self) -> date:
        return self.start.replace(day=1)


def parse_claim_month(value: str) -> date:
    text = str(value).strip()
    match = re.fullmatch(
        r"(\d{4})\s*년\s*(\d{1,2})\s*월(?:\s*\d{1,2}\s*일(?:\s*[월화수목금토일]요일)?)?",
        text,
    ) or re.fullmatch(r"(\d{4})[./-](\d{1,2})(?:[./-]\d{1,2})?", text)
    if match:
        try:
            return date(int(match[1]), int(match[2]), 1)
        except ValueError:
            pass
    raise ClaimPreviewError("Selected claim month could not be read.")


def parse_claim_week(value: str) -> int:
    match = re.fullmatch(r"([1-6])\s*주", str(value).strip())
    if not match:
        raise ClaimPreviewError("A claim week could not be read. No week was inferred.")
    return int(match[1])


def build_claim_plan(
    claim_day: date, histories: dict[date, ClaimHistory]
) -> tuple[ClaimPlanPart, ...]:
    """Split Monday through claim day by month; weeks come only from history."""
    if claim_day.weekday() > 4:
        raise ClaimPreviewError("Choose a weekday claim date.")
    start = claim_day - timedelta(days=claim_day.weekday())
    parts = []
    while start <= claim_day:
        end = start
        while end < claim_day and (end + timedelta(days=1)).month == start.month:
            end += timedelta(days=1)
        month = start.replace(day=1)
        history = histories.get(month)
        latest = next_week = None
        status = "Month not read"
        if history is not None:
            if history.month != month or any(w not in range(1, 7) for w in history.weeks):
                raise ClaimPreviewError("Invalid month history. Read the month again.")
            latest = max(history.weeks, default=0)
            candidate = latest + 1
            if candidate > 6 or candidate not in history.available_weeks:
                status = "Next week selector unavailable"
            else:
                next_week = candidate
                status = "Review required"
        parts.append(ClaimPlanPart(
            start, end, latest, next_week, status,
            history.captured_at if history else None,
        ))
        if end == claim_day:
            break
        start = end + timedelta(days=1)
    return tuple(parts)
