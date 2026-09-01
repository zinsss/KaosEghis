from PySide6.QtCore import QEvent, QMargins
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QProxyStyle,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionToolButton,
    QToolButton,
)


def bracket_button_text(label: str) -> str:
    """Return the compact visual label used by application buttons."""

    stripped = label.strip()
    if stripped.startswith("[ ") and stripped.endswith(" ]"):
        return stripped
    return f"[ {stripped} ]" if stripped else ""


class KaosEghisProxyStyle(QProxyStyle):
    """Provide layout spacing and compact bracketed button labels."""

    LAYOUT_SPACING = 8

    def polish(self, target):
        polished = super().polish(target)
        if isinstance(target, (QPushButton, QToolButton)):
            self._apply_bracketed_label(target)
            target.installEventFilter(self)
            self._reserve_bracketed_label_width(target)
        return polished

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, (QPushButton, QToolButton))
            and event.type() in {QEvent.Type.Show, QEvent.Type.Paint}
        ):
            self._apply_bracketed_label(watched)
            self._reserve_bracketed_label_width(watched)
        return super().eventFilter(watched, event)

    def pixelMetric(self, metric, option=None, widget=None):
        if metric in {
            QStyle.PixelMetric.PM_LayoutHorizontalSpacing,
            QStyle.PixelMetric.PM_LayoutVerticalSpacing,
        }:
            return self.LAYOUT_SPACING
        return super().pixelMetric(metric, option, widget)

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_PushButtonLabel:
            if isinstance(widget, QPushButton):
                self._reserve_bracketed_label_width(widget)
            display_option = QStyleOptionButton(option)
            display_option.text = bracket_button_text(display_option.text)
            return super().drawControl(element, display_option, painter, widget)
        if element == QStyle.ControlElement.CE_ToolButtonLabel:
            if isinstance(widget, QToolButton):
                self._reserve_bracketed_label_width(widget)
            display_option = QStyleOptionToolButton(option)
            display_option.text = bracket_button_text(display_option.text)
            return super().drawControl(element, display_option, painter, widget)
        return super().drawControl(element, option, painter, widget)

    def sizeFromContents(self, contents_type, option, size, widget=None):
        display_option = option
        display_size = size
        if contents_type == QStyle.ContentsType.CT_PushButton:
            display_option = QStyleOptionButton(option)
            raw_text = display_option.text
            display_option.text = bracket_button_text(raw_text)
            display_size = size.grownBy(
                self._button_text_extra_margins(display_option, raw_text)
            )
        elif contents_type == QStyle.ContentsType.CT_ToolButton:
            display_option = QStyleOptionToolButton(option)
            raw_text = display_option.text
            display_option.text = bracket_button_text(raw_text)
            display_size = size.grownBy(
                self._button_text_extra_margins(display_option, raw_text)
            )
        return super().sizeFromContents(
            contents_type, display_option, display_size, widget
        )

    @staticmethod
    def _button_text_extra_margins(option, raw_text):
        extra_width = max(
            0,
            option.fontMetrics.horizontalAdvance(bracket_button_text(raw_text))
            - option.fontMetrics.horizontalAdvance(raw_text),
        )
        return QMargins(0, 0, extra_width, 0)

    @staticmethod
    def _reserve_bracketed_label_width(button: QAbstractButton) -> None:
        display_text = bracket_button_text(button.text())
        bold_font = QFont(button.font())
        bold_font.setBold(True)
        label_width = max(
            button.fontMetrics().horizontalAdvance(display_text),
            QFontMetrics(bold_font).horizontalAdvance(display_text),
        )
        button.setMinimumWidth(max(button.minimumWidth(), label_width + 6))

    @staticmethod
    def _apply_bracketed_label(button: QAbstractButton) -> None:
        display_text = bracket_button_text(button.text())
        if display_text != button.text():
            button.setText(display_text)


NORD_QSS = """
QMainWindow,
QDialog,
QWidget {
    background-color: #2e3440;
    color: #d8dee9;
    selection-background-color: #5e81ac;
    selection-color: #eceff4;
}

QWidget:disabled {
    color: #4c566a;
}

QTabWidget::pane {
    background-color: #2e3440;
    border: 1px solid #434c5e;
    top: -1px;
}

QTabBar::tab {
    background-color: #3b4252;
    color: #d8dee9;
    border: 1px solid #434c5e;
    border-bottom: none;
    padding: 8px 14px;
}

QTabBar::tab:selected {
    background-color: #434c5e;
    color: #88c0d0;
    border-color: #5e81ac;
}

QTabBar::tab:hover:!selected {
    background-color: #4c566a;
    color: #eceff4;
}

QWidget#appNotificationArea {
    background-color: transparent;
}

QLabel#appNotificationDot,
QLabel#appNotificationText {
    background-color: transparent;
    color: #a3b1c2;
}

QLabel#appNotificationDot[notificationTone="info"],
QLabel#appNotificationText[notificationTone="info"] {
    color: #88c0d0;
}

QLabel#appNotificationDot[notificationTone="success"],
QLabel#appNotificationText[notificationTone="success"] {
    color: #a3be8c;
}

QLabel#appNotificationDot[notificationTone="warning"],
QLabel#appNotificationText[notificationTone="warning"] {
    color: #ebcb8b;
}

QLabel#appNotificationDot[notificationTone="error"],
QLabel#appNotificationText[notificationTone="error"] {
    color: #bf616a;
}

QLabel#influenzaProgramResult {
    background-color: #3b4252;
    border: 1px solid #4c566a;
    padding: 8px;
}

QLabel#influenzaProgramResult[resultState="success"] {
    border-color: #a3be8c;
    color: #a3be8c;
}

QLabel#influenzaProgramResult[resultState="warning"] {
    border-color: #ebcb8b;
    color: #ebcb8b;
}

QLabel#influenzaProgramResult[resultState="error"] {
    border-color: #bf616a;
    color: #d8dee9;
}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QTimeEdit,
QDateTimeEdit {
    background-color: #3b4252;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 4px;
    padding: 5px 6px;
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QTimeEdit:focus,
QDateTimeEdit:focus {
    border-color: #88c0d0;
}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QDateEdit:disabled {
    background-color: #2e3440;
    color: #4c566a;
    border-color: #3b4252;
}

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button {
    background-color: transparent;
    border: none;
    width: 16px;
    subcontrol-origin: border;
}

QAbstractSpinBox::up-button {
    subcontrol-position: top right;
    border-left: 1px solid #434c5e;
    border-bottom: 1px solid #434c5e;
    border-top-right-radius: 4px;
}

QAbstractSpinBox::down-button {
    subcontrol-position: bottom right;
    border-left: 1px solid #434c5e;
    border-bottom-right-radius: 4px;
}

QAbstractSpinBox::up-button:hover,
QAbstractSpinBox::down-button:hover {
    background-color: #434c5e;
}

QAbstractSpinBox::up-button:pressed,
QAbstractSpinBox::down-button:pressed {
    background-color: #4c566a;
}

QComboBox::drop-down {
    background-color: #434c5e;
    border: none;
    border-left: 1px solid #4c566a;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #3b4252;
    color: #eceff4;
    border: 1px solid #5e81ac;
    selection-background-color: #5e81ac;
    selection-color: #eceff4;
    outline: none;
}

QPushButton,
QToolButton {
    background-color: transparent;
    color: #a3b1c2;
    border: none;
    outline: none;
    min-height: 18px;
    padding: 1px 3px;
    font-weight: 400;
}

QPushButton:hover,
QToolButton:hover {
    background-color: transparent;
    color: #eceff4;
}

QPushButton:pressed,
QToolButton:pressed {
    background-color: transparent;
    color: #81a1c1;
}

QPushButton:checked,
QPushButton[pageActive="true"],
QPushButton[filterActive="true"],
QToolButton:checked {
    background-color: transparent;
    color: #88c0d0;
    font-weight: 700;
}

QPushButton[emrConnectionState="connected"] {
    background-color: transparent;
    color: #a3be8c;
    font-weight: 700;
}

QPushButton[emrConnectionState="connected"]:hover {
    background-color: transparent;
    color: #b4cfa0;
}

QPushButton[emrConnectionState="stale"] {
    background-color: transparent;
    color: #d08770;
    font-weight: 700;
}

QPushButton[emrConnectionState="stale"]:hover {
    background-color: transparent;
    color: #dca08e;
}

QPushButton:disabled,
QToolButton:disabled {
    background-color: transparent;
    color: #4c566a;
}

QTableWidget,
QTableView,
QTreeWidget,
QTreeView,
QListWidget,
QListView {
    background-color: #2e3440;
    alternate-background-color: #3b4252;
    color: #d8dee9;
    gridline-color: #434c5e;
    border: 1px solid #434c5e;
    border-radius: 4px;
    selection-background-color: #5e81ac;
    selection-color: #eceff4;
    outline: none;
}

QTableWidget::item,
QTableView::item,
QTreeWidget::item,
QTreeView::item,
QListWidget::item,
QListView::item {
    padding: 4px;
}

QTableWidget::item:hover,
QTableView::item:hover,
QTreeWidget::item:hover,
QTreeView::item:hover,
QListWidget::item:hover,
QListView::item:hover {
    background-color: #434c5e;
}

QHeaderView::section {
    background-color: #3b4252;
    color: #e5e9f0;
    border: none;
    border-right: 1px solid #4c566a;
    border-bottom: 1px solid #4c566a;
    padding: 6px;
}

QTableCornerButton::section {
    background-color: #3b4252;
    border: none;
    border-right: 1px solid #4c566a;
    border-bottom: 1px solid #4c566a;
}

QLabel,
QCheckBox,
QRadioButton,
QGroupBox {
    color: #d8dee9;
}

QGroupBox {
    border: 1px solid #434c5e;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #88c0d0;
}

QCheckBox::indicator,
QRadioButton::indicator {
    width: 15px;
    height: 15px;
    background-color: #3b4252;
    border: 1px solid #4c566a;
}

QCheckBox::indicator {
    border-radius: 3px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:checked,
QRadioButton::indicator:checked {
    background-color: #88c0d0;
    border-color: #8fbcbb;
}

QMenuBar,
QMenu,
QStatusBar {
    background-color: #3b4252;
    color: #d8dee9;
}

QMenuBar::item:selected,
QMenu::item:selected {
    background-color: #5e81ac;
    color: #eceff4;
}

QMenu::separator {
    background-color: #4c566a;
    height: 1px;
    margin: 4px 8px;
}

QToolTip {
    background-color: #434c5e;
    color: #eceff4;
    border: 1px solid #88c0d0;
    padding: 4px;
}

QSplitter::handle {
    background-color: #434c5e;
}

QSplitter::handle:hover {
    background-color: #5e81ac;
}

QProgressBar {
    background-color: #3b4252;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 4px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #88c0d0;
    border-radius: 3px;
}

QScrollBar:vertical {
    background-color: #2e3440;
    border: none;
    width: 14px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background-color: #4c566a;
    border: 2px solid #2e3440;
    border-radius: 6px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5e81ac;
}

QScrollBar::handle:vertical:pressed {
    background-color: #81a1c1;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: none;
    border: none;
    height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background-color: #2e3440;
    border: none;
    height: 14px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background-color: #4c566a;
    border: 2px solid #2e3440;
    border-radius: 6px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #5e81ac;
}

QScrollBar::handle:horizontal:pressed {
    background-color: #81a1c1;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: none;
    border: none;
    width: 0px;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

QAbstractScrollArea::corner {
    background-color: #2e3440;
}
"""


def nord_stylesheet() -> str:
    return NORD_QSS


def apply_nord_theme(application: QApplication) -> None:
    application.setStyle(KaosEghisProxyStyle())
    application.setStyleSheet(nord_stylesheet())
