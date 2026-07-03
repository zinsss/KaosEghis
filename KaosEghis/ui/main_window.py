from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMainWindow, QTabWidget

from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.vaccine_tab import VaccineTab


class MainWindow(QMainWindow):
    PACS_TAB_HEALTHY_COLOR = QColor("#cdd6f4")
    PACS_TAB_UNHEALTHY_COLOR = QColor("#f38ba8")

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.setFixedSize(1280, 875)

        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(KaosEghisTab(), "KaosEghis")
        tabs.addTab(KaosGddTab(), "KaosGdd")
        tabs.addTab(VaccineTab(), "Vaccine")
        self.pacs_panel = PacsPanel()
        self.pacs_tab_index = tabs.addTab(self.pacs_panel, "PACS")
        tabs.addTab(FluReportTab(), "Flu-Report")
        self.pacs_panel.health_state_changed.connect(self._update_pacs_tab_health)
        self._update_pacs_tab_health(self.pacs_panel.is_healthy, self.pacs_panel.health_reason)

        self.setCentralWidget(tabs)

    def _update_pacs_tab_health(self, healthy: bool, reason: str) -> None:
        color = self.PACS_TAB_HEALTHY_COLOR if healthy else self.PACS_TAB_UNHEALTHY_COLOR
        self.tabs.tabBar().setTabTextColor(self.pacs_tab_index, color)
        self.tabs.tabBar().setTabToolTip(self.pacs_tab_index, reason)
