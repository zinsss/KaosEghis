from dataclasses import dataclass
from typing import Any

from KaosEghis.core.inspector_import import InspectorAncestor, parse_ancestor_hints
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


def resolve_target_element(
    settings: dict[str, str], target: UiTargetRecord
) -> tuple[Any | None, bool | None, str]:
    title_fragment = settings.get("eghis_window_title_contains", "").strip()
    if not title_fragment:
        return None, None, "Eghis window title setting is empty."

    try:
        from pywinauto import Desktop
    except ImportError:
        return None, None, "pywinauto is not installed; UIA inspection unavailable."

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
    except Exception as error:
        return None, None, f"Unable to inspect UIA windows: {error}"

    window = _find_window_by_title(windows, title_fragment)
    if window is None:
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

    return UiaInspectionResult(
        found=True,
        message="Target found by read-only UIA inspection.",
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
    )


def _find_window_by_title(windows: list[Any], title_fragment: str) -> Any | None:
    fragment = title_fragment.casefold()
    for window in windows:
        title = _window_title(window)
        if fragment in title.casefold():
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
    if parent_automation_id:
        parent, message = _find_parent_element(window, target, parent_automation_id)
        if parent is None:
            return None, False, message
        try:
            elements = parent.descendants()
        except Exception as error:
            return (
                None,
                True,
                f"Unable to inspect children of parent '{parent_automation_id}': {error}",
            )
        match, message = _find_target_element(
            elements,
            target,
            scope_description=f"inside parent automation_id '{parent_automation_id}'",
        )
        if match is None:
            return None, True, message
        return match, True, "Target found."

    ancestor_hints = parse_ancestor_hints(_clean(target.ancestor_hint_path))
    if ancestor_hints:
        hinted_scope, _message = _find_ancestor_hint_scope(window, ancestor_hints)
        if hinted_scope is not None:
            try:
                elements = hinted_scope.descendants()
            except Exception as error:
                return (
                    None,
                    None,
                    f"Unable to inspect children under ancestor hint scope: {error}",
                )
            match, message = _find_target_element(
                elements,
                target,
                scope_description=_describe_ancestor_hints(ancestor_hints),
            )
            if match is not None:
                return match, None, "Target found."

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
    window: Any, target: UiTargetRecord, parent_automation_id: str
) -> tuple[Any | None, str]:
    try:
        parent = window.child_window(auto_id=parent_automation_id).wrapper_object()
    except Exception as error:
        message = _parent_lookup_error_message(target, parent_automation_id, error)
        return None, message
    if parent is None:
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
        if all(reader(element) == expected for _, expected, reader in criteria)
    ]
    description = ", ".join(f"{field} '{value}'" for field, value, _ in criteria)
    if scope_description:
        description = f"{description} {scope_description}"
    return _single_match(matches, target, description)


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


def _find_ancestor_hint_scope(
    window: Any,
    ancestor_hints: list[InspectorAncestor],
) -> tuple[Any | None, str]:
    scope = window
    for hint in ancestor_hints:
        hint_match = _find_ancestor_hint_match(scope, hint)
        if hint_match is None:
            return None, f"Ancestor hint '{hint.name}' could not be resolved."
        scope = hint_match
    return scope, "Ancestor hint scope found."


def _find_ancestor_hint_match(scope: Any, hint: InspectorAncestor) -> Any | None:
    direct_children = _element_children(scope)
    direct_matches = _matching_ancestor_elements(direct_children, hint)
    if len(direct_matches) == 1:
        return direct_matches[0]
    if len(direct_matches) > 1:
        return direct_matches[0]

    descendants = _element_descendants(scope)
    descendant_matches = _matching_ancestor_elements(descendants, hint)
    if len(descendant_matches) == 1:
        return descendant_matches[0]
    if len(descendant_matches) > 1:
        return descendant_matches[0]
    return None


def _matching_ancestor_elements(elements: list[Any], hint: InspectorAncestor) -> list[Any]:
    expected_name = _clean(hint.name)
    expected_control_type = _clean(hint.control_type)
    matches: list[Any] = []
    for element in elements:
        if expected_name and _element_name(element) != expected_name:
            continue
        if expected_control_type and _element_control_type(element) != expected_control_type:
            continue
        matches.append(element)
    return matches


def _element_children(scope: Any) -> list[Any]:
    children = getattr(scope, "children", None)
    if callable(children):
        try:
            return list(children())
        except Exception:
            return []
    raw_children = getattr(scope, "_children", None)
    if isinstance(raw_children, list):
        return list(raw_children)
    return []


def _element_descendants(scope: Any) -> list[Any]:
    descendants = getattr(scope, "descendants", None)
    if callable(descendants):
        return list(descendants())
    return []


def _describe_ancestor_hints(ancestor_hints: list[InspectorAncestor]) -> str:
    chain = " > ".join(
        hint.name if not hint.control_type else f"{hint.name} ({hint.control_type})"
        for hint in ancestor_hints
        if _clean(hint.name)
    )
    return f"inside ancestor hint path '{chain}'" if chain else "inside ancestor hint path"


def _window_title(window: Any) -> str:
    try:
        return window.window_text() or ""
    except Exception:
        return ""


def _element_automation_id(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    value = getattr(info, "automation_id", None)
    return str(value) if value else None


def _element_name(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    value = getattr(info, "name", None)
    if value:
        return str(value)
    try:
        value = element.window_text()
    except Exception:
        value = None
    return str(value) if value else None


def _element_control_type(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    value = getattr(info, "control_type", None)
    return str(value) if value else None


def _element_class_name(element: Any) -> str | None:
    info = getattr(element, "element_info", None)
    value = getattr(info, "class_name", None)
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
