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
    )

    assert label.vaccine_name == title
    assert label.resident_id == resident_id
    assert record.vaccine_type_name == name
    assert counts == {"flu": 7, "covid": 3}
    expected_count = ""
    if program == "national_influenza":
        expected_count = "8/100" if counted else "7/100"
    elif program == "national_covid":
        expected_count = "4/100"
    assert label.count_summary == expected_count
    assert label.influenza_total_today == (
        13 if program == "national_influenza" else None
    )


def test_exception_reprint_uses_completion_date_and_does_not_increment_count():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "600101-1000000", completed=True)
    label = VaccineTab._label_content(
        None, record, _settings(), {"flu": 7}, False, influenza_total_today=12,
    )
    assert label.vaccine_name == "노인독감.예외"
    assert label.count_summary == "7/100"
    assert label.influenza_total_today == 12


def test_unmatched_influenza_label_keeps_saved_name():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "000101-0000000")
    label = VaccineTab._label_content(None, record, _settings(), {}, True)
    assert label.vaccine_name == "Influenza"


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("influenza_total", [None, 123, 123456])
@pytest.mark.parametrize("title", [
    "노인독감", "소아독감", "노인독감.예외", "코로나.화이자", "코로나.모더나",
    "Influenza - 무료접종", "COVID-19 (Moderna)",
    "A long custom vaccine product name that must not wrap or clip",
])
def test_every_label_field_fits_its_print_area(dpi, title, influenza_total):
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

        def drawLine(self, *_args):
            pass

        def setFont(self, font):
            self.font = QFont(font)

        def drawText(self, rect, flags, text):
            bounds = QFontMetricsF(self.font, image).boundingRect(rect, int(flags), text)
            assert bounds.width() <= rect.width()
            assert bounds.height() <= rect.height()
            assert flags & Qt.TextFlag.TextSingleLine
            assert not flags & Qt.TextFlag.TextWordWrap
            assert self.font.pointSize() == -1
            drawn.append(text)
            text_rects.append(rect)
            text_colors[text] = self.pen.color()

    _paint_vaccine_label(
        RecordingPainter(), QRectF(0, 0, image.width(), image.height()),
        VaccineLabelContent(
            vaccine_name=title, patient_name="홍길동", chart_no="0000000000",
            resident_id="000101-0000000", phone="010-0000-0000",
            printed_at=datetime(2026, 12, 31), count_summary="100/100",
            influenza_total_today=influenza_total,
        ),
    )
    is_covid_pill = title in {"코로나.화이자", "코로나.모더나"}
    assert len(drawn) == 6 + is_covid_pill + (influenza_total is not None)
    if is_covid_pill:
        assert "코로나" in drawn
        manufacturer = title.split(".")[1]
        assert manufacturer in drawn
        assert len(pills) == 1
        assert pills[0][1] == (
            Qt.GlobalColor.black if manufacturer == "모더나" else Qt.GlobalColor.white
        )
        assert text_colors[manufacturer] == (
            Qt.GlobalColor.white if manufacturer == "모더나" else Qt.GlobalColor.black
        )
    else:
        assert title in drawn
        assert pills == []
    assert text_colors["010-0000-0000"] == Qt.GlobalColor.black
    for i, rect in enumerate(text_rects):
        assert all(not rect.intersects(other) for other in text_rects[i + 1:])
    if influenza_total is not None:
        assert f"오늘 총 독감: {influenza_total}" in drawn
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


def test_manufacturer_pills_have_distinct_rendered_ink_coverage():
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import _draw_vaccine_title

    app = QApplication.instance() or QApplication([])
    ratios = []
    for name in ["코로나.화이자", "코로나.모더나"]:
        image = QImage(800, 160, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        _draw_vaccine_title(painter, QRectF(0, 10, 800, 140), name, 90)
        painter.end()
        pixels = [
            image.pixelColor(x, y).lightness()
            for x in range(390, 775, 2) for y in range(25, 135, 2)
        ]
        ratios.append(sum(value < 128 for value in pixels) / len(pixels))
    assert 0.02 < ratios[0] < 0.4
    assert 0.5 < ratios[1] < 0.95
    assert ratios[1] > 2 * ratios[0]
    assert app is not None
