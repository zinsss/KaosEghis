"""Follow KDCA's authenticated menu instead of navigating around its handoff."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from KaosEghis.core.kdca_browser import (
    _document_url, document_for_url, document_identity, foreground_handle,
    owned_by_browser, refresh_window,
)
from KaosEghis.core.kdca_certificate_login import (
    KdcaCertificateLoginConfig, _find_kdca_session_controls,
)


SYSTEM_SELECTOR_NAME = "\uc2dc\uc2a4\ud15c\uc744 \uc120\ud0dd\ud574\uc8fc\uc138\uc694"
PORTAL_MENU_NAMES = {
    "general": SYSTEM_SELECTOR_NAME + " > \uc608\ubc29\uc811\uc885\uad00\ub9ac",
    "influenza": SYSTEM_SELECTOR_NAME + " > \uc608\ubc29\uc811\uc885\uad00\ub9ac",
    "covid": SYSTEM_SELECTOR_NAME + " > \ucf54\ub85c\ub09819 \uc608\ubc29\uc811\uc885\uad00\ub9ac > \ub4f1\ub85d\uc2dc\uc2a4\ud15c > \uc608\ubc29\uc811\uc885\ub4f1\ub85d\uc2dc\uc2a4\ud15c",
}
LAUNCH_CONTROL_NAMES = {
    "general": "\uc608\ubc29\uc811\uc885\ud1b5\ud569\uad00\ub9ac\uc2dc\uc2a4\ud15c",
    "influenza": "\ud604\ubb3c\uacf5\uae09\uc778\ud50c\ub8e8\uc5d4\uc790\uc2dc\uc2a4\ud15c",
}
_BROWSER_CLASSES = {"Chrome_WidgetWin_1", "MozillaWindowClass"}


def _browser_windows():
    from pywinauto import Desktop

    return [w for w in Desktop(backend="uia").windows()
            if w.element_info.class_name in _BROWSER_CLASSES and w.is_visible()]


def _origin(url):
    parsed = urlparse(url)
    return parsed.scheme, parsed.netloc.casefold()


def _name(element):
    return " ".join(str(element.element_info.name or "").split())


def _containing_document(element):
    # A trusted outer document does not make a cross-origin iframe trusted.
    parent = element.parent()
    for _ in range(40):
        if parent.element_info.control_type == "Document":
            return parent
        if parent.element_info.control_type == "Window":
            break
        parent = parent.parent()
    return None


def _controls(document, origins, *, include_images=False):
    kinds = {"Hyperlink", "Button", "Image"} if include_images else {"Hyperlink", "Button"}
    for element in document.descendants():
        try:
            if (element.element_info.control_type not in kinds
                    or not element.is_visible() or not element.is_enabled()):
                continue
            owner = _containing_document(element)
            if owner is not None and _origin(_document_url(owner)) in origins:
                yield element
        except Exception:
            continue


def _matches_launch_link(element, launch_url, control_name):
    if control_name and _name(element) == " ".join(control_name.split()):
        return True
    try:
        href = str(element.legacy_properties().get("Value", "") or "").strip()
        document = _containing_document(element)
        if not href or document is None:
            return False
        actual = urlparse(urljoin(_document_url(document), href))
        expected = urlparse(launch_url)
        return (actual.scheme, actual.netloc.casefold(), actual.path, actual.query) == (
            expected.scheme, expected.netloc.casefold(), expected.path, expected.query,
        )
    except Exception:
        return False


def _collapse_link_images(matches):
    """Chrome exposes a launch link and its contained image as separate matches."""
    identities = {(int(window.handle), document_identity(element))
                  for window, element in matches}
    actions = []
    for window, element in matches:
        contained_image = False
        if element.element_info.control_type == "Image":
            try:
                parent = element.parent()
                for _ in range(40):
                    kind = parent.element_info.control_type
                    if kind in {"Document", "Window"}:
                        break
                    if kind in {"Hyperlink", "Button"}:
                        contained_image = (int(window.handle), document_identity(parent)) in identities
                        break
                    parent = parent.parent()
            except Exception:
                # An unverified relationship must remain ambiguous.
                pass
        if not contained_image:
            actions.append((window, element))
    return actions


def _activate_once(window, element, origins, cancelled):
    """Resolve the input method before dispatch: never retry a dispatched click."""
    try:
        from pywinauto.uia_defines import NoPatternInterfaceError

        if cancelled() or not window.is_enabled():
            return False
        window.set_focus()
        owner = _containing_document(element)
        if (cancelled() or foreground_handle() != int(window.handle)
                or not element.is_visible() or not element.is_enabled()
                or owner is None or _origin(_document_url(owner)) not in origins):
            return False
        try:
            invoke = element.iface_invoke
        except NoPatternInterfaceError:
            element.click_input()
        else:
            invoke.Invoke()
        return True
    except Exception:
        return False


class KdcaPortalLaunch:
    """Follow an exact menu path, dispatching each control at most once."""

    def __init__(self, settings, system, browser_handle, *, cancelled=lambda: False):
        self.settings = settings
        self.system = system
        self.browser_handle = browser_handle
        self.cancelled = cancelled
        self.portal_url = settings.get("vaccine_kdca_portal_url", "https://is.kdca.go.kr/")
        self.launch_url = settings[f"vaccine_{system}_system_launch_url"]
        self.menu_name = settings.get(f"vaccine_{system}_system_portal_menu_name", PORTAL_MENU_NAMES[system]).strip()
        self.menu_path = [" ".join(part.split()) for part in self.menu_name.split(">") if part.strip()]
        self.control_name = settings.get(f"vaccine_{system}_system_launch_control_name", LAUNCH_CONTROL_NAMES.get(system, "")).strip()
        self.phase = "portal_menu"
        self.activated_ids = set()
        self.activated_menu_names = set()
        windows = _browser_windows()
        self.previous_handles = {int(w.handle) for w in windows}
        self.browser = next((w for w in windows if int(w.handle) == browser_handle), None)
        self.process_id = self.browser.element_info.process_id if self.browser is not None else None

    @property
    def waiting_message(self):
        return {
            "portal_menu": "waiting for the signed-in KDCA system menu",
            "system_link": "portal menu opened; waiting for the system or its launch link",
            "system_window": "launch control activated; waiting for the system window",
        }[self.phase]

    def windows(self):
        if self.browser is None:
            return []
        matches = []
        for window in _browser_windows():
            handle = int(window.handle)
            if handle == self.browser_handle or (
                self.process_id and window.element_info.process_id == self.process_id
                and (handle not in self.previous_handles or owned_by_browser(window, self.browser))
            ):
                matches.append(window)
        return matches

    def advance(self):
        """Return a sanitized terminal error, or None while waiting/progressing."""
        if self.cancelled():
            return "Vaccine system launch cancelled."
        if self.browser is None:
            return "The authenticated KDCA browser is no longer available."
        if self.phase == "system_window":
            return None
        if self.phase == "portal_menu":
            return self._open_menu()
        return self._open_launch_link()

    def _open_menu(self):
        if not self.menu_path:
            return "Set the portal menu text in Vaccine > Settings > System targets."
        window = refresh_window(self.browser)
        if window is None:
            return "The authenticated KDCA browser is no longer available."
        document = document_for_url(window, self.portal_url)
        if document is None:
            return None
        config = KdcaCertificateLoginConfig.from_settings(self.settings | {
            "vaccine_kdca_portal_url": self.portal_url,
            "vaccine_kdca_login_control_name": self.settings.get("vaccine_kdca_login_control_name", "\uacf5\ub3d9\uc778\uc99d\uc11c \ub85c\uadf8\uc778"),
            "vaccine_kdca_logout_control_name": self.settings.get("vaccine_kdca_logout_control_name", "\ub85c\uadf8\uc544\uc6c3"),
        })
        login, logout = _find_kdca_session_controls(window, config)
        if login:
            return "KDCA is showing sign-in again. Sign in before opening a vaccine system."
        if len(logout) != 1:
            return None
        origins = {_origin(self.portal_url)}
        controls = list(_controls(document, origins))
        matches = []
        matched_name = ""
        # Use the leaf directly when visible; otherwise expand only its configured ancestors.
        for name in reversed(self.menu_path):
            if name in self.activated_menu_names:
                continue
            matches = [item for item in controls if _name(item) == name
                       and document_identity(item) not in self.activated_ids]
            if matches:
                matched_name = name
                break
        if len(matches) > 1:
            return "The KDCA portal menu is ambiguous. Open the intended menu manually."
        if not matches:
            return None
        identity = document_identity(matches[0])
        if identity is None:
            return "The KDCA portal menu could not be identified safely."
        if not _activate_once(window, matches[0], origins, self.cancelled):
            return "Could not activate the KDCA portal menu. Check browser focus or a blocking popup."
        self.activated_ids.add(identity)
        self.activated_menu_names.add(matched_name)
        if matched_name == self.menu_path[-1]:
            self.phase = "system_link"
        return None

    def _open_launch_link(self):
        origins = {_origin(self.portal_url), _origin(self.launch_url)}
        matches = []
        seen = set()
        for window in self.windows():
            for document in window.descendants(control_type="Document"):
                if not document.is_visible() or _origin(_document_url(document)) not in origins:
                    continue
                for element in _controls(document, origins, include_images=bool(self.control_name)):
                    if not _matches_launch_link(element, self.launch_url, self.control_name):
                        continue
                    identity = document_identity(element)
                    if identity is None:
                        return "The vaccine launch control could not be identified safely."
                    if identity not in seen and identity not in self.activated_ids:
                        matches.append((window, element))
                        seen.add(identity)
        matches = _collapse_link_images(matches)
        if len(matches) > 1:
            return "Multiple vaccine launch controls match. Check System targets or open the system manually."
        if not matches:
            return None
        if not _activate_once(*matches[0], origins, self.cancelled):
            return "Could not activate the vaccine launch control. Check browser focus or a blocking popup."
        self.activated_ids.update(seen)
        self.phase = "system_window"
        return None
