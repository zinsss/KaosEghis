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
    background-color: #434c5e;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 4px;
    min-height: 24px;
    padding: 8px 12px;
}

QPushButton:hover,
QToolButton:hover {
    background-color: #4c566a;
    border-color: #88c0d0;
}

QPushButton:pressed,
QToolButton:pressed {
    background-color: #5e81ac;
    border-color: #81a1c1;
}

QPushButton:checked,
QPushButton[pageActive="true"],
QPushButton[filterActive="true"],
QToolButton:checked {
    background-color: #88c0d0;
    color: #2e3440;
    border-color: #8fbcbb;
}

QPushButton:disabled,
QToolButton:disabled {
    background-color: #2e3440;
    color: #4c566a;
    border-color: #3b4252;
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
