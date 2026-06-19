from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePath


@dataclass(frozen=True)
class EghisConnectorState:
    status: str
    process_running: bool
    process_name: str | None
    pid: int | None
    exe_path: str | None
    window_found: bool
    window_title: str | None
    window_handle: int | None
    is_active: bool
    last_seen_at: str | None
    message: str


_CACHED_STATE: EghisConnectorState | None = None


def discover_eghis(settings: dict[str, str]) -> EghisConnectorState:
    configured_process_name = settings.get("eghis_process_name", "")
    configured_window_title = settings.get("eghis_window_title_contains", "")
    process_info = _discover_process_info(configured_process_name)
    window_info = _discover_window_info(configured_window_title)
    is_active = _is_window_active(configured_window_title)
    last_seen_at = _timestamp_now() if process_info or window_info else None

    process_running = process_info is not None
    window_found = window_info is not None

    if process_running and window_found and is_active:
        return EghisConnectorState(
            status="green",
            process_running=True,
            process_name=process_info["process_name"],
            pid=process_info["pid"],
            exe_path=process_info["exe_path"],
            window_found=True,
            window_title=window_info["window_title"],
            window_handle=window_info["window_handle"],
            is_active=True,
            last_seen_at=last_seen_at,
            message="Connected and active",
        )
    if process_running and window_found:
        return EghisConnectorState(
            status="yellow",
            process_running=True,
            process_name=process_info["process_name"],
            pid=process_info["pid"],
            exe_path=process_info["exe_path"],
            window_found=True,
            window_title=window_info["window_title"],
            window_handle=window_info["window_handle"],
            is_active=False,
            last_seen_at=last_seen_at,
            message="Eghis found but not active",
        )
    if process_running:
        return EghisConnectorState(
            status="red",
            process_running=True,
            process_name=process_info["process_name"],
            pid=process_info["pid"],
            exe_path=process_info["exe_path"],
            window_found=False,
            window_title=None,
            window_handle=None,
            is_active=False,
            last_seen_at=last_seen_at,
            message="Eghis process found but window missing",
        )
    if window_found:
        return EghisConnectorState(
            status="red",
            process_running=False,
            process_name=None,
            pid=None,
            exe_path=None,
            window_found=True,
            window_title=window_info["window_title"],
            window_handle=window_info["window_handle"],
            is_active=is_active,
            last_seen_at=last_seen_at,
            message="Eghis window found but process mismatch",
        )
    return EghisConnectorState(
        status="red",
        process_running=False,
        process_name=None,
        pid=None,
        exe_path=None,
        window_found=False,
        window_title=None,
        window_handle=None,
        is_active=False,
        last_seen_at=None,
        message="Eghis not found",
    )


def get_cached_eghis_state() -> EghisConnectorState | None:
    return _CACHED_STATE


def refresh_cached_eghis_state(settings: dict[str, str]) -> EghisConnectorState:
    global _CACHED_STATE
    _CACHED_STATE = discover_eghis(settings)
    return _CACHED_STATE


def ensure_ready_for_macro(settings: dict[str, str]) -> EghisConnectorState:
    state = get_cached_eghis_state()
    if state is None or not is_cached_window_still_valid(state):
        state = refresh_cached_eghis_state(settings)

    if not state.process_running or not state.window_found:
        return state
    if not state.is_active:
        return replace(
            state,
            status="yellow",
            message="Eghis window is not active. Click Eghis and retry.",
        )
    return replace(state, status="green", message="Connected and active")


def is_cached_window_still_valid(state: EghisConnectorState) -> bool:
    if not state.window_found:
        return False
    if state.pid is not None and not _pid_exists(state.pid):
        return False
    current_window = _discover_window_info(state.window_title or "")
    if current_window is None:
        return False
    if state.window_handle is not None and current_window["window_handle"] is not None:
        return current_window["window_handle"] == state.window_handle
    if state.window_title:
        return current_window["window_title"] == state.window_title
    return False


def _discover_process_info(process_name: str) -> dict[str, str | int] | None:
    tokens = _normalized_candidates(process_name)
    if not tokens:
        return None
    try:
        import psutil
    except ImportError:
        return None

    try:
        processes = psutil.process_iter(["pid", "name", "exe", "cmdline"])
    except Exception:
        return None

    for process in processes:
        process_info = getattr(process, "info", {})
        matched_name = _match_process(process_info, tokens)
        if matched_name:
            return {
                "process_name": matched_name,
                "pid": process_info.get("pid"),
                "exe_path": process_info.get("exe"),
            }
    return None


def _discover_window_info(title_fragment: str) -> dict[str, str | int | None] | None:
    tokens = _normalized_candidates(title_fragment)
    if not tokens:
        return None

    for window in _windows_from_pygetwindow():
        title = (window.get("window_title") or "").strip()
        if title and any(token in title.casefold() for token in tokens):
            return window

    for window in _windows_from_pywinauto():
        title = (window.get("window_title") or "").strip()
        if title and any(token in title.casefold() for token in tokens):
            return window
    return None


def _windows_from_pygetwindow() -> list[dict[str, str | int | None]]:
    try:
        import pygetwindow
    except ImportError:
        return []

    try:
        windows = pygetwindow.getAllWindows()
    except Exception:
        return []

    results: list[dict[str, str | int | None]] = []
    for window in windows:
        title = getattr(window, "title", "") or ""
        handle = getattr(window, "_hWnd", None)
        if handle is None:
            handle = getattr(window, "hWnd", None)
        results.append({"window_title": title, "window_handle": handle})
    return results


def _windows_from_pywinauto() -> list[dict[str, str | int | None]]:
    try:
        from pywinauto import Desktop
    except ImportError:
        return []

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return []

    results: list[dict[str, str | int | None]] = []
    for window in windows:
        try:
            title = window.window_text() or ""
        except Exception:
            title = ""
        handle = getattr(window, "handle", None)
        if handle is None:
            handle = getattr(getattr(window, "element_info", None), "handle", None)
        results.append({"window_title": title, "window_handle": handle})
    return results


def _is_window_active(title_fragment: str) -> bool:
    from KaosEghis.core.emr_detector import is_target_window_active

    return is_target_window_active(title_fragment)


def _pid_exists(pid: int) -> bool:
    try:
        import psutil
    except ImportError:
        return False
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def _normalized_candidates(value: str) -> list[str]:
    raw = value.replace(";", ",")
    return [part.strip().casefold() for part in raw.split(",") if part.strip()]


def _match_process(process_info: dict, tokens: list[str]) -> str | None:
    names = _process_identity_candidates(process_info)
    for candidate in names:
        normalized = candidate.casefold()
        stem = PurePath(candidate).stem.casefold()
        for token in tokens:
            token_stem = PurePath(token).stem.casefold()
            if normalized == token or stem == token_stem:
                return candidate
            if token in normalized or token_stem in stem:
                return candidate
    return None


def _process_identity_candidates(process_info: dict) -> list[str]:
    values: list[str] = []
    name = process_info.get("name") or ""
    exe = process_info.get("exe") or ""
    cmdline = process_info.get("cmdline") or []
    if name:
        values.append(name)
    if exe:
        values.append(PurePath(exe).name)
    if cmdline:
        first = cmdline[0] or ""
        if first:
            values.append(PurePath(first).name)
    return _unique_preserving_order(values)


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _timestamp_now() -> str:
    return datetime.now().isoformat(timespec="seconds")
