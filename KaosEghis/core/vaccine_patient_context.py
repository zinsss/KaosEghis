from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Callable

from KaosEghis.core.eghis_connector import ensure_cached_connection_ready
from KaosEghis.core.uia_fast_lookup import find_uia_elements_by_automation_ids
from KaosEghis.core.vaccine_eligibility import birth_date_from_resident_id


DEFAULT_PATIENT_INFO_OPEN_COORDINATES = (210, 115)
DEFAULT_PATIENT_INFO_TIMEOUT_SECONDS = 4.0
PATIENT_FIELD_AUTOMATION_ID_FALLBACKS = {
    # Older/current patient-information views expose this value as txtSexAge,
    # while the main treatment view commonly exposes lblSexAge.
    "sex_age": ("txtSexAge",),
}


@dataclass(frozen=True)
class VaccinePatientContext:
    chart_no: str
    resident_id: str
    patient_name: str
    patient_sex: str
    patient_age: str
    patient_birth_date: str
    patient_phone: str
    patient_address: str


@dataclass(frozen=True)
class VaccinePatientFetchResult:
    success: bool
    message: str
    context: VaccinePatientContext | None
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PatientInformationResolution:
    scope: Any
    chart_value: str


@dataclass(frozen=True)
class _ResolvedChartCandidate:
    element: Any
    value: str


def resident_id_for_label(resident_id: str) -> str:
    """Preserve the captured resident-number spelling for label output."""

    return str(resident_id or "").strip()


def resident_id_for_vaccine_system(resident_id: str) -> str:
    """Remove hyphens only at the external vaccine-system input boundary."""

    return resident_id_for_label(resident_id).replace("-", "")


def fetch_vaccine_patient_context(
    settings: dict[str, str],
    target_automation_ids: dict[str, str],
    *,
    opener_coordinates: tuple[int, int] = DEFAULT_PATIENT_INFO_OPEN_COORDINATES,
    timeout_seconds: float = DEFAULT_PATIENT_INFO_TIMEOUT_SECONDS,
    connection_checker: Callable[[dict[str, str]], Any] = ensure_cached_connection_ready,
    desktop_factory: Callable[..., Any] | None = None,
    process_family_provider: Callable[[int], tuple[int, ...]] | None = None,
    process_target_finder: Callable[[str, tuple[int, ...]], Any | None] | None = None,
    clicker: Callable[[tuple[int, int]], None] | None = None,
    closer: Callable[[], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> VaccinePatientFetchResult:
    """Open the eGHIS patient-information view and read configured fields."""

    chart_automation_id = target_automation_ids.get("chart_no", "").strip()
    if not chart_automation_id:
        return VaccinePatientFetchResult(
            False,
            "Vaccine patient chart target is not configured.",
            None,
        )

    state = connection_checker(settings)
    if getattr(state, "status", "red") != "green" or getattr(state, "pid", None) is None:
        return VaccinePatientFetchResult(
            False,
            "EMR connection is not ready. Reconnect EMR and retry.",
            None,
        )

    uses_native_desktop = desktop_factory is None
    if desktop_factory is None:
        try:
            from pywinauto import Desktop
        except ImportError:
            return VaccinePatientFetchResult(
                False,
                "UIA patient information reading is unavailable.",
                None,
            )
        desktop_factory = Desktop

    if clicker is None:
        clicker = _click_patient_info_opener
    if closer is None:
        closer = _close_patient_information
    if process_family_provider is None:
        process_family_provider = _trusted_eghis_process_ids
    if process_target_finder is None and uses_native_desktop:
        process_target_finder = _find_exact_uia_edit_in_processes

    try:
        clicker(opener_coordinates)
    except Exception:
        return VaccinePatientFetchResult(
            False,
            "Patient information window could not be opened.",
            None,
        )

    try:
        desktop = desktop_factory(backend="uia")
    except Exception:
        return VaccinePatientFetchResult(
            False,
            "UIA patient information reading is unavailable.",
            None,
        )

    deadline = clock() + max(float(timeout_seconds), 0.1)
    patient_resolution = None
    while clock() <= deadline:
        # The patient-information window may start in an eGHIS helper process
        # after the opener is clicked, so refresh the trusted family each pass.
        process_ids = process_family_provider(int(state.pid))
        patient_resolution = _find_patient_information_scope(
            desktop,
            state,
            chart_automation_id,
            process_ids,
            process_target_finder=process_target_finder,
        )
        if patient_resolution is not None:
            break
        sleeper(0.1)

    if patient_resolution is None:
        return VaccinePatientFetchResult(
            False,
            "Patient information opened, but its chart-number target was not found. "
            "Check the Vaccine EMR target settings.",
            None,
        )

    field_automation_ids = {
        field_name: _field_automation_id_candidates(field_name, automation_id)
        for field_name, automation_id in target_automation_ids.items()
        if field_name != "chart_no"
    }
    configured_ids = {
        automation_id
        for candidates in field_automation_ids.values()
        for automation_id in candidates
        if automation_id != chart_automation_id
    }
    elements_by_id = _find_elements_by_automation_id(
        patient_resolution.scope,
        configured_ids,
    )
    # Keep the exact control that established popup readiness. A second tree
    # pass can omit or ambiguously expose this WinForms edit even though its
    # ValuePattern was available during the process-scoped lookup.
    values = {
        field_name: _read_first_target_value(elements_by_id, automation_ids)
        for field_name, automation_ids in field_automation_ids.items()
    }
    values["chart_no"] = patient_resolution.chart_value
    close_succeeded = True
    try:
        closer()
    except Exception:
        close_succeeded = False

    chart_no = values.get("chart_no", "").strip()
    if not chart_no:
        return VaccinePatientFetchResult(
            False,
            "Patient chart number could not be read.",
            None,
        )

    resident_id = values.get("resident_id", "").strip()
    sex, age = _split_sex_age(values.get("sex_age", ""))
    birth_date = values.get("birth_date", "").strip()
    if not birth_date:
        derived_birth_date = birth_date_from_resident_id(resident_id)
        birth_date = derived_birth_date.isoformat() if derived_birth_date else ""
    patient_phone = values.get("mobile_phone", "").strip() or values.get(
        "telephone", ""
    ).strip()
    context = VaccinePatientContext(
        chart_no=chart_no,
        resident_id=resident_id,
        patient_name=values.get("patient_name", "").strip(),
        patient_sex=sex,
        patient_age=age,
        patient_birth_date=birth_date,
        patient_phone=patient_phone,
        patient_address=values.get("address", "").strip(),
    )
    missing_fields = tuple(
        field_name
        for field_name, value in (
            ("resident_id", context.resident_id),
            ("patient_name", context.patient_name),
            ("patient_sex", context.patient_sex),
            ("patient_age", context.patient_age),
            ("birth_date", context.patient_birth_date),
            ("patient_phone", context.patient_phone),
            ("address", context.patient_address),
        )
        if not value
    )
    message = (
        "Loaded patient context from EMR."
        if not missing_fields
        else "Loaded partial patient context from EMR."
    )
    if not close_succeeded:
        message += " Close the Patient Information window manually."
    return VaccinePatientFetchResult(True, message, context, missing_fields)


def _click_patient_info_opener(coords: tuple[int, int]) -> None:
    from pywinauto import mouse

    mouse.click(button="left", coords=coords)


def _close_patient_information() -> None:
    from pywinauto.keyboard import send_keys

    send_keys("{ESC}")


def _find_patient_information_scope(
    desktop: Any,
    state: Any,
    chart_automation_id: str,
    process_ids: tuple[int, ...] | None = None,
    *,
    process_target_finder: Callable[[str, tuple[int, ...]], Any | None] | None = None,
) -> _PatientInformationResolution | None:
    cached_roots: list[Any] = []
    seen_handles: set[int] = set()
    for handle in (
        getattr(state, "main_window_handle", None),
        getattr(state, "window_handle", None),
    ):
        if handle is None or int(handle) in seen_handles:
            continue
        try:
            root = desktop.window(handle=handle).wrapper_object()
        except Exception:
            continue
        cached_roots.append(root)
        seen_handles.add(int(handle))

    trusted_process_ids = process_ids or (int(state.pid),)

    # Use the exact native UIA property query before enumerating any process
    # windows. The patient-information control has a stable Automation ID even
    # though it can live under a transient eGHIS child window.
    if process_target_finder is not None:
        try:
            chart_element = process_target_finder(
                chart_automation_id,
                tuple(int(process_id) for process_id in trusted_process_ids),
            )
        except Exception:
            chart_element = None
        resolution = _patient_information_resolution(chart_element)
        if resolution is not None:
            return resolution

    process_roots: list[Any] = []
    for process_id in trusted_process_ids:
        try:
            process_windows = desktop.windows(
                process=int(process_id),
                visible_only=False,
            )
        except TypeError:
            # Keep compatibility with small test doubles and older backends.
            try:
                process_windows = desktop.windows(process=int(process_id))
            except Exception:
                process_windows = []
        except Exception:
            process_windows = []
        for root in process_windows:
            handle = _element_handle(root)
            if handle is not None and handle in seen_handles:
                continue
            process_roots.append(root)
            if handle is not None:
                seen_handles.add(handle)

    # New helper windows are usually much smaller than the cached main window.
    # Search them before falling back to the cached eGHIS roots.
    for root in process_roots:
        chart_element = _find_element(root, chart_automation_id)
        resolution = _patient_information_resolution(
            chart_element,
            fallback_scope=root,
        )
        if resolution is not None:
            return resolution

    for root in cached_roots:
        chart_element = _find_element(root, chart_automation_id)
        resolution = _patient_information_resolution(
            chart_element,
            fallback_scope=root,
        )
        if resolution is not None:
            return resolution
    return None


def _find_exact_uia_edit_in_processes(
    automation_id: str,
    process_ids: tuple[int, ...],
) -> Any | None:
    """Find the patient-info Edit through a native exact Automation-ID query."""

    matches = find_uia_elements_by_automation_ids(
        (automation_id,),
        process_ids=process_ids,
        control_type="Edit",
    )
    candidates = _deduplicate_elements(matches.get(automation_id, []))
    visible_with_values: list[_ResolvedChartCandidate] = []
    for candidate in candidates:
        if not _element_is_visible(candidate):
            continue
        value = _read_element_value(candidate)
        if value:
            visible_with_values.append(_ResolvedChartCandidate(candidate, value))

    patient_info_candidates = [
        candidate
        for candidate in visible_with_values
        if _nearest_patient_information_scope(candidate.element) is not None
    ]
    if len(patient_info_candidates) == 1:
        return patient_info_candidates[0]
    if len(visible_with_values) == 1:
        return visible_with_values[0]
    return None


def _top_level_scope(element: Any) -> Any:
    try:
        return element.top_level_parent()
    except Exception:
        return element


def _patient_information_resolution(
    chart_element: Any | None,
    *,
    fallback_scope: Any | None = None,
) -> _PatientInformationResolution | None:
    if isinstance(chart_element, _ResolvedChartCandidate):
        chart_value = chart_element.value
        chart_element = chart_element.element
    else:
        chart_value = _read_element_value(chart_element)
    if not chart_value:
        return None
    scope = _nearest_patient_information_scope(chart_element)
    if scope is None:
        scope = fallback_scope or _top_level_scope(chart_element)
    return _PatientInformationResolution(scope, chart_value)


def _nearest_patient_information_scope(element: Any) -> Any | None:
    current = element
    for _ in range(12):
        try:
            current = current.parent()
        except Exception:
            return None
        if current is None:
            return None
        if _element_name(current).casefold() == "환자 기초 정보".casefold():
            return current
    return None


def _trusted_eghis_process_ids(root_pid: int) -> tuple[int, ...]:
    """Return the connected eGHIS process family without unrelated processes."""

    process_ids = [int(root_pid)]
    try:
        import psutil

        connected_process = psutil.Process(int(root_pid))
    except Exception:
        return tuple(process_ids)

    family_root = connected_process
    current = connected_process
    while True:
        try:
            parent = current.parent()
            parent_name = str(parent.name() or "").strip().casefold()
        except Exception:
            break
        if not parent_name.startswith("eghis"):
            break
        family_root = parent
        current = parent

    family: list[Any] = [family_root]
    try:
        family.extend(family_root.children(recursive=True))
    except Exception:
        pass
    for process in family:
        try:
            name = str(process.name() or "").strip().casefold()
            process_id = int(process.pid)
        except Exception:
            continue
        if name.startswith("eghis") and process_id not in process_ids:
            process_ids.append(process_id)
    return tuple(process_ids)


def _read_target_value(scope: Any, automation_id: str) -> str:
    element = _find_element(scope, automation_id)
    return _read_element_value(element)


def _field_automation_id_candidates(
    field_name: str,
    configured_automation_id: str,
) -> tuple[str, ...]:
    candidates = (
        str(configured_automation_id or "").strip(),
        *PATIENT_FIELD_AUTOMATION_ID_FALLBACKS.get(field_name, ()),
    )
    return tuple(dict.fromkeys(value for value in candidates if value))


def _read_first_target_value(
    elements_by_id: dict[str, Any],
    automation_ids: tuple[str, ...],
) -> str:
    for automation_id in automation_ids:
        value = _read_element_value(elements_by_id.get(automation_id))
        if value:
            return value
    return ""


def _read_element_value(element: Any | None) -> str:
    if element is None:
        return ""
    try:
        iface_value = getattr(element, "iface_value", None)
    except Exception:
        iface_value = None
    if iface_value is not None:
        for attribute in ("CurrentValue", "Value"):
            try:
                value = getattr(iface_value, attribute, None)
            except Exception:
                value = None
            text = str(value or "").strip()
            if text:
                return text

    try:
        legacy = element.legacy_properties()
    except Exception:
        legacy = None
    if isinstance(legacy, dict):
        for key in ("Value", "Name"):
            text = str(legacy.get(key) or "").strip()
            if text:
                return text

    for reader_name in ("get_value", "texts", "window_text"):
        try:
            value = getattr(element, reader_name)()
        except Exception:
            continue
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value if item).strip()
        else:
            text = str(value or "").strip()
        if text:
            return text
    try:
        return str(element.element_info.name or "").strip()
    except Exception:
        return ""


def _find_element(scope: Any, automation_id: str) -> Any | None:
    return _find_elements_by_automation_id(
        scope,
        {str(automation_id or "").strip()},
    ).get(str(automation_id or "").strip())


def _find_elements_by_automation_id(
    scope: Any,
    automation_ids: set[str],
) -> dict[str, Any]:
    wanted = {value for value in automation_ids if value}
    if not wanted:
        return {}

    element_info = getattr(scope, "element_info", None)
    if callable(getattr(element_info, "_get_elements", None)):
        matches = find_uia_elements_by_automation_ids(
            wanted,
            root_element=scope,
        )
        return {
            automation_id: selected
            for automation_id, candidates in matches.items()
            if (selected := _select_unique_visible_element(candidates)) is not None
        }

    # pywinauto WindowSpecification exposes child_window(), while a resolved
    # UIAWrapper exposes descendants(). Support both without rescanning once per field.
    descendants_method = getattr(scope, "descendants", None)
    if callable(descendants_method):
        try:
            candidates = [scope, *descendants_method()]
        except Exception:
            candidates = []
        matches: dict[str, list[Any]] = {automation_id: [] for automation_id in wanted}
        for candidate in candidates:
            candidate_id = _element_automation_id(candidate)
            if candidate_id in matches:
                matches[candidate_id].append(candidate)
        return {
            automation_id: selected
            for automation_id, candidates in matches.items()
            if (selected := _select_unique_visible_element(candidates)) is not None
        }

    child_window = getattr(scope, "child_window", None)
    if not callable(child_window):
        return {}
    resolved: dict[str, Any] = {}
    for automation_id in wanted:
        try:
            resolved[automation_id] = child_window(
                auto_id=automation_id
            ).wrapper_object()
        except Exception:
            continue
    return resolved


def _element_automation_id(element: Any) -> str:
    try:
        return str(element.element_info.automation_id or "").strip()
    except Exception:
        return ""


def _element_name(element: Any) -> str:
    try:
        return str(element.element_info.name or "").strip()
    except Exception:
        return ""


def _select_unique_visible_element(candidates: list[Any]) -> Any | None:
    """Choose an exact selector match without guessing between visible controls."""

    if len(candidates) == 1:
        return candidates[0]
    visible = [candidate for candidate in candidates if _element_is_visible(candidate)]
    return visible[0] if len(visible) == 1 else None


def _element_is_visible(element: Any) -> bool:
    try:
        return bool(element.is_visible())
    except Exception:
        pass
    info = getattr(element, "element_info", None)
    try:
        visible = getattr(info, "visible", None)
    except Exception:
        visible = None
    if visible is not None:
        return bool(visible)
    try:
        return not bool(getattr(info, "offscreen"))
    except Exception:
        return False


def _element_handle(element: Any) -> int | None:
    value = getattr(element, "handle", None)
    if value is None:
        value = getattr(getattr(element, "element_info", None), "handle", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _deduplicate_elements(elements: list[Any]) -> list[Any]:
    unique: list[Any] = []
    seen_handles: set[int] = set()
    for element in elements:
        handle = _element_handle(element)
        if handle is not None and handle > 0:
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
        unique.append(element)
    return unique


def _split_sex_age(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in re.split(r"[/|]", value or "", maxsplit=1)]
    sex_text = parts[0] if parts else ""
    age_text = parts[1] if len(parts) > 1 else ""
    normalized_sex = _normalize_sex(sex_text)
    age_match = re.search(r"\d+", age_text)
    return normalized_sex, age_match.group(0) if age_match else ""


def _normalize_sex(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.startswith(("m", "남")):
        return "M"
    if normalized.startswith(("f", "여")):
        return "F"
    return "O" if normalized else ""
