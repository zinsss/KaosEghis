from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from KaosEghis.db.repositories import PacsWorklistItemRecord


class PacsWorklistDialog(QDialog):
    STATUS_VALUES = ["active", "cancelled", "error"]

    def __init__(
        self,
        parent=None,
        item: PacsWorklistItemRecord | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PACS Worklist Row")

        self.patient_edit = QLineEdit(item.patient_name or "" if item else "")
        self.chart_no_edit = QLineEdit(item.chart_no or "" if item else "")
        self.study_edit = QLineEdit(item.study or "" if item else "")
        self.modality_edit = QLineEdit(item.modality or "" if item else "")
        self.requested_at_edit = QLineEdit(item.requested_at or "" if item else "")
        self.accession_edit = QLineEdit(item.accession_or_order_id or "" if item else "")
        self.status_combo = QComboBox()
        self.status_combo.addItems(self.STATUS_VALUES)
        default_status = item.status if item is not None else "active"
        if default_status not in self.STATUS_VALUES:
            self.status_combo.addItem(default_status)
        index = self.status_combo.findText(default_status)
        self.status_combo.setCurrentIndex(index if index >= 0 else 0)

        form = QFormLayout()
        form.addRow("Patient", self.patient_edit)
        form.addRow("Chart No", self.chart_no_edit)
        form.addRow("Study", self.study_edit)
        form.addRow("Modality", self.modality_edit)
        form.addRow("Requested At", self.requested_at_edit)
        form.addRow("Accession / Order ID", self.accession_edit)
        form.addRow("Status", self.status_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_form_data(self) -> dict[str, str]:
        return {
            "patient_name": self.patient_edit.text().strip(),
            "chart_no": self.chart_no_edit.text().strip(),
            "study": self.study_edit.text().strip(),
            "modality": self.modality_edit.text().strip(),
            "requested_at": self.requested_at_edit.text().strip(),
            "accession_or_order_id": self.accession_edit.text().strip(),
            "status": self.status_combo.currentText(),
        }

    def validate_form(self) -> str | None:
        payload = self.get_form_data()
        if not payload["accession_or_order_id"]:
            return "Accession / Order ID is required."
        if not payload["study"]:
            return "Study is required."
        if not payload["modality"]:
            return "Modality is required."
        return None

    def accept(self) -> None:
        validation_error = self.validate_form()
        if validation_error is not None:
            QMessageBox.warning(self, "Invalid PACS Worklist Row", validation_error)
            return
        super().accept()
