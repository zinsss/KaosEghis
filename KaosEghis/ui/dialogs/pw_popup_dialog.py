from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.credential_vault import CredentialEntry


class CredentialEntryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, entry: CredentialEntry | None = None) -> None:
        super().__init__(parent)
        self._delete_requested = False
        self.setWindowTitle("Credential Entry")
        self.service_name = QLineEdit(entry.service_name if entry else "")
        self.username = QLineEdit(entry.username if entry else "")
        self.password = QLineEdit(entry.password if entry else "")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.target_type = QComboBox()
        self.target_type.addItems(["external", "embedded"])
        if entry:
            index = max(0, self.target_type.findText(entry.target_type))
            self.target_type.setCurrentIndex(index)
        self.notes = QTextEdit(entry.notes if entry else "")

        form = QFormLayout()
        form.addRow("Service", self.service_name)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("Target type", self.target_type)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.delete_button: QPushButton | None = None
        if entry is not None:
            self.delete_button = buttons.addButton(
                "Delete",
                QDialogButtonBox.ButtonRole.DestructiveRole,
            )
            self.delete_button.clicked.connect(self._request_delete)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(420, 320)

    @property
    def delete_requested(self) -> bool:
        return self._delete_requested

    def values(self) -> CredentialEntry:
        return CredentialEntry(
            service_name=self.service_name.text().strip(),
            username=self.username.text(),
            password=self.password.text(),
            target_type=self.target_type.currentText(),
            notes=self.notes.toPlainText().strip(),
        )

    def _request_delete(self) -> None:
        service_name = self.service_name.text().strip()
        if not service_name:
            QMessageBox.warning(self, "KaosEghis-pw", "Service name is missing.")
            return
        confirmed = QMessageBox.question(
            self,
            "Delete Credential",
            f"Delete credential entry '{service_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._delete_requested = True
        self.accept()


class CredentialPopupDialog(QDialog):
    ACTION_TYPE_ID = "type_id"
    ACTION_TYPE_PASSWORD = "type_password"
    ACTION_TYPE_BOTH = "type_both"

    def __init__(self, entries: list[CredentialEntry], *, locked: bool, context_title: str, parent=None) -> None:
        super().__init__(parent)
        self.selected_action: str | None = None
        self.setWindowTitle("KaosEghis-pw")

        self.status_label = QLabel(
            "KaosEghis-pw is locked." if locked else "Select a service and action."
        )
        self.context_label = QLabel(
            f"Foreground window: {context_title}" if context_title else "Foreground window: (unknown)"
        )

        self.list_widget = QListWidget()
        for entry in entries:
            item = QListWidgetItem(entry.service_name)
            item.setData(256, entry.service_name)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

        self.manage_button = QPushButton("Manage")
        self.type_id_button = QPushButton("Type ID")
        self.type_password_button = QPushButton("Type Password")
        self.type_both_button = QPushButton("Type ID + Password")
        self.lock_button = QPushButton("Lock")
        self.cancel_button = QPushButton("Close")

        if locked:
            self.list_widget.setEnabled(False)
            self.type_id_button.setEnabled(False)
            self.type_password_button.setEnabled(False)
            self.type_both_button.setEnabled(False)
            self.lock_button.setEnabled(False)

        self.manage_button.clicked.connect(self._manage)
        self.type_id_button.clicked.connect(lambda: self._choose(self.ACTION_TYPE_ID))
        self.type_password_button.clicked.connect(lambda: self._choose(self.ACTION_TYPE_PASSWORD))
        self.type_both_button.clicked.connect(lambda: self._choose(self.ACTION_TYPE_BOTH))
        self.lock_button.clicked.connect(lambda: self._choose("lock"))
        self.cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.manage_button)
        buttons.addStretch()
        buttons.addWidget(self.type_id_button)
        buttons.addWidget(self.type_password_button)
        buttons.addWidget(self.type_both_button)
        buttons.addWidget(self.lock_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.context_label)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons)
        self.resize(560, 380)

    def selected_service_name(self) -> str | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        value = item.data(256)
        return value if isinstance(value, str) else None

    def _choose(self, action: str) -> None:
        if action != "lock" and not self.selected_service_name():
            QMessageBox.warning(self, "KaosEghis-pw", "Select a service first.")
            return
        self.selected_action = action
        self.accept()

    def _manage(self) -> None:
        self.selected_action = "manage"
        self.accept()
