from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Callable

from KaosEghis.core.eghis_connector import ensure_cached_connection_ready


DEFAULT_PATIENT_INFO_OPEN_COORDINATES = (209, 155)
DEFAULT_PATIENT_INFO_TIMEOUT_SECONDS = 4.0


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
    patient_scope = None
    while clock() <= deadline:
        patient_scope = _find_patient_information_scope(
            desktop,
            state,
            chart_automation_id,
        )
        if patient_scope is not None:
            break
        sleeper(0.1)

    if patient_scope is None:
        return VaccinePatientFetchResult(
            False,
            "Patient information window was not ready.",
            None,
        )

    values = {
        field_name: _read_target_value(patient_scope, automation_id)
        for field_name, automation_id in target_automation_ids.items()
        if automation_id.strip()
    }
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

    sex, age = _split_sex_age(values.get("sex_age", ""))
    patient_phone = values.get("mobile_phone", "").strip() or values.get(
        "telephone", ""
    ).strip()
    context = VaccinePatientContext(
        chart_no=chart_no,
        resident_id=values.get("resident_id", "").strip(),
        patient_name=values.get("patient_name", "").strip(),
        patient_sex=sex,
        patient_age=age,
        patient_birth_date=values.get("birth_date", "").strip(),
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
) -> Any | None:
    roots: list[Any] = []
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
        roots.append(root)
        seen_handles.add(int(handle))

    try:
        process_windows = desktop.windows(process=int(state.pid))
    except Exception:
        process_windows = []
    for root in process_windows:
        handle = _element_handle(root)
        if handle is not None and handle in seen_handles:
            continue
        roots.append(root)
        if handle is not None:
            seen_handles.add(handle)

    for root in roots:
        if _find_element(root, chart_automation_id) is not None:
            return root
    return None


def _read_target_value(scope: Any, automation_id: str) -> str:
    element = _find_element(scope, automation_id)
    if element is None:
        return ""
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
        value = element.iface_value.CurrentValue
    except Exception:
        value = ""
    if value:
        return str(value).strip()
    try:
        return str(element.element_info.name or "").strip()
    except Exception:
        return ""


def _find_element(scope: Any, automation_id: str) -> Any | None:
    try:
        return scope.child_window(auto_id=automation_id).wrapper_object()
    except Exception:
        return None


def _element_handle(element: Any) -> int | None:
    value = getattr(element, "handle", None)
    if value is None:
        value = getattr(getattr(element, "element_info", None), "handle", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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
