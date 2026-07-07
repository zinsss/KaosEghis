import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_main_window_top_level_tabs_are_exact(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "KaosEghis",
        "KaosGdd",
        "Vaccine",
        "PACS",
        "Flu-Report",
        "Settings",
    ]
    assert window.width() == 1280
    assert window.height() == 875
    assert window.minimumWidth() == 1280
    assert window.maximumWidth() == 1280
    assert window.minimumHeight() == 875
    assert window.maximumHeight() == 875


def test_main_window_marks_pacs_tab_red_when_unhealthy(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: False)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    pacs_index = [window.tabs.tabText(index) for index in range(window.tabs.count())].index("PACS")
    assert window.tabs.tabBar().tabTextColor(pacs_index).name().lower() == "#f38ba8"
    assert "KaosPACS unavailable" in window.tabs.tabBar().tabToolTip(pacs_index)


def test_kaoseghis_tab_has_compact_top_navigation_and_stacked_widget() -> None:
    _app()

    from PySide6.QtWidgets import QStackedWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    assert list(tab.nav_buttons.keys()) == ["Launcher", "Macros", "Macro Texts", "EMR"]
    assert isinstance(tab.stacked_widget, QStackedWidget)
    assert tab.stacked_widget.currentWidget() is tab.launcher_page
    assert tab.nav_buttons["Launcher"].isChecked() is True


def test_kaoseghis_top_nav_pages_are_reachable() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    tab.nav_buttons["Launcher"].click()
    assert tab.stacked_widget.currentWidget() is tab.launcher_page

    tab.nav_buttons["Macros"].click()
    assert tab.stacked_widget.currentWidget() is tab.macros_page

    tab.nav_buttons["Macro Texts"].click()
    assert tab.stacked_widget.currentWidget() is tab.macro_texts_page

    tab.nav_buttons["EMR"].click()
    assert tab.stacked_widget.currentWidget() is tab.emr_page


def test_kaosgdd_vaccine_pacs_and_flu_report_tabs_instantiate(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

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
