from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from KaosEghis.db.database import get_data_dir


VAULT_FILENAME = "KaosEghis.pw.vault.json"
KDF_ITERATIONS = 600_000


class VaultError(RuntimeError):
    pass


class InvalidMasterPasswordError(VaultError):
    pass


@dataclass(frozen=True)
class CredentialEntry:
    service_name: str
    username: str
    password: str
    target_type: str = "external"
    notes: str = ""


class CredentialVaultSession:
    def __init__(self, vault: "CredentialVault", fernet: Fernet, payload: dict) -> None:
        self._vault = vault
        self._fernet = fernet
        self._payload = payload

    @property
    def is_initialized(self) -> bool:
        return True

    def list_entries(self) -> list[CredentialEntry]:
        entries = self._payload.get("entries", {})
        return [
            CredentialEntry(
                service_name=name,
                username=str(values.get("username", "")),
                password=str(values.get("password", "")),
                target_type=str(values.get("target_type", "external")),
                notes=str(values.get("notes", "")),
            )
            for name, values in sorted(entries.items())
        ]

    def get_entry(self, service_name: str) -> CredentialEntry | None:
        values = self._payload.get("entries", {}).get(service_name)
        if values is None:
            return None
        return CredentialEntry(
            service_name=service_name,
            username=str(values.get("username", "")),
            password=str(values.get("password", "")),
            target_type=str(values.get("target_type", "external")),
            notes=str(values.get("notes", "")),
        )

    def set_entry(
        self,
        *,
        service_name: str,
        username: str,
        password: str,
        target_type: str = "external",
        notes: str = "",
    ) -> None:
        normalized_name = service_name.strip()
        if not normalized_name:
            raise ValueError("Service name is required.")
        self._payload.setdefault("entries", {})[normalized_name] = {
            "username": username,
            "password": password,
            "target_type": target_type or "external",
            "notes": notes,
        }
        self.save()

    def delete_entry(self, service_name: str) -> bool:
        entries = self._payload.setdefault("entries", {})
        removed = entries.pop(service_name, None)
        if removed is not None:
            self.save()
            return True
        return False

    def save(self) -> None:
        encrypted = self._fernet.encrypt(
            json.dumps(self._payload, ensure_ascii=False).encode("utf-8")
        )
        document = self._vault._read_document()
        document["encrypted_payload"] = base64.b64encode(encrypted).decode("ascii")
        self._vault.path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class CredentialVault:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (get_data_dir() / VAULT_FILENAME)

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, master_password: str) -> CredentialVaultSession:
        if self.exists():
            raise VaultError("Credential vault already exists.")
        salt = self._new_salt()
        fernet = self._fernet_for_password(master_password, salt)
        payload = {"entries": {}}
        encrypted = fernet.encrypt(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )
        document = {
            "version": 1,
            "kdf": "pbkdf2-sha256",
            "iterations": KDF_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
            "encrypted_payload": base64.b64encode(encrypted).decode("ascii"),
        }
        self.path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return CredentialVaultSession(self, fernet, payload)

    def unlock(self, master_password: str) -> CredentialVaultSession:
        document = self._read_document()
        try:
            salt = base64.b64decode(document["salt"])
            encrypted_payload = base64.b64decode(document["encrypted_payload"])
        except Exception as error:
            raise VaultError(f"Credential vault is invalid: {error}") from error
        fernet = self._fernet_for_password(
            master_password,
            salt,
            iterations=int(document.get("iterations", KDF_ITERATIONS)),
        )
        try:
            decrypted = fernet.decrypt(encrypted_payload)
        except InvalidToken as error:
            raise InvalidMasterPasswordError("Master password is invalid.") from error
        payload = json.loads(decrypted.decode("utf-8"))
        return CredentialVaultSession(self, fernet, payload)

    def _read_document(self) -> dict:
        if not self.exists():
            raise VaultError("Credential vault is not initialized.")
        return json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def _new_salt() -> bytes:
        import secrets

        return secrets.token_bytes(16)

    @staticmethod
    def _fernet_for_password(
        master_password: str,
        salt: bytes,
        *,
        iterations: int = KDF_ITERATIONS,
    ) -> Fernet:
        if not master_password:
            raise ValueError("Master password is required.")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
        return Fernet(key)
