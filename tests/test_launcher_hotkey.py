import ctypes
import ctypes.wintypes
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_windows_launcher_hotkey_uses_ctrl_alt_shift_f11() -> None:
    from KaosEghis.core.launcher_hotkey import _WindowsLauncherHotkeyListener

    events: list[str] = []

    class FakeApplication:
        def __init__(self) -> None:
            self.installed = []
            self.removed = []

        def installNativeEventFilter(self, event_filter) -> None:
            self.installed.append(event_filter)

        def removeNativeEventFilter(self, event_filter) -> None:
            self.removed.append(event_filter)

    class FakeUser32:
        def __init__(self) -> None:
            self.registered = []
            self.unregistered = []

        def RegisterHotKey(self, hwnd, hotkey_id, modifiers, virtual_key) -> bool:
            self.registered.append((hwnd, hotkey_id, modifiers, virtual_key))
            return True

        def UnregisterHotKey(self, hwnd, hotkey_id) -> bool:
            self.unregistered.append((hwnd, hotkey_id))
            return True

    application = FakeApplication()
    user32 = FakeUser32()
    listener = _WindowsLauncherHotkeyListener(
        lambda: events.append("launcher"),
        application=application,
        user32=user32,
    )

    assert listener.start() is True
    assert user32.registered == [
        (
            None,
            listener.HOTKEY_ID,
            listener.MOD_CONTROL
            | listener.MOD_ALT
            | listener.MOD_SHIFT
            | listener.MOD_NOREPEAT,
            listener.VK_F11,
        )
    ]

    message = ctypes.wintypes.MSG()
    message.message = listener.WM_HOTKEY
    message.wParam = listener.HOTKEY_ID
    handled, result = listener.nativeEventFilter(
        b"windows_dispatcher_MSG", ctypes.addressof(message)
    )

    assert handled is True
    assert result == 0
    assert events == ["launcher"]

    listener.stop()
    assert user32.unregistered == [(None, listener.HOTKEY_ID)]
    assert application.removed == [listener]
