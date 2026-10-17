import gc
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Windows Sandbox runs pytest with ``python -I`` so ambient working-directory
# and PYTHONPATH entries cannot make the checkout importable.  Add only this
# reviewed source root before pytest imports test modules.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
repository_root = str(REPOSITORY_ROOT)
if repository_root not in sys.path:
    sys.path.insert(0, repository_root)


def _is_windows_sandbox_identity(platform, username):
    """Return true only for Windows Sandbox's documented local account."""
    if platform != "win32" or not isinstance(username, str):
        return False
    account = username.strip().replace("/", "\\").rsplit("\\", 1)[-1]
    return account.casefold() == "wdagutilityaccount"


def _current_windows_username():
    """Read the authenticated Windows username without environment data."""
    if sys.platform != "win32":
        return ""

    import ctypes
    from ctypes import wintypes

    size = wintypes.DWORD(0)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    get_username = advapi32.GetUserNameW
    get_username.argtypes = (wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    get_username.restype = wintypes.BOOL
    get_username(None, ctypes.byref(size))
    if size.value == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(size.value)
    if not get_username(buffer, ctypes.byref(size)):
        return ""
    return buffer.value


def _skip_windows_sandbox_uia_integration(platform, username):
    if _is_windows_sandbox_identity(platform, username):
        pytest.skip("Windows Sandbox does not expose stable UIA identity for synthetic controls")


@pytest.fixture
def skip_windows_sandbox_uia_integration():
    """Skip only real-control UIA integration unsupported by Windows Sandbox."""
    _skip_windows_sandbox_uia_integration(sys.platform, _current_windows_username())


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

        # Tests build independent windows, including Qt WebEngine views.  Closing
        # and deleting every surviving top-level widget on Qt's owner thread
        # prevents native objects from being torn down during interpreter exit.
        for widget in windows_offscreen_fonts.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        gc.collect()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        windows_offscreen_fonts.processEvents()
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
