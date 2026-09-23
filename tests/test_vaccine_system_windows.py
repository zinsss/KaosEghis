from types import SimpleNamespace

import pytest

from KaosEghis.core.vaccine_system_launch import find_native_vaccine_windows


def windows_api(nodes):
    def enumerate_windows(callback, extra):
        for handle in nodes:
            callback(handle, extra)

    return SimpleNamespace(
        EnumWindows=enumerate_windows,
        IsWindowVisible=lambda handle: nodes[handle]["visible"],
        GetWindowText=lambda handle: nodes[handle]["title"],
        GetClassName=lambda handle: nodes[handle]["class_name"],
    )


@pytest.mark.parametrize("attribute,value", [
    ("title", "Other system"),
    ("class_name", "OtherClass"),
    ("visible", False),
])
def test_native_lookup_requires_visible_exact_title_and_class(attribute, value):
    matching = {"title": "Vaccine system", "class_name": "CyWindowClass", "visible": True}
    api = windows_api({101: matching, 102: matching | {attribute: value}})
    assert find_native_vaccine_windows(api, "Vaccine system", "CyWindowClass") == [101]


def test_native_lookup_returns_all_matches_for_caller_to_check_ambiguity():
    matching = {"title": "Vaccine system", "class_name": "CyWindowClass", "visible": True}
    api = windows_api({101: matching, 102: matching})
    assert find_native_vaccine_windows(api, "Vaccine system", "CyWindowClass") == [101, 102]


def test_native_lookup_handles_enumeration_failure():
    def fail(*_args):
        raise RuntimeError("unavailable")

    assert find_native_vaccine_windows(
        SimpleNamespace(EnumWindows=fail), "Vaccine system", "CyWindowClass"
    ) == []
