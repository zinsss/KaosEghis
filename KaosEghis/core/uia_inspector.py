import json
from dataclasses import dataclass
import re
from typing import Any

from KaosEghis.core.eghis_connector import get_cached_eghis_state
from KaosEghis.db.database import connect
from KaosEghis.db.repositories import UiTargetRecord, get_ui_target


@dataclass(frozen=True)
class UiaInspectionResult:
    found: bool
    message: str
    target_id: str
    parent_target_id: str | None
    parent_automation_id: str | None
    parent_found: bool | None
    automation_id: str | None
    name: str | None
    control_type: str | None
    class_name: str | None
    found_name: str | None
    found_control_type: str | None
    found_class_name: str | None
    is_enabled: bool | None
    is_visible: bool | None
    text_value: str | None
    has_keyboard_focus: bool | None = None


@dataclass(frozen=True)
class _GridRowProxy:
    scope_element: Any
    row_index: int

    def rectangle(self):
        return self.scope_element.rectangle()

    def set_focus(self) -> None:
        try:
            self.scope_element.set_focus()
        except Exception:
            return None

    def click_input(self) -> None:
        self._click(double=False)

    def double_click_input(self) -> None:
        self._click(double=True)

    def _click(self, *, double: bool) -> None:
        from pywinauto import mouse

        left, top, right, bottom = _rect_edges(self.scope_element.rectangle())
        width = max(right - left, 1)
        body_top, body_bottom = _grid_body_vertical_bounds(self.scope_element)
        row_height = _estimate_grid_row_height(self.scope_element)
        x = left + min(max(int(width * 0.08), 24), 120)
        y = int(body_top + ((self.row_index - 0.5) * row_height))
        y = max(body_top + 1, min(y, body_bottom - 1))
        coords = (x, y)
        if double:
            mouse.double_click(button="left", coords=coords)
        else:
            mouse.click(button="left", coords=coords)


def resolve_target_element(
    settings: dict[str, str], target: UiTargetRecord
) -> tuple[Any | None, bool | None, str]:
    title_fragment = settings.get("eghis_window_title_contains", "").strip()

    try:
        from pywinauto import Desktop
    except ImportError:
        return None, None, "pywinauto is not installed; UIA inspection unavailable."

    messages: list[str] = []
    saw_empty_title = False
    resolved_parent_found: bool | None = None
    backend_order = _preferred_backend_order(target)
    for backend in backend_order:
        match, parent_found, message = _resolve_target_element_for_backend(
            Desktop,
            backend,
            title_fragment,
            target,
        )
        if match is not None:
            return match, parent_found, message
        if parent_found is not None:
            resolved_parent_found = parent_found
        if message == "Eghis window title setting is empty.":
            saw_empty_title = True
        elif message:
            messages.append(f"{backend}: {message}")

    if saw_empty_title and not messages:
        return None, resolved_parent_found, "Eghis window title setting is empty."
    if messages:
        return None, resolved_parent_found, " | ".join(messages)
    return None, resolved_parent_found, "Target could not be resolved."


def resolve_target_scope_element(
    settings: dict[str, str], target: UiTargetRecord
) -> tuple[Any | None, str]:
    title_fragment = settings.get("eghis_window_title_contains", "").strip()

    try:
        from pywinauto import Desktop
    except ImportError:
        return None, "pywinauto is not installed; UIA inspection unavailable."

    messages: list[str] = []
    for backend in _preferred_backend_order(target):
        scope, message = _resolve_target_scope_element_for_backend(
            Desktop,
            backend,
            title_fragment,
            target,
        )
        if scope is not None:
            return scope, message
        if message:
            messages.append(f"{backend}: {message}")
    return None, " | ".join(messages) if messages else "Target scope could not be resolved."


def _preferred_backend_order(target: UiTargetRecord) -> tuple[str, ...]:
    has_parent_scope = bool(
        _clean(target.parent_automation_id) or _clean(getattr(target, "ancestor_path", None))
    )
    has_automation_id = bool(_clean(target.automation_id))
    has_name_pattern = bool(_clean(target.name))
    if has_parent_scope and not has_automation_id and has_name_pattern:
        return ("uia", "win32")
    if _clean(target.parent_automation_id) or _clean(getattr(target, "ancestor_path", None)):
        return ("win32", "uia")
    return ("uia", "win32")


def _resolve_target_scope_element_for_backend(
    desktop_type: Any,
    backend: str,
    title_fragment: str,
    target: UiTargetRecord,
) -> tuple[Any | None, str]:
    try:
        desktop = desktop_type(backend=backend)
        windows = desktop.windows()
    except Exception as error:
        return None, f"Unable to inspect UI windows: {error}"

    window = _find_window(desktop, windows, title_fragment)
    if window is None:
        if not title_fragment:
            return None, "Eghis window title setting is empty."
        return None, f"Eghis window containing '{title_fragment}' was not found."

    parent_automation_id = _clean(target.parent_automation_id)
    if parent_automation_id:
        parent, message = _find_parent_element(
            window,
            target,
            parent_automation_id,
            backend=backend,
        )
        if parent is not None:
            return parent, message
        return None, message
    return window, "Window found."


def _resolve_target_element_for_backend(
    desktop_type: Any,
    backend: str,
    title_fragment: str,
    target: UiTargetRecord,
) -> tuple[Any | None, bool | None, str]:
    try:
        desktop = desktop_type(backend=backend)
        windows = desktop.windows()
    except Exception as error:
        return None, None, f"Unable to inspect UIA windows: {error}"

    window = _find_window(desktop, windows, title_fragment)
    if window is None:
        if not title_fragment:
            return None, None, "Eghis window title setting is empty."
        return (
            None,
            None,
            f"Eghis window containing '{title_fragment}' was not found.",
        )

    return _resolve_target_element(window, target, set())


def inspect_target_readonly(
    settings: dict[str, str], target: UiTargetRecord
) -> UiaInspectionResult:
    match, parent_found, message = resolve_target_element(settings, target)
    if match is None:
        return _not_found(target, message, parent_found=parent_found)

    success_message = message or "Target found by read-only UIA inspection."
    if success_message == "Target found.":
        success_message = "Target found by read-only UIA inspection."

    return UiaInspectionResult(
        found=True,
        message=success_message,
        target_id=target.target_id,
        parent_target_id=target.parent_target_id,
        parent_automation_id=target.parent_automation_id,
        parent_found=parent_found,
        automation_id=target.automation_id,
        name=target.name,
        control_type=target.control_type,
        class_name=target.class_name,
        found_name=_element_name(match),
        found_control_type=_element_control_type(match),
        found_class_name=_element_class_name(match),
        is_enabled=_safe_bool(match, "is_enabled"),
        is_visible=_safe_bool(match, "is_visible"),
        text_value=_safe_text_value(match),
        has_keyboard_focus=_safe_bool(match, "has_keyboard_focus"),
    )


def _not_found(
    target: UiTargetRecord, message: str, parent_found: bool | None = None
) -> UiaInspectionResult:
    return UiaInspectionResult(
        found=False,
        message=message,
        target_id=target.target_id,
        parent_target_id=target.parent_target_id,
        parent_automation_id=target.parent_automation_id,
        parent_found=parent_found,
        automation_id=target.automation_id,
        name=target.name,
        control_type=target.control_type,
        class_name=target.class_name,
        found_name=None,
        found_control_type=None,
        found_class_name=None,
        is_enabled=None,
        is_visible=None,
        text_value=None,
        has_keyboard_focus=None,
    )


def _find_window_by_title(windows: list[Any], title_fragment: str) -> Any | None:
    fragment = title_fragment.casefold()
    for window in windows:
        title = _window_title(window)
        if fragment in title.casefold():
            return window
    return None


def _find_window(desktop: Any, windows: list[Any], title_fragment: str) -> Any | None:
    cached_state = get_cached_eghis_state()
    cached_handle = getattr(cached_state, "window_handle", None)
    if cached_handle is not None:
        window = _find_window_by_cached_handle(desktop, windows, cached_handle)
        if window is not None:
            return window
    if title_fragment:
        return _find_window_by_title(windows, title_fragment)
    return None


def _find_window_by_cached_handle(
    desktop: Any, windows: list[Any], window_handle: int
) -> Any | None:
    try:
        specification = desktop.window(handle=window_handle)
        window = specification.wrapper_object()
        if _window_handle(window) == window_handle:
            return window
    except Exception:
        pass
    return _find_window_by_handle(windows, window_handle)


def _find_window_by_handle(windows: list[Any], window_handle: int) -> Any | None:
    for window in windows:
        handle = _window_handle(window)
        if handle == window_handle:
            return window
    return None


def _resolve_target_element(
    window: Any, target: UiTargetRecord, visited_target_ids: set[str]
) -> tuple[Any | None, bool | None, str]:
    if target.target_id in visited_target_ids:
        return None, False, f"Circular parent_target_id detected for '{target.target_id}'."

    parent_target_id = _clean(target.parent_target_id)
    if parent_target_id:
        parent_target = _load_parent_target(parent_target_id)
        if parent_target is None:
            return (
                None,
                False,
                f"Parent target '{parent_target_id}' for UI target '{target.target_id}' "
                "is not registered.",
            )
        parent, _, message = _resolve_target_element(
            window, parent_target, visited_target_ids | {target.target_id}
        )
        if parent is None:
            return (
                None,
                False,
                f"Parent target '{parent_target.target_id}' for UI target "
                f"'{target.target_id}' could not be resolved: {message}",
            )
        try:
            elements = parent.descendants()
        except Exception as error:
            return (
                None,
                True,
                f"Unable to inspect children of parent target '{parent_target.target_id}': "
                f"{error}",
            )
        match, message = _find_target_element(
            elements,
            target,
            scope_description=f"inside parent '{parent_target.target_id}'",
        )
        if match is None:
            return None, True, message
        return match, True, "Target found."

    parent_automation_id = _clean(target.parent_automation_id)
    ancestor_path = _clean(getattr(target, "ancestor_path", None))
    if parent_automation_id:
        parent, message = _find_parent_element(
            window,
            target,
            parent_automation_id,
            backend=_guess_window_backend(window),
        )
        if parent is None:
            if ancestor_path:
                match, parent_found, fallback_message = _resolve_target_with_ancestor_path(
                    window, target, ancestor_path
                )
                if match is not None:
                    return match, parent_found, fallback_message
                grid_match, grid_parent_found, grid_message = _resolve_grid_row_target(
                    window,
                    target,
                    ancestor_path,
                )
                if grid_match is not None:
                    return grid_match, grid_parent_found, grid_message
                return None, parent_found, fallback_message
            return None, False, message
        match, parent_found, scoped_message = _resolve_target_inside_parent_scope(
            parent,
            target,
            scope_description=f"inside parent automation_id '{parent_automation_id}'",
            ancestor_path=ancestor_path,
            parent_anchor_name=_element_name(parent),
        )
        if match is not None:
            return match, parent_found, scoped_message
        grid_match, grid_parent_found, grid_message = _resolve_grid_row_target_in_scope(
            parent,
            target,
            ancestor_path,
            parent_found=True,
        )
        if grid_match is not None:
            return grid_match, grid_parent_found, grid_message
        return None, parent_found, scoped_message

    if ancestor_path:
        match, parent_found, message = _resolve_target_with_ancestor_path(
            window, target, ancestor_path
        )
        if match is not None:
            return match, parent_found, message
        grid_match, grid_parent_found, grid_message = _resolve_grid_row_target(
            window,
            target,
            ancestor_path,
        )
        if grid_match is not None:
            return grid_match, grid_parent_found, grid_message
        return None, parent_found, message

    try:
        elements = window.descendants()
    except Exception as error:
        return None, None, f"Unable to inspect Eghis window children: {error}"
    match, message = _find_target_element(elements, target)
    if match is None:
        return None, None, message
    return match, None, "Target found."


def _load_parent_target(parent_target_id: str) -> UiTargetRecord | None:
    with connect() as connection:
        return get_ui_target(connection, parent_target_id)


def _find_parent_element(
    window: Any,
    target: UiTargetRecord,
    parent_automation_id: str,
    *,
    backend: str | None = None,
) -> tuple[Any | None, str]:
    cached_parent = _find_parent_element_from_cached_handle(
        parent_automation_id,
        preferred_backend=backend,
    )
    if cached_parent is not None:
        return cached_parent, "Parent found."
    try:
        parent = window.child_window(auto_id=parent_automation_id).wrapper_object()
    except Exception as error:
        fallback_parent = _find_parent_element_from_descendants(
            window,
            target,
            parent_automation_id,
        )
        if fallback_parent is not None:
            return fallback_parent, "Parent found."
        message = _parent_lookup_error_message(target, parent_automation_id, error)
        return None, message
    if parent is None:
        fallback_parent = _find_parent_element_from_descendants(
            window,
            target,
            parent_automation_id,
        )
        if fallback_parent is not None:
            return fallback_parent, "Parent found."
        return (
            None,
            f"Parent automation_id '{parent_automation_id}' for UI target "
            f"'{target.target_id}' was not found.",
        )
    return parent, "Parent found."


def _parent_lookup_error_message(
    target: UiTargetRecord, parent_automation_id: str, error: Exception
    ) -> str:
    error_name = type(error).__name__
    count = getattr(error, "match_count", None)
    if error_name in {"ElementAmbiguousError", "MatchError"} or count is not None:
        detail = f" matched {count} elements." if count is not None else " matched multiple elements."
        return (
            f"Parent automation_id '{parent_automation_id}' for UI target "
            f"'{target.target_id}'{detail}"
        )
    return (
        f"Parent automation_id '{parent_automation_id}' for UI target "
        f"'{target.target_id}' was not found."
    )


def _find_parent_element_from_cached_handle(
    parent_automation_id: str,
    *,
    preferred_backend: str | None = None,
) -> Any | None:
    cached_state = get_cached_eghis_state()
    cached_handles = getattr(cached_state, "cached_grid_handles", None) or {}
    cached_handle = cached_handles.get(parent_automation_id)
    if cached_handle is None:
        return None

    backend_order = _backend_order_from_preference(preferred_backend)
    for backend in backend_order:
        parent = _wrapper_from_handle(cached_handle, backend)
        if parent is not None:
            return parent
    return None


def _backend_order_from_preference(preferred_backend: str | None) -> tuple[str, ...]:
    normalized = (preferred_backend or "").strip().casefold()
    if normalized == "uia":
        return ("uia", "win32")
    if normalized == "win32":
        return ("win32", "uia")
    return ("win32", "uia")


def _guess_window_backend(window: Any) -> str | None:
    element_info = getattr(window, "element_info", None)
    backend_name = getattr(element_info, "backend_name", None)
    if isinstance(backend_name, str) and backend_name.strip():
        return backend_name.strip()
    if getattr(element_info, "__class__", None).__name__ == "UIAElementInfo":
        return "uia"
    if getattr(element_info, "__class__", None).__name__ == "HwndElementInfo":
        return "win32"
    return None


def _wrapper_from_handle(handle: int, backend: str) -> Any | None:
    try:
        from pywinauto import Desktop

        specification = Desktop(backend=backend).window(handle=handle)
        wrapper = specification.wrapper_object()
    except Exception:
        return None
    if _window_handle(wrapper) == handle:
        return wrapper
    return None


def _find_parent_element_from_descendants(
    window: Any,
    target: UiTargetRecord,
    parent_automation_id: str,
) -> Any | None:
    try:
        descendants = window.descendants()
    except Exception:
        return None

    auto_matches = [
        element
        for element in descendants
        if _element_automation_id(element) == parent_automation_id
    ]
    if len(auto_matches) == 1:
        return auto_matches[0]
    if len(auto_matches) > 1:
        return None

    meaningful_ancestor_names = _meaningful_ancestor_names(
        _clean(getattr(target, "ancestor_path", None))
    )
    if len(meaningful_ancestor_names) != 1:
        return None

    for ancestor_name in meaningful_ancestor_names:
        name_matches = [
            element
            for element in descendants
            if _element_name(element) == ancestor_name
        ]
        if len(name_matches) == 1:
            return name_matches[0]
    return None


def _find_target_element(
    elements: list[Any], target: UiTargetRecord, scope_description: str | None = None
) -> tuple[Any | None, str]:
    automation_id = _clean(target.automation_id)
    name = _clean(target.name)
    control_type = _clean(target.control_type)
    class_name = _clean(target.class_name)

    criteria = []
    if automation_id:
        criteria.append(("automation_id", automation_id, _element_automation_id))
    if name:
        criteria.append(("name", name, _element_name))
    if control_type:
        criteria.append(("control_type", control_type, _element_control_type))
    if class_name:
        criteria.append(("class_name", class_name, _element_class_name))

    if not criteria:
        return (
            None,
            "UI target has no automation_id, name, control_type, or class_name to inspect.",
        )

    matches = [
        element
        for element in elements
        if all(_criterion_matches(reader(element), field, expected) for field, expected, reader in criteria)
    ]
    description = ", ".join(f"{field} '{value}'" for field, value, _ in criteria)
    if scope_description:
        description = f"{description} {scope_description}"
    return _single_match(matches, target, description)


def _criterion_matches(actual: str | None, field: str, expected: str) -> bool:
    if field == "name":
        return _matches_text_pattern(actual, expected)
    return actual == expected


def _matches_text_pattern(actual: str | None, expected: str) -> bool:
    actual_text = _clean(actual)
    expected_text = _clean(expected)
    if actual_text is None or expected_text is None:
        return actual_text == expected_text

    pattern_prefixes = ("regex:", "re:", "contains:", "prefix:")
    actual_folded = actual_text.casefold()
    expected_folded = expected_text.casefold()

    if expected_folded.startswith("regex:"):
        return _regex_text_match(actual_text, expected_text[6:])
    if expected_folded.startswith("re:"):
        return _regex_text_match(actual_text, expected_text[3:])
    if expected_folded.startswith("contains:"):
        needle = _clean(expected_text[9:])
        return bool(needle) and needle.casefold() in actual_folded
    if expected_folded.startswith("prefix:"):
        prefix = _clean(expected_text[7:])
        return bool(prefix) and actual_folded.startswith(prefix.casefold())
    if "*" in expected_text and not expected_folded.startswith(pattern_prefixes):
        wildcard_pattern = "^" + re.escape(expected_text).replace(r"\*", ".*") + "$"
        return re.match(wildcard_pattern, actual_text, flags=re.IGNORECASE) is not None
    return actual_folded == expected_folded


def _regex_text_match(actual: str, pattern: str) -> bool:
    compiled_pattern = _clean(pattern)
    if not compiled_pattern:
        return False
    try:
        return re.search(compiled_pattern, actual, flags=re.IGNORECASE) is not None
    except re.error:
        return False


def _resolve_target_with_ancestor_path(
    window: Any,
    target: UiTargetRecord,
    ancestor_path: str,
) -> tuple[Any | None, bool | None, str]:
    scoped_parent, parent_found, message = _resolve_ancestor_path_scope(
        window,
        target,
        ancestor_path,
    )
    if scoped_parent is None:
        return None, parent_found, message
    try:
        elements = scoped_parent.descendants()
    except Exception as error:
        return (
            None,
            parent_found,
            f"Unable to inspect ancestor-scoped children for UI target '{target.target_id}': {error}",
        )
    match, message = _find_target_element(
        elements,
        target,
        scope_description="inside ancestor path",
    )
    if match is None:
        return None, parent_found, message
    return match, parent_found, "Target found."


def _resolve_target_inside_parent_scope(
    parent: Any,
    target: UiTargetRecord,
    *,
    scope_description: str,
    ancestor_path: str | None,
    parent_anchor_name: str | None,
) -> tuple[Any | None, bool | None, str]:
    direct_match, direct_message = _find_direct_child_match(
        parent,
        target,
        scope_description=scope_description,
    )
    if direct_match is not None:
        return direct_match, True, "Target found."

    try:
        parent_elements = parent.descendants()
    except Exception as error:
        return (
            None,
            True,
            f"Unable to inspect children of {scope_description}: {error}",
        )

    relaxed_match, relaxed_message = _find_target_element_by_automation_id(
        parent_elements,
        target,
        scope_description=scope_description,
    )
    if relaxed_match is not None:
        return relaxed_match, True, "Target found."

    scoped_container = parent
    tail_failure_message = ""
    if ancestor_path:
        tail_nodes = _ancestor_tail_nodes_from_anchor(ancestor_path, parent_anchor_name)
        if tail_nodes:
            descendant_scope, message = _resolve_descendant_path(parent, tail_nodes)
            if descendant_scope is not None:
                scoped_container = descendant_scope
            else:
                tail_failure_message = message

    try:
        elements = scoped_container.descendants()
    except Exception as error:
        return (
            None,
            True,
            f"Unable to inspect children of {scope_description}: {error}",
        )
    relaxed_match, relaxed_message = _find_target_element_by_automation_id(
        elements,
        target,
        scope_description=scope_description,
    )
    if relaxed_match is not None:
        return relaxed_match, True, "Target found."

    match, message = _find_target_element(
        elements,
        target,
        scope_description=scope_description,
    )
    if match is not None:
        return match, True, "Target found."
    return None, True, relaxed_message or message or tail_failure_message


def _find_direct_child_match(
    scope: Any,
    target: UiTargetRecord,
    *,
    scope_description: str,
) -> tuple[Any | None, str]:
    automation_id = _clean(target.automation_id)
    if not automation_id:
        return None, ""
    try:
        match = scope.child_window(auto_id=automation_id).wrapper_object()
    except Exception:
        return None, ""
    if match is None:
        return None, ""
    return match, f"automation_id '{automation_id}' {scope_description}"


def _resolve_ancestor_path_scope(
    window: Any,
    target: UiTargetRecord,
    ancestor_path: str,
) -> tuple[Any | None, bool | None, str]:
    nodes = _parse_ancestor_path(ancestor_path)
    if not nodes:
        return None, False, f"UI target '{target.target_id}' has an invalid ancestor path."

    current_scope = window
    effective_nodes = _effective_ancestor_nodes(window, nodes)
    if not effective_nodes:
        return window, True, "Ancestor path matched the current window."

    last_message = f"Ancestor path for UI target '{target.target_id}' was not found."
    candidate_paths: list[list[dict[str, str]]] = []
    for start_index in range(len(effective_nodes)):
        for end_index in range(len(effective_nodes), start_index, -1):
            candidate_paths.append(effective_nodes[start_index:end_index])

    for candidate_nodes in candidate_paths:
        current_scope = window
        failed = False
        for node in candidate_nodes:
            try:
                elements = current_scope.descendants()
            except Exception as error:
                return (
                    None,
                    False,
                    f"Unable to inspect ancestor scope for UI target '{target.target_id}': {error}",
                )
            matches = [
                element
                for element in elements
                if _matches_ancestor_node(element, node)
            ]
            description = _describe_ancestor_node(node)
            if not matches:
                last_message = (
                    f"Ancestor {description} for UI target '{target.target_id}' was not found."
                )
                failed = True
                break
            if len(matches) > 1:
                last_message = (
                    f"Ancestor {description} for UI target '{target.target_id}' matched {len(matches)} elements."
                )
                failed = True
                break
            current_scope = matches[0]
        if not failed:
            return current_scope, True, "Ancestor path resolved."
    return None, False, last_message


def _resolve_descendant_path(
    scope: Any,
    nodes: list[dict[str, str]],
) -> tuple[Any | None, str]:
    current_scope = scope
    for node in nodes:
        try:
            elements = current_scope.descendants()
        except Exception as error:
            return None, f"Unable to inspect descendant scope: {error}"
        matches = [
            element
            for element in elements
            if _matches_ancestor_node(element, node)
        ]
        description = _describe_ancestor_node(node)
        if not matches:
            return None, f"Descendant {description} was not found."
        if len(matches) > 1:
            return None, f"Descendant {description} matched {len(matches)} elements."
        current_scope = matches[0]
    return current_scope, "Descendant path resolved."


def _ancestor_tail_nodes_from_anchor(
    ancestor_path: str,
    anchor_name: str | None,
) -> list[dict[str, str]]:
    nodes = _parse_ancestor_path(ancestor_path)
    if not nodes:
        return []
    if not anchor_name:
        return []

    meaningful_nodes = [node for node in nodes if not _is_noise_ancestor_node(node)]
    anchor_index = next(
        (
            index
            for index, node in enumerate(meaningful_nodes)
            if str(node.get("name", "")).strip() == anchor_name
        ),
        None,
    )
    if anchor_index is None:
        return []

    tail_nodes = meaningful_nodes[:anchor_index]
    normalized_tail = [
        node
        for node in tail_nodes
        if str(node.get("name", "")).strip().casefold()
        not in {"dockpanel", "pnlmain", "pnlmainback"}
        and not str(node.get("name", "")).strip().casefold().startswith("sidepanel")
        and not (
            len(node) == 1 and node.get("control_type") == "Window"
        )
    ]
    return list(reversed(normalized_tail))


def _single_match(
    matches: list[Any], target: UiTargetRecord, description: str
) -> tuple[Any | None, str]:
    if not matches:
        return None, f"UI target '{target.target_id}' was not found by {description}."
    if len(matches) > 1:
        return (
            None,
            f"UI target '{target.target_id}' matched {len(matches)} elements by {description}.",
        )
    return matches[0], "Target found."


def _find_target_element_by_automation_id(
    elements: list[Any],
    target: UiTargetRecord,
    scope_description: str | None = None,
) -> tuple[Any | None, str]:
    automation_id = _clean(target.automation_id)
    if not automation_id:
        return None, ""
    matches = [
        element
        for element in elements
        if _element_automation_id(element) == automation_id
    ]
    description = f"automation_id '{automation_id}'"
    if scope_description:
        description = f"{description} {scope_description}"
    return _single_match(matches, target, description)


def _resolve_grid_row_target(
    window: Any,
    target: UiTargetRecord,
    ancestor_path: str | None,
) -> tuple[Any | None, bool | None, str]:
    if not ancestor_path:
        return None, False, ""
    scope = _resolve_grid_scope_from_ancestor_path(window, ancestor_path)
    if scope is None:
        return None, False, ""
    return _resolve_grid_row_target_in_scope(
        scope,
        target,
        ancestor_path,
        parent_found=True,
    )


def _resolve_grid_row_target_in_scope(
    scope: Any,
    target: UiTargetRecord,
    ancestor_path: str | None,
    *,
    parent_found: bool,
) -> tuple[Any | None, bool | None, str]:
    if not _is_grid_row_target(target):
        return None, parent_found, ""
    row_index = _grid_row_index(target, ancestor_path)
    if row_index is None:
        return None, parent_found, ""
    return (
        _GridRowProxy(scope, row_index),
        parent_found,
        f"Grid row target '{target.target_id}' resolved to row {row_index}.",
    )


def _is_grid_row_target(target: UiTargetRecord) -> bool:
    control_type = (_clean(target.control_type) or "").casefold()
    if control_type not in {"dataitem", "listitem"}:
        return False
    return _grid_row_index(target, _clean(getattr(target, "ancestor_path", None))) is not None


def _grid_row_index(target: UiTargetRecord, ancestor_path: str | None) -> int | None:
    candidates = [
        _clean(target.name) or "",
        *[
            str(node.get("name", "")).strip()
            for node in _parse_ancestor_path(ancestor_path or "")
            if str(node.get("name", "")).strip()
        ],
    ]
    for candidate in candidates:
        match = re.search(r"\brow\s+(\d+)\b", candidate, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _resolve_grid_scope_from_ancestor_path(window: Any, ancestor_path: str) -> Any | None:
    nodes = _parse_ancestor_path(ancestor_path)
    for node in nodes:
        name = str(node.get("name", "")).strip()
        if not name:
            continue
        lowered = name.casefold()
        if "list" in lowered or "리스트" in name:
            return _resolve_single_ancestor_node(window, node)
    for node in nodes:
        name = str(node.get("name", "")).strip()
        if name in {"MainView", "Data Panel"}:
            return _resolve_single_ancestor_node(window, node)
    return None


def _resolve_single_ancestor_node(window: Any, node: dict[str, str]) -> Any | None:
    try:
        elements = window.descendants()
    except Exception:
        return None
    matches = [
        element
        for element in elements
        if _matches_ancestor_node(element, node)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches and node.get("name"):
        name = str(node.get("name", "")).strip()
        name_matches = [
            element
            for element in elements
            if _element_name(element) == name
        ]
        if len(name_matches) == 1:
            return name_matches[0]
    return None


def _rect_edges(rect: Any) -> tuple[int, int, int, int]:
    left = int(getattr(rect, "left", getattr(rect, "L", 0)))
    top = int(getattr(rect, "top", getattr(rect, "T", 0)))
    right = int(getattr(rect, "right", getattr(rect, "R", left)))
    bottom = int(getattr(rect, "bottom", getattr(rect, "B", top)))
    return left, top, right, bottom


def _grid_body_vertical_bounds(scope_element: Any) -> tuple[int, int]:
    left, top, right, bottom = _rect_edges(scope_element.rectangle())
    width = max(right - left, 1)
    body_top = top + 28
    body_bottom = bottom - 4
    try:
        children = scope_element.children()
    except Exception:
        children = []
    body_candidates: list[tuple[int, int]] = []
    for child in children:
        try:
            child_left, child_top, child_right, child_bottom = _rect_edges(child.rectangle())
        except Exception:
            continue
        child_width = child_right - child_left
        child_height = child_bottom - child_top
        if child_width >= width * 0.75 and child_height >= 80:
            body_candidates.append((child_top, child_bottom))
    if body_candidates:
        body_top = min(candidate[0] for candidate in body_candidates)
        body_bottom = max(candidate[1] for candidate in body_candidates)
    if body_bottom <= body_top:
        body_bottom = max(bottom - 4, body_top + 20)
    return body_top, body_bottom


def _estimate_grid_row_height(scope_element: Any) -> int:
    body_top, body_bottom = _grid_body_vertical_bounds(scope_element)
    visible_height = max(body_bottom - body_top, 1)
    return max(18, min(26, int(round(visible_height / 24))))


def _parse_ancestor_path(ancestor_path: str) -> list[dict[str, str]]:
    try:
        raw_nodes = json.loads(ancestor_path)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_nodes, list):
        return []
    nodes: list[dict[str, str]] = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        normalized = {
            key: str(value).strip()
            for key, value in node.items()
            if key in {"name", "automation_id", "control_type", "class_name"}
            and str(value).strip()
        }
        if normalized:
            nodes.append(normalized)
    return nodes


def _effective_ancestor_nodes(window: Any, nodes: list[dict[str, str]]) -> list[dict[str, str]]:
    meaningful = [node for node in nodes if not _is_noise_ancestor_node(node)]
    ordered = list(reversed(meaningful))

    effective: list[dict[str, str]] = []
    for node in ordered:
        if _matches_ancestor_node(window, node):
            continue
        effective.append(node)
    return effective


def _meaningful_ancestor_names(ancestor_path: str | None) -> list[str]:
    if not ancestor_path:
        return []
    names: list[str] = []
    for node in reversed(_parse_ancestor_path(ancestor_path)):
        name = str(node.get("name", "")).strip()
        if not name or name in {"[ No Parent ]", "데스크톱", "데스크톱 2"}:
            continue
        lowered = name.casefold()
        if lowered in {"dockpanel", "pnlmain", "pnlmainback"}:
            continue
        if lowered.startswith("sidepanel"):
            continue
        if name not in names:
            names.append(name)
    return names


def _is_noise_ancestor_node(node: dict[str, str]) -> bool:
    name = str(node.get("name", "")).strip()
    if name in {"", "[ No Parent ]", "데스크톱", "데스크톱 2"}:
        return True
    return False


def _matches_ancestor_node(element: Any, node: dict[str, str]) -> bool:
    criteria = []
    if node.get("automation_id"):
        criteria.append(_element_automation_id(element) == node["automation_id"])
    if node.get("name"):
        criteria.append(_element_name(element) == node["name"])
    if node.get("control_type"):
        criteria.append(_element_control_type(element) == node["control_type"])
    if node.get("class_name"):
        criteria.append(_element_class_name(element) == node["class_name"])
    return bool(criteria) and all(criteria)


def _describe_ancestor_node(node: dict[str, str]) -> str:
    parts = [f"{key} '{value}'" for key, value in node.items() if value]
    return ", ".join(parts) if parts else "path node"


def _window_title(window: Any) -> str:
    try:
        return window.window_text() or ""
    except Exception:
        return ""


def _window_handle(window: Any) -> int | None:
    value = getattr(window, "handle", None)
    if value is not None:
        try:
            return int(value)
        except Exception:
            return None
    info = getattr(window, "element_info", None)
    value = getattr(info, "handle", None)
    if value is not None:
        try:
            return int(value)
        except Exception:
            return None
    return None


def _element_automation_id(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    try:
        value = getattr(info, "automation_id", None)
    except Exception:
        value = None
    return str(value) if value else None


def _element_name(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    try:
        value = getattr(info, "name", None)
    except Exception:
        value = None
    if value:
        return str(value)
    try:
        value = element.window_text()
    except Exception:
        value = None
    return str(value) if value else None


def _element_control_type(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    try:
        value = getattr(info, "control_type", None)
    except Exception:
        value = None
    if value:
        return str(value)
    try:
        value = element.friendly_class_name()
    except Exception:
        value = None
    return str(value) if value else None


def _element_class_name(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    try:
        value = getattr(info, "class_name", None)
    except Exception:
        value = None
    if value:
        return str(value)
    try:
        value = element.class_name()
    except Exception:
        value = None
    return str(value) if value else None


def _safe_bool(element: Any, method_name: str) -> bool | None:
    try:
        method = getattr(element, method_name)
        return bool(method())
    except Exception:
        return None


def _safe_text_value(element: Any) -> str | None:
    for method_name in ("get_value", "texts"):
        try:
            value = getattr(element, method_name)()
        except Exception:
            continue
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value if item)
        else:
            text = str(value) if value is not None else ""
        if text:
            return text

    try:
        iface_value = element.iface_value
        value = iface_value.CurrentValue
    except Exception:
        return None
    return str(value) if value else None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
