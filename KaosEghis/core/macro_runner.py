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
from KaosEghis.core.uia_inspector import resolve_target_element
from KaosEghis.db.database import connect, get_database_path
from KaosEghis.db.repositories import (
    EmrUiTargetRecord,
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
        for step in steps:
            if self._cancel_requested:
                self._clear_resolved_target_cache()
                return MacroRunResult(
                    False, "Macro execution canceled.", executed_steps, executed_steps + 1
                )

            result = self._execute_step_with_retries(step)
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
        state = ensure_cached_connection_ready(settings)
        if state.status != "green":
            self._clear_resolved_target_cache()
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
                self._clear_resolved_target_cache()
                return MacroRunResult(False, "Macro execution canceled.", 0, None)
            if time.monotonic() >= deadline:
                self._clear_resolved_target_cache()
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
            self._clear_resolved_target_cache()
            target, resolve_message = self._resolve_runtime_target(
                settings,
                step.target_id,
                force_refresh=True,
            )
            if target is None:
                return MacroRunResult(False, resolve_message, 0, None)
            try:
                target.click_input()
            except Exception:
                self._clear_resolved_target_cache()
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
            if "window" in message.casefold():
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

    def _start_run_state(self) -> None:
        self._clear_resolved_target_cache()
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
        parent_automation_id = None
        parent_target_key = emr_target.parent_target_key
        if parent_target_key:
            parent_target = get_emr_ui_target_by_key(
                connection,
                emr_target.profile_id,
                parent_target_key,
            )
            if parent_target is not None:
                parent_automation_id = parent_target.automation_id
        return UiTargetRecord(
            id=emr_target.id,
            target_id=emr_target.target_key,
            parent_target_id=parent_target_key,
            parent_automation_id=parent_automation_id,
            automation_id=emr_target.automation_id,
            name=emr_target.name_match,
            control_type=emr_target.control_type,
            class_name=emr_target.class_name,
            created_at=emr_target.created_at,
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
        if action in {"click", "hotkey", "key", "type_text", "paste_text"}:
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
