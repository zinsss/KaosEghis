from dataclasses import dataclass


@dataclass(frozen=True)
class UiTarget:
    target_id: str
    automation_id: str | None = None
    name: str | None = None
    control_type: str | None = None


def wait_for_target(_: UiTarget, timeout_seconds: float = 5.0) -> bool:
    raise NotImplementedError("UIA target waits are not implemented.")

