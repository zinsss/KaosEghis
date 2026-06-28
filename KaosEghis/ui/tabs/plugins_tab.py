from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from KaosEghis.ui.plugins.flu_panel import FluPanel
from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel


class PluginsTab(QWidget):
    """Dedicated tab for KaosEghis plugin workflows."""

    def __init__(self) -> None:
        super().__init__()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(PacsPanel())
        splitter.addWidget(WeeklyVisitsPanel())
        splitter.addWidget(FluPanel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(splitter)
