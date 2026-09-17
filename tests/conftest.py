import sys

import pytest


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
