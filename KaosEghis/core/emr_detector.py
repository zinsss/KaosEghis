from KaosEghis.core.safety_gate import SafetyResult


def check_process_running(process_name: str) -> bool:
    if not process_name.strip():
        return False
    try:
        import psutil
    except ImportError:
        return False

    target = process_name.casefold()
    try:
        processes = psutil.process_iter(["name"])
        for process in processes:
            name = process.info.get("name") or ""
            if name.casefold() == target:
                return True
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False
    return False


def find_window_by_title_contains(title_fragment: str) -> bool:
    return bool(_matching_window_titles(title_fragment))


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


def _matching_window_titles(title_fragment: str) -> list[str]:
    fragment = title_fragment.strip().casefold()
    if not fragment:
        return []
    try:
        import pygetwindow
    except ImportError:
        return []

    try:
        titles = pygetwindow.getAllTitles()
    except Exception:
        return []
    return [title for title in titles if fragment in title.casefold()]


def activate_eghis_window() -> SafetyResult:
    return SafetyResult(False, "Eghis window activation is not implemented.")
