from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MacroAction(str, Enum):
    TYPE_TEXT_KEYBOARD = "type_text_keyboard"
    TYPE_TEXT_CLIPBOARD = "type_text_clipboard"
    SET_TEXT_UIA = "set_text_uia"
    MOUSE_CLICK = "mouse_click"
    WAIT_FOR_TARGET = "wait_for_target"
    CHECK_PROCESS = "check_process"
    ACTIVATE_WINDOW = "activate_window"
    READ_TEXT_UIA = "read_text_uia"


@dataclass(frozen=True)
class MacroStep:
    action: MacroAction
    target_id: str | None = None
    value: str | None = None
    timeout_seconds: float = 5.0
    retries: int = 0
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MacroRunResult:
    success: bool
    message: str
    completed_steps: int = 0

