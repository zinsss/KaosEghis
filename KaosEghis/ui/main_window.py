from PySide6.QtWidgets import QMainWindow, QTabWidget

from KaosEghis.ui.tabs.eghis_assist_tab import EghisAssistTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.resize(1180, 780)

        tabs = QTabWidget()
        tabs.addTab(EghisAssistTab(), "Eghis Assist")
        tabs.addTab(KaosGddTab(), "KaosGDD")
        tabs.addTab(SettingsTab(), "Settings")

        self.setCentralWidget(tabs)
