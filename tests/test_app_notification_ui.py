from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStyle


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_notification_area_shows_colored_text_state() -> None:
    _app()

    from KaosEghis.ui.main_window import AppNotificationArea

    area = AppNotificationArea()
    area.show_message("Captured and copied", "success")

    assert area.text.text() == "Captured and copied"
    assert area.text.property("notificationTone") == "success"
    assert area.dot.property("notificationTone") == "success"


def test_shared_style_provides_button_layout_spacing() -> None:
    _app()

    from KaosEghis.ui.theme import KaosEghisProxyStyle

    style = KaosEghisProxyStyle()

    assert (
        style.pixelMetric(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)
        == style.LAYOUT_SPACING
    )
    assert (
        style.pixelMetric(QStyle.PixelMetric.PM_LayoutVerticalSpacing)
        == style.LAYOUT_SPACING
    )


def test_main_window_places_notification_in_tab_bar_corner(tmp_path, monkeypatch) -> None:
    _app()

    from PySide6.QtCore import Qt

    from KaosEghis.ui.main_window import MainWindow

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))
    window = MainWindow()

    assert (
        window.tabs.cornerWidget(Qt.Corner.TopRightCorner)
        is window.notification_area
    )

    window.macros_tab.emr_page.app_notification.emit(
        "Captured and copied", "success"
    )
    QApplication.processEvents()

    assert window.notification_area.text.text() == "Captured and copied"
    assert window.notification_area.text.property("notificationTone") == "success"
    window.close()
