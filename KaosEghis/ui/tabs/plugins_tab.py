from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from KaosEghis.ui.plugins.flu_panel import FluPanel
from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.plugins.weekly_visits_panel import WeeklyVisitsPanel


class PluginsTab(QWidget):
    """Dedicated tab for KaosEghis plugin workflows."""

    def __init__(self) -> None:
        super().__init__()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(PacsPanel())
        splitter.addWidget(_build_flu_group())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(splitter)


def _build_flu_group() -> QWidget:
    container = QWidget()
    title = QLabel("KaosEghis-flu statistics")
    title.setObjectName("pluginTitle")

    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(title)
    layout.addWidget(WeeklyVisitsPanel())
    layout.addWidget(FluPanel())
    return container
