CATPPUCCIN_MOCHA_QSS = """
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
}

QTabBar::tab {
    background-color: #181825;
    color: #bac2de;
    border: 1px solid #313244;
    border-bottom: none;
    padding: 8px 14px;
}

QTabBar::tab:selected {
    background-color: #313244;
    color: #cba6f7;
}

QTabBar::tab:hover {
    background-color: #45475a;
    color: #cdd6f4;
}

QLineEdit,
QTextEdit,
QPlainTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus {
    border-color: #89b4fa;
}

QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 7px 12px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QPushButton:pressed {
    background-color: #181825;
    border-color: #cba6f7;
}

QPushButton:disabled {
    background-color: #181825;
    color: #6c7086;
    border-color: #313244;
}

QPushButton[connectionState="connected"] {
    background-color: #a6e3a1;
    color: #181825;
    border-color: #a6e3a1;
    font-weight: 600;
}

QPushButton[connectionState="stale"] {
    background-color: #f9e2af;
    color: #181825;
    border-color: #f38ba8;
    font-weight: 600;
}

QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QTableWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #313244;
    color: #bac2de;
    border: 1px solid #45475a;
    padding: 6px;
}

QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QLabel {
    color: #cdd6f4;
}

QComboBox,
QSpinBox,
QDoubleSpinBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px;
}

QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border-color: #89b4fa;
}

QCheckBox {
    color: #cdd6f4;
}

QScrollBar:vertical,
QScrollBar:horizontal {
    background-color: #181825;
    border: none;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {
    background-color: #89b4fa;
}
"""


def catppuccin_mocha_stylesheet() -> str:
    return CATPPUCCIN_MOCHA_QSS
