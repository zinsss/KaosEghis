import gc
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture(scope="session", autouse=True)
def windows_offscreen_fonts():
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM", "").split(":")[0] != "offscreen":
        yield
        return

    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # Windows' offscreen plugin may expose zero system fonts and measure missing-glyph boxes.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for filename in ("malgun.ttf", "malgunbd.ttf", "segoeui.ttf", "segoeuib.ttf"):
        if QFontDatabase.addApplicationFont(str(fonts / filename)) < 0:
            pytest.fail(f"Windows offscreen tests require system font: {filename}")
    yield app


@pytest.fixture(autouse=True)
def windows_offscreen_cleanup(windows_offscreen_fonts):
    yield
    if windows_offscreen_fonts is not None:
        from PySide6.QtCore import QCoreApplication, QEvent

        # Collect widget cycles on Qt's owner thread, not a later test's DB worker.
        gc.collect()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def isolated_network(monkeypatch):
    import socket

    loopback = {"127.0.0.1", "::1", "localhost"}
    test_ports = set()
    original_bind = socket.socket.bind
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_address_info = socket.getaddrinfo

    def bind(sock, address):
        if address[0] not in loopback or address[1] != 0:
            raise AssertionError("Tests may bind only ephemeral loopback listeners")
        result = original_bind(sock, address)
        test_ports.add(sock.getsockname()[1])
        return result

    def check(address):
        if address[0] not in loopback or address[1] not in test_ports:
            raise AssertionError("Tests must mock network access outside test-owned listeners")

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    def address_info(host, *args, **kwargs):
        if host not in loopback:
            raise AssertionError("Tests must mock non-loopback DNS lookup")
        return original_address_info(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "bind", bind)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", address_info)


@pytest.fixture(autouse=True)
def isolated_webengine_navigation(monkeypatch):
    # Qt WebEngine uses native networking, outside the Python socket guard.
    try:
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        return
    for widget in (QWebEnginePage, QWebEngineView):
        for method in ("load", "setUrl"):
            monkeypatch.setattr(widget, method, lambda *_a, **_k: None)


@pytest.fixture(autouse=True)
def simulated_pacs_health_for_ui(monkeypatch):
    from KaosEghis.ui.plugins import pacs_panel

    # Ordinary widget construction must not probe the clinic's real PACS service.
    # Health-behavior tests explicitly replace this default with their own fake.
    monkeypatch.setattr(pacs_panel, "check_kaospacs_health", lambda _settings: False)


@pytest.fixture(autouse=True)
def isolated_emr_database_boundary(monkeypatch):
    from KaosEghis.core import emr_read_queue

    # Tests must not take the running clinic app's named mutex or open a real DB.
    monkeypatch.setattr(emr_read_queue, "_mutex_name", f"Local\\KaosEghis-test-{uuid4().hex}")
    try:
        import psycopg2
    except ImportError:
        return

    def forbidden(*_args, **_kwargs):
        pytest.fail("Tests must provide a mocked EMR database connection")

    monkeypatch.setattr(psycopg2, "connect", forbidden)


@pytest.fixture(autouse=True)
def simulated_macro_desktop(monkeypatch):
    from KaosEghis.core import macro_runner

    # Macro tests provide simulated EMR state, independent of the operator's lock.
    # Desktop-guard tests explicitly replace this stub with their tested outcome.
    monkeypatch.setattr(macro_runner, "interactive_desktop_error", lambda: None)
    if sys.platform != "win32":
        return
    try:
        import pyautogui
    except ImportError:
        return

    # Keep the public keyboard/mouse API testable without sending OS input.
    for name in (
        "_keyDown", "_keyUp", "_click", "_mouseDown", "_mouseUp",
        "_moveTo", "_scroll", "_hscroll", "_vscroll",
    ):
        if hasattr(pyautogui.platformModule, name):
            monkeypatch.setattr(pyautogui.platformModule, name, lambda *_a, **_k: None)
