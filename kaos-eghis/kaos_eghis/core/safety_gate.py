from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    reason: str


def block_not_implemented(action_name: str) -> SafetyResult:
    return SafetyResult(False, f"{action_name} is blocked: not implemented.")

