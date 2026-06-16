from dataclasses import dataclass
from typing import Any

from KaosEghis.db.repositories import UiTargetRecord


@dataclass(frozen=True)
class UiaInspectionResult:
    found: bool
    message: str
    target_id: str
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


def inspect_target_readonly(
    settings: dict[str, str], target: UiTargetRecord
) -> UiaInspectionResult:
    title_fragment = settings.get("eghis_window_title_contains", "").strip()
    if not title_fragment:
        return _not_found(target, "Eghis window title setting is empty.")

    try:
        from pywinauto import Desktop
    except ImportError:
        return _not_found(target, "pywinauto is not installed; UIA inspection unavailable.")

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
    except Exception as error:
        return _not_found(target, f"Unable to inspect UIA windows: {error}")

    window = _find_window_by_title(windows, title_fragment)
    if window is None:
        return _not_found(
            target, f"Eghis window containing '{title_fragment}' was not found."
        )

    try:
        elements = window.descendants()
    except Exception as error:
        return _not_found(target, f"Unable to inspect Eghis window children: {error}")

    match, message = _find_target_element(elements, target)
    if match is None:
        return _not_found(target, message)

    return UiaInspectionResult(
        found=True,
        message="Target found by read-only UIA inspection.",
        target_id=target.target_id,
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


def _not_found(target: UiTargetRecord, message: str) -> UiaInspectionResult:
    return UiaInspectionResult(
        found=False,
        message=message,
        target_id=target.target_id,
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


def _find_target_element(
    elements: list[Any], target: UiTargetRecord
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
