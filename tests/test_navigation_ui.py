import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_main_window_top_level_tabs_are_exact() -> None:
    _app()

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "KaosEghis",
        "KaosGdd",
        "Vaccine",
        "PACS",
        "Flu-Report",
    ]
    assert 520 <= window.width() <= 680
    assert 760 <= window.height() <= 900


def test_kaoseghis_tab_has_compact_top_navigation_and_stacked_widget() -> None:
    _app()

    from PySide6.QtWidgets import QStackedWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    assert list(tab.nav_buttons.keys()) == ["Macros", "Presets", "EMR", "Settings"]
    assert isinstance(tab.stacked_widget, QStackedWidget)
    assert tab.stacked_widget.currentWidget() is tab.macros_page
    assert tab.nav_buttons["Macros"].isChecked() is True


def test_kaoseghis_top_nav_pages_are_reachable() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    tab.nav_buttons["Presets"].click()
    assert tab.stacked_widget.currentWidget() is tab.presets_page

    tab.nav_buttons["EMR"].click()
    assert tab.stacked_widget.currentWidget() is tab.emr_page

    tab.nav_buttons["Settings"].click()
    assert tab.stacked_widget.currentWidget() is tab.settings_page

    tab.nav_buttons["Macros"].click()
    assert tab.stacked_widget.currentWidget() is tab.macros_page


def test_kaosgdd_vaccine_pacs_and_flu_report_tabs_instantiate() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.flu_panel import FluPanel
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel
    from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
    from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    kaosgdd_tab = KaosGddTab()
    vaccine_tab = VaccineTab()
    pacs_panel = PacsPanel()
    flu_report_tab = FluReportTab()

    assert kaosgdd_tab is not None
    assert vaccine_tab is not None
    assert pacs_panel is not None
    assert flu_report_tab.findChild(FluPanel) is not None
    assert "KaosEghis-flu Report" in [
        label.text() for label in flu_report_tab.findChildren(QLabel)
    ]


def test_vaccine_tab_placeholder_text() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    tab = VaccineTab()
    labels = [label.text() for label in tab.findChildren(QLabel)]

    assert "Vaccine" in labels
    assert "Status: planned plugin" in labels
    assert "Vaccine plugin is planned. No workflow is active yet." in labels
