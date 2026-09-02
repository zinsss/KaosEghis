from PySide6.QtWidgets import QApplication

from KaosEghis.ui.startup_splash import StartupSplash
from KaosEghis.ui.theme import apply_nord_theme


def run() -> int:
    app = QApplication.instance() or QApplication([])
    apply_nord_theme(app)
    splash = StartupSplash()
    splash.show()

    try:
        splash.set_status("Preparing local data...")
        from KaosEghis.db.database import initialize_database

        initialize_database()

        splash.set_status("Starting integrations...")
        from KaosEghis.service.kaospacs_api import start_server_in_thread

        patient_context_runtime = None
        try:
            patient_context_runtime = start_server_in_thread()
        except (OSError, RuntimeError):
            # The desktop remains usable if the optional LAN context API cannot bind.
            pass
        if patient_context_runtime is not None:
            app.aboutToQuit.connect(patient_context_runtime.stop)

        # Qt establishes the Windows GUI thread as STA. Import automation modules
        # only afterward so they cannot initialize COM as MTA and disable OLE drag/drop.
        splash.set_status("Building workspace...")
        from KaosEghis.ui.main_window import MainWindow

        window = MainWindow()
        splash.set_status("Starting runtime services...")
        window.initialize_runtime_services()
        window.show()
        app.processEvents()
        splash.finish(window)
        window.prompt_startup_master_password()
    except Exception:
        splash.close()
        raise

    return app.exec()
