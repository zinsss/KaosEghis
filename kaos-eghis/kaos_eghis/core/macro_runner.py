from collections.abc import Sequence

from kaos_eghis.core.macro_models import MacroRunResult, MacroStep


class MacroRunner:
    def run(self, steps: Sequence[MacroStep], dry_run: bool = True) -> MacroRunResult:
        if dry_run:
            return MacroRunResult(False, "Macro execution is blocked: dry-run stub only.", 0)
        raise NotImplementedError("Real macro execution is not implemented.")

