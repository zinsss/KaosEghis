import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_plugin_ui_modules_import() -> None:
    import KaosEghis.ui.plugins.flu_panel
    import KaosEghis.ui.plugins.pacs_panel
    import KaosEghis.ui.plugins.weekly_visits_panel
    import KaosEghis.ui.tabs.kaosclip_tab
    import KaosEghis.ui.tabs.plugins_tab


def test_plugins_tab_can_be_instantiated_without_backends() -> None:
    _app()

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()

    assert tab is not None


def test_pacs_panel_has_required_worklist_columns() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    panel = PacsPanel()

    assert panel.WORKLIST_COLUMNS == [
        "Status",
        "Patient",
        "Chart No",
        "Study",
        "Modality",
        "Requested At",
        "Accession / Order ID",
    ]
    assert "PACS Worklist" in [label.text() for label in panel.findChildren(QLabel)]


def test_flu_panel_can_load_week_without_backend() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel()
    panel.load_report()

    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert "Weekly - Influenza Report" in labels
    assert "Total Visits(Practice) Count: 0" in panel.report_output.toPlainText()


def test_weekly_visits_panel_can_load_without_backend(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel

    panel = WeeklyVisitsPanel(db_path=tmp_path / "KaosEghis.sqlite")

    assert panel.REPORT_COLUMNS == ["Age Group", "Visits", "Patients"]
    assert "unavailable" in panel.report_status.text()


def test_weekly_visits_panel_label_contains_kaoseghis_flu(tmp_path) -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel

    panel = WeeklyVisitsPanel(db_path=tmp_path / "KaosEghis.sqlite")
    labels = [label.text() for label in panel.findChildren(QLabel)]

    assert "KaosEghis-flu weekly practice-count report" in labels


def test_plugins_tab_groups_weekly_panel_under_kaoseghis_flu() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()
    labels = [label.text() for label in tab.findChildren(QLabel)]

    assert "Weekly - Influenza Report" in labels
    assert "PACS Worklist" in labels
