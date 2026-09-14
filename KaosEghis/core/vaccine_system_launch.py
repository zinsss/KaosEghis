"""Explicit browser launch helpers for the external vaccine systems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse
import webbrowser


@dataclass(frozen=True)
class VaccineSystemLaunchResult:
    success: bool
    message: str


_SYSTEMS = {
    "general": ("General vaccine system", "vaccine_general_system_launch_url"),
    "influenza": ("Influenza vaccine system", "vaccine_influenza_system_launch_url"),
    "covid": ("COVID vaccine system", "vaccine_covid_system_launch_url"),
}


def open_vaccine_system(
    settings: dict[str, str],
    system: str,
    *,
    opener: Callable[..., bool] = webbrowser.open,
) -> VaccineSystemLaunchResult:
    """Open one configured external system without passing patient data or credentials."""

    target = _SYSTEMS.get(system)
    if target is None:
        return VaccineSystemLaunchResult(False, "Vaccine system is not configured.")
    label, setting_key = target
    url = str(settings.get(setting_key, "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return VaccineSystemLaunchResult(
            False,
            f"{label} launch URL is not configured.",
        )
    try:
        opened = bool(opener(url, new=2, autoraise=True))
    except Exception:
        opened = False
    if not opened:
        return VaccineSystemLaunchResult(False, f"Could not open {label}.")
    return VaccineSystemLaunchResult(
        True,
        f"{label} opened. Complete sign-in and the remaining workflow manually.",
    )
