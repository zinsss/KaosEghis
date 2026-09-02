import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_startup_splash_constructs_and_updates_safe_status() -> None:
    _app()

    from KaosEghis.ui.startup_splash import StartupSplash

    splash = StartupSplash()
    splash.set_status("  Building   workspace...  ")

    assert splash.pixmap().width() == StartupSplash.WIDTH
    assert splash.pixmap().height() == StartupSplash.HEIGHT
    assert splash.message() == "Building workspace..."


def test_startup_splash_blank_status_uses_safe_default() -> None:
    _app()

    from KaosEghis.ui.startup_splash import StartupSplash

    splash = StartupSplash()
    splash.set_status("   ")

    assert splash.message() == "Starting..."
