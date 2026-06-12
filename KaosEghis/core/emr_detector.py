from KaosEghis.core.safety_gate import SafetyResult


def check_eghis_process(_: str) -> SafetyResult:
    return SafetyResult(False, "Eghis process detection is not implemented.")


def find_eghis_window(_: str) -> SafetyResult:
    return SafetyResult(False, "Eghis window detection is not implemented.")


def activate_eghis_window() -> SafetyResult:
    return SafetyResult(False, "Eghis window activation is not implemented.")
