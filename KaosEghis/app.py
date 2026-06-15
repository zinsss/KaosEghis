from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import initialize_database
from KaosEghis.ui.main_window import MainWindow
from KaosEghis.ui.theme import catppuccin_mocha_stylesheet


def run() -> int:
    initialize_database()
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(catppuccin_mocha_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()
