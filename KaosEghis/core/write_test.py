from dataclasses import dataclass

from KaosEghis.core.uia_inspector import resolve_target_element
from KaosEghis.db.repositories import UiTargetRecord


@dataclass(frozen=True)
class WriteTestResult:
    success: bool
    message: str
    target_id: str
    method: str
    text_length: int
    focused: bool | None


def set_value_to_target_for_test(
    settings: dict[str, str], target: UiTargetRecord, text: str
) -> WriteTestResult:
    return _run_set_value_test(settings, target, text)


def set_edit_text_to_target_for_test(
    settings: dict[str, str], target: UiTargetRecord, text: str
) -> WriteTestResult:
    if not text.strip():
        return _failed_result(target, "set_edit_text", text, "Write test text is empty.")

    element, _parent_found, message = resolve_target_element(settings, target)
    if element is None:
        return _failed_result(target, "set_edit_text", text, message)

    focused = _try_focus_target(element)
    try:
        element.set_edit_text(text)
    except Exception as error:
        return WriteTestResult(
            success=False,
            message=f"set_edit_text test failed for target '{target.target_id}': {error}",
            target_id=target.target_id,
            method="set_edit_text",
            text_length=len(text),
            focused=focused,
        )

    return WriteTestResult(
        success=True,
        message=f"set_edit_text test wrote text to target '{target.target_id}'.",
        target_id=target.target_id,
        method="set_edit_text",
        text_length=len(text),
        focused=focused,
    )


def _run_set_value_test(
    settings: dict[str, str], target: UiTargetRecord, text: str
) -> WriteTestResult:
    if not text.strip():
        return _failed_result(target, "set_value", text, "Write test text is empty.")

    element, _parent_found, message = resolve_target_element(settings, target)
    if element is None:
        return _failed_result(target, "set_value", text, message)

    try:
        iface_value = element.iface_value
    except Exception as error:
        return _failed_result(
            target,
            "set_value",
            text,
            f"ValuePattern is not available for target '{target.target_id}': {error}",
        )

    if iface_value is None:
        return _failed_result(
            target,
            "set_value",
            text,
            f"ValuePattern is not available for target '{target.target_id}'.",
        )

    try:
        is_read_only = getattr(iface_value, "CurrentIsReadOnly", None)
    except Exception:
        is_read_only = None
    if is_read_only is True:
        return _failed_result(
            target,
            "set_value",
            text,
            f"ValuePattern target '{target.target_id}' is read-only.",
        )

    try:
        iface_value.SetValue(text)
    except Exception as error:
        return _failed_result(
            target,
            "set_value",
            text,
            f"SetValue test failed for target '{target.target_id}': {error}",
        )

    return WriteTestResult(
        success=True,
        message=f"SetValue test wrote text to target '{target.target_id}'.",
        target_id=target.target_id,
        method="set_value",
        text_length=len(text),
        focused=None,
    )


def _failed_result(
    target: UiTargetRecord, method: str, text: str, message: str
) -> WriteTestResult:
    return WriteTestResult(
        success=False,
        message=message,
        target_id=target.target_id,
        method=method,
        text_length=len(text),
        focused=None,
    )


def _try_focus_target(element: object) -> bool | None:
    try:
        element.set_focus()
    except Exception:
        return False
    return True
