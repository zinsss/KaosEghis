from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class VaccineTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Vaccine")
        title.setObjectName("pageTitle")

        status = QLabel("Status: planned plugin")
        description = QLabel(
            "Vaccine plugin is planned. No workflow is active yet."
        )
        description.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addWidget(description)
        layout.addStretch()
