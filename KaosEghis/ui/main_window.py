from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QWidget,
)

from KaosEghis.core.scheduler import SchedulerRuntime
from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab
from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
from KaosEghis.ui.tabs.scan_tab import ScanTab
from KaosEghis.ui.tabs.scheduler_tab import SchedulerTab
from KaosEghis.ui.tabs.settings_tab import SettingsTab
from KaosEghis.ui.tabs.vaccine_tab import VaccineTab


class AppNotificationArea(QWidget):
    TONES = {"neutral", "info", "success", "warning", "error"}

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("appNotificationArea")
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.dot = QLabel("\u25cf")
        self.dot.setObjectName("appNotificationDot")
        self.text = QLabel("Ready")
        self.text.setObjectName("appNotificationText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 12, 0)
        layout.setSpacing(6)
        layout.addStretch()
        layout.addWidget(self.dot)
        layout.addWidget(self.text)

        self.show_message("Ready", "neutral")

    def show_message(self, message: str, tone: str = "info") -> None:
        safe_message = " ".join(str(message).split()).strip() or "Ready"
        safe_tone = tone if tone in self.TONES else "info"
        self.text.setText(safe_message)
        self.setToolTip(safe_message)
        for widget in (self.dot, self.text):
            widget.setProperty("notificationTone", safe_tone)
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class MainWindow(QMainWindow):
    PACS_TAB_HEALTHY_COLOR = QColor("#d8dee9")
    PACS_TAB_UNHEALTHY_COLOR = QColor("#bf616a")

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.setFixedSize(1438, 1194)

        tabs = QTabWidget()
        self.tabs = tabs
        self.notification_area = AppNotificationArea()
        tabs.setCornerWidget(
            self.notification_area, Qt.Corner.TopRightCorner
        )
        self.kaoseghis_tab = KaosEghisTab()
        self.scheduler_runtime = SchedulerRuntime(parent=self)
        tabs.addTab(self.kaoseghis_tab, "Macros")
        tabs.addTab(KaosGddTab(), "KaosGdd")
        tabs.addTab(VaccineTab(), "Vaccine")
        self.pacs_panel = PacsPanel()
        self.pacs_tab_index = tabs.addTab(self.pacs_panel, "PACS")
        tabs.addTab(FluReportTab(), "Flu-Report")
        tabs.addTab(ScanTab(), "Scan")
        self.scheduler_tab = SchedulerTab(runtime=self.scheduler_runtime)
        tabs.addTab(self.scheduler_tab, "Scheduler")
        tabs.addTab(SettingsTab(), "Settings")
        self.pacs_panel.health_state_changed.connect(self._update_pacs_tab_health)
        self.kaoseghis_tab.emr_page.app_notification.connect(
            self.show_notification
        )
        self.scheduler_runtime.notification_requested.connect(
            self.show_notification
        )
        self._update_pacs_tab_health(self.pacs_panel.is_healthy, self.pacs_panel.health_reason)

        self.setCentralWidget(tabs)
        self.scheduler_runtime.start()

    def show_notification(self, message: str, tone: str = "info") -> None:
        self.notification_area.show_message(message, tone)

    def _update_pacs_tab_health(self, healthy: bool, reason: str) -> None:
        color = self.PACS_TAB_HEALTHY_COLOR if healthy else self.PACS_TAB_UNHEALTHY_COLOR
        self.tabs.tabBar().setTabTextColor(self.pacs_tab_index, color)
        self.tabs.tabBar().setTabToolTip(self.pacs_tab_index, reason)

    def closeEvent(self, event) -> None:
        self.scheduler_runtime.stop()
        super().closeEvent(event)
