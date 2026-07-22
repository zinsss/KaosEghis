from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import random
import time

from KaosEghis.core.clipboard_service import copy_text, restore_clipboard
from KaosEghis.core.eghis_connector import (
    build_connector_settings,
    ensure_cached_connection_ready,
    refresh_cached_eghis_state,
)
from KaosEghis.core.macro_models import MacroRunResult, MacroStep
from KaosEghis.core.uia_inspector import resolve_target_element, resolve_target_scope_element
from KaosEghis.core.wait_engine import WaitCondition, wait_for_target_condition
from KaosEghis.db.database import connect, get_database_path
from KaosEghis.db.repositories import (
    EmrUiTargetRecord,
    get_emr_target_profile,
    UiTargetRecord,
    get_emr_ui_target_by_key,
    get_item,
    get_settings,
    get_ui_target,
    list_macro_steps,
    resolve_macro_emr_target_profile,
)


@dataclass
class _RunMetrics:
    cache_hits: int = 0
    cache_misses: int = 0
    resolved_targets: int = 0


class MacroRunner:
    def __init__(self, db_path: Path | None = None) -> None:
        self._cancel_requested = False
        self._db_path = db_path
        self._current_settings: dict[str, str] | None = None
        self._current_profile_name: str | None = None
        self._current_profile_id: int | None = None
        self._connection_ready_confirmed = False
        self._resolved_target_cache: dict[tuple[int | None, str, str | None], object] = {}
        self._resolved_target_aliases: dict[str, tuple[int | None, str, str | None]] = {}
        self._run_metrics = _RunMetrics()

    def cancel(self) -> None:
        self._cancel_requested = True
        self._clear_resolved_target_cache()

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
            base_settings = settings or get_settings(connection)
            run_settings = self._build_execution_settings(base_settings, profile)
        self._current_profile_name = profile.name if profile is not None else None
        self._current_profile_id = profile.id if profile is not None else None

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
        self._start_run_state()

        if dry_run:
            return self._build_dry_run_result(steps)
        if settings is None:
            self._clear_resolved_target_cache()
            return MacroRunResult(
                False,
                "window not ready",
                0,
                None,
            )

        state = ensure_cached_connection_ready(settings)
        if state.status != "green":
            self._clear_resolved_target_cache()
            return MacroRunResult(
                False,
                state.message or "window not ready",
                0,
                None,
            )

        executed_steps = 0
        self._current_settings = settings
        self._connection_ready_confirmed = True
        for step in steps:
            if self._cancel_requested:
                self._clear_resolved_target_cache()
                return MacroRunResult(
                    False, "Macro execution canceled.", executed_steps, executed_steps + 1
                )

            result = self._execute_step_with_timing(step)
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
                self._clear_resolved_target_cache()
                return MacroRunResult(
                    False, "Macro execution canceled.", executed_steps, executed_steps + 1
                )

        return MacroRunResult(
            True,
            self._with_run_metrics("Macro execution completed."),
            executed_steps,
            None,
        )

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
        lines.append(self._metrics_text())
        lines.append("No actions executed.")
        return MacroRunResult(
            True,
            "\n".join(lines),
            len(steps),
            None,
        )

    def _execute_step_with_retries(self, step: MacroStep) -> MacroRunResult:
        attempts = max(int(step.retries or 0), 0) + 1
        last_result = MacroRunResult(False, "unknown error", 0, None)
        for attempt in range(attempts):
            last_result = self._execute_step(step)
            if last_result.success:
                return last_result
            if not self._should_retry_step(step, last_result.message, attempt, attempts):
                return last_result
            self._clear_resolved_target_cache()
        return last_result

    def _execute_step_with_timing(self, step: MacroStep) -> MacroRunResult:
        before_result = self._run_optional_step_wait(step)
        if not before_result.success:
            return before_result
        return self._execute_step_with_retries(step)

    def _run_optional_step_wait(
        self,
        step: MacroStep,
    ) -> MacroRunResult:
        if not step.options.get("wait_before_enabled", False):
            return MacroRunResult(True, "Optional wait disabled.", 0, None)
        milliseconds = step.options.get("wait_before_ms", 100)
        return self._wait_milliseconds(
            milliseconds,
            success_message="Waited before action.",
        )

    def _execute_step(self, step: MacroStep) -> MacroRunResult:
        action = self._action_name(step)
        if action in {"delay_ms", "wait"}:
            return self._run_delay(step)
        if action == "focus_window":
            return self._run_focus_window(self._require_settings())
        if action == "wait_window":
            return self._run_wait_window(step, self._require_settings())
        if action == "when_ready":
            return self._run_when_ready(step, self._require_settings())
        if action == "wait_text_or_image":
            return MacroRunResult(False, "unsupported action", 0, None)
        if action == "select":
            return self._run_select(step, self._require_settings())
        if action == "click":
            return self._run_click(step, self._require_settings())
        if action == "double_click":
            return self._run_double_click(step, self._require_settings())
        if action in {"hotkey", "key"}:
            return self._run_hotkey(step)
        if action in {"type_text", "type_text_keyboard"}:
            return self._run_type_text(step)
        if action in {"paste_text", "type_text_clipboard"}:
            return self._run_paste_text(step)
        if action == "set_text_uia":
            return self._run_set_text_uia(step, self._require_settings())
        if action == "set_edit_text":
            return self._run_set_edit_text(step, self._require_settings())
        if action == "preset_text":
            return self._run_preset_text(step, self._require_settings())
        return MacroRunResult(False, "unsupported action", 0, None)

    def _run_delay(self, step: MacroStep) -> MacroRunResult:
        milliseconds = step.options.get("ms", step.value)
        return self._wait_milliseconds(milliseconds)

    def _wait_milliseconds(
        self,
        milliseconds: object,
        *,
        success_message: str | None = None,
    ) -> MacroRunResult:
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
        return MacroRunResult(
            True,
            success_message or f"Delayed {milliseconds} ms.",
            1,
            None,
        )

    def _run_focus_window(self, settings: dict[str, str]) -> MacroRunResult:
        if self._connection_ready_confirmed and self._current_settings == settings:
            return MacroRunResult(True, "Focused configured Eghis window.", 1, None)
        state = ensure_cached_connection_ready(settings)
        if state.status != "green":
            self._clear_resolved_target_cache()
            return MacroRunResult(False, state.message or "window not ready", 0, None)
        self._connection_ready_confirmed = True
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
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "Macro execution canceled.", 0, None)
            if time.monotonic() >= deadline:
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "timeout", 0, None)
            time.sleep(0.05)

    def _run_when_ready(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        with connect(self._db_path or get_database_path()) as connection:
            target_record, _cache_key = self._load_runtime_target_record(
                connection, step.target_id
            )
        if target_record is None:
            return MacroRunResult(False, "target not found", 0, None)

        result = wait_for_target_condition(
            settings,
            target_record,
            WaitCondition.KEYBOARD_FOCUS,
            timeout_ms=max(0, int(float(step.timeout_seconds or 0.0) * 1000)),
            poll_ms=100,
        )
        if not result.success:
            if "timed out" in result.message.casefold():
                return MacroRunResult(False, "timeout", 0, None)
            return MacroRunResult(False, "window not ready", 0, None)
        return MacroRunResult(
            True,
            f"Target '{step.target_id}' is ready.",
            1,
            None,
        )

    def _run_click(self, step: MacroStep, settings: dict[str, str]) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        clicked = self._activate_target_element(target)
        if not clicked:
            self._clear_resolved_target_cache()
            target, resolve_message = self._resolve_runtime_target(
                settings,
                step.target_id,
                force_refresh=True,
            )
            if target is None:
                return MacroRunResult(False, resolve_message, 0, None)
            clicked = self._activate_target_element(target)
            if not clicked:
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Clicked target '{step.target_id}'.", 1, None)

    def _run_select(self, step: MacroStep, settings: dict[str, str]) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        with connect(self._db_path or get_database_path()) as connection:
            target_record, _cache_key = self._load_runtime_target_record(
                connection, step.target_id
            )
        if target_record is not None:
            fast_selected = self._select_from_parent_scope(settings, target_record)
            if fast_selected:
                return MacroRunResult(True, f"Selected target '{step.target_id}'.", 1, None)
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        selected = self._select_target_element(target)
        if not selected:
            self._clear_resolved_target_cache()
            target, resolve_message = self._resolve_runtime_target(
                settings,
                step.target_id,
                force_refresh=True,
            )
            if target is None:
                return MacroRunResult(False, resolve_message, 0, None)
            selected = self._select_target_element(target)
            if not selected:
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Selected target '{step.target_id}'.", 1, None)

    def _run_double_click(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        clicked = self._double_activate_target_element(target)
        if not clicked:
            self._clear_resolved_target_cache()
            target, resolve_message = self._resolve_runtime_target(
                settings,
                step.target_id,
                force_refresh=True,
            )
            if target is None:
                return MacroRunResult(False, resolve_message, 0, None)
            clicked = self._double_activate_target_element(target)
            if not clicked:
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Double-clicked target '{step.target_id}'.", 1, None)

    def _run_hotkey(self, step: MacroStep) -> MacroRunResult:
        key = step.options.get("key", step.value)
        if not isinstance(key, str) or not key:
            return MacroRunResult(False, "unknown error", 0, None)
        try:
            self._send_hotkey_sequence(key)
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
        if not self._send_text_direct(
            text,
            press_enter_before=step.options.get("press_enter_before", False),
            press_enter_after=step.options.get("press_enter_after", False),
        ):
            return MacroRunResult(False, "input failed", 0, None)
        if step.options.get("press_enter_before", False) and step.options.get("press_enter_after", False):
            return MacroRunResult(True, "Pressed Enter, typed text, and pressed Enter.", 1, None)
        if step.options.get("press_enter_before", False):
            return MacroRunResult(True, "Pressed Enter and typed text.", 1, None)
        if step.options.get("press_enter_after", False):
            return MacroRunResult(True, "Typed text and pressed Enter.", 1, None)
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
            self._send_clipboard_paste(
                press_enter_before=step.options.get("press_enter_before", False),
                press_enter_after=step.options.get("press_enter_after", False),
            )
        except Exception:
            if snapshot is not None:
                try:
                    restore_clipboard(snapshot)
                except Exception:
                    pass
            if self._send_text_direct(
                text,
                press_enter_before=step.options.get("press_enter_before", False),
                press_enter_after=step.options.get("press_enter_after", False),
            ):
                return MacroRunResult(True, self._text_action_success_message(step, pasted=False), 1, None)
            return MacroRunResult(False, "input failed" if snapshot is not None else "clipboard failed", 0, None)

        try:
            restore_clipboard(snapshot)
        except Exception:
            return MacroRunResult(True, self._text_action_success_message(step, pasted=True), 1, None)
        return MacroRunResult(True, self._text_action_success_message(step, pasted=True), 1, None)

    def _run_preset_text(
        self,
        step: MacroStep,
        _settings: dict[str, str],
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
            options={
                "text": text,
                "press_enter_before": step.options.get("press_enter_before", False),
                "press_enter_after": step.options.get("press_enter_after", False),
            },
        )
        return self._run_paste_text(preset_step)

    def _run_set_text_uia(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "input failed", 0, None)

        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)

        if self._set_text_uia_on_element(target, text):
            return MacroRunResult(True, f"Set text on target '{step.target_id}'.", 1, None)

        self._clear_resolved_target_cache()
        target, resolve_message = self._resolve_runtime_target(
            settings,
            step.target_id,
            force_refresh=True,
        )
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        if not self._set_text_uia_on_element(target, text):
            self._clear_resolved_target_cache()
            return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Set text on target '{step.target_id}'.", 1, None)

    def _run_set_edit_text(
        self,
        step: MacroStep,
        settings: dict[str, str],
    ) -> MacroRunResult:
        if not step.target_id:
            return MacroRunResult(False, "target not found", 0, None)
        text = step.options.get("text", step.value)
        if not isinstance(text, str) or not text:
            return MacroRunResult(False, "input failed", 0, None)

        target, resolve_message = self._resolve_runtime_target(settings, step.target_id)
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)

        if self._set_edit_text_on_element(
            target,
            text,
            press_enter_before=step.options.get("press_enter_before", False),
            press_enter_after=step.options.get("press_enter_after", False),
        ):
            return MacroRunResult(True, f"Set edit text on target '{step.target_id}'.", 1, None)

        self._clear_resolved_target_cache()
        target, resolve_message = self._resolve_runtime_target(
            settings,
            step.target_id,
            force_refresh=True,
        )
        if target is None:
            return MacroRunResult(False, resolve_message, 0, None)
        if not self._set_edit_text_on_element(
            target,
            text,
            press_enter_before=step.options.get("press_enter_before", False),
            press_enter_after=step.options.get("press_enter_after", False),
        ):
            self._clear_resolved_target_cache()
            return MacroRunResult(False, "input failed", 0, None)
        return MacroRunResult(True, f"Set edit text on target '{step.target_id}'.", 1, None)

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
            if row is None and reference.endswith(" (random)"):
                row = connection.execute(
                    """
                    SELECT id, name, item_type
                    FROM items
                    WHERE name = ? AND item_type = 'randomized_clipboard'
                    """,
                    (reference.removesuffix(" (random)").strip(),),
                ).fetchone()
            if row is None and reference.endswith(" (copy)"):
                row = connection.execute(
                    """
                    SELECT id, name, item_type
                    FROM items
                    WHERE name = ? AND item_type = 'clipboard'
                    """,
                    (reference.removesuffix(" (copy)").strip(),),
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

    @staticmethod
    def _send_clipboard_paste(
        *,
        press_enter_before: bool = False,
        press_enter_after: bool = False,
    ) -> None:
        from pywinauto.keyboard import send_keys

        if press_enter_before:
            send_keys("{ENTER}")
        time.sleep(0.05)
        send_keys("^v")
        time.sleep(0.15)
        if press_enter_after:
            send_keys("{ENTER}")

    @staticmethod
    def _send_text_direct(
        text: str,
        *,
        press_enter_before: bool = False,
        press_enter_after: bool = False,
    ) -> bool:
        try:
            from pywinauto.keyboard import send_keys

            if press_enter_before:
                send_keys("{ENTER}")
            send_keys(text)
            if press_enter_after:
                send_keys("{ENTER}")
        except Exception:
            return False
        return True

    @staticmethod
    def _set_text_uia_on_element(element: object, text: str) -> bool:
        try:
            iface_value = element.iface_value
        except Exception:
            return False
        if iface_value is None:
            return False
        try:
            is_read_only = getattr(iface_value, "CurrentIsReadOnly", None)
        except Exception:
            is_read_only = None
        if is_read_only is True:
            return False
        try:
            iface_value.SetValue(text)
        except Exception:
            return False
        return True

    @staticmethod
    def _set_edit_text_on_element(
        element: object,
        text: str,
        *,
        press_enter_before: bool = False,
        press_enter_after: bool = False,
    ) -> bool:
        try:
            element.set_focus()
        except Exception:
            pass
        try:
            if press_enter_before:
                from pywinauto.keyboard import send_keys

                send_keys("{ENTER}")
            element.set_edit_text(text)
            if press_enter_after:
                from pywinauto.keyboard import send_keys

                send_keys("{ENTER}")
        except Exception:
            return False
        return True

    @staticmethod
    def _send_hotkey_sequence(key: str) -> None:
        from pywinauto.keyboard import send_keys

        for segment in [part.strip() for part in key.split(",") if part.strip()]:
            send_keys(_normalize_hotkey_segment(segment))

    @staticmethod
    def _text_action_success_message(step: MacroStep, *, pasted: bool) -> str:
        action_word = "Pasted text" if pasted else "Typed text"
        before = bool(step.options.get("press_enter_before", False))
        after = bool(step.options.get("press_enter_after", False))
        if before and after:
            return f"Pressed Enter, {action_word.lower()}, and pressed Enter."
        if before:
            return f"Pressed Enter and {action_word.lower()}."
        if after:
            return f"{action_word} and pressed Enter."
        return f"{action_word}."

    def _resolve_runtime_target(
        self, settings: dict[str, str], target_id: str, force_refresh: bool = False
    ) -> tuple[object | None, str]:
        if not force_refresh:
            cache_key = self._resolved_target_aliases.get(target_id)
            if cache_key is not None and cache_key in self._resolved_target_cache:
                self._run_metrics.cache_hits += 1
                return self._resolved_target_cache[cache_key], "Target resolved."
        self._run_metrics.cache_misses += 1
        with connect(self._db_path or get_database_path()) as connection:
            target_record, cache_key = self._load_runtime_target_record(connection, target_id)
        if target_record is None or cache_key is None:
            self._clear_resolved_target_cache()
            return None, "target not found"
        if not force_refresh and cache_key in self._resolved_target_cache:
            self._resolved_target_aliases[target_id] = cache_key
            self._run_metrics.cache_hits += 1
            return self._resolved_target_cache[cache_key], "Target resolved."
        element, _parent_found, message = resolve_target_element(
            settings, target_record
        )
        if element is None:
            self._clear_resolved_target_cache()
            if "timed out" in message.casefold() or "timeout" in message.casefold():
                return None, "timeout"
            if _message_indicates_window_not_ready(message):
                return None, "window not ready"
            return None, "target not found"
        self._resolved_target_cache[cache_key] = element
        self._resolved_target_aliases[target_id] = cache_key
        self._run_metrics.resolved_targets = len(self._resolved_target_cache)
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
            self._clear_resolved_target_cache()
            target, resolve_message = self._resolve_runtime_target(
                settings,
                step.target_id,
                force_refresh=True,
            )
            if target is None:
                return MacroRunResult(False, resolve_message, 0, None)
            focused, focus_message = self._focus_target_element(target)
            if not focused:
                self._clear_resolved_target_cache()
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

    @staticmethod
    def _activate_target_element(element: object) -> bool:
        if MacroRunner._looks_like_tab_target(element):
            if MacroRunner._select_tab_target(element):
                return True
            if MacroRunner._click_element_center(element):
                return True

        activation_methods: list[str] = []
        if MacroRunner._looks_like_toggle_target(element):
            activation_methods.extend(["click_input", "click", "toggle", "invoke"])
        else:
            activation_methods.extend(["click_input", "click", "invoke"])

        for method_name in activation_methods:
            method = getattr(element, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _double_activate_target_element(element: object) -> bool:
        if MacroRunner._looks_like_tab_target(element):
            if MacroRunner._select_tab_target(element):
                return True
            if MacroRunner._double_click_element_center(element):
                return True
        for method_name in ("double_click_input", "double_click"):
            method = getattr(element, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _select_target_element(element: object) -> bool:
        if MacroRunner._select_tab_target(element):
            return True

        for method_name in ("select", "Select"):
            method = getattr(element, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                return True
            except Exception:
                continue
        return False

    def _select_from_parent_scope(
        self,
        settings: dict[str, str],
        target_record: UiTargetRecord,
    ) -> bool:
        if not self._is_parent_scoped_name_target(target_record):
            return False
        scope, _message = resolve_target_scope_element(settings, target_record)
        if scope is None:
            return False
        child = self._find_named_child_in_scope(scope, target_record.name)
        if child is None:
            return False
        if self._select_target_element(child):
            return True
        child_name = str(getattr(getattr(child, "element_info", None), "name", "") or "").strip()
        if child_name:
            for method_name in ("_select", "select", "Select"):
                method = getattr(scope, method_name, None)
                if not callable(method):
                    continue
                try:
                    method(child_name)
                    return True
                except Exception:
                    continue
        return False

    @staticmethod
    def _is_parent_scoped_name_target(target_record: UiTargetRecord) -> bool:
        return bool(
            target_record.parent_automation_id
            and target_record.name
            and not target_record.automation_id
        )

    @staticmethod
    def _find_named_child_in_scope(scope: object, expected_name: str | None) -> object | None:
        if not expected_name:
            return None
        try:
            children = list(scope.children())
        except Exception:
            try:
                children = list(scope.descendants())
            except Exception:
                return None
        for child in children:
            actual_name = str(
                getattr(getattr(child, "element_info", None), "name", "") or ""
            ).strip()
            if MacroRunner._matches_name_pattern(actual_name, expected_name):
                return child
        return None

    @staticmethod
    def _matches_name_pattern(actual_name: str | None, expected_name: str) -> bool:
        actual = (actual_name or "").strip()
        expected = (expected_name or "").strip()
        if not actual or not expected:
            return False
        expected_lower = expected.casefold()
        actual_lower = actual.casefold()
        if expected_lower.startswith("prefix:"):
            prefix = expected[7:].strip()
            return bool(prefix) and actual_lower.startswith(prefix.casefold())
        if expected_lower.startswith("contains:"):
            needle = expected[9:].strip()
            return bool(needle) and needle.casefold() in actual_lower
        if "*" in expected:
            import re

            wildcard_pattern = "^" + re.escape(expected).replace(r"\*", ".*") + "$"
            return re.match(wildcard_pattern, actual, flags=re.IGNORECASE) is not None
        return actual_lower == expected_lower

    @staticmethod
    def _looks_like_toggle_target(element: object) -> bool:
        element_info = getattr(element, "element_info", None)
        control_type = str(getattr(element_info, "control_type", "") or "").casefold()
        if control_type in {"checkbox", "radio button", "radiobutton"}:
            return True
        friendly_name = getattr(element, "friendly_class_name", None)
        if callable(friendly_name):
            try:
                if str(friendly_name() or "").casefold() in {"checkbox", "radiobutton", "radio button"}:
                    return True
            except Exception:
                return False
        return False

    @staticmethod
    def _looks_like_tab_target(element: object) -> bool:
        element_info = getattr(element, "element_info", None)
        control_type = str(getattr(element_info, "control_type", "") or "").casefold()
        if control_type in {"tabitem", "tab item"}:
            return True
        friendly_name = getattr(element, "friendly_class_name", None)
        if callable(friendly_name):
            try:
                if str(friendly_name() or "").casefold() in {"tabitem", "tab item"}:
                    return True
            except Exception:
                return False
        return False

    @staticmethod
    def _select_tab_target(element: object) -> bool:
        selection_item = getattr(element, "iface_selection_item", None)
        if selection_item is not None:
            for method_name in ("Select", "select"):
                method = getattr(selection_item, method_name, None)
                if not callable(method):
                    continue
                try:
                    method()
                    return True
                except Exception:
                    continue

        for method_name in ("select", "Select"):
            method = getattr(element, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                return True
            except Exception:
                continue

        parent = None
        try:
            parent = element.parent()
        except Exception:
            parent = None
        if parent is not None:
            element_name = str(
                getattr(getattr(element, "element_info", None), "name", "") or ""
            ).strip()
            if element_name:
                for method_name in ("_select", "select", "Select"):
                    method = getattr(parent, method_name, None)
                    if not callable(method):
                        continue
                    try:
                        method(element_name)
                        return True
                    except Exception:
                        continue
        return False

    @staticmethod
    def _click_element_center(element: object) -> bool:
        coords = MacroRunner._preferred_click_coords(element)
        if coords is None:
            return False
        try:
            from pywinauto import mouse

            mouse.click(button="left", coords=coords)
            return True
        except Exception:
            return False

    @staticmethod
    def _double_click_element_center(element: object) -> bool:
        coords = MacroRunner._preferred_click_coords(element)
        if coords is None:
            return False
        try:
            from pywinauto import mouse

            mouse.double_click(button="left", coords=coords)
            return True
        except Exception:
            return False

    @staticmethod
    def _element_center_coords(element: object) -> tuple[int, int] | None:
        rectangle = getattr(element, "rectangle", None)
        if not callable(rectangle):
            return None
        try:
            rect = rectangle()
        except Exception:
            return None

        left = int(getattr(rect, "left", getattr(rect, "L", 0)))
        top = int(getattr(rect, "top", getattr(rect, "T", 0)))
        right = int(getattr(rect, "right", getattr(rect, "R", left)))
        bottom = int(getattr(rect, "bottom", getattr(rect, "B", top)))
        if right <= left or bottom <= top:
            return None
        return ((left + right) // 2, (top + bottom) // 2)

    @staticmethod
    def _preferred_click_coords(element: object) -> tuple[int, int] | None:
        rectangle = getattr(element, "rectangle", None)
        if not callable(rectangle):
            return None
        try:
            rect = rectangle()
        except Exception:
            return None

        left = int(getattr(rect, "left", getattr(rect, "L", 0)))
        top = int(getattr(rect, "top", getattr(rect, "T", 0)))
        right = int(getattr(rect, "right", getattr(rect, "R", left)))
        bottom = int(getattr(rect, "bottom", getattr(rect, "B", top)))
        if right <= left or bottom <= top:
            return None

        if MacroRunner._looks_like_tab_target(element):
            width = right - left
            height = bottom - top
            x = left + (width // 2)
            y = top + max(4, min(8, max(1, height // 3)))
            y = min(y, bottom - 2)
            return (x, y)

        return ((left + right) // 2, (top + bottom) // 2)

    def _dry_run_step_line(self, step: MacroStep, index: int) -> str:
        action = self._action_name(step)
        display_order = step.options.get("step_order", index)
        target = f" target_id={step.target_id}" if step.target_id else ""
        timing_text = self._dry_run_timing_text(step)

        if action in {"delay_ms", "wait"}:
            duration = step.options.get("ms", step.value)
            return (
                f"{display_order}. delay_ms value={duration}{timing_text} "
                "(dry run only)"
            )
        if action == "preset_text":
            return (
                f"{display_order}. preset_text value={step.value}{timing_text} "
                "(dry run only)"
            )
        if action == "wait_text_or_image":
            return (
                f"{display_order}. wait_text_or_image{target}{timing_text} "
                "(placeholder, dry run only)"
            )
        if action == "wait_window":
            return (
                f"{display_order}. wait_window timeout={step.timeout_seconds} "
                f"retries={step.retries}{timing_text} (dry run only)"
            )
        if action == "when_ready":
            return (
                f"{display_order}. when_ready{target} timeout={step.timeout_seconds} "
                f"retries={step.retries}{timing_text} "
                "(wait for keyboard focus/caret, dry run only)"
            )

        value = step.options.get("text") or step.options.get("key") or step.value
        value_text = f" value={value}" if value else ""
        enter_parts = []
        if action in {"type_text", "paste_text", "preset_text", "set_text_uia", "set_edit_text"} and step.options.get("press_enter_before", False):
            enter_parts.append("enter_before=yes")
        if action in {"type_text", "paste_text", "preset_text", "set_text_uia", "set_edit_text"} and step.options.get("press_enter_after", False):
            enter_parts.append("enter_after=yes")
        enter_text = f" {' '.join(enter_parts)}" if enter_parts else ""
        return (
            f"{display_order}. {action}{target}{value_text}{enter_text}{timing_text} "
            f"timeout={step.timeout_seconds} retries={step.retries}"
        )

    @staticmethod
    def _dry_run_timing_text(step: MacroStep) -> str:
        parts: list[str] = []
        if step.options.get("wait_before_enabled", False):
            parts.append(f"wait_before={step.options.get('wait_before_ms', 100)}ms")
        return f" {' '.join(parts)}" if parts else ""

    @staticmethod
    def _action_name(step: MacroStep) -> str:
        action = step.action
        return action.value if hasattr(action, "value") else str(action)

    def _require_settings(self) -> dict[str, str]:
        if self._current_settings is None:
            raise RuntimeError("Macro execution blocked: Eghis connector settings are required.")
        return self._current_settings

    def _start_run_state(self) -> None:
        self._clear_resolved_target_cache()
        self._connection_ready_confirmed = False
        self._run_metrics = _RunMetrics()

    def _clear_resolved_target_cache(self) -> None:
        self._resolved_target_cache.clear()
        self._resolved_target_aliases.clear()

    def _metrics_text(self) -> str:
        return (
            f"Resolved targets: {self._run_metrics.resolved_targets} | "
            f"Cache hits: {self._run_metrics.cache_hits} | "
            f"Cache misses: {self._run_metrics.cache_misses}"
        )

    def _with_run_metrics(self, base_message: str) -> str:
        return f"{base_message}\n{self._metrics_text()}"

    @staticmethod
    def _should_retry_step(
        step: MacroStep,
        message: str,
        attempt_index: int,
        attempts: int,
    ) -> bool:
        if attempt_index + 1 >= attempts:
            return False
        if not step.target_id:
            return False
        return message in {"target not found", "window not ready", "timeout"}

    def _load_runtime_target_record(
        self,
        connection,
        target_id: str,
    ) -> tuple[UiTargetRecord | None, tuple[int | None, str, str | None] | None]:
        if self._current_profile_id is not None:
            emr_target = get_emr_ui_target_by_key(connection, self._current_profile_id, target_id)
            if emr_target is not None:
                runtime_target = self._runtime_target_from_emr_target(connection, emr_target)
                cache_key = (
                    emr_target.profile_id,
                    emr_target.target_key,
                    emr_target.parent_target_key,
                )
                return runtime_target, cache_key

        legacy_target = get_ui_target(connection, target_id)
        if legacy_target is None:
            return None, None
        cache_key = (
            None,
            legacy_target.target_id,
            legacy_target.parent_target_id,
        )
        return legacy_target, cache_key

    def _runtime_target_from_emr_target(
        self,
        connection,
        emr_target: EmrUiTargetRecord,
    ) -> UiTargetRecord:
        profile = get_emr_target_profile(connection, emr_target.profile_id)
        profile_main_window_automation_id = (
            profile.main_window_automation_id
            if profile is not None and profile.main_window_automation_id
            else None
        )
        parent_automation_id = emr_target.scope_automation_id
        parent_target_key = emr_target.parent_target_key
        if parent_automation_id is None and parent_target_key:
            parent_target = get_emr_ui_target_by_key(
                connection,
                emr_target.profile_id,
                parent_target_key,
            )
            if parent_target is not None:
                parent_automation_id = parent_target.automation_id
        if profile_main_window_automation_id and parent_automation_id in {None, "MdiMain"}:
            parent_automation_id = profile_main_window_automation_id
        return UiTargetRecord(
            id=emr_target.id,
            target_id=emr_target.target_key,
            parent_target_id=None,
            parent_automation_id=parent_automation_id,
            automation_id=emr_target.automation_id,
            name=emr_target.name_match,
            control_type=emr_target.control_type,
            class_name=emr_target.class_name,
            created_at=emr_target.created_at,
            ancestor_path=emr_target.ancestor_path,
        )

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
        if "reconnect manually and retry" in lowered:
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
        if action in {"click", "double_click", "hotkey", "key", "type_text", "paste_text"}:
            if "clipboard" in lowered and action == "paste_text":
                return "clipboard failed"
            return "input failed"
        return "unknown error"

    @staticmethod
    def _build_execution_settings(
        base_settings: dict[str, str],
        profile,
    ) -> dict[str, str]:
        if profile is None:
            return dict(base_settings)
        return build_connector_settings(
            base_settings,
            process_name=profile.process_name or base_settings.get("eghis_process_name"),
            window_title_contains=profile.window_title_contains
            or base_settings.get("eghis_window_title_contains"),
            executable_path=profile.executable_path or base_settings.get("eghis_executable_path"),
            main_window_automation_id=profile.main_window_automation_id
            or base_settings.get("eghis_main_window_automation_id"),
            patient_status_tab_automation_id=profile.patient_status_tab_automation_id
            or base_settings.get("eghis_patient_status_tab_automation_id")
            or "tabProc",
            prescription_grid_automation_id=profile.prescription_grid_automation_id
            or base_settings.get("eghis_prescription_grid_automation_id")
            or "tree처방",
            symptom_grid_automation_id=profile.symptom_grid_automation_id
            or base_settings.get("eghis_symptom_grid_automation_id")
            or "grdSymp",
            diagnosis_grid_automation_id=profile.diagnosis_grid_automation_id
            or base_settings.get("eghis_diagnosis_grid_automation_id")
            or "tree상병",
            patient_list_grid_automation_id=profile.patient_list_grid_automation_id
            or base_settings.get("eghis_patient_list_grid_automation_id")
            or "grdOpdList",
        )


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
        if action in {"type_text", "paste_text", "type_text_keyboard", "type_text_clipboard", "set_text_uia", "set_edit_text"} and step.value is not None:
            options["text"] = step.value
    if action in {"type_text", "paste_text", "preset_text", "type_text_keyboard", "type_text_clipboard", "set_text_uia", "set_edit_text"} and getattr(step, "press_enter_before", False):
        options["press_enter_before"] = True
    if action in {"type_text", "paste_text", "preset_text", "type_text_keyboard", "type_text_clipboard", "set_text_uia", "set_edit_text"} and step.press_enter_after:
        options["press_enter_after"] = True
    if step.wait_before_enabled:
        options["wait_before_enabled"] = True
        options["wait_before_ms"] = step.wait_before_ms
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


def _normalize_hotkey_segment(segment: str) -> str:
    normalized = segment.strip()
    modifier_tokens = {
        "{ALT}": "%",
        "{CTRL}": "^",
        "{CONTROL}": "^",
        "{SHIFT}": "+",
        "{WIN}": "#",
    }
    prefixes = ""
    while True:
        matched = False
        for token, prefix in modifier_tokens.items():
            if normalized.upper().startswith(token):
                prefixes += prefix
                normalized = normalized[len(token) :].lstrip()
                matched = True
                break
        if not matched:
            break
    if prefixes:
        return prefixes + normalized
    return normalized


def _message_indicates_window_not_ready(message: str) -> bool:
    lowered = (message or "").casefold()
    return any(
        phrase in lowered
        for phrase in (
            "eghis window containing",
            "window title setting is empty",
            "unable to inspect eghis window children",
            "unable to inspect uia windows",
            "window not available",
        )
    )
