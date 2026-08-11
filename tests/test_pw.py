import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_credential_vault_create_and_unlock_roundtrip(tmp_path) -> None:
    from KaosEghis.core.credential_vault import CredentialVault

    vault = CredentialVault(tmp_path / "vault.json")

    session = vault.create("clinic-master")
    session.set_entry(
        service_name="Paperless",
        username="leejs",
        password="pw123!",
        target_type="embedded",
        notes="internal",
    )

    unlocked = vault.unlock("clinic-master")
    entry = unlocked.get_entry("Paperless")

    assert entry is not None
    assert entry.username == "leejs"
    assert entry.password == "pw123!"
    assert entry.target_type == "embedded"


def test_credential_vault_rejects_wrong_master_password(tmp_path) -> None:
    import pytest

    from KaosEghis.core.credential_vault import (
        CredentialVault,
        InvalidMasterPasswordError,
    )

    vault = CredentialVault(tmp_path / "vault.json")
    vault.create("correct-password")

    with pytest.raises(InvalidMasterPasswordError):
        vault.unlock("wrong-password")


def test_credential_vault_delete_entry_roundtrip(tmp_path) -> None:
    from KaosEghis.core.credential_vault import CredentialVault

    vault = CredentialVault(tmp_path / "vault.json")
    session = vault.create("clinic-master")
    session.set_entry(
        service_name="Paperless",
        username="leejs",
        password="pw123!",
    )

    assert session.delete_entry("Paperless") is True
    assert session.get_entry("Paperless") is None

    unlocked = vault.unlock("clinic-master")
    assert unlocked.get_entry("Paperless") is None


def test_pw_runtime_unlock_and_lock_transitions(tmp_path) -> None:
    _app()

    from KaosEghis.core.pw_runtime import PwRuntime

    runtime = PwRuntime()
    runtime.vault.path = tmp_path / "vault.json"

    success, message = runtime.initialize_or_unlock("clinic-master")
    assert success is True
    assert "unlocked" in message.lower()
    assert runtime.is_unlocked is True

    runtime.lock()
    assert runtime.is_unlocked is False


def test_main_window_has_hidden_pw_runtime() -> None:
    _app()

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    assert hasattr(window, "pw_runtime")


def test_master_password_dialog_is_application_modal_and_stays_on_top() -> None:
    _app()

    from PySide6.QtCore import Qt

    from KaosEghis.ui.dialogs.master_password_dialog import MasterPasswordDialog

    dialog = MasterPasswordDialog(vault_exists=True)

    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert (
        dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    ) == Qt.WindowType.WindowStaysOnTopHint


def test_credential_entry_dialog_exposes_delete_for_existing_entry() -> None:
    _app()

    from KaosEghis.core.credential_vault import CredentialEntry
    from KaosEghis.ui.dialogs.pw_popup_dialog import CredentialEntryDialog

    dialog = CredentialEntryDialog(
        entry=CredentialEntry(
            service_name="Paperless",
            username="leejs",
            password="pw123!",
        )
    )

    assert dialog.delete_button is not None
    assert dialog.delete_button.text() == "Delete"
