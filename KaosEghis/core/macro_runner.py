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
from KaosEghis.db.repositories import (
    get_item,
    get_settings,
    list_macro_steps,
    resolve_macro_emr_target_profile,
)


class MacroRunner:
    def __init__(self, db_path: Path | None = None) -> None:
        self._cancel_requested = False
        self._db_path = db_path
        self._current_settings: dict[str, str] | None = None
        self._current_profile_name: str | None = None

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
            profile = resolve_macro_emr_target_profile(connection, item)

            steps = [
                _db_macro_step_to_runtime_step(step)
                for step in list_macro_steps(connection, item_id)
            ]
            run_settings = settings or get_settings(connection)
        self._current_profile_name = profile.name if profile is not None else None

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
                "window not ready",
                0,
                None,
            )

        state = ensure_ready_for_macro(settings)
        if state.status != "green":
            return MacroRunResult(
                False,
                state.message or "window not ready",
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
                sanitized_message = self._sanitize_failure_message(
                    self._action_name(step),
                    result.message,
                )
                return MacroRunResult(
                    False,
                    sanitized_message,
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
        profile_name = self._current_profile_name or "(No EMR profile)"
        lines = [
            f"Dry run only. Profile: {profile_name}",
            "Planned macro steps:",
        ]
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
            return MacroRunResult(False, "unsupported action", 0, None)
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
        return MacroRunResult(False, "unsupported action", 0, None)

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
                "unknown error",
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
            return MacroRunResult(False, state.message or "window not ready", 0, None)
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
                return MacroRunResult(False, "timeout", 0, None)
            time.sleep(0.05)

    def _run_click(self, step: MacroStep, settings: dict[str, str]) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        try:
            target.click_input()
        except Exception:
            return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Clicked target '{step.target_id}'.", 1, None)

    def _run_hotkey(self, step: MacroStep) -> MacroRunResult:
        key = step.options.get("key", step.value)
        if not isinstance(key, str) or not key:
            return MacroRunResult(False, "unknown error", 0, None)
        try:
            from pywinauto.keyboard import send_keys

            send_keys(key)
        except Exception:
            return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Sent hotkey: {key}", 1, None)

    def _run_type_text(self, step: MacroStep) -> MacroRunResult:
        if step.target_id:
            target_result = self._focus_runtime_target(step)
            if target_result is not None:
                return target_result
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "unknown error", 0, None)
        try:
            from pywinauto.keyboard import send_keys

            send_keys(text)
        except Exception:
            return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, "Typed text.", 1, None)

    def _run_paste_text(self, step: MacroStep) -> MacroRunResult:
        if step.target_id:
            target_result = self._focus_runtime_target(step)
            if target_result is not None:
                return target_result
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "clipboard failed", 0, None)

        snapshot = None
        try:
            snapshot = copy_text(text)
            from pywinauto.keyboard import send_keys

            send_keys("^v")
            time.sleep(0.15)
        except Exception:
            if snapshot is not None:
                try:
                    restore_clipboard(snapshot)
                except Exception:
                    pass
            return MacroRunResult(False, "input failed" if snapshot is not None else "clipboard failed", 0, None)

        try:
            restore_clipboard(snapshot)
        except Exception:
            return MacroRunResult(False, "clipboard failed", 0, None)
        return MacroRunResult(True, "Pasted text.", 1, None)

    def _run_preset_text(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        reference = step.options.get("preset", step.value)
        if not isinstance(reference, str) or not reference.strip():
            return MacroRunResult(False, "clipboard failed", 0, None)

        text = self._resolve_preset_text(reference.strip())
        if text is None:
            return MacroRunResult(False, "clipboard failed", 0, None)

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
            return None, "target not found"

        from KaosEghis.db.repositories import _ui_target_from_row

        element, _parent_found, message = resolve_target_element(
            settings, _ui_target_from_row(target)
        )
        if element is None:
            if "timed out" in message.casefold() or "timeout" in message.casefold():
                return None, "timeout"
            if "window" in message.casefold():
                return None, "window not ready"
            return None, "target not found"
        return element, "Target resolved."

    def _focus_runtime_target(self, step: MacroStep) -> MacroRunResult | None:
        if not step.target_id:
            return None
        settings = self._require_settings()
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        focused, focus_message = self._focus_target_element(target)
        if not focused:
            return MacroRunResult(False, focus_message, 0, None)
        return None

    @staticmethod
    def _focus_target_element(element: object) -> tuple[bool, str]:
        try:
            element.set_focus()
            return True, "Target focused."
        except Exception:
            pass
        try:
            element.click_input()
            return True, "Target clicked."
        except Exception:
            return False, "target not resolved"

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

    @staticmethod
    def _sanitize_failure_message(action: str, message: str) -> str:
        lowered = (message or "").strip().casefold()
        if lowered in {
            "target not found",
            "input failed",
            "clipboard failed",
            "window not ready",
            "timeout",
            "unsupported action",
            "unknown error",
            "macro execution canceled.",
        }:
            return message
        if "target" in lowered:
            return "target not found"
        if "window" in lowered or "focus" in lowered:
            return "window not ready"
        if "timeout" in lowered or "timed out" in lowered:
            return "timeout"
        if "clipboard" in lowered or "preset" in lowered:
            return "clipboard failed"
        if "unsupported" in lowered or action == "wait_text_or_image":
            return "unsupported action"
        if action in {"click", "hotkey", "key", "type_text", "paste_text"}:
            if "clipboard" in lowered and action == "paste_text":
                return "clipboard failed"
            return "input failed"
        return "unknown error"


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
