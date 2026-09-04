from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def find_uia_elements_by_automation_ids(
    automation_ids: Iterable[str],
    *,
    root_handle: int | None = None,
    root_element: Any | None = None,
    process_ids: Iterable[int] = (),
    control_type: str | None = None,
) -> dict[str, list[Any]]:
    """Run one native UIA query for exact Automation IDs.

    pywinauto's normal ``auto_id`` filtering first enumerates a subtree and
    filters it in Python. eGHIS has a large UI tree, so build the AutomationId
    property condition directly and let Windows UI Automation do the filtering.
    """

    wanted = tuple(dict.fromkeys(str(value or "").strip() for value in automation_ids))
    wanted = tuple(value for value in wanted if value)
    if not wanted:
        return {}

    try:
        from pywinauto.controls.uiawrapper import UIAWrapper
        from pywinauto.uia_defines import IUIA
        from pywinauto.uia_element_info import UIAElementInfo
    except ImportError:
        return {}

    try:
        uia = IUIA()
        conditions = [
            _combine_conditions(
                uia,
                [
                    uia.iuia.CreatePropertyCondition(
                        uia.UIA_dll.UIA_AutomationIdPropertyId,
                        automation_id,
                    )
                    for automation_id in wanted
                ],
                use_or=True,
            )
        ]

        normalized_process_ids = tuple(
            dict.fromkeys(int(process_id) for process_id in process_ids)
        )
        if normalized_process_ids:
            conditions.append(
                _combine_conditions(
                    uia,
                    [
                        uia.iuia.CreatePropertyCondition(
                            uia.UIA_dll.UIA_ProcessIdPropertyId,
                            process_id,
                        )
                        for process_id in normalized_process_ids
                    ],
                    use_or=True,
                )
            )
        if control_type:
            control_type_id = uia.known_control_types.get(control_type)
            if control_type_id is None:
                return {}
            conditions.append(
                uia.iuia.CreatePropertyCondition(
                    uia.UIA_dll.UIA_ControlTypePropertyId,
                    control_type_id,
                )
            )

        condition = _combine_conditions(uia, conditions, use_or=False)
        root_info = _root_element_info(
            UIAElementInfo,
            root_handle=root_handle,
            root_element=root_element,
        )
        if root_info is None:
            return {}
        element_infos = root_info._get_elements(
            uia.tree_scope["descendants"],
            condition,
            cache_enable=False,
        )
    except Exception:
        return {}

    matches: dict[str, list[Any]] = {automation_id: [] for automation_id in wanted}
    seen: set[tuple[str, int]] = set()
    for element_info in element_infos:
        try:
            automation_id = str(element_info.automation_id or "").strip()
        except Exception:
            continue
        if automation_id not in matches:
            continue
        identity = _element_identity(element_info)
        if identity is not None and (automation_id, identity) in seen:
            continue
        try:
            wrapper = UIAWrapper(element_info)
        except Exception:
            continue
        matches[automation_id].append(wrapper)
        if identity is not None:
            seen.add((automation_id, identity))
    return matches


def _combine_conditions(uia: Any, conditions: list[Any], *, use_or: bool) -> Any:
    if not conditions:
        return uia.true_condition
    if len(conditions) == 1:
        return conditions[0]
    creator = (
        uia.iuia.CreateOrConditionFromArray
        if use_or
        else uia.iuia.CreateAndConditionFromArray
    )
    return creator(conditions)


def _root_element_info(
    element_info_type: Any,
    *,
    root_handle: int | None,
    root_element: Any | None,
) -> Any | None:
    if root_element is not None:
        element_info = getattr(root_element, "element_info", root_element)
        if callable(getattr(element_info, "_get_elements", None)):
            return element_info
    if root_handle is not None:
        try:
            return element_info_type(int(root_handle))
        except Exception:
            return None
    try:
        return element_info_type()
    except Exception:
        return None


def _element_identity(element_info: Any) -> int | None:
    try:
        handle = int(element_info.handle or 0)
    except Exception:
        handle = 0
    if handle > 0:
        return handle
    try:
        return hash(tuple(element_info.runtime_id or ()))
    except Exception:
        return None
