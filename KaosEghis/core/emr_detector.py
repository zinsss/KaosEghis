from dataclasses import dataclass
from pathlib import PurePath

from KaosEghis.core.safety_gate import SafetyResult


@dataclass(frozen=True)
class EmrConnectionStatus:
    connected: bool
    process_running: bool
    process_matches: tuple[str, ...]
    window_found: bool
    window_matches: tuple[str, ...]
    message: str


def check_process_running(process_name: str) -> bool:
    return bool(find_matching_processes(process_name))


def find_matching_processes(process_name: str) -> list[str]:
    tokens = _normalized_candidates(process_name)
    if not tokens:
        return []
    try:
        import psutil
    except ImportError:
        return []

    matches: list[tuple[int, str]] = []
    try:
        processes = psutil.process_iter(["name", "exe", "cmdline"])
        for process in processes:
            matched = _match_process_with_score(process.info, tokens)
            if matched is not None:
                matched_name, score = matched
                matches.append((score, matched_name))
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return []
    ordered = [name for _score, name in sorted(matches, key=lambda item: item[0], reverse=True)]
    return _unique_preserving_order(ordered)


def find_window_by_title_contains(title_fragment: str) -> bool:
    return bool(find_matching_window_titles(title_fragment))


def get_active_window_title() -> str:
    try:
        import pygetwindow
    except ImportError:
        return ""

    try:
        active_window = pygetwindow.getActiveWindow()
    except Exception:
        return ""
    if active_window is None:
        return ""
    return active_window.title or ""


def is_target_window_active(title_fragment: str) -> bool:
    fragment = title_fragment.strip().casefold()
    if not fragment:
        return False
    return fragment in get_active_window_title().casefold()


def find_matching_window_titles(title_fragment: str) -> list[str]:
    tokens = _normalized_candidates(title_fragment)
    if not tokens:
        return []

    titles = _window_titles_from_pygetwindow() + _window_titles_from_pywinauto()
    return _unique_preserving_order(
        title
        for title in titles
        if title and any(token in title.casefold() for token in tokens)
    )


def detect_eghis_connection(process_name: str, title_fragment: str) -> EmrConnectionStatus:
    process_matches = tuple(find_matching_processes(process_name))
    window_matches = tuple(find_matching_window_titles(title_fragment))
    process_running = bool(process_matches)
    window_found = bool(window_matches)
    connected = process_running and window_found

    if connected:
        return EmrConnectionStatus(
            connected=True,
            process_running=True,
            process_matches=process_matches,
            window_found=True,
            window_matches=window_matches,
            message="Connected",
        )
    if window_found and not process_running:
        return EmrConnectionStatus(
            connected=False,
            process_running=False,
            process_matches=process_matches,
            window_found=True,
            window_matches=window_matches,
            message="Eghis window found, but the process name setting did not match.",
        )
    if process_running and not window_found:
        return EmrConnectionStatus(
            connected=False,
            process_running=True,
            process_matches=process_matches,
            window_found=False,
            window_matches=window_matches,
            message="Eghis process found, but the window title setting did not match.",
        )
    return EmrConnectionStatus(
        connected=False,
        process_running=False,
        process_matches=process_matches,
        window_found=False,
        window_matches=window_matches,
        message="Eghis process and window were not detected.",
    )


def activate_eghis_window() -> SafetyResult:
    return SafetyResult(False, "Eghis window activation is not implemented.")


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
    return _unique_preserving_order(value for value in values if value)


def _normalized_candidates(value: str) -> list[str]:
    raw = value.replace(";", ",")
    parts = [part.strip().casefold() for part in raw.split(",")]
    return [part for part in parts if part]


def _window_titles_from_pygetwindow() -> list[str]:
    try:
        import pygetwindow
    except ImportError:
        return []

    try:
        return [title for title in pygetwindow.getAllTitles() if title]
    except Exception:
        return []


def _window_titles_from_pywinauto() -> list[str]:
    try:
        from pywinauto import Desktop
    except ImportError:
        return []

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return []
    return [getattr(window, "window_text", lambda: "")() or "" for window in windows]


def _unique_preserving_order(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
