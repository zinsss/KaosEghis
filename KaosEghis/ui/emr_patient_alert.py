from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class EmrPatientAlertPopup(QDialog):
    def __init__(self) -> None:
        super().__init__(None)
        self.setObjectName("emrPatientAlertPopup")
        self.setWindowTitle("Important EMR note")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(520, 220)

        marker = QLabel("***")
        marker.setObjectName("emrPatientAlertMarker")
        marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message = QLabel("IMPORTANT PATIENT NOTE")
        message.setObjectName("emrPatientAlertTitle")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction = QLabel("Review the patient memo in EMR before proceeding.")
        instruction.setObjectName("emrPatientAlertInstruction")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(6)
        layout.addWidget(marker)
        layout.addWidget(message)
        layout.addWidget(instruction)

        self.setStyleSheet(
            """
            QDialog#emrPatientAlertPopup {
                background-color: #b00020;
                border: 3px solid #ffffff;
            }
            QLabel#emrPatientAlertMarker {
                color: #ffffff;
                font-size: 64px;
                font-weight: 800;
            }
            QLabel#emrPatientAlertTitle {
                color: #ffffff;
                font-size: 27px;
                font-weight: 800;
            }
            QLabel#emrPatientAlertInstruction {
                color: #ffffff;
                font-size: 17px;
                font-weight: 600;
            }
            """
        )

    def show_alert(self) -> None:
        self._move_to_top_right()
        self.show()
        self.raise_()

    def clear_alert(self) -> None:
        self.hide()

    def _move_to_top_right(self) -> None:
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 24, area.top() + 24)
