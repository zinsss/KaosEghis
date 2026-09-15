from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRectF, QUrl
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

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


_EMBEDDED_DARK_MENU_STYLE_SCRIPT = """
(() => {
    const styleId = "kaoseghis-embedded-menu-theme";
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
        html { color-scheme: dark !important; }
        select, select option, select optgroup {
            color-scheme: dark !important;
            color: #eceff4 !important;
            background-color: #2e3440 !important;
        }
        select {
            border-color: #4c566a !important;
        }
        select option:checked {
            background-color: #5e81ac !important;
            color: #eceff4 !important;
        }
    `;
    document.head.appendChild(style);
})();
"""


class _RoundedViewportMask(QObject):
    """Clip a web viewport because a parent stylesheet cannot clip WebEngine content."""

    def __init__(self, view: QWidget, radius: float = 6.0) -> None:
        super().__init__(view)
        self._view = view
        self._radius = radius

    def eventFilter(self, watched, event) -> bool:
        if watched is self._view and event.type() == QEvent.Type.Resize:
            self.apply()
        return super().eventFilter(watched, event)

    def apply(self) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(self._view.rect()), self._radius, self._radius)
        self._view.setMask(QRegion(path.toFillPolygon().toPolygon()))


class KaosGddWebPanel(QWidget):
    """Reusable KaosGDD browser surface with persistent local browser storage."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        viewport_width: int | None = None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self._loaded = False

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
        self.web_view.setObjectName("launcherKaosGddWebView")
        self.web_page = QWebEnginePage(self.web_profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.loadFinished.connect(self._apply_embedded_menu_theme)
        if viewport_width is None:
            layout.addWidget(self.web_view)
            return

        self.web_view.setFixedWidth(viewport_width)
        self._web_view_mask = _RoundedViewportMask(self.web_view)
        self.web_view.installEventFilter(self._web_view_mask)
        self._web_view_mask.apply()
        self.web_frame = QFrame()
        self.web_frame.setObjectName("launcherKaosGddFrame")
        self.web_frame.setFixedWidth(viewport_width + 2)
        frame_layout = QVBoxLayout(self.web_frame)
        # The frame's contents rect already excludes its one-pixel border.
        # Extra margins would let the fixed-width web view cover the right edge.
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self.web_view)

        centered_view = QHBoxLayout()
        centered_view.setContentsMargins(0, 0, 0, 0)
        centered_view.addStretch()
        centered_view.addWidget(self.web_frame)
        centered_view.addStretch()
        layout.addLayout(centered_view)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.load_page()

    def load_page(self) -> None:
        """Load only when the surface becomes visible, avoiding hidden startup traffic."""

        if self._loaded or not hasattr(self, "web_view"):
            return
        self._loaded = True
        self.web_view.setUrl(QUrl(_kaosgdd_url(self._db_path)))

    def _apply_embedded_menu_theme(self, loaded: bool) -> None:
        if loaded:
            self.web_page.runJavaScript(_EMBEDDED_DARK_MENU_STYLE_SCRIPT)


class KaosGddTab(KaosGddWebPanel):
    """Compatibility wrapper for the original full-page KaosGDD surface."""

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path)


def _kaosgdd_url(db_path: Path | None = None) -> str:
    initialize_database(db_path)
    with connect(db_path) as connection:
        settings = get_settings(connection)
    return settings.get("kaosgdd_url", DEFAULT_CONFIG.kaosgdd_url)


def _configure_persistent_profile(profile, _slug: str = "kaosgdd") -> None:
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
