from PySide6.QtWidgets import QMainWindow, QTabWidget

from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab
from KaosEghis.ui.tabs.kaosclip_tab import KaosClipTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.plugins_tab import PluginsTab
from KaosEghis.ui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.resize(1180, 780)

        tabs = QTabWidget()
        tabs.addTab(KaosEghisTab(), "KaosEghis")
        tabs.addTab(KaosGddTab(), "KaosGdd")
        tabs.addTab(KaosClipTab(), "KaosClip")
        tabs.addTab(PluginsTab(), "Plugins")
        tabs.addTab(SettingsTab(), "Settings")

        self.setCentralWidget(tabs)
