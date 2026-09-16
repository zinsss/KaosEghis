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
    label = module.VaccineTab._label_content(None, record, _settings(), counts, counted)

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


def test_exception_reprint_uses_completion_date_and_does_not_increment_count():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "600101-1000000", completed=True)
    label = VaccineTab._label_content(None, record, _settings(), {"flu": 7}, False)
    assert label.vaccine_name == "노인독감.예외"
    assert label.count_summary == "7/100"


def test_unmatched_influenza_label_keeps_saved_name():
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    record = _record("Influenza", "national_influenza", "000101-0000000")
    label = VaccineTab._label_content(None, record, _settings(), {}, True)
    assert label.vaccine_name == "Influenza"


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("title", [
    "노인독감", "소아독감", "노인독감.예외", "코로나.화이자", "코로나.모더나",
    "Influenza - 무료접종", "COVID-19 (Moderna)",
    "A long custom vaccine product name that must not wrap or clip",
])
def test_every_label_field_fits_its_print_area(dpi, title):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFont, QFontMetricsF, QImage
    from PySide6.QtWidgets import QApplication

    from KaosEghis.core.printer_service import VaccineLabelContent, _paint_vaccine_label

    app = QApplication.instance() or QApplication([])
    image = QImage(round(80 / 25.4 * dpi), round(40 / 25.4 * dpi), QImage.Format.Format_RGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    drawn = []

    class RecordingPainter:
        def device(self):
            return image

        def setPen(self, _pen):
            pass

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

    _paint_vaccine_label(
        RecordingPainter(), QRectF(0, 0, image.width(), image.height()),
        VaccineLabelContent(
            vaccine_name=title, patient_name="홍길동", chart_no="0000000000",
            resident_id="000101-0000000", phone="010-0000-0000",
            printed_at=datetime(2026, 12, 31), count_summary="100/100",
        ),
    )
    assert len(drawn) == 6
    assert title in drawn
    assert app is not None
