from PySide6.QtWidgets import QApplication

from KaosEghis.core.kaospacs_patient_context_api import (
    config_from_settings,
    start_patient_context_api,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings
from KaosEghis.ui.main_window import MainWindow
from KaosEghis.ui.theme import catppuccin_mocha_stylesheet


def run() -> int:
    initialize_database()
    with connect() as connection:
        settings = get_settings(connection)
    patient_context_api = start_patient_context_api(config_from_settings(settings))
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(catppuccin_mocha_stylesheet())
    window = MainWindow()
    window.show()
    try:
        return app.exec()
    finally:
        if patient_context_api is not None:
            patient_context_api.stop()
