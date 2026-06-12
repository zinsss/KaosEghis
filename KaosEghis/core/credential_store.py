import keyring


SERVICE_NAME = "KaosEghis"


def get_password(reference_name: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, reference_name)


def set_password(reference_name: str, password: str) -> None:
    keyring.set_password(SERVICE_NAME, reference_name, password)


def delete_password(reference_name: str) -> None:
    keyring.delete_password(SERVICE_NAME, reference_name)

