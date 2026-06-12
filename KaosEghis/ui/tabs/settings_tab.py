from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget

from KaosEghis.config import DEFAULT_CONFIG


class SettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        process_name = QLineEdit(DEFAULT_CONFIG.eghis_process_name)
        window_title = QLineEdit(DEFAULT_CONFIG.eghis_window_title_match)
        kaosgdd_url = QLineEdit(DEFAULT_CONFIG.kaosgdd_url)
        credential_ref = QLineEdit(DEFAULT_CONFIG.credential_reference_name)

        layout = QFormLayout(self)
        layout.addRow("Eghis process name", process_name)
        layout.addRow("Eghis window title match", window_title)
        layout.addRow("KaosGDD URL", kaosgdd_url)
        layout.addRow("Credential reference name", credential_ref)
