from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import initialize_database
from KaosEghis.service.kaospacs_api import start_server_in_thread
from KaosEghis.ui.theme import apply_nord_theme


def run() -> int:
    initialize_database()
    app = QApplication.instance() or QApplication([])
    apply_nord_theme(app)

    # Qt establishes the Windows GUI thread as STA. Import automation modules
    # only afterward so they cannot initialize COM as MTA and disable OLE drag/drop.
    from KaosEghis.ui.main_window import MainWindow

    patient_context_runtime = None
    try:
        patient_context_runtime = start_server_in_thread()
    except (OSError, RuntimeError):
        # The desktop remains usable if the optional LAN context API cannot bind.
        pass
    if patient_context_runtime is not None:
        app.aboutToQuit.connect(patient_context_runtime.stop)
    window = MainWindow()
    window.initialize_runtime_services()
    window.prompt_startup_master_password()
    window.show()
    return app.exec()
