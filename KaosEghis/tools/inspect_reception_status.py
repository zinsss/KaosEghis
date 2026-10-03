"""One-shot, passive reception UI inspection; output contains no patient values."""

import argparse
from collections import Counter, deque
import ctypes
import json
import os
from pathlib import Path
import re
import threading
import time


EMR_TITLE = "\uc774\uc9c0\uc2a4 \uc804\uc790\ucc28\ud2b8 2.0"
PANE_NAME = "\uc678\ub798\ub9ac\uc2a4\ud2b8"
TAB_NAME = "\uc9c4\ub8cc\ub300\uae30"
STATES = ("\uc811\uc218", "\uc9c4\ub8cc", "\ubcf4\ub958", "\uc644\ub8cc", "\ucde8\uc18c", "\ub300\uae30", "\uc9c4\ub8cc\ub300\uae30", "\uc9c4\ub8cc\uc911")
HEADERS = {
    "\ud658\uc790\ubc88\ud638", "\ucc28\ud2b8\ubc88\ud638", "\uc811\uc218\ubc88\ud638", "\uc0c1\ud0dc",
    "\uc9c4\ub8cc\uc77c\uc790", "\uc9c4\ub8cc\uc77c", "\uc811\uc218\uc77c\uc790", "\uc9c4\ub8cc\uc0c1\ud0dc",
    "\ud658\uc790\uba85", "\uc131\uba85", "\uc131\ubcc4", "\ub098\uc774", "\uc811\uc218\uc2dc\uac04", "\uc9c4\ub8cc\uc2dc\uac04",
}
LAYOUT = {"Window", "Pane", "Group", "Custom", "Tab", "TabItem", "ToolBar"}


def status_label(text):
    for state in STATES:
        if re.fullmatch(re.escape(state) + r"(?:\s*[\[(]?\s*\d+\s*(?:\uba85|\uac74)?\s*[\])]?)?", text.strip()):
            return state
    return None


def safe_header(text):
    text = text.strip()
    match = re.fullmatch(r"(.+?) row \d+", text)
    text = match[1] if match else text
    return text if text in HEADERS else None


def describe_grid(grid, path, deadline):
    result = {"path": path, "headers": []}
    try:
        result.update(rows=int(grid.iface_grid.CurrentRowCount), columns=int(grid.iface_grid.CurrentColumnCount))
    except Exception:
        result["dimensions_available"] = False
    pending = deque([(grid, 0)])
    visited = 0
    kinds = Counter()
    while pending and visited < 80 and time.monotonic() < deadline:
        parent, depth = pending.popleft()
        for child in parent.children():
            visited += 1
            kind = child.element_info.control_type
            kinds[kind] += 1
            if kind in {"Header", "HeaderItem"}:
                header = safe_header(child.element_info.name or "")
                if header and header not in result["headers"]:
                    result["headers"].append(header)
            if kind in {"Header", "Custom", "Pane"} and depth < 3:
                pending.append((child, depth + 1))
            if visited >= 80 or time.monotonic() >= deadline:
                break
    result["child_types"] = dict(kinds)
    return result


def reception_ancestor(node, pid):
    for _ in range(20):
        if node is None or node.element_info.process_id != pid:
            return None
        if (node.element_info.name or "").strip() == PANE_NAME:
            return node
        node = node.parent()
    return None


def window_is_cloaked(handle):
    from ctypes import wintypes
    value = wintypes.DWORD()
    function = ctypes.WinDLL("dwmapi").DwmGetWindowAttribute
    function.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
    result = function(handle, 14, ctypes.byref(value), ctypes.sizeof(value))
    return result != 0 or bool(value.value)


def inspect_ui(point=None, wait_visible=0, *, observer=None):
    import win32gui
    import win32process
    from pywinauto import Desktop
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_element_info import UIAElementInfo

    if not ctypes.windll.shell32.IsUserAnAdmin():
        return {"status": "not_elevated", "actions_sent": 0}
    roots = []
    win32gui.EnumWindows(lambda h, _: roots.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h).strip() == EMR_TITLE else None, None)
    if len(roots) != 1:
        return {"status": "emr_not_unique", "actions_sent": 0}
    visible_deadline = time.monotonic() + wait_visible
    while window_is_cloaked(roots[0]) and time.monotonic() < visible_deadline:
        time.sleep(0.25)
    if window_is_cloaked(roots[0]):
        return {"status": "emr_not_on_visible_desktop", "actions_sent": 0}
    panes = []
    win32gui.EnumChildWindows(roots[0], lambda h, _: panes.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h).strip() == PANE_NAME else None, None)
    if len(panes) != 1:
        return {"status": "reception_pane_not_unique", "actions_sent": 0}
    root = UIAWrapper(UIAElementInfo(panes[0]))
    origin = "native_pane"
    if point is not None:
        pid = win32process.GetWindowThreadProcessId(roots[0])[1]
        left, top, right, bottom = win32gui.GetWindowRect(panes[0])
        points = [point] + [(left + int((right-left)*x), top + int((bottom-top)*y))
                            for y in (0.08, 0.25, 0.55) for x in (0.2, 0.5, 0.8)]
        desktop = Desktop(backend="uia")
        for candidate in points:
            node = reception_ancestor(desktop.from_point(*candidate), pid)
            if node is not None:
                root, origin = node, "visible_point_ancestor"
                break
        else:
            return {"status": "reception_pane_not_visible_at_probe_points", "actions_sent": 0}
    pending = deque([(root, 0, [PANE_NAME])])
    deadline = time.monotonic() + 12
    visited = 0
    tabs, grids, grid_controls, kinds = [], [], [], Counter()
    while pending and visited < 250 and time.monotonic() < deadline:
        parent, depth, path = pending.popleft()
        for child in parent.children():
            visited += 1
            kind = child.element_info.control_type
            kinds[kind] += 1
            next_path = path
            if kind == "TabItem":
                label = status_label(child.element_info.name or "")
                if label:
                    selected = None
                    try:
                        selected = bool(child.iface_selection_item.CurrentIsSelected)
                    except Exception:
                        pass
                    tabs.append({"status": label, "selected": selected, "visible": child.is_visible()})
                    next_path = path + [label]
            elif kind == "Tab" and (child.element_info.name or "").strip() == TAB_NAME:
                next_path = path + [TAB_NAME]
            if kind in {"Table", "DataGrid"}:
                grid_controls.append(child)
                grids.append(describe_grid(child, path, deadline))
            elif kind in LAYOUT and depth < 16:
                pending.append((child, depth + 1, next_path))
            if visited >= 250 or time.monotonic() >= deadline:
                break
    if observer is not None:
        if pending or time.monotonic() >= deadline:
            raise RuntimeError("incomplete_ui_search")
        observer(root, tabs, grid_controls)
    return {"status": "passive_ui_read_complete", "origin": origin, "visited": visited, "tabs": tabs, "grids": grids,
            "layout_types": dict(kinds),
            "bounded_search_incomplete": bool(pending), "actions_sent": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--point", nargs=2, type=int)
    parser.add_argument("--wait-visible", type=int, choices=range(0, 61), default=0)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists() or not output.parent.is_dir():
        raise SystemExit("Output must be a new file in an existing directory")

    def finish(report):
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)

    def timeout():
        finish({"status": "passive_ui_read_timeout", "actions_sent": 0})
        # This helper opens no database connection and sends no UI input.
        os._exit(2)

    watchdog = threading.Timer(25 + args.wait_visible, timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        try:
            report = inspect_ui(args.point, args.wait_visible)
        except Exception as exc:
            report = {"status": "stopped", "exception_type": type(exc).__name__, "actions_sent": 0}
        watchdog.cancel()
        finish(report)
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
