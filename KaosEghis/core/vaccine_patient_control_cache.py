"""Transient native control identities for repeat patient-information reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _ControlIdentity:
    handle: int
    process_id: int
    runtime_id: tuple[int, ...]
    automation_id: str
    control_type: str


def _identity(element: Any) -> _ControlIdentity | None:
    try:
        info = element.element_info
        # Cache control addresses, never UIA property values from an earlier patient.
        info.set_cache_strategy(False)
        identity = _ControlIdentity(
            int(info.handle or 0), int(info.process_id), tuple(info.runtime_id or ()),
            str(info.automation_id or ""), str(info.control_type or ""),
        )
        if identity.handle > 0 and identity.process_id > 0 and identity.runtime_id:
            return identity
    except Exception:
        pass
    return None


def _process_lifetimes(process_ids: tuple[int, ...]) -> tuple[tuple[int, float], ...]:
    import psutil

    return tuple((pid, psutil.Process(pid).create_time()) for pid in sorted(set(process_ids)))


def _belongs_to_scope(handle: int, scope_handle: int) -> bool:
    import win32gui

    return bool(
        win32gui.IsWindow(handle) and win32gui.IsWindow(scope_handle)
        and (handle == scope_handle or win32gui.IsChild(scope_handle, handle))
    )


def _selector_signature(selectors: dict[str, tuple[str, ...]]) -> tuple:
    return tuple(sorted(selectors.items()))


@dataclass(frozen=True)
class PatientControlCache:
    """Only native/UIA identities are retained, so no COM objects cross threads."""

    root_pid: int
    root_handle: int
    process_lifetimes: tuple[tuple[int, float], ...]
    selectors: tuple
    scope: _ControlIdentity
    controls: tuple[tuple[str, _ControlIdentity], ...]

    @classmethod
    def create(
        cls, root_pid: int, root_handle: int | None, scope: Any,
        elements: dict[str, Any], selectors: dict[str, tuple[str, ...]],
    ) -> PatientControlCache | None:
        try:
            scope_id = _identity(scope)
            if scope_id is None or not root_handle or not scope.is_visible():
                return None
            identities = []
            for automation_id, element in elements.items():
                identity = _identity(element)
                if (
                    identity is not None and identity.automation_id == automation_id
                    and identity.process_id == scope_id.process_id and element.is_visible()
                    and _belongs_to_scope(identity.handle, scope_id.handle)
                ):
                    identities.append((automation_id, identity))
            if selectors["chart_no"][0] not in dict(identities):
                return None
            return cls(
                root_pid, int(root_handle),
                _process_lifetimes((root_pid, scope_id.process_id)),
                _selector_signature(selectors), scope_id, tuple(identities),
            )
        except Exception:
            return None

    def resolve(
        self, desktop: Any, root_pid: int, root_handle: int | None,
        selectors: dict[str, tuple[str, ...]],
        *, allow_hidden_scope: bool = False,
    ) -> tuple[Any, dict[str, Any]] | None:
        try:
            if (
                (root_pid, root_handle) != (self.root_pid, self.root_handle)
                or _selector_signature(selectors) != self.selectors
                or _process_lifetimes((root_pid, self.scope.process_id)) != self.process_lifetimes
                or not _belongs_to_scope(self.scope.handle, self.scope.handle)
            ):
                return None
            scope = desktop.window(handle=self.scope.handle).wrapper_object()
            if _identity(scope) != self.scope:
                return None
            scope_visible = scope.is_visible()
            if not scope_visible and not allow_hidden_scope:
                return None
            elements = {}
            for automation_id, identity in self.controls:
                if not _belongs_to_scope(identity.handle, self.scope.handle):
                    return None
                element = desktop.window(handle=identity.handle).wrapper_object()
                if _identity(element) != identity or (scope_visible and not element.is_visible()):
                    return None
                elements[automation_id] = element
            return scope, elements
        except Exception:
            return None
