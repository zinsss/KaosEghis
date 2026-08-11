from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QApplication, QWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class FakeWebView(QWidget):
    loadStarted = Signal()
    loadFinished = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.loaded_urls: list[str] = []

    def setUrl(self, url: QUrl) -> None:
        self.loaded_urls.append(url.toString())


def test_launcher_embed_defers_loading_until_activation(monkeypatch) -> None:
    _app()
    import KaosEghis.ui.launcher_agenda_panel as panel_module

    monkeypatch.setattr(panel_module, "QWebEngineView", FakeWebView)
    panel = panel_module.AgendaSuppliesPanel()

    assert panel.web_view is not None
    assert panel.web_view.loaded_urls == []
    assert panel.status_label.text() == "Not loaded yet."

    panel.ensure_loaded()

    assert panel.web_view.loaded_urls == [
        "http://100.94.208.16:8090/embed/agenda-supplies"
    ]


def test_reload_uses_configured_internal_embed_url(monkeypatch) -> None:
    _app()
    import KaosEghis.ui.launcher_agenda_panel as panel_module

    monkeypatch.setattr(panel_module, "QWebEngineView", FakeWebView)
    panel = panel_module.AgendaSuppliesPanel(
        "http://100.64.0.10:9000/embed/agenda-supplies"
    )

    panel.reload_button.click()
    panel.reload_button.click()

    assert panel.web_view.loaded_urls == [
        "http://100.64.0.10:9000/embed/agenda-supplies",
        "http://100.64.0.10:9000/embed/agenda-supplies",
    ]


def test_open_external_browser_uses_internal_embed_url(monkeypatch) -> None:
    _app()
    import KaosEghis.ui.launcher_agenda_panel as panel_module

    monkeypatch.setattr(panel_module, "QWebEngineView", FakeWebView)
    opened: list[str] = []
    monkeypatch.setattr(
        panel_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )
    panel = panel_module.AgendaSuppliesPanel()

    panel.open_external_button.click()

    assert opened == ["http://100.94.208.16:8090/embed/agenda-supplies"]


def test_embed_load_result_updates_status(monkeypatch) -> None:
    _app()
    import KaosEghis.ui.launcher_agenda_panel as panel_module

    monkeypatch.setattr(panel_module, "QWebEngineView", FakeWebView)
    panel = panel_module.AgendaSuppliesPanel()

    panel.web_view.loadFinished.emit(True)
    assert panel.status_label.text() == "KaosGDD Agenda: embedded web view"

    panel.web_view.loadFinished.emit(False)
    assert panel.status_label.text() == "KaosGDD Agenda unavailable."


def test_embed_fallback_is_available_without_qt_webengine(monkeypatch) -> None:
    _app()
    import KaosEghis.ui.launcher_agenda_panel as panel_module

    monkeypatch.setattr(panel_module, "QWebEngineView", None)
    panel = panel_module.AgendaSuppliesPanel()

    assert panel.web_view is None
    assert panel.fallback_label is not None
    assert "100.94.208.16:8090" in panel.fallback_label.text()
    assert panel.reload_button.isEnabled() is False
    assert panel.open_external_button.isEnabled() is True


def test_embed_url_supports_environment_override(monkeypatch) -> None:
    from KaosEghis.ui.launcher_agenda_panel import kaosgdd_embed_url

    monkeypatch.setenv(
        "KAOSGDD_EMBED_URL",
        "http://100.64.0.20:8090/embed/agenda-supplies",
    )

    assert (
        kaosgdd_embed_url()
        == "http://100.64.0.20:8090/embed/agenda-supplies"
    )


def test_native_kaosgdd_api_client_was_removed() -> None:
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    assert not (project_root / "KaosEghis" / "core" / "kaosgdd_client.py").exists()
