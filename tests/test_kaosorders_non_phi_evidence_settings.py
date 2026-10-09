import ast
from pathlib import Path
import sqlite3

import pytest

from KaosEghis.core import kaosorders_non_phi_evidence_settings as settings


class FailingCursor:
    def __init__(self, *, stage, value):
        self.stage = stage
        self.value = value
        self.execute_count = 0
        self.close_attempts = 0
        self.closed = False

    def execute(self, _statement, _parameters=None):
        if self.closed:
            if self.stage == "cursor_post_close_verification":
                return None
            raise sqlite3.ProgrammingError("SYNTHETIC_PRIVATE_CANARY")
        self.execute_count += 1
        stages = {
            1: "pragma_set",
            2: "pragma_query",
            3: "value_query",
        }
        if self.stage == stages.get(self.execute_count):
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")

    def fetchone(self):
        if self.stage == "pragma_fetch":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return (1,)

    def fetchmany(self, _maximum):
        if self.stage == "value_fetch":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return [(self.value,)]

    def close(self):
        self.close_attempts += 1
        if self.stage == "cursor_close":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        self.closed = True


class FailingConnection:
    def __init__(self, *, stage, value):
        self.stage = stage
        self.cursor_value = FailingCursor(stage=stage, value=value)
        self.cursor_attempts = 0
        self.close_attempts = 0
        self.closed = False

    def cursor(self):
        self.cursor_attempts += 1
        if self.stage == "cursor_create":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return self.cursor_value

    def close(self):
        self.close_attempts += 1
        if self.stage == "connection_close":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        self.closed = True

    def execute(self, _statement):
        if self.closed and self.stage != "connection_post_close_verification":
            raise sqlite3.ProgrammingError("SYNTHETIC_PRIVATE_CANARY")
        return None


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


def test_opaque_value_reaches_connection_path_byte_for_byte_without_echo(
    tmp_path, monkeypatch, capsys, caplog,
):
    value = "  postgresql://synthetic.invalid/경계?token=Ω  "
    store = _store(tmp_path, [("synthetic.connection", value)])
    observed = []

    class SyntheticPath:
        def __init__(self, opaque_value):
            observed.append(opaque_value)

    sentinel = object()
    monkeypatch.setattr(settings, "Psycopg2SingleConnectionPath", SyntheticPath)
    monkeypatch.setattr(
        settings,
        "build_disabled_orders_evidence_composition",
        lambda *, path, monotonic: sentinel,
    )
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=store,
        locator="synthetic.connection",
    )

    result = settings.build_disabled_orders_evidence_composition_from_settings(
        resolver=resolver,
    )

    assert result is sentinel
    assert observed == [value]
    assert observed[0].encode("utf-8") == value.encode("utf-8")
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


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


@pytest.mark.parametrize(
    "stage",
    [
        "connect",
        "cursor_create",
        "pragma_set",
        "pragma_query",
        "pragma_fetch",
        "value_query",
        "value_fetch",
        "cursor_close",
        "cursor_post_close_verification",
        "connection_close",
        "connection_post_close_verification",
    ],
)
def test_every_settings_failure_cleans_up_fails_fixed_and_consumes_once(
    tmp_path, monkeypatch, capsys, caplog, stage,
):
    locator = "synthetic.private.locator"
    value = "  SYNTHETIC_PRIVATE_VALUE_한글  "
    store = _store(tmp_path, [(locator, value)])
    connection = FailingConnection(stage=stage, value=value)
    connect_calls = []
    composition_calls = []

    def connect(*_args, **_kwargs):
        connect_calls.append(True)
        if stage == "connect":
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return connection

    monkeypatch.setattr(settings.sqlite3, "connect", connect)
    monkeypatch.setattr(
        settings,
        "Psycopg2SingleConnectionPath",
        lambda _value: composition_calls.append(True),
    )
    resolver = settings.ApplicationSettingsOpaqueResolver(
        store_path=store,
        locator=locator,
    )

    with pytest.raises(settings.SettingsResolutionRejected) as error:
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )

    assert str(error.value) == "settings_resolution_failed"
    assert connect_calls == [True]
    assert connection.cursor_attempts == (0 if stage == "connect" else 1)
    if stage == "connect":
        assert connection.close_attempts == 0
        assert connection.cursor_value.close_attempts == 0
    else:
        assert connection.close_attempts == 1
        if stage == "cursor_create":
            assert connection.cursor_value.close_attempts == 0
        else:
            assert connection.cursor_value.close_attempts == 1
    assert composition_calls == []
    assert locator not in repr(error.value) and value not in repr(error.value)
    assert capsys.readouterr() == ("", "")
    assert not caplog.records

    with pytest.raises(
        settings.SettingsResolutionRejected,
        match=r"^settings_resolution_failed$",
    ):
        settings.build_disabled_orders_evidence_composition_from_settings(
            resolver=resolver,
        )
    assert connect_calls == [True]
    assert connection.close_attempts == (0 if stage == "connect" else 1)


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
