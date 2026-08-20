from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


INFLUENZA_ELDERLY_GROUPS = {
    "elderly_75_plus",
    "elderly_70_74",
    "elderly_65_69",
}
INFLUENZA_CHILD_GROUPS = {"child_two_dose", "child_one_dose"}
INFLUENZA_SCHEDULE_KEYS = {
    "elderly_75_plus": ("elderly_75_plus_start", "elderly_program_end"),
    "elderly_70_74": ("elderly_70_74_start", "elderly_program_end"),
    "elderly_65_69": ("elderly_65_69_start", "elderly_program_end"),
    "child_two_dose": ("child_two_dose_start", "child_two_dose_end"),
    "child_one_dose": ("child_one_dose_start", "child_one_dose_end"),
}


@dataclass(frozen=True)
class InfluenzaEligibilityResult:
    status: str
    allowed: bool
    message: str
    group_key: str | None
    group_label: str | None
    schedule_start: str | None
    schedule_end: str | None
    counted: bool
    today_count: int
    daily_cap: int
    remaining: int
    requires_operator_confirmation: bool = False


def birth_date_from_resident_id(resident_id: str) -> date | None:
    """Extract a birth date without retaining or returning the resident ID."""

    digits = "".join(character for character in str(resident_id) if character.isdigit())
    if len(digits) != 13:
        return None
    century_code = digits[6]
    if century_code in {"1", "2", "5", "6"}:
        century = 1900
    elif century_code in {"3", "4", "7", "8"}:
        century = 2000
    elif century_code in {"9", "0"}:
        century = 1800
    else:
        return None
    try:
        return date(century + int(digits[:2]), int(digits[2:4]), int(digits[4:6]))
    except ValueError:
        return None


def evaluate_influenza_program(
    settings: dict[str, str],
    resident_id: str,
    *,
    on_date: date | None = None,
    counted_today: int = 0,
) -> InfluenzaEligibilityResult:
    today = on_date or date.today()
    schedule_data = _load_json_object(settings.get("vaccine_schedule_rules_json", ""))
    age_groups = _load_json_list(settings.get("vaccine_age_groups_json", ""))
    if schedule_data is None or age_groups is None:
        return _result(
            "configuration_error",
            "Influenza schedule or age-group settings are invalid JSON.",
            counted_today=counted_today,
        )
    influenza = schedule_data.get("influenza")
    if not isinstance(influenza, dict):
        return _result(
            "configuration_error",
            "Influenza schedule settings are missing.",
            counted_today=counted_today,
        )
    cap = _daily_cap(influenza)
    if cap is None:
        return _result(
            "configuration_error",
            "Influenza daily cap must be a whole number greater than or equal to zero.",
            counted_today=counted_today,
            daily_cap=0,
        )
    if not _as_bool(influenza.get("program_enabled", False)):
        return _result(
            "configuration_required",
            "Influenza season is disabled until its dates and birth ranges are reviewed.",
            counted_today=counted_today,
            daily_cap=cap,
        )

    birth_date = birth_date_from_resident_id(resident_id)
    if birth_date is None:
        return _result(
            "patient_context_required",
            "A complete resident ID is required to determine the birth-date group.",
            counted_today=counted_today,
            daily_cap=cap,
        )

    return evaluate_influenza_program_for_birth_date(
        influenza,
        age_groups,
        birth_date,
        on_date=today,
        counted_today=counted_today,
    )


def evaluate_influenza_program_for_birth_date(
    influenza_schedule: dict[str, Any],
    age_groups: list[Any],
    birth_date: date,
    *,
    on_date: date,
    counted_today: int = 0,
) -> InfluenzaEligibilityResult:
    cap = _daily_cap(influenza_schedule)
    if cap is None:
        return _result(
            "configuration_error",
            "Influenza daily cap must be a whole number greater than or equal to zero.",
            counted_today=counted_today,
            daily_cap=0,
        )
    matches: list[tuple[str, str]] = []
    for raw_group in age_groups:
        if not isinstance(raw_group, dict):
            continue
        if str(raw_group.get("vaccine", "")).strip().lower() != "influenza":
            continue
        key = str(raw_group.get("key", "")).strip()
        if key == "exception_influenza":
            continue
        label = str(raw_group.get("label", "")).strip() or key
        lower_text = str(raw_group.get("birth_date_from", "")).strip()
        upper_text = str(raw_group.get("birth_date_to", "")).strip()
        if not lower_text and not upper_text:
            continue
        lower = _parse_date(lower_text) if lower_text else None
        upper = _parse_date(upper_text) if upper_text else None
        if (lower_text and lower is None) or (upper_text and upper is None):
            return _result(
                "configuration_error",
                f"Birth-date range for '{label}' is invalid.",
                counted_today=counted_today,
                daily_cap=cap,
            )
        if lower is not None and upper is not None and lower > upper:
            return _result(
                "configuration_error",
                f"Birth-date range for '{label}' is reversed.",
                counted_today=counted_today,
                daily_cap=cap,
            )
        if (lower is None or lower <= birth_date) and (
            upper is None or birth_date <= upper
        ):
            matches.append((key, label))

    if not matches:
        return _result(
            "private_or_unmatched",
            "No configured national influenza birth-date group matches this patient.",
            counted_today=counted_today,
            daily_cap=cap,
        )

    matched_keys = {key for key, _label in matches}
    if matched_keys and matched_keys <= INFLUENZA_CHILD_GROUPS:
        return _evaluate_child_program(
            influenza_schedule,
            matches,
            on_date=on_date,
            counted_today=counted_today,
            daily_cap=cap,
        )

    if len(matches) > 1:
        return _result(
            "configuration_error",
            "Multiple influenza birth-date groups overlap for this patient.",
            counted_today=counted_today,
            daily_cap=cap,
        )

    group_key, group_label = matches[0]
    schedule_keys = INFLUENZA_SCHEDULE_KEYS.get(group_key)
    if schedule_keys is None:
        return _result(
            "configuration_error",
            f"No schedule mapping exists for '{group_label}'.",
            group_key=group_key,
            group_label=group_label,
            counted_today=counted_today,
            daily_cap=cap,
        )
    start = _parse_date(influenza_schedule.get(schedule_keys[0]))
    end = _parse_date(influenza_schedule.get(schedule_keys[1]))
    if start is None or end is None or start > end:
        return _result(
            "configuration_error",
            f"Schedule dates for '{group_label}' are incomplete or invalid.",
            group_key=group_key,
            group_label=group_label,
            counted_today=counted_today,
            daily_cap=cap,
        )

    if on_date < start:
        if group_key in INFLUENZA_ELDERLY_GROUPS and _as_bool(
            influenza_schedule.get("allow_elderly_exception", False)
        ):
            earliest = _parse_date(influenza_schedule.get("elderly_75_plus_start"))
            if earliest is not None and earliest <= on_date <= end:
                return _result(
                    "eligible_exception",
                    "This age group's standard opening date has not arrived. "
                    "The configured medically underserved rural-area exception applies "
                    "without consuming the shared daily cap.",
                    allowed=True,
                    group_key=group_key,
                    group_label=group_label,
                    schedule_start=start.isoformat(),
                    schedule_end=end.isoformat(),
                    counted=False,
                    counted_today=counted_today,
                    daily_cap=cap,
                )
        return _result(
            "blocked",
            "The configured vaccination window has not started for this group.",
            group_key=group_key,
            group_label=group_label,
            schedule_start=start.isoformat(),
            schedule_end=end.isoformat(),
            counted_today=counted_today,
            daily_cap=cap,
        )
    if on_date > end:
        return _result(
            "blocked",
            "The configured vaccination window has ended for this group.",
            group_key=group_key,
            group_label=group_label,
            schedule_start=start.isoformat(),
            schedule_end=end.isoformat(),
            counted_today=counted_today,
            daily_cap=cap,
        )
    if counted_today >= cap:
        return _result(
            "cap_reached",
            "The configured influenza daily cap has been reached.",
            group_key=group_key,
            group_label=group_label,
            schedule_start=start.isoformat(),
            schedule_end=end.isoformat(),
            counted=True,
            counted_today=counted_today,
            daily_cap=cap,
        )
    return _result(
        "eligible",
        "Configured national influenza date, birth-range, and cap checks passed.",
        allowed=True,
        group_key=group_key,
        group_label=group_label,
        schedule_start=start.isoformat(),
        schedule_end=end.isoformat(),
        counted=True,
        counted_today=counted_today,
        daily_cap=cap,
    )


def _evaluate_child_program(
    influenza_schedule: dict[str, Any],
    matches: list[tuple[str, str]],
    *,
    on_date: date,
    counted_today: int,
    daily_cap: int,
) -> InfluenzaEligibilityResult:
    two_dose_start = _parse_date(influenza_schedule.get("child_two_dose_start"))
    two_dose_end = _parse_date(influenza_schedule.get("child_two_dose_end"))
    one_dose_start = _parse_date(influenza_schedule.get("child_one_dose_start"))
    one_dose_end = _parse_date(influenza_schedule.get("child_one_dose_end"))
    child_dates = (two_dose_start, two_dose_end, one_dose_start, one_dose_end)
    group_label = matches[0][1] or "Eligible child"
    if (
        any(value is None for value in child_dates)
        or two_dose_start > two_dose_end
        or one_dose_start > one_dose_end
        or two_dose_start > one_dose_start
    ):
        return _result(
            "configuration_error",
            "Child influenza schedule dates are incomplete or invalid.",
            group_key="child_two_dose",
            group_label=group_label,
            counted_today=counted_today,
            daily_cap=daily_cap,
        )

    if on_date < two_dose_start:
        return _result(
            "blocked",
            "The configured child influenza window has not started.",
            group_key="child_two_dose",
            group_label=group_label,
            schedule_start=two_dose_start.isoformat(),
            schedule_end=one_dose_end.isoformat(),
            counted_today=counted_today,
            daily_cap=daily_cap,
        )

    if on_date < one_dose_start:
        if on_date > two_dose_end:
            return _result(
                "blocked",
                "The early two-dose child window is not open.",
                group_key="child_two_dose",
                group_label=group_label,
                schedule_start=two_dose_start.isoformat(),
                schedule_end=two_dose_end.isoformat(),
                counted_today=counted_today,
                daily_cap=daily_cap,
            )
        if counted_today >= daily_cap:
            return _result(
                "cap_reached",
                "The configured influenza daily cap has been reached.",
                group_key="child_two_dose",
                group_label=group_label,
                schedule_start=two_dose_start.isoformat(),
                schedule_end=two_dose_end.isoformat(),
                counted=True,
                counted_today=counted_today,
                daily_cap=daily_cap,
            )
        return _result(
            "review_required",
            "Before label printing, check the vaccination system manually to confirm "
            "that this child is a first-time influenza recipient requiring two doses.",
            group_key="child_two_dose",
            group_label=group_label,
            schedule_start=two_dose_start.isoformat(),
            schedule_end=two_dose_end.isoformat(),
            counted=True,
            counted_today=counted_today,
            daily_cap=daily_cap,
            requires_operator_confirmation=True,
        )

    if on_date > one_dose_end:
        return _result(
            "blocked",
            "The configured child influenza window has ended.",
            group_key="child_one_dose",
            group_label=group_label,
            schedule_start=one_dose_start.isoformat(),
            schedule_end=one_dose_end.isoformat(),
            counted_today=counted_today,
            daily_cap=daily_cap,
        )
    if counted_today >= daily_cap:
        return _result(
            "cap_reached",
            "The configured influenza daily cap has been reached.",
            group_key="child_one_dose",
            group_label=group_label,
            schedule_start=one_dose_start.isoformat(),
            schedule_end=one_dose_end.isoformat(),
            counted=True,
            counted_today=counted_today,
            daily_cap=daily_cap,
        )
    return _result(
        "eligible",
        "The configured child influenza window and daily cap checks passed.",
        allowed=True,
        group_key="child_one_dose",
        group_label=group_label,
        schedule_start=one_dose_start.isoformat(),
        schedule_end=one_dose_end.isoformat(),
        counted=True,
        counted_today=counted_today,
        daily_cap=daily_cap,
    )


def _result(
    status: str,
    message: str,
    *,
    allowed: bool = False,
    group_key: str | None = None,
    group_label: str | None = None,
    schedule_start: str | None = None,
    schedule_end: str | None = None,
    counted: bool = False,
    counted_today: int = 0,
    daily_cap: int = 100,
    requires_operator_confirmation: bool = False,
) -> InfluenzaEligibilityResult:
    normalized_count = max(0, int(counted_today))
    normalized_cap = max(0, int(daily_cap))
    return InfluenzaEligibilityResult(
        status=status,
        allowed=allowed,
        message=message,
        group_key=group_key,
        group_label=group_label,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
        counted=counted,
        today_count=normalized_count,
        daily_cap=normalized_cap,
        remaining=max(0, normalized_cap - normalized_count),
        requires_operator_confirmation=requires_operator_confirmation,
    )


def _load_json_object(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_json_list(value: str) -> list[Any] | None:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, list) else None


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    for format_string in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, format_string).date()
        except ValueError:
            continue
    return None


def _daily_cap(schedule: dict[str, Any]) -> int | None:
    try:
        value = int(schedule.get("daily_cap", 100))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
