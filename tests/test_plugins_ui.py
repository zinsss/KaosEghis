import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_plugin_ui_modules_import() -> None:
    import KaosEghis.ui.plugins.flu_panel
    import KaosEghis.ui.plugins.pacs_panel
    import KaosEghis.ui.tabs.kaosclip_tab
    import KaosEghis.ui.tabs.plugins_tab


def test_plugins_tab_can_be_instantiated_without_backends() -> None:
    _app()

    from KaosEghis.ui.tabs.plugins_tab import PluginsTab

    tab = PluginsTab()

    assert tab is not None


def test_pacs_panel_has_required_worklist_columns() -> None:
    _app()

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


def test_flu_panel_can_load_week_without_backend() -> None:
    _app()

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel()
    panel.load_week()

    assert "not connected" in panel.preview.toPlainText()
