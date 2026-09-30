import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

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
        assert label.minimumHeight() >= 52


@pytest.mark.parametrize("width", [900, 1100, 1280])
def test_counter_row_fits_and_preserves_count_values(page, width):
    page._update_today_counts(
        {"vaccine_influenza_daily_cap": "100", "vaccine_covid_daily_cap": "100"},
        {"flu": 100, "covid": 99},
    )
    page.resize(width, 900)
    page.show()
    QApplication.instance().processEvents()
    flu, covid = page.today_influenza_count_label, page.today_covid_count_label
    assert flu.text() == "Influenza today: 100\u00a0/\u00a0100"
    assert covid.text() == "COVID-19 today: 99\u00a0/\u00a0100"
    assert flu.geometry().right() < covid.geometry().left()
    for label in (flu, covid):
        assert label.parentWidget().rect().contains(label.geometry())
        text_bounds = label.fontMetrics().boundingRect(
            label.contentsRect(), Qt.TextFlag.TextWordWrap, label.text(),
        )
        assert text_bounds.height() <= label.height() - 8
