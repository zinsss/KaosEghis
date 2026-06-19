from collections.abc import Sequence
import time

from KaosEghis.core.clipboard_service import copy_text, restore_clipboard
from KaosEghis.core.eghis_connector import ensure_ready_for_macro
from KaosEghis.core.macro_models import MacroRunResult, MacroStep


class MacroRunner:
    def __init__(self) -> None:
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

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

        executed_steps = 0
        for step in steps:
            if self._cancel_requested:
                return MacroRunResult(False, "Macro execution canceled.", executed_steps)

            result = self._execute_step(step)
            if not result.success:
                return MacroRunResult(False, result.message, executed_steps)

            executed_steps += 1
            if self._cancel_requested:
                return MacroRunResult(False, "Macro execution canceled.", executed_steps)

        return MacroRunResult(True, "Macro execution completed.", executed_steps)

    def _execute_step(self, step: MacroStep) -> MacroRunResult:
        action = self._action_name(step)
        if action == "wait":
            return self._run_wait(step)
        if action == "key":
            return self._run_key(step)
        if action == "paste_text":
            return self._run_paste_text(step)
        return MacroRunResult(False, f"Unsupported macro action: {action}", 0)

    def _run_wait(self, step: MacroStep) -> MacroRunResult:
        milliseconds = step.options.get("ms")
        if not isinstance(milliseconds, int) or milliseconds < 0:
            return MacroRunResult(False, "wait action requires non-negative integer params['ms'].", 0)
        time.sleep(milliseconds / 1000.0)
        return MacroRunResult(True, f"Waited {milliseconds} ms.", 1)

    def _run_key(self, step: MacroStep) -> MacroRunResult:
        key = step.options.get("key")
        if not isinstance(key, str) or not key:
            return MacroRunResult(False, "key action requires string params['key'].", 0)
        try:
            from pywinauto.keyboard import send_keys

            send_keys(key)
        except Exception as error:
            return MacroRunResult(False, f"key action failed: {error}", 0)
        return MacroRunResult(True, f"Sent key: {key}", 1)

    def _run_paste_text(self, step: MacroStep) -> MacroRunResult:
        text = step.options.get("text")
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "paste_text action requires string params['text'].", 0)

        snapshot = None
        try:
            snapshot = copy_text(text)
            from pywinauto.keyboard import send_keys

            send_keys("^v")
            time.sleep(0.15)
        except Exception as error:
            if snapshot is not None:
                try:
                    restore_clipboard(snapshot)
                except Exception:
                    pass
            return MacroRunResult(False, f"paste_text action failed: {error}", 0)

        try:
            restore_clipboard(snapshot)
        except Exception as error:
            return MacroRunResult(False, f"paste_text restore failed: {error}", 0)
        return MacroRunResult(True, "Pasted text.", 1)

    @staticmethod
    def _action_name(step: MacroStep) -> str:
        action = step.action
        return action.value if hasattr(action, "value") else str(action)
