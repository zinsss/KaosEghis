"""Disabled settings resolver for the reviewed Orders evidence composition.

The settings-store path and opaque locator are injected only for an approved
attempt.  This module performs no discovery, source authentication, network
access, runtime activation, or logging.
"""

from pathlib import Path
import sqlite3
import time

from KaosEghis.core.kaosorders_non_phi_evidence_composition import (
    DisabledOrdersEvidenceComposition,
    Psycopg2SingleConnectionPath,
    build_disabled_orders_evidence_composition,
)


_MAX_LOCATOR_CHARACTERS = 128


class SettingsResolutionRejected(RuntimeError):
    """Fixed non-sensitive settings-resolution rejection."""


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


class ApplicationSettingsOpaqueResolver(_Redacted):
    """Resolve one opaque value from one explicitly injected read-only store."""

    __slots__ = ("_attempted", "_locator", "_store_path")

    def __init__(self, *, store_path: Path, locator: str):
        if (
            not isinstance(store_path, Path)
            or not store_path.is_absolute()
            or type(locator) is not str
            or not locator
            or len(locator) > _MAX_LOCATOR_CHARACTERS
            or any(ord(character) < 0x20 for character in locator)
        ):
            raise SettingsResolutionRejected("settings_resolution_failed")
        self._store_path = store_path
        self._locator = locator
        self._attempted = False

    def _resolve_once(self) -> str:
        if self._attempted:
            raise SettingsResolutionRejected("settings_resolution_failed")
        self._attempted = True

        connection = None
        cursor = None
        resolved_value = None
        failed = False
        try:
            store_path = self._store_path.resolve(strict=True)
            if store_path != self._store_path or not store_path.is_file():
                raise SettingsResolutionRejected("settings_resolution_failed")
            connection = sqlite3.connect(
                f"{store_path.as_uri()}?mode=ro",
                uri=True,
                timeout=1.0,
            )
            cursor = connection.cursor()
            cursor.execute("PRAGMA query_only = ON")
            cursor.execute("PRAGMA query_only")
            if cursor.fetchone() != (1,):
                raise SettingsResolutionRejected("settings_resolution_failed")
            cursor.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (self._locator,),
            )
            rows = cursor.fetchmany(2)
            if (
                len(rows) != 1
                or type(rows[0]) is not tuple
                or len(rows[0]) != 1
                or type(rows[0][0]) is not str
                or not rows[0][0].strip()
            ):
                raise SettingsResolutionRejected("settings_resolution_failed")
            resolved_value = rows[0][0].strip()
        except SettingsResolutionRejected:
            failed = True
        except Exception:
            failed = True
        finally:
            self._locator = ""
            cursor_closed = cursor is None
            connection_closed = connection is None
            if cursor is not None:
                try:
                    cursor.close()
                    try:
                        cursor.execute("SELECT 1")
                    except sqlite3.ProgrammingError:
                        cursor_closed = True
                    else:
                        cursor_closed = False
                except Exception:
                    cursor_closed = False
            if connection is not None:
                try:
                    connection.close()
                    try:
                        connection.execute("SELECT 1")
                    except sqlite3.ProgrammingError:
                        connection_closed = True
                    else:
                        connection_closed = False
                except Exception:
                    connection_closed = False

        if failed or not cursor_closed or not connection_closed:
            resolved_value = None
            raise SettingsResolutionRejected("settings_resolution_failed")
        if type(resolved_value) is not str or not resolved_value:
            raise SettingsResolutionRejected("settings_resolution_failed")
        return resolved_value


def build_disabled_orders_evidence_composition_from_settings(
    *, resolver: ApplicationSettingsOpaqueResolver,
    monotonic=time.monotonic,
) -> DisabledOrdersEvidenceComposition:
    """Resolve once and construct the still-disabled reviewed composition."""

    if type(resolver) is not ApplicationSettingsOpaqueResolver:
        raise SettingsResolutionRejected("settings_resolution_failed")
    opaque_value = resolver._resolve_once()
    try:
        path = Psycopg2SingleConnectionPath(opaque_value)
    finally:
        opaque_value = ""
    return build_disabled_orders_evidence_composition(
        path=path,
        monotonic=monotonic,
    )
