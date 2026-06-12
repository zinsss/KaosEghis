from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication


@dataclass
class ClipboardSnapshot:
    text: str


def copy_text(text: str) -> ClipboardSnapshot:
    clipboard = QGuiApplication.clipboard()
    snapshot = ClipboardSnapshot(clipboard.text())
    clipboard.setText(text)
    return snapshot


def restore_clipboard(snapshot: ClipboardSnapshot) -> None:
    QGuiApplication.clipboard().setText(snapshot.text)

