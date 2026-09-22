from PySide6.QtWidgets import QApplication

from KaosEghis.core.startup_diagnostics import StartupDiagnostics
from KaosEghis.ui.startup_splash import StartupSplash
from KaosEghis.ui.theme import apply_nord_theme


def run() -> int:
    app = QApplication.instance() or QApplication([])
    apply_nord_theme(app)
    splash = StartupSplash()
    splash.show()
    diagnostics = StartupDiagnostics()

    def stage(message: str) -> None:
        diagnostics.stage(message)
        splash.set_status(message)

    try:
        stage("Preparing local data...")
        from KaosEghis.db.database import initialize_database

        initialize_database()

        stage("Starting integrations...")
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
        stage("Building workspace...")
        from KaosEghis.ui.main_window import MainWindow

        window = MainWindow()
        stage("Starting runtime services...")
        window.initialize_runtime_services()
        window.show()
        app.processEvents()
        splash.finish(window)
        diagnostics.close("ready")
        window.prompt_startup_master_password()
    except Exception as exc:
        diagnostics.close("failed:" + type(exc).__name__)
        splash.close()
        raise
    finally:
        diagnostics.close()

    return app.exec()
