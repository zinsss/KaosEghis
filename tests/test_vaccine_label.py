import json
import os
from datetime import datetime
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _settings():
    return {
        "vaccine_schedule_rules_json": json.dumps({"influenza": {
            "program_enabled": True,
            "allow_rural_exception": True,
            "daily_cap": 100,
            "elderly_75_plus_start": "2026-10-11",
            "elderly_65_69_start": "2026-10-18",
            "elderly_program_end": "2027-04-30",
            "child_one_dose_start": "2026-10-05",
            "child_one_dose_end": "2027-04-30",
        }}),
        "vaccine_age_groups_json": json.dumps([
            {"key": key, "vaccine": "influenza", "birth_date_from": start,
             "birth_date_to": end}
            for key, start, end in [
                ("elderly_75_plus", "1900-01-01", "1951-12-31"),
                ("elderly_65_69", "1957-01-01", "1961-12-31"),
                ("child_one_dose", "2013-01-01", "2026-03-31"),
            ]
        ]),
    }


def _record(name, program, resident_id, *, completed=False):
    return SimpleNamespace(
        vaccine_type_name=name,
        program_type=program,
        patient_name="홍길동",
        patient_chart_no="0000",
        patient_resident_id=resident_id,
        patient_phone="010-0000-0000",
        status="completed" if completed else "prepared",
        completed_on="2026-10-12" if completed else None,
    )


@pytest.mark.parametrize("name,program,resident_id,counted,title", [
    ("Influenza", "national_influenza", "500101-1000000", True, "노인독감"),
    ("Influenza", "national_influenza", "190101-3000000", True, "소아독감"),
    ("Influenza", "national_influenza", "600101-1000000", False, "노인독감.예외"),
    ("COVID-19 (Pfizer)", "national_covid", "500101-1000000", True, "코로나.화이자"),
    ("COVID-19 (Moderna)", "national_covid", "500101-1000000", True, "코로나.모더나"),
    ("Influenza (general/private)", "general_influenza", "500101-1000000", False,
     "Influenza (general/private)"),
    ("Custom product", "national_covid", "500101-1000000", True, "Custom product"),
    ("Tdap", "general", "500101-1000000", False, "Tdap"),
    ("노인독감", "general_influenza", "500101-1000000", False, "노인독감"),
    ("코로나.모더나", "general", "500101-1000000", False, "코로나.모더나"),
])
def test_print_title_uses_program_without_changing_record(
    monkeypatch, name, program, resident_id, counted, title,
):
    import KaosEghis.ui.tabs.vaccine_tab as module

    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 10, 12, 10, 0)

    monkeypatch.setattr(module, "datetime", FixedDatetime)
    record = _record(name, program, resident_id)
    counts = {"flu": 7, "covid": 3}
    label = module.VaccineTab._label_content(
        None, record, _settings(), counts, counted, influenza_total_today=12,
        covid_totals_today={"COVID-19 (Pfizer)": 21, "코로나.화이자": 1, "COVID-19 (Moderna)": 5},
    )

    assert label.vaccine_name == title
    assert label.resident_id == resident_id
    assert record.vaccine_type_name == name
    assert counts == {"flu": 7, "covid": 3}
    expected_count = ""
    expected_daily = ""
    if program == "national_influenza":
        expected_count = "8/100" if counted else "7/100"
        expected_daily = "오늘 총 독감: 13"
    elif program == "national_covid":
        expected_count = "4/100"
        if title == "코로나.화이자":
            expected_daily = "오늘 화이자: 23"
        elif title == "코로나.모더나":
            expected_daily = "오늘 모더나: 6"
    assert label.count_summary == expected_count
    assert label.daily_total_summary == expected_daily
    styles = {
        "노인독감": "flu_elderly", "소아독감": "flu_child", "노인독감.예외": "flu_exception",
        "코로나.화이자": "covid_pfizer", "코로나.모더나": "covid_moderna",
    }
    assert label.title_style == (
        styles.get(title, "plain") if program.startswith("national_") else "plain"
    )


def test_exception_reprint_uses_completion_date_and_does_not_increment_count():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "600101-1000000", completed=True)
    label = VaccineTab._label_content(
        None, record, _settings(), {"flu": 7}, False, influenza_total_today=12,
    )
    assert label.vaccine_name == "노인독감.예외"
    assert label.count_summary == "7/100"
    assert label.daily_total_summary == "오늘 총 독감: 12"
    assert label.title_style == "flu_exception"


def test_unmatched_influenza_label_keeps_saved_name():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "000101-0000000")
    label = VaccineTab._label_content(None, record, _settings(), {}, True)
    assert label.vaccine_name == "Influenza"
    assert label.title_style == "plain"


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("daily_summary", ["", "오늘 총 독감:123", "오늘 화이자:123456", "오늘 모더나:123"])
@pytest.mark.parametrize("title,style", [
    ("노인독감", "flu_elderly"), ("소아독감", "flu_child"),
    ("노인독감.예외", "flu_exception"), ("코로나.화이자", "covid_pfizer"),
    ("코로나.모더나", "covid_moderna"),
    ("Influenza - 무료접종", "plain"), ("COVID-19 (Moderna)", "plain"),
    ("Influenza - 일반", "plain"), ("Tdap", "plain"),
    ("A long custom vaccine product name that must not wrap or clip", "plain"),
    ("노인독감", "plain"), ("소아독감", "plain"), ("노인독감.예외", "plain"),
    ("코로나.화이자", "plain"), ("코로나.모더나", "plain"),
])
def test_every_label_field_fits_its_print_area(dpi, title, style, daily_summary):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFont, QFontMetricsF, QImage, QPen
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import VaccineLabelContent, _paint_vaccine_label

    app = QApplication.instance() or QApplication([])
    image = QImage(round(80 / 25.4 * dpi), round(40 / 25.4 * dpi), QImage.Format.Format_RGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    drawn = []
    text_rects = []
    text_colors = {}
    pills = []
    fonts = {}
    alignments = {}
    lines = []

    class RecordingPainter:
        def device(self):
            return image

        def setPen(self, pen):
            self.pen = QPen(pen)

        def setBrush(self, brush):
            self.brush = brush

        def save(self):
            self.saved_pen = QPen(self.pen)

        def restore(self):
            self.pen = self.saved_pen

        def drawRoundedRect(self, rect, *_args):
            pills.append((rect, self.brush))

        def drawLine(self, *args):
            lines.append(args)

        def setFont(self, font):
            self.font = QFont(font)

        def drawText(self, rect, flags, text):
            bounds = QFontMetricsF(self.font, image).boundingRect(rect, int(flags), text)
            assert bounds.width() <= rect.width()
            assert bounds.height() <= rect.height()
            assert flags & Qt.TextFlag.TextSingleLine
            assert not flags & Qt.TextFlag.TextWordWrap
            assert self.font.pointSize() == -1
            assert self.font.bold()
            drawn.append(text)
            text_rects.append(rect)
            text_colors[text] = self.pen.color()
            fonts[text] = self.font.pixelSize()
            alignments[text] = flags

    _paint_vaccine_label(
        RecordingPainter(), QRectF(0, 0, image.width(), image.height()),
        VaccineLabelContent(
            vaccine_name=title, patient_name="홍길동", chart_no="0000000000",
            resident_id="000101-0000000", phone="010-0000-0000",
            printed_at=datetime(2026, 12, 31), count_summary="100/100", daily_total_summary=daily_summary,
            title_style=style,
        ),
    )
    pill_parts = {
        "flu_elderly": ["노인", "독감"], "flu_child": ["소아", "독감"],
        "flu_exception": ["노인", "독감", "예외"],
        "covid_pfizer": ["코로나", "화이자"], "covid_moderna": ["코로나", "모더나"],
    }.get(style)
    assert len(drawn) == 5 + len(pill_parts or [title]) + bool(daily_summary)
    if pill_parts:
        assert all(part in drawn for part in pill_parts)
        pill_text = pill_parts[1]
        assert len(pills) == 1
        assert pills[0][1] == (
            Qt.GlobalColor.white if style == "covid_pfizer" else Qt.GlobalColor.black
        )
        assert text_colors[pill_text] == (
            Qt.GlobalColor.black if style == "covid_pfizer" else Qt.GlobalColor.white
        )
        assert text_colors[pill_parts[0]] == Qt.GlobalColor.black
        if len(pill_parts) == 3:
            assert text_colors["예외"] == Qt.GlobalColor.black
        pill_rect = pills[0][0]
        pill_text_rect = text_rects[drawn.index(pill_text)]
        prefix_rect = text_rects[drawn.index(pill_parts[0])]
        assert pill_rect.width() - pill_text_rect.width() <= fonts[pill_text] * 0.4
        assert pill_rect.left() - prefix_rect.right() <= fonts[pill_text] * 0.15
        assert pill_rect.height() < image.height() * 0.26
        inner_height = image.height() - image.width() * 0.14
        previous_title_height = inner_height * 0.48 - image.height() * 0.05
        assert fonts[pill_text] == max(1, round(min(image.height() / 4.9, previous_title_height * 0.54)))
        assert pill_rect.center().y() == pytest.approx((lines[0][1] + lines[1][1]) / 2)
        assert pill_rect.top() - lines[0][1] > image.height() * 0.075
        assert lines[1][1] - pill_rect.bottom() > image.height() * 0.075
    else:
        assert title in drawn
        assert pills == []
    patient_heading = "홍길동  0000000000"
    assert patient_heading in drawn
    assert text_colors[patient_heading] == Qt.GlobalColor.black
    assert text_rects[drawn.index(patient_heading)].top() < lines[0][1]
    assert alignments[patient_heading] & Qt.AlignmentFlag.AlignLeft
    for i, rect in enumerate(text_rects):
        assert all(not rect.intersects(other) for other in text_rects[i + 1:])
    assert "26.12.31" in drawn
    assert "2026.12.31" not in drawn
    assert "100/100" in drawn
    assert alignments["26.12.31"] & Qt.AlignmentFlag.AlignRight
    footer_rects = [text_rects[drawn.index(value)] for value in ["000101-0000000", "010-0000-0000", "26.12.31"]]
    assert all(rect.top() > lines[1][1] for rect in footer_rects)
    assert len({rect.center().y() for rect in footer_rects}) == 1
    assert all(left.right() < right.left() for left, right in zip(footer_rects, footer_rects[1:]))
    assert alignments["000101-0000000"] & Qt.AlignmentFlag.AlignLeft
    assert alignments["010-0000-0000"] & Qt.AlignmentFlag.AlignHCenter
    assert alignments["100/100"] & Qt.AlignmentFlag.AlignHCenter
    assert text_rects[drawn.index("100/100")].center().x() == pytest.approx(image.width() / 2)
    if daily_summary:
        assert daily_summary in drawn
        assert alignments[daily_summary] & Qt.AlignmentFlag.AlignRight
    assert len(lines) == 2
    assert lines[1][1] - lines[0][1] == pytest.approx((image.height() - image.width() * 0.14) * 0.58)
    assert app is not None


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_plain_titles_use_the_pill_title_font_standard(dpi):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import _draw_vaccine_title

    app = QApplication.instance() or QApplication([])
    image = QImage(round(80 / 25.4 * dpi), round(40 / 25.4 * dpi), QImage.Format.Format_RGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    rect = QRectF(0, 0, image.width() * 0.86, image.height() * 0.2956)
    drawn_sizes = []

    class RecordingPainter(QPainter):
        def drawText(self, *_args):
            drawn_sizes.append(self.font().pixelSize())

    painter = RecordingPainter(image)
    try:
        for title, style in [
            ("노인독감", "flu_elderly"), ("코로나.모더나", "covid_moderna"),
            ("Influenza - 일반", "plain"), ("Tdap", "plain"),
        ]:
            _draw_vaccine_title(painter, rect, title, image.height() / 4.9, style=style)
    finally:
        painter.end()
    assert len(set(drawn_sizes)) == 1
    assert app is not None


def test_national_influenza_total_includes_exception_but_excludes_private(tmp_path):
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record, delete_vaccine_record, get_today_national_influenza_total,
        get_today_vaccine_counts, mark_vaccine_record_cancelled,
        mark_vaccine_record_completed, mark_vaccine_record_printed,
    )

    path = tmp_path / "labels.sqlite"
    initialize_database(path)
    with connect(path) as connection:
        assert get_today_national_influenza_total(connection, "2026-10-12") == 0
        records = []
        for program, counted, completion in [
            ("national_influenza", True, "2026-10-12"),
            ("national_influenza", False, "2026-10-12"),
            ("general_influenza", False, "2026-10-12"),
            ("national_covid", True, "2026-10-12"),
            ("general", False, "2026-10-12"),
            ("national_influenza", True, "2026-10-11"),
            ("national_influenza", False, None),
            ("national_influenza", False, None),
        ]:
            record = create_vaccine_record(
                connection, vaccine_type_id=None, vaccine_type_name="Fake product",
                program_type=program,
            )
            records.append(record)
            if completion:
                mark_vaccine_record_completed(
                    connection, record.id, counts_toward_cap=counted,
                    completed_at=f"{completion}T10:00:00+09:00",
                )
        mark_vaccine_record_printed(connection, records[-1].id)
        before = connection.total_changes
        assert get_today_national_influenza_total(connection, "2026-10-12") == 2
        assert get_today_vaccine_counts(connection, "2026-10-12") == {"flu": 1, "covid": 1}
        assert connection.total_changes == before

        mark_vaccine_record_completed(connection, records[0].id)
        assert get_today_national_influenza_total(connection, "2026-10-12") == 2
        mark_vaccine_record_cancelled(connection, records[2].id)
        assert get_today_national_influenza_total(connection, "2026-10-12") == 2
        delete_vaccine_record(connection, records[0].id)
        assert get_today_national_influenza_total(connection, "2026-10-12") == 1


def test_covid_manufacturer_totals_include_exceptions_not_private_or_other_days(tmp_path):
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record, get_today_national_covid_totals, get_today_vaccine_counts,
        mark_vaccine_record_cancelled, mark_vaccine_record_completed, mark_vaccine_record_printed,
    )

    path = tmp_path / "covid-labels.sqlite"
    initialize_database(path)
    with connect(path) as connection:
        assert get_today_national_covid_totals(connection, "2026-10-12") == {}
        records = []
        for name, program, counted, day in [
            ("COVID-19 (Pfizer)", "national_covid", True, "2026-10-12"),
            ("코로나.화이자", "national_covid", False, "2026-10-12"),
            ("COVID-19 (Moderna)", "national_covid", True, "2026-10-12"),
            ("COVID-19 (Pfizer)", "general", False, "2026-10-12"),
            ("COVID-19 (Moderna)", "national_covid", True, "2026-10-11"),
            ("COVID-19 (Pfizer)", "national_covid", True, None),
        ]:
            record = create_vaccine_record(
                connection, vaccine_type_id=None, vaccine_type_name=name, program_type=program,
            )
            records.append(record)
            if day:
                mark_vaccine_record_completed(
                    connection, record.id, counts_toward_cap=counted,
                    completed_at=f"{day}T10:00:00+09:00",
                )
        mark_vaccine_record_printed(connection, records[-1].id)
        before = connection.total_changes
        assert get_today_national_covid_totals(connection, "2026-10-12") == {
            "COVID-19 (Pfizer)": 1, "코로나.화이자": 1, "COVID-19 (Moderna)": 1,
        }
        assert get_today_vaccine_counts(connection, "2026-10-12") == {"flu": 0, "covid": 2}
        assert connection.total_changes == before
        mark_vaccine_record_cancelled(connection, records[2].id)
        assert get_today_national_covid_totals(connection, "2026-10-12") == {
            "COVID-19 (Pfizer)": 1, "코로나.화이자": 1,
        }


@pytest.mark.parametrize("name,expected", [
    ("COVID-19 (Pfizer)", "오늘 화이자: 22"), ("COVID-19 (Moderna)", "오늘 모더나: 5"),
])
def test_covid_reprint_keeps_current_manufacturer_total(name, expected):
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record(name, "national_covid", "500101-1000000", completed=True)
    totals = {"COVID-19 (Pfizer)": 21, "코로나.화이자": 1, "COVID-19 (Moderna)": 5}
    label = VaccineTab._label_content(
        None, record, _settings(), {"covid": 25}, True, covid_totals_today=totals,
    )
    assert label.count_summary == "25/100"
    assert label.daily_total_summary == expected
    assert sum(totals.values()) == 27


def test_manufacturer_pills_have_distinct_rendered_ink_coverage():
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import _draw_vaccine_title

    app = QApplication.instance() or QApplication([])
    ratios = []
    for name, style in [("코로나.화이자", "covid_pfizer"), ("코로나.모더나", "covid_moderna")]:
        image = QImage(800, 160, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        _draw_vaccine_title(painter, QRectF(0, 10, 800, 140), name, 90, style=style)
        painter.end()
        pixels = [image.pixelColor(x, y).lightness() for x in range(410, 615, 2) for y in range(45, 115, 2)]
        ratios.append(sum(value < 128 for value in pixels) / len(pixels))
    assert 0.02 < ratios[0] < 0.4
    assert 0.5 < ratios[1] < 0.95
    assert ratios[1] > 2 * ratios[0]
    assert app is not None


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("style", [
    "flu_elderly", "flu_child", "flu_exception", "covid_pfizer", "covid_moderna", "plain",
])
def test_print_raster_contains_header_dividers_and_patient_details(dpi, style):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import VaccineLabelContent, render_vaccine_label_image

    app = QApplication.instance() or QApplication([])
    width, height = round(80 / 25.4 * dpi), round(40 / 25.4 * dpi)
    image = render_vaccine_label_image(
        VaccineLabelContent(
            vaccine_name="Influenza - 일반", title_style=style, patient_name="인쇄테스트",
            chart_no="0000", resident_id="000101-0000000", phone="010-0000-0000",
            printed_at=datetime(2026, 9, 17), count_summary="7/100", daily_total_summary="오늘 총 독감: 12",
        ), width=width, height=height, dpi_x=dpi, dpi_y=dpi,
    )
    assert image.format() == QImage.Format.Format_RGB32
    assert image.width() == width and image.height() == height
    assert image.dotsPerMeterX() == image.dotsPerMeterY() == round(dpi / 0.0254)
    sampled_colors = {
        image.pixel(x, y) for x in range(0, width, 4) for y in range(0, height, 4)
    }
    assert sampled_colors == {0xFF000000, 0xFFFFFFFF}

    margin = width * 0.07
    inner_width, inner_height = width - 2 * margin, height - 2 * margin
    bottom_line = margin + inner_height * 0.76
    lower_height = height - margin - bottom_line
    fields = {
        "patient heading": (margin, margin, inner_width * 0.36, inner_height * 0.15),
        "counter": (margin + inner_width * 0.39, margin, inner_width * 0.22, inner_height * 0.15),
        "daily total": (margin + inner_width * 0.64, margin, inner_width * 0.36, inner_height * 0.15),
        "resident": (margin, bottom_line + lower_height * 0.1, inner_width * 0.38, lower_height * 0.8),
        "phone": (margin + inner_width * 0.41, bottom_line + lower_height * 0.1, inner_width * 0.34, lower_height * 0.8),
        "date": (margin + inner_width * 0.78, bottom_line + lower_height * 0.1, inner_width * 0.22, lower_height * 0.8),
    }
    for name, (x, y, w, h) in fields.items():
        black = sum(
            image.pixel(px, py) == 0xFF000000
            for px in range(round(x), round(x + w), max(1, dpi // 150))
            for py in range(round(y), round(y + h), max(1, dpi // 150))
        )
        assert black > 15, name
    for line in [margin + inner_height * 0.18, bottom_line]:
        coverage = max(
            sum(image.pixel(x, y) == 0xFF000000 for x in range(round(margin), round(width - margin)))
            for y in range(round(line) - 2, round(line) + 3)
        )
        assert coverage > inner_width * 0.95
    assert app is not None


@pytest.mark.parametrize("failure", ["render", "begin", "draw", "end"])
def test_print_raster_failures_do_not_report_success(monkeypatch, failure):
    from unittest.mock import Mock

    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage
    import KaosEghis.core.printer_service as module

    printer = Mock()
    printer.isValid.return_value = True
    printer.pageRect.return_value = QRectF(0, 0, 640, 318)
    printer.logicalDpiX.return_value = printer.logicalDpiY.return_value = 203
    painter = Mock()
    painter.begin.return_value = failure != "begin"
    painter.end.return_value = failure != "end"
    render = Mock(return_value=QImage(640, 318, QImage.Format.Format_RGB32))
    if failure == "render":
        render.side_effect = ValueError("private detail must not escape")
    if failure == "draw":
        painter.drawImage.side_effect = RuntimeError("private detail must not escape")
    monkeypatch.setattr(module, "QPrinter", Mock(return_value=printer))
    monkeypatch.setattr(module, "QPainter", Mock(return_value=painter))
    monkeypatch.setattr(module, "render_vaccine_label_image", render)
    result = module.print_vaccine_label(
        module.VaccineLabelContent("Test", "Test", "0000", "", "", datetime(2026, 9, 17)),
        printer_name="Fake printer",
    )
    assert result.success is False
    assert "private detail" not in result.message
    if failure == "render":
        painter.begin.assert_not_called()
    elif failure != "begin":
        painter.end.assert_called_once()
    assert painter.drawImage.call_count <= 1
