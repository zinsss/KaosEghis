from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MacroAction(str, Enum):
    FOCUS_WINDOW = "focus_window"
    WAIT_WINDOW = "wait_window"
    WAIT_TEXT_OR_IMAGE = "wait_text_or_image"
    IS_READY_UIA = "is_ready_uia"
    CLICK = "click"
    PRESS = "press"
    HOTKEY = "hotkey"
    TYPE_TEXT = "type_text"
    COPY_TEXT = "copy_text"
    PASTE_TEXT = "paste_text"
    SET_TEXT = "set_text"
    PRESET_TEXT = "preset_text"
    WAIT = "wait"
    DELAY_MS = "delay_ms"


@dataclass(frozen=True)
class MacroStep:
    action: MacroAction | str
    target_id: str | None = None
    value: str | None = None
    timeout_seconds: float = 5.0
    retries: int = 0
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MacroRunResult:
    success: bool
    message: str
    executed_steps: int = 0
    failed_step: int | None = None

    @property
    def completed_steps(self) -> int:
        return self.executed_steps

