from datetime import date, datetime

import pytest

from KaosEghis.core.claim_preparation import (
    ClaimHistory, ClaimPreviewError, build_claim_plan, parse_claim_month, parse_claim_week,
)


def history(month, weeks=(), available=(1, 2, 3, 4, 5, 6)):
    return ClaimHistory(month, weeks, available, datetime(2026, 9, 18, 12), (100, 200))


@pytest.mark.parametrize("value", ["2026년 9월 18일 금요일", "2026년9월", "2026/09", "2026-09-18", " 2026.9 "])
def test_month_parser_uses_selected_year_and_month(value):
    assert parse_claim_month(value) == date(2026, 9, 1)


@pytest.mark.parametrize("value", ["", "9월", "2026/13", "2026/00", "unavailable", "2026/09 extra"])
def test_invalid_month_is_not_today(value):
    with pytest.raises(ClaimPreviewError):
        parse_claim_month(value)


@pytest.mark.parametrize("value, expected", [("1주", 1), (" 5 주 ", 5), ("6주", 6)])
def test_week_parser(value, expected):
    assert parse_claim_week(value) == expected


@pytest.mark.parametrize("value", ["", "0주", "7주", "청구단위 row 1", "2", "1주 2주"])
def test_invalid_week_does_not_become_empty_history(value):
    with pytest.raises(ClaimPreviewError):
        parse_claim_week(value)


def test_next_week_uses_maximum_not_row_order_or_duplicate_insurance_rows():
    month = date(2026, 9, 1)
    part, = build_claim_plan(date(2026, 9, 18), {month: history(month, (1, 2, 1, 2))})
    assert (part.start, part.end) == (date(2026, 9, 14), date(2026, 9, 18))
    assert (part.latest_week, part.next_week) == (2, 3)
    assert part.status == "Review required"


def test_october_2_boundary_example_uses_each_month_history():
    september, october = date(2026, 9, 1), date(2026, 10, 1)
    parts = build_claim_plan(date(2026, 10, 2), {
        september: history(september, (1, 2, 3, 4, 4)),
        october: history(october),
    })
    assert [(p.start, p.end, p.next_week) for p in parts] == [
        (date(2026, 9, 28), date(2026, 9, 30), 5),
        (date(2026, 10, 1), date(2026, 10, 2), 1),
    ]


def test_previous_month_last_week_can_be_six_not_calendar_assumption():
    month = date(2026, 9, 1)
    parts = build_claim_plan(date(2026, 10, 2), {month: history(month, (5,))})
    assert parts[0].next_week == 6
    assert parts[1].next_week is None


def test_year_boundary_and_monday_do_not_add_unrelated_months():
    assert [p.month for p in build_claim_plan(date(2027, 1, 1), {})] == [
        date(2026, 12, 1), date(2027, 1, 1),
    ]
    monday, = build_claim_plan(date(2026, 6, 1), {})
    assert monday.start == monday.end == date(2026, 6, 1)


def test_empty_and_unread_are_different():
    month = date(2026, 9, 1)
    missing, = build_claim_plan(date(2026, 9, 18), {})
    empty, = build_claim_plan(date(2026, 9, 18), {month: history(month)})
    assert missing.next_week is None
    assert missing.latest_week is None
    assert empty.next_week == 1
    assert empty.latest_week == 0


@pytest.mark.parametrize("weeks, available", [((6,), (1, 2, 3, 4, 5, 6)), ((2,), (1, 2)), ((), ())])
def test_missing_or_invalid_next_week_blocks_plan(weeks, available):
    month = date(2026, 9, 1)
    part, = build_claim_plan(date(2026, 9, 18), {month: history(month, weeks, available)})
    assert part.next_week is None
    assert part.status == "Next week selector unavailable"


def test_weekend_not_silently_treated_as_friday():
    with pytest.raises(ClaimPreviewError, match="weekday"):
        build_claim_plan(date(2026, 10, 3), {})
