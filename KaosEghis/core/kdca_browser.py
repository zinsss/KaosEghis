"""Small UIA helpers for retaining the browser used for KDCA authentication."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse


def refresh_window(window: Any) -> Any | None:
    """Rebind by HWND after navigation instead of retaining a stale UIA tree."""
    try:
        from pywinauto import Desktop

        return Desktop(backend="uia").window(handle=int(window.handle)).wrapper_object()
    except Exception:
        return None


def document_for_url(window: Any, url: str, *, match_path: bool = False) -> Any | None:
    return next(iter_documents_for_url(window, url, match_path=match_path), None)


def iter_documents_for_url(window: Any, url: str, *, match_path: bool = False) -> Iterator[Any]:
    """Include matching frames, while keeping single-document callers lazy."""
    expected = urlparse(url)
    try:
        documents = window.descendants(control_type="Document")
    except Exception:
        return
    for document in documents:
        try:
            if not document.is_visible():
                continue
            actual = urlparse(_document_url(document))
            if (actual.scheme, actual.netloc.casefold()) != (
                expected.scheme, expected.netloc.casefold(),
            ):
                continue
            if match_path and actual.path != expected.path:
                continue
            yield document
        except Exception:
            continue


def _document_url(document: Any) -> str:
    try:
        value = document.get_value()
        if value:
            return str(value)
    except Exception:
        pass
    try:
        return str(document.legacy_properties().get("Value", ""))
    except Exception:
        return ""


def document_identity(document: Any) -> tuple[int, ...] | None:
    try:
        identity = document.element_info.runtime_id
        return tuple(identity) if identity else None
    except Exception:
        return None


def foreground_handle() -> int:
    try:
        import win32gui

        return int(win32gui.GetForegroundWindow() or 0)
    except Exception:
        return 0


def owned_by_browser(window: Any, browser: Any) -> bool:
    try:
        import win32con
        import win32gui

        return int(win32gui.GetAncestor(int(window.handle), win32con.GA_ROOTOWNER)) == int(browser.handle)
    except Exception:
        return False


def has_keyboard_focus(element: Any) -> bool:
    try:
        return bool(element.has_keyboard_focus())
    except Exception:
        return False


def focused_element() -> Any:
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo

    return UIAWrapper(UIAElementInfo(IUIA().iuia.GetFocusedElement()))


def navigate_browser(handle: int, url: str, *, cancelled=lambda: False) -> bool:
    """Navigate the authenticated window, never a different browser/profile.

    No clipboard is used. A modal native popup or focus change aborts before
    sending further keys; no notices are dismissed automatically.
    """
    try:
        from pywinauto import Desktop
        from pywinauto.keyboard import send_keys
        from KaosEghis.core.kdca_certificate_login import _send_unicode_text

        browser = Desktop(backend="uia").window(handle=handle).wrapper_object()
        if cancelled() or not browser.is_visible() or not browser.is_enabled():
            return False
        browser.set_focus()
        if cancelled() or foreground_handle() != handle:
            return False
        send_keys("^l", pause=0.05)
        # Ctrl+L must reach the browser's address field, not a page input.
        focused = focused_element()
        if (
            cancelled() or foreground_handle() != handle
            or focused.element_info.control_type != "Edit"
            or not has_keyboard_focus(focused)
        ):
            return False
        parent = focused.parent()
        for _ in range(16):
            if parent.element_info.control_type == "Document":
                return False
            if int(getattr(parent, "handle", 0) or 0) == handle:
                break
            parent = parent.parent()
        else:
            return False
        if not _send_unicode_text(url):
            return False
        if cancelled() or foreground_handle() != handle or not has_keyboard_focus(focused):
            return False
        send_keys("{ENTER}", pause=0.05)
        return True
    except Exception:
        return False
