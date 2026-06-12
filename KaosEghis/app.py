from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import initialize_database
from KaosEghis.ui.main_window import MainWindow


def run() -> int:
    initialize_database()
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
