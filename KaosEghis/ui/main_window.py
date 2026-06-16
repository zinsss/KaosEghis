from PySide6.QtWidgets import QMainWindow, QTabWidget

from KaosEghis.ui.tabs.eghis_assist_tab import MacrosTab
from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.resize(1180, 780)

        tabs = QTabWidget()
        tabs.addTab(KaosEghisTab(), "KaosEghis")
        tabs.addTab(KaosGddTab(), "KaosGDD")
        tabs.addTab(MacrosTab(), "Macros")
        tabs.addTab(SettingsTab(), "Settings")

        self.setCentralWidget(tabs)
