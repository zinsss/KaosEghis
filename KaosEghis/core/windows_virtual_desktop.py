"""Verified virtual-desktop selection for explicit desktop automation."""

from __future__ import annotations

from dataclasses import dataclass

from KaosEghis.core.windows_desktop import interactive_desktop_error


@dataclass(frozen=True)
class VirtualDesktopResult:
    success: bool
    status: str
    message: str


def ensure_first_virtual_desktop() -> VirtualDesktopResult:
    """Switch by desktop identity, never by simulated directional shortcuts."""

    if interactive_desktop_error() is not None:
        return VirtualDesktopResult(False, "desktop_unavailable", "Unlock Windows before switching desktops.")
    try:
        from pyvda import VirtualDesktop

        first = VirtualDesktop(1)
        if VirtualDesktop.current().id != first.id:
            first.go(allow_set_foreground=False)
        if (
            VirtualDesktop.current().id != first.id
            or VirtualDesktop(1).id != first.id
        ):
            return VirtualDesktopResult(
                False, "desktop_switch_failed", "Virtual Desktop 1 switch is not confirmed; reset deferred.",
            )
    except ImportError:
        return VirtualDesktopResult(
            False, "unavailable", "Virtual desktop support is unavailable; install the project dependencies.",
        )
    except Exception:
        return VirtualDesktopResult(
            False, "desktop_switch_failed", "Virtual Desktop 1 could not be selected or verified; reset deferred.",
        )
    return VirtualDesktopResult(True, "ready", "Virtual Desktop 1 is active.")


def first_virtual_desktop_is_active() -> bool:
    """Read-only final guard; do not reacquire a desktop the operator left."""

    if interactive_desktop_error() is not None:
        return False
    try:
        from pyvda import VirtualDesktop

        return VirtualDesktop.current().id == VirtualDesktop(1).id
    except Exception:
        return False
