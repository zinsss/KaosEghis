from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import PurePath
import time


CACHE_TTL_SECONDS = 10
FOCUS_RETRY_ATTEMPTS = 5
FOCUS_RETRY_DELAY_SECONDS = 0.1


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
    window_owner_pid: int | None
    is_active: bool
    last_seen_at: str | None
    message: str


_CACHED_STATE: EghisConnectorState | None = None


def build_connector_settings(
    base_settings: dict[str, str],
    *,
    process_name: str | None = None,
    window_title_contains: str | None = None,
    executable_path: str | None = None,
) -> dict[str, str]:
    settings = dict(base_settings)
    if process_name is not None:
        settings["eghis_process_name"] = process_name
    if window_title_contains is not None:
        settings["eghis_window_title_contains"] = window_title_contains
    if executable_path is not None:
        settings["eghis_executable_path"] = executable_path
    return settings


def discover_eghis(settings: dict[str, str]) -> EghisConnectorState:
    configured_process_name = settings.get("eghis_process_name", "")
    configured_window_title = settings.get("eghis_window_title_contains", "")
    process_info = _discover_process_info(configured_process_name)
    window_info = _discover_window_info(configured_window_title)
    window_handle = None if window_info is None else window_info.get("window_handle")
    window_owner_pid = _get_window_owner_pid(window_handle) if window_handle is not None else None
    is_active = bool(window_handle is not None and _foreground_handle_matches(window_handle))
    last_seen_at = _timestamp_now() if process_info or window_info else None

    process_running = process_info is not None
    window_found = window_info is not None

    if process_running and window_found and process_info["pid"] != window_owner_pid:
        return EghisConnectorState(
            status="red",
            process_running=True,
            process_name=process_info["process_name"],
            pid=process_info["pid"],
            exe_path=process_info["exe_path"],
            window_found=True,
            window_title=window_info["window_title"],
            window_handle=window_info["window_handle"],
            window_owner_pid=window_owner_pid,
            is_active=is_active,
            last_seen_at=last_seen_at,
            message="window process mismatch",
        )
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
            window_owner_pid=window_owner_pid,
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
            window_owner_pid=window_owner_pid,
            is_active=False,
            last_seen_at=last_seen_at,
            message="Connected - will focus on run",
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
            window_owner_pid=None,
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
            window_owner_pid=window_owner_pid,
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
        window_owner_pid=None,
        is_active=False,
        last_seen_at=None,
        message="Eghis not found",
    )


def get_cached_eghis_state() -> EghisConnectorState | None:
    return _CACHED_STATE


def clear_cached_eghis_state() -> None:
    global _CACHED_STATE
    _CACHED_STATE = None


def cached_state_matches_settings(
    state: EghisConnectorState | None, settings: dict[str, str]
) -> bool:
    if state is None:
        return False
    return _process_identity_matches_state(state, settings)


def refresh_cached_eghis_state(settings: dict[str, str]) -> EghisConnectorState:
    global _CACHED_STATE
    _CACHED_STATE = discover_eghis(settings)
    return _CACHED_STATE


def ensure_cached_connection_ready(settings: dict[str, str]) -> EghisConnectorState:
    global _CACHED_STATE
    state = get_cached_eghis_state()
    if state is None:
        return _manual_reconnect_required(
            None,
            "Application not connected. Connect manually and retry.",
        )
    if not state.process_running or state.pid is None or not _pid_exists(state.pid):
        blocked = _manual_reconnect_required(
            state,
            "Application not running. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked
    if not _process_identity_matches_state(state, settings):
        blocked = _manual_reconnect_required(
            state,
            "Connected application does not match preset. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked
    if state.window_handle is None or not _window_handle_is_valid(state.window_handle):
        blocked = _manual_reconnect_required(
            state,
            "Application connection stale. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked
    owner_pid = _get_window_owner_pid(state.window_handle)
    if owner_pid is None or owner_pid != state.pid:
        blocked = _manual_reconnect_required(
            replace(state, window_owner_pid=owner_pid),
            "Application connection stale. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked
    if _has_blocking_modal_dialog(state, settings):
        blocked = _manual_reconnect_required(
            state,
            "Application not focusable. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked
    is_active_now = _foreground_handle_matches(state.window_handle)
    state = replace(state, is_active=is_active_now)
    if not is_active_now:
        focus_succeeded, _focus_reason = _focus_and_confirm_window(
            state.window_handle,
            state,
            settings,
        )
        if not focus_succeeded:
            blocked = _manual_reconnect_required(
                state,
                "Application not focusable. Reconnect manually and retry.",
            )
            _CACHED_STATE = blocked
            return blocked
    foreground = _get_foreground_window_info()
    if foreground is None or foreground.get("window_handle") != state.window_handle:
        blocked = _manual_reconnect_required(
            state,
            "Application not focusable. Reconnect manually and retry.",
        )
        _CACHED_STATE = blocked
        return blocked

    ready = replace(
        state,
        status="green",
        is_active=True,
        window_owner_pid=owner_pid,
        last_seen_at=_timestamp_now(),
        message="Connected and active",
    )
    _CACHED_STATE = ready
    return ready


def ensure_ready_for_macro(settings: dict[str, str]) -> EghisConnectorState:
    global _CACHED_STATE
    state = get_cached_eghis_state()
    if state is None or _is_state_stale(state) or not is_cached_window_still_valid(state):
        rediscovered = refresh_cached_eghis_state(settings)
        if not rediscovered.process_running or not rediscovered.window_found:
            blocked = replace(rediscovered, status="red", message="rediscovery failed")
            _CACHED_STATE = blocked
            return blocked
        if rediscovered.window_owner_pid != rediscovered.pid:
            blocked = replace(rediscovered, status="red", is_active=False, message="window process mismatch")
            _CACHED_STATE = blocked
            return blocked
        state = rediscovered

    if not state.process_running or state.pid is None or not _pid_exists(state.pid):
        blocked = replace(state, status="red", is_active=False, message="Eghis not running")
        _CACHED_STATE = blocked
        return blocked

    if not _process_identity_matches_state(state, settings):
        blocked = replace(state, status="red", is_active=False, message="Eghis not running")
        _CACHED_STATE = blocked
        return blocked

    if state.window_handle is None or not _window_handle_is_valid(state.window_handle):
        blocked = replace(state, status="red", window_found=False, is_active=False, message="window handle invalid")
        _CACHED_STATE = blocked
        return blocked

    owner_pid = _get_window_owner_pid(state.window_handle)
    if owner_pid is None or owner_pid != state.pid:
        blocked = replace(state, status="red", is_active=False, window_owner_pid=owner_pid, message="window process mismatch")
        _CACHED_STATE = blocked
        return blocked

    if _has_blocking_modal_dialog(state, settings):
        blocked = replace(state, status="red", is_active=False, message="modal/popup detected")
        _CACHED_STATE = blocked
        return blocked

    if not state.is_active:
        focus_succeeded, focus_reason = _focus_and_confirm_window(
            state.window_handle,
            state,
            settings,
        )
        if not focus_succeeded:
            blocked = replace(state, status="red", is_active=False, message=focus_reason)
            _CACHED_STATE = blocked
            return blocked

    foreground = _get_foreground_window_info()
    if foreground is None or foreground.get("window_handle") != state.window_handle:
        reason = "modal/popup detected" if _foreground_looks_like_modal(foreground, state, settings) else "foreground mismatch"
        blocked = replace(state, status="red", is_active=False, message=reason)
        _CACHED_STATE = blocked
        return blocked

    ready = replace(state, status="green", is_active=True, window_owner_pid=owner_pid, last_seen_at=_timestamp_now(), message="Connected and active")
    _CACHED_STATE = ready
    return ready


def is_cached_window_still_valid(state: EghisConnectorState) -> bool:
    if not state.window_found:
        return False
    if _is_state_stale(state):
        return False
    if state.pid is None or not _pid_exists(state.pid):
        return False
    if state.window_handle is None:
        return False
    if not _window_handle_is_valid(state.window_handle):
        return False
    owner_pid = _get_window_owner_pid(state.window_handle)
    return owner_pid == state.pid and owner_pid == state.window_owner_pid


def _is_state_stale(state: EghisConnectorState) -> bool:
    if not state.last_seen_at:
        return True
    try:
        seen = datetime.fromisoformat(state.last_seen_at)
    except ValueError:
        return True
    return datetime.now() - seen > timedelta(seconds=CACHE_TTL_SECONDS)


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

    best_match: dict[str, str | int] | None = None
    best_score = -1
    for process in processes:
        process_info = getattr(process, "info", {})
        matched = _match_process_with_score(process_info, tokens)
        if matched is None:
            continue
        matched_name, score = matched
        if score > best_score:
            best_score = score
            best_match = {
                "process_name": matched_name,
                "pid": process_info.get("pid"),
                "exe_path": process_info.get("exe"),
            }
    return best_match


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


def _foreground_handle_matches(window_handle: int) -> bool:
    foreground = _get_foreground_window_info()
    if foreground is None:
        return False
    return foreground.get("window_handle") == window_handle


def _get_foreground_window_info() -> dict[str, str | int | None] | None:
    try:
        import pygetwindow
    except ImportError:
        return None
    try:
        active = pygetwindow.getActiveWindow()
    except Exception:
        return None
    if active is None:
        return None
    title = getattr(active, "title", "") or ""
    handle = getattr(active, "_hWnd", None)
    if handle is None:
        handle = getattr(active, "hWnd", None)
    return {"window_title": title, "window_handle": handle}


def _get_window_owner_pid(window_handle: int | None) -> int | None:
    if window_handle is None:
        return None
    try:
        import win32process
        _thread_id, pid = win32process.GetWindowThreadProcessId(window_handle)
        return int(pid)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(wintypes.HWND(window_handle), ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def _window_handle_is_valid(window_handle: int) -> bool:
    if window_handle is None:
        return False
    try:
        import win32gui

        return bool(win32gui.IsWindow(window_handle))
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        return bool(ctypes.windll.user32.IsWindow(wintypes.HWND(window_handle)))
    except Exception:
        pass
    windows = _windows_from_pygetwindow() + _windows_from_pywinauto()
    return any(window.get("window_handle") == window_handle for window in windows)


def _focus_window_handle(window_handle: int) -> bool:
    try:
        import win32con
        import win32gui

        win32gui.ShowWindow(window_handle, win32con.SW_RESTORE)
        win32gui.BringWindowToTop(window_handle)
        win32gui.SetForegroundWindow(window_handle)
        return True
    except Exception:
        pass
    try:
        import pygetwindow
        window = pygetwindow.Win32Window(window_handle)
        window.activate()
        return True
    except Exception:
        pass
    try:
        from pywinauto import Desktop
        Desktop(backend="uia").window(handle=window_handle).set_focus()
        return True
    except Exception:
        return False


def _focus_and_confirm_window(
    window_handle: int,
    state: EghisConnectorState,
    settings: dict[str, str],
) -> tuple[bool, str]:
    if not _focus_window_handle(window_handle):
        return False, "focus failed"

    for attempt in range(FOCUS_RETRY_ATTEMPTS):
        foreground = _get_foreground_window_info()
        if foreground is not None and foreground.get("window_handle") == window_handle:
            return True, "Connected and active"
        if _foreground_looks_like_modal(foreground, state, settings):
            return False, "modal/popup detected"
        if attempt < FOCUS_RETRY_ATTEMPTS - 1:
            time.sleep(FOCUS_RETRY_DELAY_SECONDS)
            _focus_window_handle(window_handle)

    return False, "foreground mismatch"


def _has_blocking_modal_dialog(state: EghisConnectorState, settings: dict[str, str]) -> bool:
    foreground = _get_foreground_window_info()
    return _foreground_looks_like_modal(foreground, state, settings)


def _foreground_looks_like_modal(
    foreground: dict[str, str | int | None] | None,
    state: EghisConnectorState,
    settings: dict[str, str],
) -> bool:
    if foreground is None:
        return False
    foreground_handle = foreground.get("window_handle")
    if foreground_handle == state.window_handle:
        return False
    title = str(foreground.get("window_title") or "")
    fragment = settings.get("eghis_window_title_contains", "").strip().casefold()
    state_title = (state.window_title or "").casefold()
    return bool(
        title
        and (
            (fragment and fragment in title.casefold())
            or (state_title and state_title in title.casefold())
        )
    )


def _process_identity_matches_state(state: EghisConnectorState, settings: dict[str, str]) -> bool:
    configured = settings.get("eghis_process_name", "")
    tokens = _normalized_candidates(configured)
    if not tokens:
        return False
    configured_executable_path = (settings.get("eghis_executable_path") or "").strip()
    if configured_executable_path and not _executable_path_matches(
        state.exe_path, configured_executable_path
    ):
        return False
    process_info = {
        "name": state.process_name or "",
        "exe": state.exe_path or "",
        "cmdline": [state.exe_path] if state.exe_path else [],
    }
    return _match_process_with_score(process_info, tokens) is not None


def _manual_reconnect_required(
    state: EghisConnectorState | None,
    message: str,
) -> EghisConnectorState:
    if state is None:
        return EghisConnectorState(
            status="red",
            process_running=False,
            process_name=None,
            pid=None,
            exe_path=None,
            window_found=False,
            window_title=None,
            window_handle=None,
            window_owner_pid=None,
            is_active=False,
            last_seen_at=None,
            message=message,
        )
    return replace(state, status="red", is_active=False, message=message)


def _executable_path_matches(actual: str | None, configured: str) -> bool:
    if not actual:
        return False
    return PurePath(actual).as_posix().casefold() == PurePath(configured).as_posix().casefold()


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
    matched = _match_process_with_score(process_info, tokens)
    return None if matched is None else matched[0]


def _match_process_with_score(
    process_info: dict, tokens: list[str]
) -> tuple[str, int] | None:
    names = _process_identity_candidates(process_info)
    best_match: tuple[str, int] | None = None
    for candidate in names:
        normalized = candidate.casefold()
        stem = PurePath(candidate).stem.casefold()
        for token in tokens:
            token_stem = PurePath(token).stem.casefold()
            if normalized == token or stem == token_stem:
                score = 3
            elif normalized.endswith(token) or stem.endswith(token_stem):
                score = 2
            elif token in normalized or token_stem in stem:
                score = 1
            else:
                continue
            if best_match is None or score > best_match[1]:
                best_match = (candidate, score)
    return best_match


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
