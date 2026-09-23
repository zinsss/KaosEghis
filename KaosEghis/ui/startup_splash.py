from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen


class StartupSplash(QSplashScreen):
    WIDTH = 520
    HEIGHT = 240

    def __init__(self) -> None:
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(QColor("#2e3440"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(0, 0, 8, self.HEIGHT, QColor("#88c0d0"))

        title_font = QFont("Segoe UI", 28)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#eceff4"))
        painter.drawText(42, 76, "KaosEghis")

        subtitle_font = QFont("Segoe UI", 11)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#d8dee9"))
        painter.drawText(44, 112, "Clinical workspace")

        painter.setPen(QColor("#4c566a"))
        painter.drawLine(44, 142, self.WIDTH - 40, 142)
        painter.end()

        super().__init__(
            pixmap,
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("startupSplash")
        self.set_status("Starting...")

    def set_status(self, message: str) -> None:
        safe_message = " ".join(str(message).split()).strip() or "Starting..."
        self.showMessage(
            safe_message,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            QColor("#a3be8c"),
        )
        application = QApplication.instance()
        if application is not None:
            application.processEvents()
