from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import random
import time

from KaosEghis.core.clipboard_service import copy_text, restore_clipboard
from KaosEghis.core.eghis_connector import (
    ensure_ready_for_macro,
    refresh_cached_eghis_state,
)
from KaosEghis.core.macro_models import MacroRunResult, MacroStep
from KaosEghis.core.uia_inspector import resolve_target_element
from KaosEghis.db.database import connect, get_database_path
from KaosEghis.db.repositories import get_item, get_settings, list_macro_steps


class MacroRunner:
    def __init__(self, db_path: Path | None = None) -> None:
        self._cancel_requested = False
        self._db_path = db_path
        self._current_settings: dict[str, str] | None = None

    def cancel(self) -> None:
        self._cancel_requested = True

    def reset_cancel(self) -> None:
        self._cancel_requested = False

    def execute_macro(
        self,
        item_id: int,
        dry_run: bool = False,
        settings: dict[str, str] | None = None,
    ) -> MacroRunResult:
        self.reset_cancel()
        with connect(self._db_path or get_database_path()) as connection:
            item = get_item(connection, item_id)
            if item is None:
                return MacroRunResult(False, "Macro not found.", 0, None)

            steps = [
                _db_macro_step_to_runtime_step(step)
                for step in list_macro_steps(connection, item_id)
            ]
            run_settings = settings or get_settings(connection)

        if not dry_run and not item.is_enabled:
            return MacroRunResult(False, "Macro execution blocked: macro is disabled.", 0, None)

        return self.run(
            steps,
            dry_run=dry_run,
            settings=run_settings,
        )

    def run(
        self,
        steps: Sequence[MacroStep],
        dry_run: bool = True,
        settings: dict[str, str] | None = None,
    ) -> MacroRunResult:
        self.reset_cancel()

        if dry_run:
            return self._build_dry_run_result(steps)
        if settings is None:
            return MacroRunResult(
                False,
                "Macro execution blocked: Eghis connector settings are required.",
                0,
                None,
            )

        state = ensure_ready_for_macro(settings)
        if state.status != "green":
            return MacroRunResult(
                False,
                f"Macro execution blocked: {state.message}",
                0,
                None,
            )

        executed_steps = 0
        self._current_settings = settings
        for step in steps:
            if self._cancel_requested:
                return MacroRunResult(
                    False, "Macro execution canceled.", executed_steps, executed_steps + 1
                )

            result = self._execute_step(step)
            if not result.success:
                failed_step = step.options.get("step_order")
                if not isinstance(failed_step, int):
                    failed_step = executed_steps + 1
                return MacroRunResult(
                    False,
                    result.message,
                    executed_steps,
                    failed_step,
                )

            executed_steps += 1
            if self._cancel_requested:
                return MacroRunResult(
                    False, "Macro execution canceled.", executed_steps, executed_steps + 1
                )

        return MacroRunResult(True, "Macro execution completed.", executed_steps, None)

    def _build_dry_run_result(self, steps: Sequence[MacroStep]) -> MacroRunResult:
        lines = ["Dry run only. Planned macro steps:"]
        for index, step in enumerate(steps, start=1):
            lines.append(self._dry_run_step_line(step, index))
        if not steps:
            lines.append("No steps defined.")
        lines.append("No actions executed.")
        return MacroRunResult(
            True,
            "\n".join(lines),
            len(steps),
            None,
        )

    def _execute_step(self, step: MacroStep) -> MacroRunResult:
        action = self._action_name(step)
        if action in {"delay_ms", "wait"}:
            return self._run_delay(step)
        if action == "focus_window":
            return self._run_focus_window(self._require_settings())
        if action == "wait_window":
            return self._run_wait_window(step, self._require_settings())
        if action == "wait_text_or_image":
            return MacroRunResult(False, "wait_text_or_image is not implemented yet.", 0, None)
        if action == "click":
            return self._run_click(step, self._require_settings())
        if action in {"hotkey", "key"}:
            return self._run_hotkey(step)
        if action in {"type_text", "type_text_keyboard"}:
            return self._run_type_text(step)
        if action in {"paste_text", "type_text_clipboard"}:
            return self._run_paste_text(step)
        if action == "preset_text":
            return self._run_preset_text(step, self._require_settings())
        return MacroRunResult(False, f"Unsupported macro action: {action}", 0, None)

    def _run_delay(self, step: MacroStep) -> MacroRunResult:
        milliseconds = step.options.get("ms", step.value)
        if isinstance(milliseconds, str):
            try:
                milliseconds = int(milliseconds)
            except ValueError:
                milliseconds = None
        if not isinstance(milliseconds, int) or milliseconds < 0:
            return MacroRunResult(
                False,
                "delay_ms action requires non-negative integer params['ms'].",
                0,
                None,
            )

        deadline = time.monotonic() + (milliseconds / 1000.0)
        while True:
            if self._cancel_requested:
                return MacroRunResult(False, "Macro execution canceled.", 0, None)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            time.sleep(min(0.05, remaining))
        return MacroRunResult(True, f"Delayed {milliseconds} ms.", 1, None)

    def _run_focus_window(self, settings: dict[str, str]) -> MacroRunResult:
        state = ensure_ready_for_macro(settings)
        if state.status != "green":
            return MacroRunResult(False, f"focus_window failed: {state.message}", 0, None)
        return MacroRunResult(True, "Focused configured Eghis window.", 1, None)

    def _run_wait_window(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        timeout_seconds = float(step.timeout_seconds or 0.0)
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            state = refresh_cached_eghis_state(settings)
            if state.window_found:
                return MacroRunResult(True, "Window found.", 1, None)
            if self._cancel_requested:
                return MacroRunResult(False, "Macro execution canceled.", 0, None)
            if time.monotonic() >= deadline:
                return MacroRunResult(False, "wait_window timed out.", 0, None)
            time.sleep(0.05)

    def _run_click(self, step: MacroStep, settings: dict[str, str]) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "click action requires target_id.", 0, None)
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        try:
            target.click_input()
        except Exception as error:
            return MacroRunResult(False, f"click action failed: {error}", 0, None)
        return MacroRunResult(True, f"Clicked target '{step.target_id}'.", 1, None)

    def _run_hotkey(self, step: MacroStep) -> MacroRunResult:
        key = step.options.get("key", step.value)
        if not isinstance(key, str) or not key:
            return MacroRunResult(False, "hotkey action requires string params['key'].", 0, None)
        try:
            from pywinauto.keyboard import send_keys

            send_keys(key)
        except Exception as error:
            return MacroRunResult(False, f"hotkey action failed: {error}", 0, None)
        return MacroRunResult(True, f"Sent hotkey: {key}", 1, None)

    def _run_type_text(self, step: MacroStep) -> MacroRunResult:
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "type_text action requires string text.", 0, None)
        try:
            from pywinauto.keyboard import send_keys

            send_keys(text)
        except Exception as error:
            return MacroRunResult(False, f"type_text action failed: {error}", 0, None)
        return MacroRunResult(True, "Typed text.", 1, None)

    def _run_paste_text(self, step: MacroStep) -> MacroRunResult:
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "paste_text action requires string text.", 0, None)

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
            return MacroRunResult(False, f"paste_text action failed: {error}", 0, None)

        try:
            restore_clipboard(snapshot)
        except Exception as error:
            return MacroRunResult(False, f"paste_text restore failed: {error}", 0, None)
        return MacroRunResult(True, "Pasted text.", 1, None)

    def _run_preset_text(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        reference = step.options.get("preset", step.value)
        if not isinstance(reference, str) or not reference.strip():
            return MacroRunResult(False, "preset_text action requires a preset reference.", 0, None)

        text = self._resolve_preset_text(reference.strip())
        if text is None:
            return MacroRunResult(False, f"preset_text action could not resolve preset '{reference}'.", 0, None)

        preset_step = MacroStep(
            action="paste_text",
            target_id=step.target_id,
            value=text,
            timeout_seconds=step.timeout_seconds,
            retries=step.retries,
            options={"text": text},
        )
        return self._run_paste_text(preset_step)

    def _resolve_preset_text(self, reference: str) -> str | None:
        with connect(self._db_path or get_database_path()) as connection:
            row = None
            if reference.isdigit():
                row = connection.execute(
                    """
                    SELECT id, name, item_type
                    FROM items
                    WHERE id = ? AND item_type IN ('clipboard', 'randomized_clipboard')
                    """,
                    (int(reference),),
                ).fetchone()
            if row is None:
                row = connection.execute(
                    """
                    SELECT id, name, item_type
                    FROM items
                    WHERE name = ? AND item_type IN ('clipboard', 'randomized_clipboard')
                    """,
                    (reference,),
                ).fetchone()
            if row is None:
                return None

            variants = [
                variant_row[0]
                for variant_row in connection.execute(
                    """
                    SELECT body
                    FROM clipboard_variants
                    WHERE item_id = ?
                    ORDER BY id
                    """,
                    (row[0],),
                ).fetchall()
            ]
            if not variants:
                return None
            if row[2] == "randomized_clipboard":
                return random.choice(variants)
            return variants[0]

    def _resolve_runtime_target(
        self, settings: dict[str, str], target_id: str
    ) -> tuple[object | None, str]:
        with connect(self._db_path or get_database_path()) as connection:
            target = connection.execute(
                """
                SELECT id, target_id, parent_target_id, parent_automation_id, automation_id,
                       name, control_type, class_name, created_at
                FROM ui_targets
                WHERE target_id = ?
                """,
                (target_id,),
            ).fetchone()
        if target is None:
            return None, f"UI target '{target_id}' is not registered."

        from KaosEghis.db.repositories import _ui_target_from_row

        element, _parent_found, message = resolve_target_element(
            settings, _ui_target_from_row(target)
        )
        if element is None:
            return None, message
        return element, "Target resolved."

    def _dry_run_step_line(self, step: MacroStep, index: int) -> str:
        action = self._action_name(step)
        display_order = step.options.get("step_order", index)
        target = f" target_id={step.target_id}" if step.target_id else ""

        if action in {"delay_ms", "wait"}:
            duration = step.options.get("ms", step.value)
            return f"{display_order}. delay_ms value={duration} (dry run only)"
        if action == "preset_text":
            return f"{display_order}. preset_text value={step.value} (dry run only)"
        if action == "wait_text_or_image":
            return f"{display_order}. wait_text_or_image{target} (placeholder, dry run only)"
        if action == "wait_window":
            return (
                f"{display_order}. wait_window timeout={step.timeout_seconds} "
                f"retries={step.retries} (dry run only)"
            )

        value = step.options.get("text") or step.options.get("key") or step.value
        value_text = f" value={value}" if value else ""
        return (
            f"{display_order}. {action}{target}{value_text} "
            f"timeout={step.timeout_seconds} retries={step.retries}"
        )

    @staticmethod
    def _action_name(step: MacroStep) -> str:
        action = step.action
        return action.value if hasattr(action, "value") else str(action)

    def _require_settings(self) -> dict[str, str]:
        if self._current_settings is None:
            raise RuntimeError("Macro execution blocked: Eghis connector settings are required.")
        return self._current_settings


def _db_macro_step_to_runtime_step(step) -> MacroStep:
    options: dict[str, object] = {"step_order": step.step_order}
    action = step.action
    if action in {"delay_ms", "wait_ms"} and step.value is not None:
        try:
            options["ms"] = int(step.value)
        except ValueError:
            options["ms"] = step.value
    if action in {"hotkey", "key"} and step.value is not None:
        options["key"] = step.value
    if action in {"type_text", "paste_text", "type_text_keyboard", "type_text_clipboard"} and step.value is not None:
        options["text"] = step.value
    if action == "preset_text" and step.value is not None:
        options["preset"] = step.value

    normalized_action = {
        "wait_ms": "delay_ms",
        "key": "hotkey",
        "type_text_keyboard": "type_text",
        "type_text_clipboard": "paste_text",
    }.get(action, action)

    return MacroStep(
        action=normalized_action,
        target_id=step.target_id,
        value=step.value,
        timeout_seconds=step.timeout_seconds,
        retries=step.retries,
        options=options,
    )
