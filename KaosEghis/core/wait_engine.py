from dataclasses import dataclass
from enum import Enum
from time import monotonic, sleep

from KaosEghis.core.uia_inspector import UiaInspectionResult, inspect_target_readonly
from KaosEghis.db.repositories import UiTargetRecord


class WaitCondition(str, Enum):
    EXISTS = "exists"
    VISIBLE = "visible"
    ENABLED = "enabled"
    TEXT_NON_EMPTY = "text_non_empty"
    KEYBOARD_FOCUS = "keyboard_focus"


@dataclass(frozen=True)
class WaitResult:
    success: bool
    message: str
    target_id: str
    condition: str
    elapsed_ms: int
    attempts: int


def wait_for_target_condition(
    settings: dict[str, str],
    target: UiTargetRecord,
    condition: WaitCondition | str,
    timeout_ms: int = 5000,
    poll_ms: int = 200,
) -> WaitResult:
    condition_value = _condition_value(condition)
    timeout_ms = max(0, int(timeout_ms))
    poll_ms = max(1, int(poll_ms))
    start = monotonic()
    deadline = start + (timeout_ms / 1000)
    attempts = 0
    last_message = "Condition was not checked."

    while True:
        attempts += 1
        try:
            inspection = inspect_target_readonly(settings, target)
        except Exception as error:
            return _result(
                False,
                f"Wait failed safely: {error}",
                target.target_id,
                condition_value,
                start,
                attempts,
            )

        last_message = inspection.message
        if is_condition_satisfied(inspection, condition_value):
            return _result(
                True,
                f"Condition satisfied: {condition_value}.",
                target.target_id,
                condition_value,
                start,
                attempts,
            )

        if monotonic() >= deadline:
            break
        sleep(min(poll_ms / 1000, max(0, deadline - monotonic())))

    return _result(
        False,
        f"Timed out waiting for {condition_value}. Last inspection: {last_message}",
        target.target_id,
        condition_value,
        start,
        attempts,
    )


def is_condition_satisfied(
    inspection: UiaInspectionResult, condition: WaitCondition | str
) -> bool:
    condition_value = _condition_value(condition)
    if condition_value == WaitCondition.EXISTS.value:
        return inspection.found is True
    if condition_value == WaitCondition.VISIBLE.value:
        return inspection.found is True and inspection.is_visible is True
    if condition_value == WaitCondition.ENABLED.value:
        return inspection.found is True and inspection.is_enabled is True
    if condition_value == WaitCondition.TEXT_NON_EMPTY.value:
        return inspection.found is True and bool((inspection.text_value or "").strip())
    if condition_value == WaitCondition.KEYBOARD_FOCUS.value:
        return inspection.found is True and inspection.has_keyboard_focus is True
    raise ValueError(f"Unsupported wait condition: {condition_value}")


def _condition_value(condition: WaitCondition | str) -> str:
    if isinstance(condition, WaitCondition):
        return condition.value
    return str(condition)


def _result(
    success: bool,
    message: str,
    target_id: str,
    condition: str,
    start: float,
    attempts: int,
) -> WaitResult:
    return WaitResult(
        success=success,
        message=message,
        target_id=target_id,
        condition=condition,
        elapsed_ms=max(0, int((monotonic() - start) * 1000)),
        attempts=attempts,
    )
