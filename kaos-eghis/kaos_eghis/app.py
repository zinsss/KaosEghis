from PySide6.QtWidgets import QApplication

from kaos_eghis.ui.main_window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()

