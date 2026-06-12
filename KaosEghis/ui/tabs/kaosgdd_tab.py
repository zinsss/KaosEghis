from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from KaosEghis.config import DEFAULT_CONFIG
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


class KaosGddTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl(_kaosgdd_url()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_view)


def _kaosgdd_url() -> str:
    initialize_database()
    with connect() as connection:
        settings = get_settings(connection)
    return settings.get("kaosgdd_url", DEFAULT_CONFIG.kaosgdd_url)
