import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_current_day_orders_shadow as sender
from current_day_orders_contract_cases import TestCurrentDayOrdersContract


@pytest.fixture
def model():
    return SimpleNamespace(
        **{name: getattr(sender, name) for name in (
            "SyntheticDayContext", "SyntheticEncounter", "SyntheticOrderKey",
            "SyntheticOrderQualifiers", "SyntheticOrder", "SyntheticCollectionMemory",
            "EncounterState", "OrderState", "Flag", "CurrentDayOrdersRejected",
            "build_synthetic_collection", "compare_synthetic_collections",
        )},
        decimal_parts=lambda value: value.as_tuple(),
    )


def test_no_source_runtime_io_or_receiver_dependency():
    path = Path(sender.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {"dataclasses", "datetime", "decimal", "enum", "threading", "unicodedata"}
    forbidden = {"open", "print", "eval", "exec", "__import__", "json", "hashlib", "sqlite3", "socket", "requests", "httpx"}
    assert not {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & forbidden
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in {"read_text", "write_text", "write_bytes", "connect", "log", "debug", "info", "warning", "now", "today", "quantize", "normalize"}
                   for node in ast.walk(tree))
    for source in path.parents[1].rglob("*.py"):
        if source != path:
            assert "emr_current_day_orders_shadow" not in source.read_text(encoding="utf-8")
