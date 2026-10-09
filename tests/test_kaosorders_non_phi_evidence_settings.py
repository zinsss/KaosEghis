import ast
from pathlib import Path
import sqlite3

import pytest

from KaosEghis.core import kaosorders_non_phi_evidence_settings as settings


def _store(tmp_path: Path, rows: list[tuple[str, object]]) -> Path:
    path = (tmp_path / "synthetic-settings.sqlite").resolve()
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE app_settings (key TEXT, value)")
        connection.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()
    return path


def test_exact_synthetic_setting_builds_disabled_composition_and_closes_store(
    tmp_path,
):
    store = _store(
        tmp_path,
        [("synthetic.connection", "postgresql://synthetic.invalid/review")],
    )
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=store,
        locator="synthetic.connection",
    )

    composition = settings.build_disabled_orders_evidence_composition_from_settings(
        resolver=resolver,
    )

    assert composition.final_artifact is None
    assert len(composition.statement_digests) == 9
    store.unlink()
    assert not store.exists()


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [("synthetic.connection", "")],
        [("synthetic.connection", None)],
        [
            ("synthetic.connection", "postgresql://synthetic.invalid/one"),
            ("synthetic.connection", "postgresql://synthetic.invalid/two"),
        ],
    ],
)
def test_missing_blank_non_string_or_duplicate_value_fails_closed(tmp_path, rows):
    store = _store(tmp_path, rows)
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=store,
        locator="synthetic.connection",
    )

    with pytest.raises(
        settings.SettingsResolutionRejected,
        match=r"^settings_resolution_failed$",
    ):
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )


def test_missing_store_and_relative_path_fail_closed_without_creation(tmp_path):
    missing = (tmp_path / "missing.sqlite").resolve()
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=missing,
        locator="synthetic.connection",
    )
    with pytest.raises(settings.SettingsResolutionRejected):
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )
    assert not missing.exists()

    with pytest.raises(settings.SettingsResolutionRejected):
        settings.ApplicationSettingsOpaqueResolver(
            store_path=Path("relative.sqlite"),
            locator="synthetic.connection",
        )


def test_symlink_store_is_rejected_without_reading_target(tmp_path):
    target = _store(
        tmp_path,
        [("synthetic.connection", "postgresql://synthetic.invalid/review")],
    )
    link = tmp_path / "linked.sqlite"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=link.absolute(),
        locator="synthetic.connection",
    )
    with pytest.raises(settings.SettingsResolutionRejected):
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )


def test_resolver_is_single_use_and_never_echoes_locator_or_value(tmp_path):
    locator = "synthetic.private.locator"
    value = "PRIVATE_SYNTHETIC_CANARY"
    store = _store(tmp_path, [(locator, value)])
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=store,
        locator=locator,
    )
    assert repr(resolver) == "<ApplicationSettingsOpaqueResolver: redacted>"
    composition = settings.build_disabled_orders_evidence_composition_from_settings(
        resolver=resolver,
    )
    assert composition.final_artifact is None
    with pytest.raises(settings.SettingsResolutionRejected) as error:
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )
    assert str(error.value) == "settings_resolution_failed"
    assert locator not in repr(error.value) and value not in repr(error.value)


def test_locator_is_parameterized_and_runtime_remains_unwired():
    source_path = Path(settings.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    execute_calls = [
        node for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
    ]
    assert any(
        len(node.args) == 2
        and isinstance(node.args[1], ast.Tuple)
        for node in execute_calls
    )
    imported_roots = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
    }
    called_names = {
        node.func.id
        for node in calls
        if isinstance(node.func, ast.Name)
    }
    assert "logging" not in imported_roots and "print" not in called_names
    assert "psycopg2" not in source and "connect_timeout" not in source

    module_name = "kaosorders_non_phi_evidence_settings"
    for path in Path("KaosEghis").rglob("*.py"):
        if path.resolve() == source_path.resolve():
            continue
        assert module_name not in path.read_text(encoding="utf-8"), path
