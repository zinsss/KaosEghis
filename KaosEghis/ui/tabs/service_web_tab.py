from pathlib import Path

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


class ServiceWebTab(QWidget):
    def __init__(
        self,
        *,
        profile_name: str,
        setting_key: str,
        default_url: str,
        fallback_text: str,
        db_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self._setting_key = setting_key
        self._default_url = default_url

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if (
            QWebEngineView is None
            or QWebEnginePage is None
            or QWebEngineProfile is None
        ):
            fallback = QLabel(fallback_text)
            fallback.setMargin(12)
            layout.addWidget(fallback)
            return

        self.web_profile = QWebEngineProfile(profile_name, self)
        _configure_persistent_profile(self.web_profile, profile_name.lower())
        self.web_view = QWebEngineView()
        self.web_page = QWebEnginePage(self.web_profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.setUrl(QUrl(self._service_url()))
        layout.addWidget(self.web_view)

    def _service_url(self) -> str:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        return settings.get(self._setting_key, self._default_url) or self._default_url


def _configure_persistent_profile(profile, slug: str) -> None:
    profile_root = get_data_dir() / "web" / slug
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
