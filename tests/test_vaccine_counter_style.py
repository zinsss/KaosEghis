from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from KaosEghis.core.printer_service import VaccineLabelPrintResult
from KaosEghis.db.database import connect
from KaosEghis.db.repositories import (
    create_vaccine_record,
    mark_vaccine_record_cancelled,
    mark_vaccine_record_completed,
)
from KaosEghis.ui.tabs.vaccine_tab import VaccineTab
from KaosEghis.ui.theme import NORD_QSS


@pytest.fixture
def page(tmp_path):
    app = QApplication.instance() or QApplication([])
    panel = VaccineTab(tmp_path / "test.sqlite")
    panel.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    panel.setStyleSheet(NORD_QSS)
    yield panel
    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_counters_use_large_bold_distinct_text(page):
    for label, color in (
        (page.today_influenza_count_label, "#88c0d0"),
        (page.today_covid_count_label, "#ebcb8b"),
    ):
        label.ensurePolished()
        assert label.font().pixelSize() == 18
        assert label.font().bold()
        assert label.palette().color(QPalette.ColorRole.WindowText).name() == color
        assert label.wordWrap()
        assert label.minimumHeight() >= 76


@pytest.mark.parametrize("width", [900, 1100, 1280])
def test_counter_row_fits_and_preserves_count_values(page, width):
    page._update_today_counts(
        {"vaccine_influenza_daily_cap": "100", "vaccine_covid_daily_cap": "100"},
        {"flu": 100, "covid": 99},
        {"flu": 123, "covid": 45},
    )
    page.resize(width, 900)
    page.show()
    QApplication.instance().processEvents()
    flu, covid = page.today_influenza_count_label, page.today_covid_count_label
    assert flu.text() == "Influenza today: 100\u00a0/\u00a0100\n\uc608\uc678: 123"
    assert covid.text() == "COVID-19 today: 99\u00a0/\u00a0100\n\uc608\uc678: 45"
    assert flu.geometry().right() < covid.geometry().left()
    for label in (flu, covid):
        assert label.parentWidget().rect().contains(label.geometry())
        text_bounds = label.fontMetrics().boundingRect(
            label.contentsRect(), Qt.TextFlag.TextWordWrap, label.text(),
        )
        assert text_bounds.height() <= label.height() - 8


def test_exception_counts_refresh_on_page_and_settings_reload(page):
    labels = (page.today_influenza_count_label, page.today_covid_count_label)
    assert all(label.text().endswith("\uc608\uc678: 0") for label in labels)
    with connect(page._db_path) as connection:
        entries = []
        for program in ("national_influenza", "national_covid"):
            entry = create_vaccine_record(
                connection, vaccine_type_id=None,
                vaccine_type_name="Synthetic vaccine", program_type=program,
            )
            mark_vaccine_record_completed(
                connection, entry.id, counts_toward_cap=False,
                completed_at=datetime.now().isoformat(timespec="seconds"),
            )
            entries.append(entry)
    page.refresh_view()
    assert all(label.text().endswith("\uc608\uc678: 1") for label in labels)
    assert all("0\u00a0/\u00a0100" in label.text() for label in labels)
    page._handle_vaccine_settings_changed()
    assert all(label.text().endswith("\uc608\uc678: 1") for label in labels)
    with connect(page._db_path) as connection:
        for entry in entries:
            mark_vaccine_record_cancelled(connection, entry.id)
    page.refresh_view()
    assert all(label.text().endswith("\uc608\uc678: 0") for label in labels)


@pytest.mark.parametrize("program,label_name", [
    ("national_influenza", "today_influenza_count_label"),
    ("national_covid", "today_covid_count_label"),
])
def test_exception_label_reprint_does_not_increment_counter(page, monkeypatch, program, label_name):
    with connect(page._db_path) as connection:
        entry = create_vaccine_record(
            connection, vaccine_type_id=None,
            vaccine_type_name="Synthetic vaccine", program_type=program,
        )
        completed = mark_vaccine_record_completed(
            connection, entry.id, counts_toward_cap=False,
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
    monkeypatch.setattr(page, "_record_for_label_print", lambda: completed)
    monkeypatch.setattr(
        "KaosEghis.ui.tabs.vaccine_tab.print_vaccine_label",
        lambda *_args, **_kwargs: VaccineLabelPrintResult(True, "Synthetic print"),
    )
    for _ in range(2):
        assert page._print_current_label() is not None
        assert getattr(page, label_name).text().endswith("\uc608\uc678: 1")
