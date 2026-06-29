from PySide6.QtWidgets import QMainWindow, QTabWidget

from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.vaccine_tab import VaccineTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.resize(1180, 780)

        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(KaosEghisTab(), "KaosEghis")
        tabs.addTab(KaosGddTab(), "KaosGdd")
        tabs.addTab(VaccineTab(), "Vaccine")
        tabs.addTab(PacsPanel(), "PACS")
        tabs.addTab(FluReportTab(), "Flu-Report")

        self.setCentralWidget(tabs)
