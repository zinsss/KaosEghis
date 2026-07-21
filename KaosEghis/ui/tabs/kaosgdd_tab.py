from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - depends on optional Qt WebEngine install
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineView = None

from KaosEghis.config import DEFAULT_CONFIG
from KaosEghis.db.database import connect, get_data_dir, initialize_database
from KaosEghis.db.repositories import get_settings


class KaosGddTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if (
            QWebEngineView is None
            or QWebEnginePage is None
            or QWebEngineProfile is None
        ):
            fallback = QLabel("KaosGdd webview not available.")
            fallback.setMargin(12)
            layout.addWidget(fallback)
            return

        self.web_profile = QWebEngineProfile("KaosGdd", self)
        _configure_persistent_profile(self.web_profile)
        self.web_view = QWebEngineView()
        self.web_page = QWebEnginePage(self.web_profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.setUrl(QUrl(_kaosgdd_url()))
        layout.addWidget(self.web_view)


def _kaosgdd_url() -> str:
    initialize_database()
    with connect() as connection:
        settings = get_settings(connection)
    return settings.get("kaosgdd_url", DEFAULT_CONFIG.kaosgdd_url)


def _configure_persistent_profile(profile) -> None:
    profile_root = get_data_dir() / "web" / "kaosgdd"
    storage_path = profile_root / "storage"
    cache_path = profile_root / "cache"
    storage_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    profile.setPersistentStoragePath(str(storage_path))
    profile.setCachePath(str(cache_path))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
