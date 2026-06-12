from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EghisAssistTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Eghis Assist")
        title.setObjectName("pageTitle")

        search = QLineEdit()
        search.setPlaceholderText("Search automation, clipboard presets, workflows...")

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Name", "Type", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setItem(0, 0, QTableWidgetItem(""))

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setPlaceholderText("Status and safety messages will appear here.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(search)
        layout.addWidget(table)
        layout.addWidget(log)

