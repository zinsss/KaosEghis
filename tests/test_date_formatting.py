from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("2026-01-23", "2026년1월23일"),
        ("2026-01-23,2026-01-31", "2026년1월23,31일"),
        (
            "2023-01-30, 2023-02-02, 2023-02-06, 2023-03-30",
            "2023년1월30일 2월2,6일 3월30일",
        ),
        (
            "2026-01-23, 2026-01-31, 2026-02-02, 2026-02-05, "
            "2026-02-10, 2026-03-03",
            "2026년1월23,31일 2월2,5,10일 3월3일",
        ),
        (
            "2025-12-30, 2026-01-02, 2026-01-05, 2026-02-01",
            "2025년12월30일 2026년1월2,5일 2월1일",
        ),
        (
            "2026-03-03,2026-01-31,2026-01-23,2026-02-02",
            "2026년1월23,31일 2월2일 3월3일",
        ),
        (
            "2026-01-23, 2026-01-23, 2026-01-31",
            "2026년1월23,31일",
        ),
        (
            "  2026-01-23 ,\n 2026-02-02  , 2026-02-05 ",
            "2026년1월23일 2월2,5일",
        ),
        ("   ", ""),
    ),
)
def test_format_dates_korean_compact(value: str, expected: str) -> None:
    from KaosEghis.core.date_formatting import format_dates_korean_compact

    assert format_dates_korean_compact(value) == expected


@pytest.mark.parametrize("value", ("2026-02-30", "2026/01/23", "2026-01-23,"))
def test_format_dates_korean_compact_rejects_invalid_dates(value: str) -> None:
    from KaosEghis.core.date_formatting import (
        DateFormatValidationError,
        format_dates_korean_compact,
    )

    with pytest.raises(DateFormatValidationError):
        format_dates_korean_compact(value)


def test_date_formatter_page_formats_and_copies(monkeypatch) -> None:
    _app()

    import KaosEghis.ui.tabs.date_formatter_page as formatter_module

    copied: list[str] = []
    monkeypatch.setattr(formatter_module, "copy_text", copied.append)
    page = formatter_module.DateFormatterPage()
    page.input_text.setPlainText(
        "2026-02-10, 2026-01-23, 2026-02-05, 2026-01-23"
    )

    page.format_button.click()
    page.copy_button.click()

    assert page.output_text.toPlainText() == "2026년1월23일 2월5,10일"
    assert copied == ["2026년1월23일 2월5,10일"]
    assert page.status_label.text() == "Copied."


def test_date_formatter_page_handles_invalid_date_without_raising() -> None:
    _app()

    from KaosEghis.ui.tabs.date_formatter_page import DateFormatterPage

    page = DateFormatterPage()
    page.input_text.setPlainText("2026-02-30")

    page.format_button.click()

    assert page.output_text.toPlainText() == ""
    assert page.status_label.text().startswith("Invalid date.")
