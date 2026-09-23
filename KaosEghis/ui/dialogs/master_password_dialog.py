from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class MasterPasswordDialog(QDialog):
    def __init__(self, *, vault_exists: bool, parent=None) -> None:
        super().__init__(parent)
        self._vault_exists = vault_exists
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowTitle(
            "Unlock KaosEghis-pw" if vault_exists else "Create KaosEghis-pw"
        )

        self.message = QLabel(
            "Enter the master password for KaosEghis-pw."
            if vault_exists
            else "Create a master password for KaosEghis-pw."
        )
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.status_label = QLabel("")

        form = QFormLayout()
        form.addRow("Master password", self.password_input)
        if not vault_exists:
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow("Confirm", self.confirm_input)

        buttons = QDialogButtonBox()
        self.ok_button = buttons.addButton(
            "Unlock" if vault_exists else "Create",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.message)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addWidget(buttons)
        self.resize(420, 180)

    def password(self) -> str:
        return self.password_input.text()

    def _validate_and_accept(self) -> None:
        password = self.password_input.text()
        if not password:
            self.status_label.setText("Master password is required.")
            return
        if not self._vault_exists and password != self.confirm_input.text():
            self.status_label.setText("Master password confirmation does not match.")
            return
        self.accept()
