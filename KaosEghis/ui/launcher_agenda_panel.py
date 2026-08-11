from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - depends on optional Qt WebEngine install
    QWebEngineView = None


DEFAULT_KAOSGDD_EMBED_URL = (
    "http://100.94.208.16:8090/embed/agenda-supplies"
)
FLAT_TEXT_BUTTON_STYLE = """
QPushButton {
    background: transparent;
    border: none;
    padding: 2px 4px;
    color: #d8dee9;
}
QPushButton:hover {
    background: transparent;
    border: none;
    color: #88c0d0;
}
QPushButton:pressed {
    background: transparent;
    border: none;
    color: #81a1c1;
}
QPushButton:disabled {
    background: transparent;
    border: none;
    color: #4c566a;
}
"""


def kaosgdd_embed_url() -> str:
    return (
        os.environ.get("KAOSGDD_EMBED_URL", "").strip()
        or DEFAULT_KAOSGDD_EMBED_URL
    )


class AgendaSuppliesPanel(QWidget):
    def __init__(
        self,
        embed_url: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.embed_url = (embed_url or kaosgdd_embed_url()).strip()
        self._load_requested = False

        self.status_label = QLabel("Not loaded yet.")
        self.status_label.setObjectName("secondaryText")
        self.reload_button = QPushButton("Reload")
        self.reload_button.setFlat(True)
        self.reload_button.setStyleSheet(FLAT_TEXT_BUTTON_STYLE)
        self.reload_button.clicked.connect(self.reload)
        self.open_external_button = QPushButton("Open in Browser")
        self.open_external_button.setFlat(True)
        self.open_external_button.setStyleSheet(FLAT_TEXT_BUTTON_STYLE)
        self.open_external_button.clicked.connect(self.open_external)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.status_label, 1)
        controls.addWidget(self.reload_button)
        controls.addWidget(self.open_external_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)

        self.web_view = None
        self.fallback_label = None
        if QWebEngineView is None:
            self.fallback_label = QLabel(
                "Embedded browser support is unavailable.\n\n"
                f"{self.embed_url}"
            )
            self.fallback_label.setWordWrap(True)
            self.status_label.setText("KaosGDD embed unavailable.")
            self.reload_button.setEnabled(False)
            layout.addWidget(self.fallback_label, 1)
            return

        self.web_view = QWebEngineView()
        self.web_view.setObjectName("kaosgddAgendaSuppliesWebView")
        self.web_view.loadStarted.connect(self._load_started)
        self.web_view.loadFinished.connect(self._load_finished)
        layout.addWidget(self.web_view, 1)

    def ensure_loaded(self) -> None:
        if self._load_requested:
            return
        self.reload()

    def reload(self) -> None:
        if self.web_view is None:
            return
        self._load_requested = True
        self.status_label.setText("Loading KaosGDD Agenda...")
        self.web_view.setUrl(QUrl(self.embed_url))

    def open_external(self) -> None:
        QDesktopServices.openUrl(QUrl(self.embed_url))

    def _load_started(self) -> None:
        self.status_label.setText("Loading KaosGDD Agenda...")

    def _load_finished(self, succeeded: bool) -> None:
        self.status_label.setText(
            "KaosGDD Agenda: embedded web view"
            if succeeded
            else "KaosGDD Agenda unavailable."
        )
