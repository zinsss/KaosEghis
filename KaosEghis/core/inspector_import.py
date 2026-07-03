from __future__ import annotations

from dataclasses import dataclass
import json
import re


LOCALIZED_CONTROL_TYPE_MAP = {
    "도구 모음": "ToolBar",
    "그룹": "Group",
    "창": "Window",
    "단추": "Button",
    "편집": "Edit",
    "문서": "Document",
    "창틀": "Pane",
}


@dataclass(frozen=True)
class InspectorAncestor:
    name: str
    control_type: str | None
    localized_control_type: str | None


@dataclass(frozen=True)
class InspectorImportRecord:
    name: str | None
    control_type: str | None
    automation_id: str | None
    class_name: str | None
    localized_control_type: str | None
    ancestors: list[InspectorAncestor]


def parse_inspector_text(text: str) -> InspectorImportRecord:
    lines = text.splitlines()
    name = _normalized_value(_match_prefixed_value(lines, "Name:"))
    control_type = _extract_control_type(_match_prefixed_value(lines, "ControlType:"))
    automation_id = _normalized_value(_match_prefixed_value(lines, "AutomationId:"))
    class_name = _normalized_value(_match_prefixed_value(lines, "ClassName:"))
    localized_control_type = _normalized_value(
        _match_prefixed_value(lines, "LocalizedControlType:")
    )
    ancestors = _parse_ancestors(lines)
    return InspectorImportRecord(
        name=name,
        control_type=control_type or _control_type_from_localized(localized_control_type),
        automation_id=automation_id,
        class_name=class_name,
        localized_control_type=localized_control_type,
        ancestors=ancestors,
    )


def list_meaningful_ancestors(record: InspectorImportRecord) -> list[InspectorAncestor]:
    meaningful: list[InspectorAncestor] = []
    for ancestor in record.ancestors:
        normalized_name = (ancestor.name or "").strip()
        if not normalized_name:
            continue
        if normalized_name == "[ No Parent ]":
            continue
        if "데스크톱" in normalized_name or normalized_name.casefold().startswith("desktop"):
            continue
        meaningful.append(ancestor)
    return meaningful


def derive_target_key(name: str | None, fallback_prefix: str = "target") -> str:
    if name:
        normalized = re.sub(r"[^\w]+", "_", name.strip().casefold(), flags=re.UNICODE)
        normalized = normalized.strip("_")
        if normalized:
            return normalized
    return fallback_prefix


def derive_ancestor_key(ancestor: InspectorAncestor) -> str:
    base = derive_target_key(ancestor.name, "ancestor")
    control_type = (ancestor.control_type or "").strip().casefold()
    if control_type:
        return f"{base}.{control_type}"
    return base


def serialize_ancestor_hints(ancestors: list[InspectorAncestor]) -> str:
    return json.dumps(
        [
            {
                "name": ancestor.name,
                "control_type": ancestor.control_type,
                "localized_control_type": ancestor.localized_control_type,
            }
            for ancestor in ancestors
        ],
        ensure_ascii=False,
    )


def parse_ancestor_hints(value: str | None) -> list[InspectorAncestor]:
    if not value:
        return []
    try:
        raw_items = json.loads(value)
    except json.JSONDecodeError:
        return _parse_ancestor_hint_lines(value)
    if not isinstance(raw_items, list):
        return []
    ancestors: list[InspectorAncestor] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        name = str(raw_item.get("name") or "").strip()
        if not name:
            continue
        control_type = _normalized_value(raw_item.get("control_type"))
        localized_control_type = _normalized_value(raw_item.get("localized_control_type"))
        ancestors.append(
            InspectorAncestor(
                name=name,
                control_type=control_type,
                localized_control_type=localized_control_type,
            )
        )
    return ancestors


def _parse_ancestors(lines: list[str]) -> list[InspectorAncestor]:
    ancestors: list[InspectorAncestor] = []
    collecting = False
    for line in lines:
        if not collecting:
            if line.startswith("Ancestors:"):
                collecting = True
                remainder = line.partition("Ancestors:")[2].strip()
                if remainder:
                    parsed = _parse_ancestor_line(remainder)
                    if parsed is not None:
                        ancestors.append(parsed)
                continue
        else:
            if not line.startswith((" ", "\t")):
                break
            parsed = _parse_ancestor_line(line.strip())
            if parsed is not None:
                ancestors.append(parsed)
    return list(reversed(ancestors))


def _parse_ancestor_line(line: str) -> InspectorAncestor | None:
    if not line or line == "[ No Parent ]":
        return None
    match = re.match(r'"(?P<name>.*)"\s*(?P<localized>.+)?$', line)
    if match is None:
        return InspectorAncestor(name=line, control_type=None, localized_control_type=None)
    name = match.group("name") or ""
    localized = _normalized_value(match.group("localized"))
    return InspectorAncestor(
        name=name,
        control_type=_control_type_from_localized(localized),
        localized_control_type=localized,
    )


def _parse_ancestor_hint_lines(value: str) -> list[InspectorAncestor]:
    ancestors: list[InspectorAncestor] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|", 1)]
        name = parts[0]
        if not name:
            continue
        control_type = parts[1] if len(parts) > 1 and parts[1] else None
        ancestors.append(
            InspectorAncestor(
                name=name,
                control_type=control_type,
                localized_control_type=None,
            )
        )
    return ancestors


def _match_prefixed_value(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line.partition(prefix)[2].strip()
    return None


def _extract_control_type(value: str | None) -> str | None:
    value = _normalized_value(value)
    if not value:
        return None
    match = re.search(r"UIA_(?P<name>[A-Za-z0-9]+)ControlTypeId", value)
    if match is not None:
        return match.group("name")
    return value


def _normalized_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == "[Not supported]":
        return None
    if len(stripped) >= 2 and stripped.startswith('"') and stripped.endswith('"'):
        stripped = stripped[1:-1]
    return stripped


def _control_type_from_localized(value: str | None) -> str | None:
    if value is None:
        return None
    return LOCALIZED_CONTROL_TYPE_MAP.get(value.strip())
