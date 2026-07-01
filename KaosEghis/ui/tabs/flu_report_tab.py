from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from KaosEghis.ui.plugins.flu_panel import FluPanel


class FluReportTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("KaosEghis-flu Report")
        title.setObjectName("pageTitle")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(FluPanel())
