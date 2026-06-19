from collections.abc import Sequence

from KaosEghis.core.eghis_connector import ensure_ready_for_macro
from KaosEghis.core.macro_models import MacroRunResult, MacroStep


class MacroRunner:
    def run(
        self,
        steps: Sequence[MacroStep],
        dry_run: bool = True,
        settings: dict[str, str] | None = None,
    ) -> MacroRunResult:
        if dry_run:
            return MacroRunResult(False, "Macro execution is blocked: dry-run stub only.", 0)
        if settings is None:
            return MacroRunResult(False, "Macro execution blocked: Eghis connector settings are required.", 0)
        state = ensure_ready_for_macro(settings)
        if state.status != "green":
            return MacroRunResult(False, f"Macro execution blocked: {state.message}", 0)
        raise NotImplementedError("Real macro execution is not implemented.")
