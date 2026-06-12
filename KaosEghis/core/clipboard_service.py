from dataclasses import dataclass


@dataclass
class ClipboardSnapshot:
    text: str


def copy_text(text: str) -> ClipboardSnapshot:
    from PySide6.QtGui import QGuiApplication

    clipboard = QGuiApplication.clipboard()
    snapshot = ClipboardSnapshot(clipboard.text())
    clipboard.setText(text)
    return snapshot


def restore_clipboard(snapshot: ClipboardSnapshot) -> None:
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText(snapshot.text)
