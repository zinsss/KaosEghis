from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget


class KaosClipTab(QWidget):
    """Future clipboard organizer surface."""

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("KaosClip")
        title.setObjectName("pluginTitle")

        description = QPlainTextEdit()
        description.setReadOnly(True)
        description.setPlainText(
            "KaosClip clipboard organizer is planned for a future PR.\n\n"
            "Expected scope:\n"
            "- Clipboard history\n"
            "- Favorites\n"
            "- Snippets\n"
            "- Search\n"
            "- Randomized clipboard presets"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(description)
