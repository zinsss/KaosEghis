import pytest

from conftest import (
    _is_windows_sandbox_identity,
    _skip_windows_sandbox_uia_integration,
)


@pytest.mark.parametrize(
    "username",
    [
        "WDAGUtilityAccount",
        "WORKGROUP\\WDAGUtilityAccount",
        "wdagutilityaccount",
    ],
)
def test_windows_sandbox_identity_is_recognized_on_windows(username):
    assert _is_windows_sandbox_identity("win32", username)


@pytest.mark.parametrize(
    "platform,username",
    [
        ("win32", "clinic\\operator"),
        ("win32", "WDAGUtilityAccount-other"),
        ("linux", "WDAGUtilityAccount"),
        ("darwin", "WORKGROUP\\WDAGUtilityAccount"),
        ("win32", ""),
        ("win32", None),
    ],
)
def test_windows_sandbox_identity_does_not_match_other_contexts(platform, username):
    assert not _is_windows_sandbox_identity(platform, username)
    _skip_windows_sandbox_uia_integration(platform, username)


def test_windows_sandbox_identity_skips_before_the_integration_test_body():
    with pytest.raises(pytest.skip.Exception, match="stable UIA identity"):
        _skip_windows_sandbox_uia_integration("win32", "WDAGUtilityAccount")
