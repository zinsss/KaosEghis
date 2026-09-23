import os
import subprocess
import sys

import pytest


def test_app_import_does_not_initialize_pywinauto_before_qapplication() -> None:
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import KaosEghis.app; "
                "assert 'pywinauto.keyboard' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM apartment check")
def test_main_window_load_keeps_qt_gui_thread_sta() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    script = """
import ctypes
from PySide6.QtWidgets import QApplication

application = QApplication([])
from KaosEghis.ui.main_window import MainWindow

ole32 = ctypes.OleDLL('ole32')
apartment = ctypes.c_int(-1)
qualifier = ctypes.c_int(-1)
ole32.CoGetApartmentType(ctypes.byref(apartment), ctypes.byref(qualifier))
assert apartment.value in (0, 3), apartment.value
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
