import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime
from pathlib import Path

import pytest

from KaosEghis.core import kaosorders_current_day_orders as model


DAY = date(2026, 10, 7)


@pytest.fixture
def parent_row():
    return {
        "encounter_id": "synthetic-encounter-1",
        "chart_number": "TEST-0001",
        "patient_name": "Synthetic Alpha",
        "sex": "F",
        "age": 53,
        "state": model.IncludedParentState.ON_HOLD,
        "hold_yn": "N",
    }


@pytest.fixture
def child_row():
    return {
        "key": {
            "encounter_id": "synthetic-encounter-1",
            "order_date": DAY,
            "order_number": "1",
            "order_sequence": "1",
        },
        "catalog_code": None,
        "catalog_name": "",
        "user_code": "TEST-CODE",
        "user_name": "Synthetic order",
        "order_type": "TEST-TYPE",
        "department_code": "",
        "state": model.ChildState.ACTIVE,
        "dc_yn": "N",
        "act_yn": "N",
    }


def parent(row):
    return model.build_synthetic_parent(row, synthetic_fixture=True)


def child(row):
    return model.build_synthetic_child(row, synthetic_fixture=True)


def collection(parents, children, *, day=DAY):
    return model.validate_synthetic_collection(
        day, tuple(parents), tuple(children), synthetic_fixture=True
    )


def test_new_identity_is_independent_and_mapping_remains_unassigned():
    assert model.CONTRACT_ID == "kaosorders.current-day-orders"
    assert model.CONTRACT_VERSION == 1
    assert model.PROJECTION_ID == "kaosorders-current-day-orders-v1"
    assert not hasattr(model, "MAPPING_REVISION")
    assert not hasattr(model, "PRODUCTION_MAPPING_REVISION")


def test_closed_model_fields_match_accepted_parent_and_child_boundaries(parent_row, child_row):
    assert [field.name for field in fields(parent(parent_row))] == list(model.PARENT_FIELDS)
    assert [field.name for field in fields(child(child_row))] == list(model.CHILD_FIELDS)
    assert [field.name for field in fields(child(child_row).key)] == list(model.KEY_FIELDS)


@pytest.mark.parametrize("state", list(model.IncludedParentState))
def test_all_five_included_parent_states_are_exact(parent_row, state):
    parent_row["state"] = state
    assert parent(parent_row).state is state


@pytest.mark.parametrize("invalid", ["CANCELLED", None, "ON_HOLD", True, 1])
def test_cancelled_or_untyped_parent_state_is_outside_projection(parent_row, invalid):
    parent_row["state"] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_parent_state$"):
        parent(parent_row)


@pytest.mark.parametrize("sex,age", [("M", 0), ("F", 130), (None, None), (None, 42)])
def test_parent_demographic_boundary(parent_row, sex, age):
    parent_row.update(sex=sex, age=age)
    result = parent(parent_row)
    assert result.sex is sex and result.age == age


@pytest.mark.parametrize(
    "sex,age", [("O", 1), ("", 1), (" M", 1), (1, 1), ("M", -1), ("F", 131), ("F", True), ("F", 1.5)]
)
def test_invalid_parent_demographics_are_fixed_rejections(parent_row, sex, age):
    parent_row.update(sex=sex, age=age)
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_demographics$"):
        parent(parent_row)


@pytest.mark.parametrize("field", ["encounter_id", "chart_number", "patient_name"])
@pytest.mark.parametrize("invalid", [None, "", " ", " padded ", 1, "A\nB", "A\u202eB"])
def test_required_parent_text_rejects_null_blank_padding_type_and_controls(parent_row, field, invalid):
    parent_row[field] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_text$"):
        parent(parent_row)


@pytest.mark.parametrize("field,limit", [("encounter_id", model.CODE_LIMIT), ("chart_number", model.CODE_LIMIT), ("patient_name", model.NAME_LIMIT)])
def test_parent_text_exact_bounds_are_not_truncated(parent_row, field, limit):
    parent_row[field] = "S" * limit
    assert getattr(parent(parent_row), field) == parent_row[field]
    parent_row[field] += "S"
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_text$"):
        parent(parent_row)


@pytest.mark.parametrize("flag", ["Y", "N"])
def test_parent_flag_is_strict(parent_row, flag):
    parent_row["hold_yn"] = flag
    assert parent(parent_row).hold_yn == flag


@pytest.mark.parametrize("invalid", [None, "", "y", " Y", "Y ", True, 1, "UNKNOWN"])
def test_parent_flag_rejects_coercion(parent_row, invalid):
    parent_row["hold_yn"] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_flag$"):
        parent(parent_row)


@pytest.mark.parametrize("field", model.CHILD_TEXT_FIELDS)
@pytest.mark.parametrize("value", [None, "", " ", "  exact text  ", "A\u00a0B", "합성 처방", "e\u0301", "é"])
def test_nullable_child_text_is_exact_without_trim_normalization_or_fallback(child_row, field, value):
    child_row[field] = value
    assert getattr(child(child_row), field) == value


@pytest.mark.parametrize("field", model.CHILD_TEXT_FIELDS)
@pytest.mark.parametrize("invalid", [1, True, b"PRIVATE", [], {}, "A\x00B", "A\nB", "A\u202eB", "A\ud800B", "A\u2028B"])
def test_child_text_wrong_types_and_controls_fail_without_echo(child_row, field, invalid):
    child_row[field] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_text$") as error:
        child(child_row)
    assert str(error.value) == "invalid_text" and "PRIVATE" not in repr(error.value)


@pytest.mark.parametrize("field", model.CHILD_TEXT_FIELDS)
def test_child_text_exact_bounds_are_not_truncated(child_row, field):
    limit = model.NAME_LIMIT if field.endswith("name") else model.CODE_LIMIT
    child_row[field] = "합" * limit
    assert getattr(child(child_row), field) == child_row[field]
    child_row[field] += "합"
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_text$"):
        child(child_row)


@pytest.mark.parametrize("state", list(model.ChildState))
@pytest.mark.parametrize("dc,act", [("N", "N"), ("N", "Y"), ("Y", "N"), ("Y", "Y")])
def test_child_state_and_flags_are_independent_exact_facts(child_row, state, dc, act):
    child_row.update(state=state, dc_yn=dc, act_yn=act)
    result = child(child_row)
    assert (result.state, result.dc_yn, result.act_yn) == (state, dc, act)


@pytest.mark.parametrize("field", ["dc_yn", "act_yn"])
@pytest.mark.parametrize("invalid", [None, "", "y", " Y", "Y ", True, 1, "UNKNOWN"])
def test_child_flags_reject_coercion(child_row, field, invalid):
    child_row[field] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_flag$"):
        child(child_row)


@pytest.mark.parametrize("invalid", [None, "ACTIVE", "CANCELLED", True, 1])
def test_child_state_requires_the_closed_enum(child_row, invalid):
    child_row["state"] = invalid
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_child_state$"):
        child(child_row)


@pytest.mark.parametrize("field", model.KEY_FIELDS)
def test_each_key_part_changes_identity(child_row, field):
    first = child(child_row)
    child_row["key"][field] = date(2026, 10, 6) if field == "order_date" else "other"
    assert child(child_row).key != first.key


@pytest.mark.parametrize(
    "field,invalid",
    [("order_date", "2026-10-07"), ("order_date", datetime(2026, 10, 7)), ("order_date", None),
     ("encounter_id", ""), ("encounter_id", " padded "), ("order_number", 1),
     ("order_sequence", True), ("order_number", "A\nB")],
)
def test_invalid_key_parts_are_not_coerced(child_row, field, invalid):
    child_row["key"][field] = invalid
    with pytest.raises(model.CurrentDayFactRejected) as error:
        child(child_row)
    assert str(error.value) in {"invalid_key", "invalid_text"}


@pytest.mark.parametrize("target", ["parent", "child", "key"])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_synthetic_factories_enforce_closed_fields(parent_row, child_row, target, change):
    row = parent_row if target == "parent" else child_row
    container = child_row["key"] if target == "key" else row
    if change == "missing":
        container.pop(next(iter(container)))
    else:
        container["private_marker"] = "PRIVATE_VALUE"
    factory = parent if target == "parent" else child
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_fields$") as error:
        factory(row)
    assert "PRIVATE" not in repr(error.value)


@pytest.mark.parametrize("permission", [None, False, 1, "yes"])
def test_explicit_synthetic_permission_is_required(parent_row, child_row, permission):
    with pytest.raises(model.CurrentDayFactRejected, match="^synthetic_fixture_required$"):
        model.build_synthetic_parent(parent_row, synthetic_fixture=permission)
    with pytest.raises(model.CurrentDayFactRejected, match="^synthetic_fixture_required$"):
        model.build_synthetic_child(child_row, synthetic_fixture=permission)


def test_models_are_immutable_detached_and_redacted(parent_row, child_row):
    built_parent = parent(parent_row)
    built_child = child(child_row)
    parent_row["patient_name"] = "PRIVATE_MARKER"
    child_row["key"]["encounter_id"] = "PRIVATE_MARKER"
    child_row["user_name"] = "PRIVATE_MARKER"
    assert built_parent.patient_name == "Synthetic Alpha"
    assert built_child.key.encounter_id == "synthetic-encounter-1"
    assert built_child.user_name == "Synthetic order"
    assert repr(built_parent) == "<SyntheticCurrentDayParent: redacted>"
    assert repr(built_child) == "<SyntheticCurrentDayChild: redacted>"
    with pytest.raises(FrozenInstanceError):
        built_parent.age = 1
    with pytest.raises(AttributeError):
        object.__setattr__(built_child, "notes", "PRIVATE_MARKER")


def test_collection_sorts_deterministically_and_keeps_no_order_parent(parent_row, child_row):
    first = parent(parent_row)
    parent_row.update(encounter_id="synthetic-encounter-0", chart_number="TEST-0000")
    no_order = parent(parent_row)
    child_row["key"].update(order_number="2")
    second_child = child(child_row)
    child_row["key"].update(order_number="1")
    first_child = child(child_row)
    result = collection((first, no_order), (second_child, first_child))
    assert [row.encounter_id for row in result.parents] == ["synthetic-encounter-0", "synthetic-encounter-1"]
    assert [row.key.order_number for row in result.children] == ["1", "2"]
    assert not any(row.key.encounter_id == no_order.encounter_id for row in result.children)


def test_collection_keeps_cancelled_fee_unclassified_and_blank_facts(parent_row, child_row):
    p = parent(parent_row)
    child_row.update(
        catalog_code="", catalog_name=None, user_code=None, user_name="",
        order_type="TEST-FEE", department_code=None,
        state=model.ChildState.CANCELLED, dc_yn="Y", act_yn="N",
    )
    result = collection((p,), (child(child_row),))
    assert result.children[0].state is model.ChildState.CANCELLED
    assert result.children[0].catalog_code == "" and result.children[0].catalog_name is None
    assert not hasattr(result.children[0], "category") and not hasattr(result.children[0], "fee_excluded")


def test_duplicate_parent_child_and_orphan_reject_whole_collection(parent_row, child_row):
    p = parent(parent_row)
    c = child(child_row)
    with pytest.raises(model.CurrentDayFactRejected, match="^duplicate_parent$"):
        collection((p, p), (c,))
    with pytest.raises(model.CurrentDayFactRejected, match="^duplicate_child$"):
        collection((p,), (c, c))
    child_row["key"]["encounter_id"] = "synthetic-missing-parent"
    with pytest.raises(model.CurrentDayFactRejected, match="^orphan_child$"):
        collection((p,), (child(child_row),))


def test_collection_bounds_and_types_are_exact(monkeypatch, parent_row, child_row):
    p = parent(parent_row)
    c = child(child_row)
    monkeypatch.setattr(model, "MAX_PARENTS", 0)
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_row_bound$"):
        collection((p,), ())
    monkeypatch.setattr(model, "MAX_PARENTS", 1)
    monkeypatch.setattr(model, "MAX_CHILDREN", 0)
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_row_bound$"):
        collection((p,), (c,))
    with pytest.raises(model.CurrentDayFactRejected, match="^invalid_row_bound$"):
        model.validate_synthetic_collection(DAY, [p], (), synthetic_fixture=True)


def test_same_key_any_child_fact_change_is_full_replacement(parent_row, child_row):
    p = parent(parent_row)
    original = child(child_row)
    previous = collection((p,), (original,))
    for field, value in (
        ("catalog_code", "OTHER"), ("catalog_name", "Other name"),
        ("user_code", "OTHER-USER"), ("user_name", "Other user name"),
        ("order_type", None), ("department_code", "OTHER-DEPT"),
        ("state", model.ChildState.CANCELLED), ("dc_yn", "Y"), ("act_yn", "Y"),
    ):
        changed = replace(original, **{field: value}, synthetic_fixture=True)
        comparison = model.compare_synthetic_collections(previous, collection((p,), (changed,)))
        assert comparison.child_upserts == (changed,)
        assert comparison.missing_child_keys == ()


def test_explicit_cancellation_absence_and_reappearance_are_distinct(parent_row, child_row):
    p = parent(parent_row)
    active = child(child_row)
    baseline = collection((p,), (active,))
    cancelled = replace(active, state=model.ChildState.CANCELLED, dc_yn="Y", synthetic_fixture=True)
    cancellation = model.compare_synthetic_collections(baseline, collection((p,), (cancelled,)))
    assert cancellation.child_upserts == (cancelled,) and not cancellation.missing_child_keys
    absent_facts = collection((p,), ())
    absence = model.compare_synthetic_collections(collection((p,), (cancelled,)), absent_facts)
    assert absence.child_upserts == () and absence.missing_child_keys == (active.key,)
    reappearance = model.compare_synthetic_collections(absent_facts, baseline)
    assert reappearance.child_upserts == (active,) and not reappearance.missing_child_keys


def test_parent_removal_and_restoration_include_child_absence_and_reappearance(parent_row, child_row):
    p = parent(parent_row)
    c = child(child_row)
    baseline = collection((p,), (c,))
    empty = collection((), ())
    removed = model.compare_synthetic_collections(baseline, empty)
    assert removed.missing_parent_ids == (p.encounter_id,)
    assert removed.missing_child_keys == (c.key,)
    restored = model.compare_synthetic_collections(empty, baseline)
    assert restored.parent_upserts == (p,) and restored.child_upserts == (c,)


def test_initial_comparison_is_full_and_same_day_is_required(parent_row, child_row):
    facts = collection((parent(parent_row),), (child(child_row),))
    initial = model.compare_synthetic_collections(None, facts)
    assert initial.full_replacement is True
    assert initial.parent_upserts == facts.parents and initial.child_upserts == facts.children
    with pytest.raises(model.CurrentDayFactRejected, match="^scope_mismatch$"):
        model.compare_synthetic_collections(facts, collection((), (), day=date(2026, 10, 8)))


def test_no_io_runtime_wire_reader_or_mapping_surface():
    path = Path(model.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {"dataclasses", "datetime", "enum", "unicodedata"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not calls & {"open", "print", "eval", "exec", "__import__"}
    for forbidden in (
        "serialize", "parse_json", "publish", "read_day", "MAPPING_REVISION",
        "source_epoch", "revision", "endpoint", "token", "retry",
    ):
        assert not hasattr(model, forbidden)
    root = path.parents[1]
    for other in root.rglob("*.py"):
        if other != path:
            assert "kaosorders_current_day_orders" not in other.read_text(encoding="utf-8-sig")
