from __future__ import annotations

from datetime import datetime
import re
import time
from typing import Any

from KaosEghis.core.claim_preparation import (
    ClaimHistory, ClaimPreviewError, parse_claim_month, parse_claim_week,
)
from KaosEghis.core.eghis_connector import get_cached_eghis_state


CLAIM_WINDOW = "[청구] 청구내역집계"
MAX_ROWS = 128
READ_SECONDS = 8.0


def connected_claim_identity() -> tuple[int, int] | None:
    state = get_cached_eghis_state()
    if (
        state is None or state.status not in {"green", "yellow"}
        or not state.process_running or not state.window_found
        or not state.pid or not state.window_handle
        or state.window_owner_pid != state.pid
    ):
        return None
    return state.pid, state.window_handle


def read_claim_history() -> ClaimHistory:
    """Read one already-open month. No focus, selection, scrolling or input."""
    connection = connected_claim_identity()
    if connection is None:
        raise ClaimPreviewError("Connect EMR before reading claim history.")
    import pythoncom

    pythoncom.CoInitialize()
    try:
        reader = _ClaimReader(connection)
        scope = reader.claim_scope()
        first = reader.snapshot(scope)
        second = reader.snapshot(scope)
        if first != second or connected_claim_identity() != connection:
            raise ClaimPreviewError("Claim screen changed during the read. Read it again.")
        reader.check_time()
        return ClaimHistory(*first, datetime.now(), connection)
    except ClaimPreviewError:
        raise
    except Exception:
        # UIA exceptions may contain window contents. Do not display or log them.
        raise ClaimPreviewError("Claim screen could not be read. No week was inferred.") from None
    finally:
        pythoncom.CoUninitialize()


class _ClaimReader:
    def __init__(self, connection: tuple[int, int]) -> None:
        from pywinauto.uia_defines import IUIA

        self.pid, self.handle = connection
        self.uia = IUIA()
        self.deadline = time.monotonic() + READ_SECONDS

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            raise ClaimPreviewError("Claim screen read timed out. No week was inferred.")

    def find(
        self, root: Any, control_type: str, *, name: str = "",
        automation_id: str = "", children: bool = False,
    ) -> list[Any]:
        from pywinauto.controls.uiawrapper import UIAWrapper

        self.check_time()
        uia = self.uia
        properties = [
            (uia.UIA_dll.UIA_ProcessIdPropertyId, self.pid),
            (uia.UIA_dll.UIA_ControlTypePropertyId, uia.known_control_types[control_type]),
        ]
        if name:
            properties.append((uia.UIA_dll.UIA_NamePropertyId, name))
        if automation_id:
            properties.append((uia.UIA_dll.UIA_AutomationIdPropertyId, automation_id))
        condition = uia.iuia.CreateAndConditionFromArray([
            uia.iuia.CreatePropertyCondition(prop, value) for prop, value in properties
        ])
        infos = root.element_info._get_elements(
            uia.tree_scope["children" if children else "descendants"],
            condition, cache_enable=False,
        )
        self.check_time()
        return [UIAWrapper(info) for info in infos]

    def one(self, root: Any, control_type: str, **criteria: Any) -> Any:
        matches = self.find(root, control_type, **criteria)
        if len(matches) != 1:
            selector = criteria.get("automation_id") or criteria.get("name") or control_type
            raise ClaimPreviewError(f"Claim target missing or ambiguous: {selector}.")
        return matches[0]

    def claim_scope(self) -> Any:
        import win32gui
        import win32process
        from pywinauto.controls.uiawrapper import UIAWrapper
        from pywinauto.uia_element_info import UIAElementInfo

        if (
            not win32gui.IsWindow(self.handle)
            or win32process.GetWindowThreadProcessId(self.handle)[1] != self.pid
        ):
            raise ClaimPreviewError("EMR connection changed. Reconnect EMR.")
        roots = []

        def visit(handle: int, _extra: Any) -> None:
            if (
                win32gui.IsWindowVisible(handle)
                and win32gui.GetWindowText(handle) == CLAIM_WINDOW
                and win32process.GetWindowThreadProcessId(handle)[1] == self.pid
            ):
                roots.append(handle)

        win32gui.EnumWindows(visit, None)
        if roots:
            if len(roots) != 1:
                raise ClaimPreviewError("More than one claim window is open.")
            scope = UIAWrapper(UIAElementInfo(roots[0]))
        else:
            root = UIAWrapper(UIAElementInfo(self.handle))
            scope = self.one(root, "Window", name=CLAIM_WINDOW)
        self.check_time()
        if not scope.is_visible() or not scope.is_enabled():
            raise ClaimPreviewError("Open the claim aggregation screen and close its dialogs first.")
        return scope

    @staticmethod
    def value(element: Any) -> str:
        # Do not fall back to Name: a cell's name is its column/row, not its value.
        for reader in (
            lambda: element.iface_value.CurrentValue,
            lambda: element.legacy_properties().get("Value"),
        ):
            try:
                value = reader()
                if value is not None and str(value).strip():
                    return str(value).strip()
            except Exception:
                pass
        raise ClaimPreviewError("A claim field has no readable value.")

    def row_count(self, table: Any) -> int:
        self.check_time()
        try:
            count = int(table.iface_grid.CurrentRowCount)
        except Exception:
            raise ClaimPreviewError("Total claim row count is unavailable; completeness cannot be verified.") from None
        if not 0 <= count <= MAX_ROWS:
            raise ClaimPreviewError("Claim history exceeds the bounded preview read.")
        return count

    def snapshot(self, scope: Any) -> tuple:
        self.check_time()
        if not scope.is_visible() or not scope.is_enabled():
            raise ClaimPreviewError("Claim screen is not ready.")
        filters = self.one(scope, "Pane", name="조회구분")
        weekly = self.one(filters, "RadioButton", name="rdoWeek")
        if not weekly.iface_selection_item.CurrentIsSelected:
            raise ClaimPreviewError("Select 주단위 in EMR before reading.")
        build = self.one(filters, "Button", automation_id="btnBuild")
        if not build.is_enabled() or "[집계 대기]" not in build.element_info.name:
            raise ClaimPreviewError("Wait until claim aggregation is idle before reading.")
        month_control = self.one(filters, "ComboBox", automation_id="mpDemandYm")
        month = parse_claim_month(self.value(month_control))
        available = tuple(sorted({
            parse_claim_week(button.element_info.name)
            for button in self.find(filters, "RadioButton")
            if re.fullmatch(r"[1-6]\s*주", button.element_info.name or "")
            and button.is_enabled() and button.is_visible()
        }))
        pane = self.one(scope, "Pane", name="청구리스트")
        table = self.one(pane, "Table", name="MainView")
        count = self.row_count(table)
        panel = self.one(table, "Custom", name="Data Panel")
        rows = self.find(panel, "ListItem", children=True)
        if len(rows) != count:
            raise ClaimPreviewError("Only part of the claim list was read. No week was inferred.")
        weeks = []
        indices = set()
        for row in rows:
            self.check_time()
            match = re.fullmatch(r"Row (\d+)", row.element_info.name or "")
            if not match or int(match[1]) in indices:
                raise ClaimPreviewError("Claim row identities could not be verified.")
            index = int(match[1])
            indices.add(index)
            row_month = self.one(row, "DataItem", name=f"진료년월 row {index}")
            if parse_claim_month(self.value(row_month)) != month:
                raise ClaimPreviewError("Claim list month does not match the selected month.")
            week = self.one(row, "DataItem", name=f"청구단위 row {index}")
            weeks.append(parse_claim_week(self.value(week)))
        if indices != set(range(1, count + 1)) or self.row_count(table) != count:
            raise ClaimPreviewError("Claim list is incomplete or changed during the read.")
        if parse_claim_month(self.value(month_control)) != month:
            raise ClaimPreviewError("Selected claim month changed during the read.")
        self.check_time()
        return month, tuple(sorted(weeks)), available
