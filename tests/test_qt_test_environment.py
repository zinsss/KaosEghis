import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows offscreen font regression")
@pytest.mark.parametrize("family", ["Malgun Gothic", "Segoe UI"])
@pytest.mark.parametrize("bold", [False, True])
def test_offscreen_layout_uses_real_windows_fonts(windows_offscreen_fonts, family, bold):
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetricsF

    if windows_offscreen_fonts is None:
        pytest.skip("Not using the offscreen platform")
    assert family in QFontDatabase.families()
    font = QFont(family)
    font.setPixelSize(51)
    font.setBold(bold)
    assert QFontInfo(font).family() == family
    assert QFontInfo(font).bold() is bold
    metrics = QFontMetricsF(font)
    assert metrics.inFont("W")
    assert metrics.horizontalAdvance("WWW") > metrics.horizontalAdvance("iii")
    if family == "Malgun Gothic":
        assert all(metrics.inFontUcs4(ord(character)) for character in "\ub3c5\uac10\ubaa8\ub354\ub098")
