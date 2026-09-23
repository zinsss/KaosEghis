from pathlib import Path

from KaosEghis.config import DEFAULT_CONFIG
from KaosEghis.ui.tabs.service_web_tab import ServiceWebTab


class MemosTab(ServiceWebTab):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(
            profile_name="Memos",
            setting_key="memos_url",
            default_url=DEFAULT_CONFIG.memos_url,
            fallback_text="Memos webview not available.",
            db_path=db_path,
        )
