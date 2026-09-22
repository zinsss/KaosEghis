from types import SimpleNamespace

import pytest

from KaosEghis.core import kdca_portal_launch as portal
from KaosEghis.core import vaccine_system_launch as launch


PORTAL_URL = "https://is.kdca.go.kr/isc/main.do"
LAUNCH_URL = "https://ois.kdca.go.kr/iris/index_run.jsp"


class Node:
    sequence = 0

    def __init__(self, kind, *, name="", url="", children=(), handle=0, pid=10,
                 visible=True, enabled=True, auto_id=""):
        Node.sequence += 1
        self.element_info = SimpleNamespace(
            control_type=kind, name=name, process_id=pid,
            class_name="Chrome_WidgetWin_1", runtime_id=(Node.sequence,), automation_id=auto_id,
        )
        self.url, self.children, self.handle = url, list(children), handle
        self.visible, self.enabled = visible, enabled
        self._parent = None
        self.clicked = 0
        self.focused = False
        self.iface_invoke = SimpleNamespace(Invoke=self.click_input)
        for child in self.children:
            child._parent = self

    def parent(self):
        return self._parent

    def descendants(self, **kwargs):
        result = []
        for child in self.children:
            if ((not kwargs.get("control_type") or child.element_info.control_type == kwargs["control_type"])
                    and (not kwargs.get("auto_id") or child.element_info.automation_id == kwargs["auto_id"])):
                result.append(child)
            result.extend(child.descendants(**kwargs))
        return result

    def get_value(self):
        return self.url

    def legacy_properties(self):
        return {"Value": self.url}

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def set_focus(self):
        self.focused = True

    def click_input(self):
        self.clicked += 1

    def replace(self, *children):
        self.children = list(children)
        for child in children:
            child._parent = self


@pytest.fixture
def scene(monkeypatch):
    menu = Node("Hyperlink", name=portal.PORTAL_MENU_NAMES["general"].split(">")[-1].strip())
    logout = Node("Hyperlink", name="Logout", url="https://is.kdca.go.kr/isc/logout.do")
    document = Node("Document", url=PORTAL_URL, children=[menu, logout])
    window = Node("Window", handle=101, children=[document])
    windows = [window]
    settings = {
        "vaccine_general_system_launch_url": LAUNCH_URL,
        "vaccine_kdca_portal_url": "https://is.kdca.go.kr/",
        "vaccine_kdca_login_control_name": "Login",
        "vaccine_kdca_logout_control_name": "Logout",
    }
    monkeypatch.setattr(portal, "_browser_windows", lambda: windows)
    monkeypatch.setattr(portal, "refresh_window", lambda w: w)
    monkeypatch.setattr(portal, "foreground_handle", lambda: 101)
    monkeypatch.setattr(portal, "owned_by_browser", lambda *_args: False)
    return SimpleNamespace(menu=menu, logout=logout, document=document, window=window,
                           windows=windows, settings=settings)


def test_portal_menu_and_selection_link_activate_once(scene):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    assert operation.advance() is None
    assert scene.menu.clicked == 1
    assert operation.phase == "system_link"
    link = Node("Hyperlink", url=LAUNCH_URL)
    scene.document.replace(link)
    assert operation.advance() is None
    assert operation.phase == "system_window"
    assert operation.advance() is None
    assert scene.menu.clicked == link.clicked == 1


def test_direct_launch_menu_is_not_clicked_again_while_navigation_is_loading(scene):
    scene.menu.url = LAUNCH_URL
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    for _ in range(3):
        assert operation.advance() is None
    assert scene.menu.clicked == 1


@pytest.mark.parametrize("system", ["general", "influenza", "covid"])
def test_each_system_uses_its_exact_configured_menu(scene, system):
    scene.settings[f"vaccine_{system}_system_launch_url"] = LAUNCH_URL
    scene.menu.element_info.name = portal.PORTAL_MENU_NAMES[system].split(">")[-1].strip()
    operation = portal.KdcaPortalLaunch(scene.settings, system, 101)
    assert operation.advance() is None
    assert scene.menu.clicked == 1


def test_covid_expands_configured_ancestors_then_clicks_registration_leaf(scene):
    scene.settings["vaccine_covid_system_launch_url"] = "https://ois.kdca.go.kr/covr/index_run.jsp"
    path = [name.strip() for name in portal.PORTAL_MENU_NAMES["covid"].split(">")][1:]
    root, branch, leaf = [Node("Hyperlink", name=name) for name in path]
    leaf.url = "menuGo.do?menuid=203488"
    scene.document.replace(scene.logout, root)
    operation = portal.KdcaPortalLaunch(scene.settings, "covid", 101)
    assert operation.advance() is None
    assert operation.phase == "portal_menu"
    assert operation.advance() is None
    assert root.clicked == 1
    replacement = Node("Hyperlink", name=path[0])
    scene.document.replace(scene.logout, replacement)
    assert operation.advance() is None
    assert replacement.clicked == 0
    scene.document.replace(scene.logout, root, branch)
    assert operation.advance() is None
    assert operation.phase == "portal_menu"
    scene.document.replace(scene.logout, root, branch, leaf)
    assert operation.advance() is None
    assert operation.phase == "system_link"
    assert [item.clicked for item in (root, branch, leaf)] == [1, 1, 1]


@pytest.mark.parametrize("system,image_id", [("general", "ocs_button1"), ("influenza", "inf_button1")])
def test_selection_image_matches_exact_alt_text(scene, system, image_id):
    scene.settings["vaccine_influenza_system_launch_url"] = "https://ois.kdca.go.kr/iroi/indexWSP.jsp"
    operation = portal.KdcaPortalLaunch(scene.settings, system, 101)
    assert operation.advance() is None
    image = Node("Image", name=portal.LAUNCH_CONTROL_NAMES[system], auto_id=image_id)
    unrelated = Node("Image", name="Other system")
    scene.document.url = "https://ois.kdca.go.kr/irad/regsCommon.do"
    scene.document.replace(image, unrelated)
    assert operation.advance() is None
    assert image.clicked == 1
    assert unrelated.clicked == 0


@pytest.mark.parametrize("system", ["general", "influenza", "covid"])
def test_closed_system_selector_opens_full_route_once(scene, system):
    from KaosEghis.db.repositories import DEFAULT_SETTINGS

    scene.settings[f"vaccine_{system}_system_launch_url"] = DEFAULT_SETTINGS[f"vaccine_{system}_system_launch_url"]
    path = [part.strip() for part in portal.PORTAL_MENU_NAMES[system].split(">")]
    controls = [Node("Hyperlink", name=part) for part in path]
    assert controls[0].element_info.name == portal.SYSTEM_SELECTOR_NAME
    controls[-1].url = "menuGo.do?menuid=" + ("203488" if system == "covid" else "197625")
    operation = portal.KdcaPortalLaunch(scene.settings, system, 101)

    for index, control in enumerate(controls):
        scene.document.replace(scene.logout, *controls[:index + 1])
        assert operation.advance() is None
        assert control.clicked == 1
        assert all(item.clicked == 1 for item in controls[:index + 1])
        assert operation.advance() is None
        assert control.clicked == 1
        assert operation.phase == ("system_link" if index == len(controls) - 1 else "portal_menu")

    if system in {"general", "influenza"}:
        general = Node("Image", name=portal.LAUNCH_CONTROL_NAMES["general"], auto_id="ocs_button1")
        influenza = Node("Image", name=portal.LAUNCH_CONTROL_NAMES["influenza"], auto_id="inf_button1")
        selection = Node("Document", url="https://ois.kdca.go.kr/irad/regsCommon.do", children=[general, influenza])
        scene.document.replace(scene.logout, selection)
        assert operation.advance() is None
        assert operation.phase == "system_window"
        assert (general.clicked, influenza.clicked) == ((1, 0) if system == "general" else (0, 1))


def test_portal_fallback_selectors_match_settings_defaults():
    from KaosEghis.db.repositories import DEFAULT_SETTINGS

    for system, path in portal.PORTAL_MENU_NAMES.items():
        assert DEFAULT_SETTINGS[f"vaccine_{system}_system_portal_menu_name"] == path
        assert DEFAULT_SETTINGS[f"vaccine_{system}_system_launch_control_name"] == portal.LAUNCH_CONTROL_NAMES.get(system, "")


@pytest.mark.parametrize("problem", ["text_child", "duplicate", "hidden", "disabled", "wrong_name", "iframe"])
def test_portal_menu_matching_rejects_ambiguous_or_wrong_controls(scene, problem):
    extra = Node("Hyperlink", name=scene.menu.element_info.name)
    if problem == "text_child":
        extra.element_info.control_type = "Text"
        scene.menu.replace(extra)
    elif problem == "duplicate":
        scene.document.replace(scene.menu, scene.logout, extra)
    elif problem == "hidden":
        scene.menu.visible = False
    elif problem == "disabled":
        scene.menu.enabled = False
    elif problem == "wrong_name":
        scene.menu.element_info.name += " announcements"
    else:
        scene.document.replace(scene.logout, Node("Document", url="https://unrelated.test/", children=[scene.menu]))
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    error = operation.advance()
    assert scene.menu.clicked == (1 if problem == "text_child" else 0)
    assert extra.clicked == 0
    if problem == "duplicate":
        assert "ambiguous" in error


def test_expired_login_does_not_activate_menu(scene):
    scene.document.replace(scene.menu, Node("Hyperlink", name="Login"))
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    assert "sign-in" in operation.advance()
    assert scene.menu.clicked == 0


@pytest.mark.parametrize("problem", ["missing_logout", "duplicate_logout", "untrusted_portal"])
def test_menu_requires_positive_signed_in_portal(scene, problem):
    if problem == "missing_logout":
        scene.document.replace(scene.menu)
    elif problem == "duplicate_logout":
        scene.document.replace(scene.menu, scene.logout, Node("Button", name="Logout"))
    else:
        scene.document.url = "https://is.kdca.go.kr.unrelated.test/"
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    assert operation.advance() is None
    assert scene.menu.clicked == 0


@pytest.mark.parametrize("url,match", [
    (LAUNCH_URL, True),
    ("/iris/index_run.jsp", True),
    ("/covr/index_run.jsp", False),
    ("https://ois.kdca.go.kr.unrelated.test/iris/index_run.jsp", False),
    ("javascript:openSystem()", False),
    ("", False),
])
def test_launch_link_matches_configured_destination_not_nearby_system(scene, url, match):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    link = Node("Hyperlink", url=url)
    scene.document.url = "https://ois.kdca.go.kr/irad/regsCommon.do"
    scene.document.replace(link)
    assert operation.advance() is None
    assert link.clicked == int(match)


def test_explicit_launch_control_text_supports_javascript_buttons(scene):
    scene.settings["vaccine_general_system_launch_control_name"] = "Start General"
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    link = Node("Button", name="Start General", url="javascript:start()")
    scene.document.replace(link)
    assert operation.advance() is None
    assert link.clicked == 1


def test_duplicate_selection_links_are_not_guessed(scene):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    links = [Node("Hyperlink", url=LAUNCH_URL), Node("Hyperlink", url=LAUNCH_URL)]
    scene.document.replace(*links)
    assert "Multiple" in operation.advance()
    assert all(item.clicked == 0 for item in links)


def test_nested_document_enumeration_deduplicates_same_link(scene):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    link = Node("Hyperlink", url=LAUNCH_URL)
    scene.document.replace(Node("Document", url="https://ois.kdca.go.kr/", children=[link]))
    assert operation.advance() is None
    assert link.clicked == 1


def test_cross_origin_frame_cannot_supply_launch_control(scene):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    link = Node("Hyperlink", url=LAUNCH_URL)
    scene.document.replace(Node("Document", url="https://unrelated.test/", children=[link]))
    assert operation.advance() is None
    assert link.clicked == 0


def test_only_original_browser_and_new_same_process_popups_are_considered(scene, monkeypatch):
    old_window = Node("Window", handle=102)
    scene.windows.append(old_window)
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    popup = Node("Window", handle=103)
    other_browser = Node("Window", handle=104, pid=20)
    scene.windows.extend([popup, other_browser])
    assert [w.handle for w in operation.windows()] == [101, 103]
    monkeypatch.setattr(portal, "owned_by_browser", lambda w, _parent: w is old_window)
    assert [w.handle for w in operation.windows()] == [101, 102, 103]


def test_new_browser_popup_can_supply_system_selection(scene, monkeypatch):
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101)
    operation.phase = "system_link"
    link = Node("Hyperlink", url=LAUNCH_URL)
    popup = Node("Window", handle=103, children=[Node("Document", url="https://ois.kdca.go.kr/", children=[link])])
    scene.windows.append(popup)
    monkeypatch.setattr(portal, "foreground_handle", lambda: 103)
    assert operation.advance() is None
    assert link.clicked == 1


@pytest.mark.parametrize("problem", ["focus", "cancel", "modal", "invoke_raises"])
def test_activation_stops_without_fallback_click(scene, monkeypatch, problem):
    if problem == "focus":
        monkeypatch.setattr(portal, "foreground_handle", lambda: 999)
    elif problem == "modal":
        scene.window.enabled = False
    elif problem == "invoke_raises":
        scene.menu.iface_invoke = SimpleNamespace(Invoke=lambda: (_ for _ in ()).throw(RuntimeError("after dispatch")))
    operation = portal.KdcaPortalLaunch(scene.settings, "general", 101, cancelled=lambda: problem == "cancel")
    assert operation.advance()
    assert scene.menu.clicked == 0


def test_image_without_invoke_pattern_uses_one_targeted_click(scene):
    from pywinauto.uia_defines import NoPatternInterfaceError

    class Image(Node):
        @property
        def iface_invoke(self):
            raise NoPatternInterfaceError()

        @iface_invoke.setter
        def iface_invoke(self, value):
            pass

    image = Image("Image", name="Start General")
    scene.document.replace(image)
    assert portal._activate_once(scene.window, image, {portal._origin(PORTAL_URL)}, lambda: False)
    assert image.clicked == 1


def test_influenza_readiness_can_use_verified_popup(scene):
    field = Node("Edit", auto_id="edtPtntRrn1")
    popup = Node("Window", handle=103, children=[Node("Document", url="https://ois.kdca.go.kr/iroi/indexWS.jsp", children=[field])])
    settings = {"vaccine_influenza_system_launch_url": "https://ois.kdca.go.kr/iroi/indexWSP.jsp"}
    assert launch.vaccine_system_is_ready(settings, "influenza", windows=[popup])
    popup.children[0].url = "https://ois.kdca.go.kr/iris/index_run.do"
    assert not launch.vaccine_system_is_ready(settings, "influenza", windows=[popup])


def test_influenza_readiness_checks_nested_application_document(scene):
    field = Node("Edit", auto_id="edtPtntRrn1")
    flu = Node("Document", url="https://ois.kdca.go.kr/iroi/websquare/websquare.html", children=[field])
    scene.document.url = "https://ois.kdca.go.kr/irad/regsCommon.do"
    scene.document.replace(flu)
    settings = {"vaccine_influenza_system_launch_url": "https://ois.kdca.go.kr/iroi/indexWSP.jsp"}
    assert launch.vaccine_system_is_ready(settings, "influenza", windows=[scene.window])
    field.element_info.automation_id = "different-input"
    assert not launch.vaccine_system_is_ready(settings, "influenza", windows=[scene.window])
