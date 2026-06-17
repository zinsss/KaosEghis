from dataclasses import dataclass
import time

from KaosEghis.core.clipboard_service import copy_text, restore_clipboard
from KaosEghis.core.uia_inspector import resolve_target_element
from KaosEghis.db.repositories import UiTargetRecord


@dataclass(frozen=True)
class PasteTestResult:
    success: bool
    message: str
    target_id: str
    pasted_text_length: int
    clipboard_restored: bool
    focused: bool | None


def paste_text_to_target_for_test(
    settings: dict[str, str], target: UiTargetRecord, text: str
) -> PasteTestResult:
    if not text.strip():
        return PasteTestResult(
            success=False,
            message="Paste test text is empty.",
            target_id=target.target_id,
            pasted_text_length=0,
            clipboard_restored=False,
            focused=None,
        )

    element, _parent_found, message = resolve_target_element(settings, target)
    if element is None:
        return PasteTestResult(
            success=False,
            message=message,
            target_id=target.target_id,
            pasted_text_length=len(text),
            clipboard_restored=False,
            focused=None,
        )

    focused, focus_message = _focus_target_for_paste(element)
    if not focused:
        return PasteTestResult(
            success=False,
            message=focus_message,
            target_id=target.target_id,
            pasted_text_length=len(text),
            clipboard_restored=False,
            focused=False,
        )

    snapshot = None
    clipboard_restored = False
    try:
        snapshot = copy_text(text)
        from pywinauto.keyboard import send_keys

        send_keys("^v")
        time.sleep(0.15)
    except Exception as error:
        message = f"Paste test failed after resolving target '{target.target_id}': {error}"
        if snapshot is not None:
            clipboard_restored = _try_restore_clipboard(snapshot)
        return PasteTestResult(
            success=False,
            message=message,
            target_id=target.target_id,
            pasted_text_length=len(text),
            clipboard_restored=clipboard_restored,
            focused=True,
        )

    if snapshot is not None:
        clipboard_restored = _try_restore_clipboard(snapshot)

    restore_message = (
        "Clipboard restored."
        if clipboard_restored
        else "Clipboard restore was not available."
    )
    return PasteTestResult(
        success=True,
        message=(
            f"Paste test sent Ctrl+V to target '{target.target_id}'. {restore_message}"
        ),
        target_id=target.target_id,
        pasted_text_length=len(text),
        clipboard_restored=clipboard_restored,
        focused=True,
    )


def _focus_target_for_paste(element: object) -> tuple[bool, str]:
    try:
        element.set_focus()
        return True, "Target focused for paste test."
    except Exception:
        pass

    try:
        element.click_input()
        return True, "Target clicked for paste test."
    except Exception as error:
        return False, f"Could not focus target for paste test: {error}"


def _try_restore_clipboard(snapshot: object) -> bool:
    try:
        restore_clipboard(snapshot)
    except Exception:
        return False
    return True
