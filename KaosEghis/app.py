from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import initialize_database
from KaosEghis.service.kaospacs_api import start_server_in_thread
from KaosEghis.ui.main_window import MainWindow
from KaosEghis.ui.theme import nord_stylesheet


def run() -> int:
    initialize_database()
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(nord_stylesheet())
    patient_context_runtime = None
    try:
        patient_context_runtime = start_server_in_thread()
    except (OSError, RuntimeError):
        # The desktop remains usable if the optional LAN context API cannot bind.
        pass
    if patient_context_runtime is not None:
        app.aboutToQuit.connect(patient_context_runtime.stop)
    window = MainWindow()
    window.show()
    return app.exec()
