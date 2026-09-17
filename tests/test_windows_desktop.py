from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from KaosEghis.core import windows_desktop


@pytest.mark.parametrize("name", ["Default", "default"])
def test_default_input_desktop_is_available(monkeypatch, name):
    monkeypatch.setattr(windows_desktop, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(windows_desktop, "_input_desktop_name", lambda: name)
    assert windows_desktop.interactive_desktop_error() is None


@pytest.mark.parametrize("name", ["Winlogon", "Screen-saver", ""])
def test_other_input_desktops_block_without_switching(monkeypatch, name):
    monkeypatch.setattr(windows_desktop, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(windows_desktop, "_input_desktop_name", lambda: name)
    assert windows_desktop.interactive_desktop_error() == windows_desktop.DESKTOP_UNAVAILABLE_MESSAGE


def test_uninspectable_input_desktop_fails_closed(monkeypatch):
    monkeypatch.setattr(windows_desktop, "sys", SimpleNamespace(platform="win32"))

    def denied():
        raise OSError("private diagnostic details")

    monkeypatch.setattr(windows_desktop, "_input_desktop_name", denied)
    assert windows_desktop.interactive_desktop_error() == windows_desktop.DESKTOP_UNAVAILABLE_MESSAGE


def test_non_windows_does_not_call_windows_api(monkeypatch):
    monkeypatch.setattr(windows_desktop, "sys", SimpleNamespace(platform="linux"))
    probe = Mock(side_effect=AssertionError("Windows API called"))
    monkeypatch.setattr(windows_desktop, "_input_desktop_name", probe)
    assert windows_desktop.interactive_desktop_error() is None
    probe.assert_not_called()


@pytest.mark.parametrize("name_read_succeeds", [True, False])
def test_native_probe_closes_handle_and_only_reads(monkeypatch, name_read_succeeds):
    api = SimpleNamespace(
        OpenInputDesktop=Mock(return_value=731),
        GetUserObjectInformationW=Mock(),
        CloseDesktop=Mock(return_value=True),
    )

    def read_name(_handle, _index, output, _size, _needed):
        if not name_read_succeeds:
            raise OSError("cannot read name")
        output.value = "Default"
        return True

    api.GetUserObjectInformationW.side_effect = read_name
    monkeypatch.setattr(windows_desktop.ctypes, "WinDLL", lambda *_a, **_k: api, raising=False)
    if name_read_succeeds:
        assert windows_desktop._input_desktop_name() == "Default"
    else:
        with pytest.raises(OSError):
            windows_desktop._input_desktop_name()
    api.OpenInputDesktop.assert_called_once_with(0, False, 1)
    api.CloseDesktop.assert_called_once_with(731)
