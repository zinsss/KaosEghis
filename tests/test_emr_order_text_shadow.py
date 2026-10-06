import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime
from pathlib import Path

import pytest

from KaosEghis.core import emr_order_text_shadow as model
from KaosEghis.core.emr_source import EghisSourceDayReader, OrderKey, ReadStatus


@pytest.fixture
def row():
    return {
        "key": {"encounter_id": "synthetic-encounter", "order_date": date(2026, 1, 2),
                "order_number": "1", "order_sequence": "2"},
        "catalog_code": "", "catalog_name": None,
        "user_code": "SYNTHETIC-CODE", "user_name": "Synthetic order name",
    }


def build(row):
    return model.build_synthetic_order_text(row, synthetic_fixture=True)


def test_four_distinct_fields_preserve_blank_catalog_and_user_pair(row):
    result = build(row)
    assert result.catalog_code == "" and result.catalog_name is None
    assert result.user_code == row["user_code"] and result.user_name == row["user_name"]
    assert [field.name for field in fields(result)] == ["key", *model.TEXT_FIELDS]
    assert not hasattr(result, "display_name") and not hasattr(result, "category")


@pytest.mark.parametrize("field", model.TEXT_FIELDS)
@pytest.mark.parametrize("value", [None, "", " ", "  Synthetic text  ", "A\u00a0B",
                                    "\ud569\uc131 \ucc98\ubc29", "e\u0301", "\u00e9"])
def test_exact_text_no_trim_unicode_normalization_or_fallback(row, field, value):
    row[field] = value
    result = build(row)
    assert getattr(result, field) == value


def test_null_empty_and_whitespace_remain_distinct(row):
    values = [build(dict(row, user_name=name)) for name in (None, "", " ")]
    assert len(set(values)) == 3


@pytest.mark.parametrize("field", model.TEXT_FIELDS)
@pytest.mark.parametrize("invalid", [1, True, b"PRIVATE_MARKER", [], {},
                                     "A\x00B", "A\tB", "A\nB", "A\rB", "A\x7fB",
                                     "A\x85B", "A\u202eB", "A\u200bB", "A\ud800B",
                                     "A\u2028B", "A\u2029B"])
def test_wrong_types_and_control_characters_fail_without_echo(row, field, invalid):
    row[field] = invalid
    with pytest.raises(model.OrderTextRejected, match="^invalid_order_text$"):
        build(row)


@pytest.mark.parametrize("field", model.TEXT_FIELDS)
def test_exact_bound_accepted_and_overflow_not_truncated(row, field):
    bound = model.CODE_LIMIT if field.endswith("code") else model.NAME_LIMIT
    row[field] = "\ud569" * bound
    assert getattr(build(row), field) == row[field]
    row[field] += "\ud569"
    with pytest.raises(model.OrderTextRejected, match="^invalid_order_text$"):
        build(row)


@pytest.mark.parametrize("permission", [None, False, 1, "yes"])
def test_explicit_synthetic_flag_on_factory_and_direct_construction(row, permission):
    with pytest.raises(model.OrderTextRejected, match="^synthetic_fixture_required$"):
        model.build_synthetic_order_text(row, synthetic_fixture=permission)
    with pytest.raises(model.OrderTextRejected, match="^synthetic_fixture_required$"):
        model.SyntheticOrderText(OrderKey(**row["key"]), *(row[f] for f in model.TEXT_FIELDS),
                                 synthetic_fixture=permission)


@pytest.mark.parametrize("field", ["key", *model.TEXT_FIELDS])
def test_missing_fields_are_not_defaulted_to_null(row, field):
    del row[field]
    with pytest.raises(model.OrderTextRejected, match="^invalid_fields$"):
        build(row)


@pytest.mark.parametrize("extra", ["hold_opd", "patient_name", "resident_id", "dob", "phone", "address",
                                   "diagnosis", "notes", "insurance", "credentials", "sql", "raw_rows",
                                   "payload", "category", "display_name", "visible", "pacs", "dicom",
                                   "mwl", "orthanc", "act_yn", "source_epoch", "revision"])
@pytest.mark.parametrize("location", ["row", "key"])
def test_unknown_and_forbidden_fields_rejected_not_removed(row, extra, location):
    (row if location == "row" else row["key"])[extra] = "PRIVATE_MARKER"
    with pytest.raises(model.OrderTextRejected, match="^invalid_fields$") as error:
        build(row)
    assert "PRIVATE_MARKER" not in str(error.value) and extra not in str(error.value)


@pytest.mark.parametrize("field", model.KEY_FIELDS)
def test_four_part_identity_changes_are_not_collapsed(row, field):
    original = build(row)
    row["key"][field] = date(2026, 1, 3) if field == "order_date" else "other"
    assert original.key != build(row).key


@pytest.mark.parametrize("field", model.TEXT_FIELDS)
def test_same_key_content_change_and_reuse_remain_visible(row, field):
    original = build(row)
    row[field] = "Synthetic replacement"
    edited = build(row)
    assert original.key == edited.key and original != edited
    for name in model.TEXT_FIELDS:
        row[name] = "Synthetic reused key"
    reused = build(row)
    assert reused.key == original.key and reused != original and reused != edited


@pytest.mark.parametrize("field,value", [
    ("order_date", "2026-01-02"), ("order_date", datetime(2026, 1, 2)),
    ("order_date", None), ("order_number", 1), ("order_sequence", True),
    ("encounter_id", ""), ("encounter_id", " padded "), ("encounter_id", "x" * 129),
    ("order_number", "A\u202eB"), ("order_sequence", "A\nB"),
])
def test_invalid_identity_is_not_coerced(row, field, value):
    row["key"][field] = value
    with pytest.raises(model.OrderTextRejected, match="^invalid_order_key$"):
        build(row)


def test_input_is_detached_and_repr_redacted(row, capsys, caplog):
    key = OrderKey(**row["key"])
    result = model.SyntheticOrderText(key, *(row[f] for f in model.TEXT_FIELDS), synthetic_fixture=True)
    key.__dict__["encounter_id"] = "PRIVATE_MARKER"
    row["user_name"] = "PRIVATE_MARKER"
    assert result.key.encounter_id == "synthetic-encounter"
    assert result.user_name == "Synthetic order name"
    assert repr(result) == str(result) == "<SyntheticOrderText: redacted>"
    with pytest.raises(FrozenInstanceError):
        result.user_name = "PRIVATE_MARKER"
    with pytest.raises(AttributeError):
        object.__setattr__(result, "hold_opd", "PRIVATE_MARKER")
    assert capsys.readouterr() == ("", "") and not caplog.records


def test_direct_construction_and_replace_revalidate(row):
    key = OrderKey(**row["key"])
    key.__dict__["notes"] = "PRIVATE_MARKER"
    with pytest.raises(model.OrderTextRejected, match="^invalid_order_key$"):
        model.SyntheticOrderText(key, *(row[f] for f in model.TEXT_FIELDS), synthetic_fixture=True)
    with pytest.raises(model.OrderTextRejected, match="^invalid_order_text$"):
        replace(build(row), user_name="bad\nvalue", synthetic_fixture=True)


@pytest.mark.parametrize("value", [None, [], (), "PRIVATE_MARKER"])
def test_closed_object_shapes(row, value):
    with pytest.raises(model.OrderTextRejected, match="^invalid_fields$"):
        build(value)
    row["key"] = value
    with pytest.raises(model.OrderTextRejected, match="^invalid_fields$"):
        build(row)


def test_empty_facts_are_not_an_empty_snapshot_or_a_missing_order(row):
    row.update(dict.fromkeys(model.TEXT_FIELDS))
    result = build(row)
    assert result.key == OrderKey(**row["key"])
    assert not hasattr(result, "complete") and not hasattr(result, "verified_empty")
    assert not hasattr(result, "state")
    assert EghisSourceDayReader().read_day(date(2026, 1, 2), None).status is ReadStatus.UNAVAILABLE


def test_no_io_or_runtime_importer_or_wire_surface():
    path = Path(model.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module if isinstance(node, ast.ImportFrom) else alias.name
               for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in node.names}
    assert imports == {"dataclasses", "datetime", "unicodedata", "KaosEghis.core.emr_source"}
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & {"open", "print", "eval", "exec", "__import__"}
    root = path.parents[1]
    for other in root.rglob("*.py"):
        if other != path:
            assert "emr_order_text_shadow" not in other.read_text(encoding="utf-8-sig")
    for forbidden in ("serialize", "parse_json", "publish", "read_day", "display_name"):
        assert not hasattr(model, forbidden)
