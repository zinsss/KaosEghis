"""Shared synthetic known-answer cases, not a wire fixture or production adapter.

Each repository runs these against its own implementation via a test-only facade.
Only primitive fact values and exact decimal tuples form the compatibility oracle.
"""

from dataclasses import FrozenInstanceError, fields
from datetime import date, datetime
from decimal import Decimal, localcontext
from itertools import product

import pytest


DAY = date(2026, 10, 10)
TEXT_FIELDS = ("catalog_code", "catalog_name", "user_code", "user_name", "order_type", "department_code")
DECIMAL_FIELDS = ("daily_quantity", "frequency_count", "day_count")
KEY_FIELDS = ("encounter_id", "order_date", "order_number", "order_sequence")
STATES = ("REGISTERED", "IN_PROGRESS", "ON_HOLD", "CONSULTATION_COMPLETED", "PAYMENT_COMPLETED", "CANCELLED")
CHANGE_FIELDS = ("encounter_added", "encounter_replaced", "encounter_removed", "order_added", "order_replaced", "order_removed")


def context(m, day=DAY):
    return m.SyntheticDayContext(day, synthetic_fixture=True)


def parent(m, identifier="synthetic-parent", state="ON_HOLD"):
    return m.SyntheticEncounter(identifier, m.EncounterState(state), synthetic_fixture=True)


def key(m, **changes):
    values = dict(encounter_id="synthetic-parent", order_date=DAY, order_number="1", order_sequence="1")
    values.update(changes)
    return m.SyntheticOrderKey(**values, synthetic_fixture=True)


def order_values(m):
    return dict(
        key=key(m), catalog_code="", catalog_name=None, user_code="SYNTHETIC-CODE",
        user_name="\ud569\uc131 \ucc98\ubc29", order_type="SYNTHETIC-TYPE",
        department_code="SYNTHETIC-DEPARTMENT", daily_quantity=Decimal("1.250"),
        frequency_count=Decimal("3.00"), day_count=Decimal("7.0"),
        state=m.OrderState.ACTIVE,
        qualifiers=m.SyntheticOrderQualifiers(m.Flag.NO, m.Flag.NO, synthetic_fixture=True),
    )


def order(m, **changes):
    values = order_values(m)
    values.update(changes)
    return m.SyntheticOrder(**values, synthetic_fixture=True)


def collection(m, parents=(), children=(), day=DAY):
    return m.build_synthetic_collection(context(m, day), parents, children, synthetic_fixture=True)


def memory(m):
    return m.SyntheticCollectionMemory(context(m), synthetic_fixture=True)


def observed_order(m, item):
    return (
        tuple(getattr(item.key, name) for name in KEY_FIELDS),
        *(getattr(item, name) for name in TEXT_FIELDS),
        *(None if getattr(item, name) is None else m.decimal_parts(getattr(item, name)) for name in DECIMAL_FIELDS),
        item.state.value, (item.qualifiers.dc_yn.value, item.qualifiers.act_yn.value),
    )


def changes(result):
    return tuple(getattr(result, name) for name in CHANGE_FIELDS)


class TestCurrentDayOrdersContract:
    def test_identity_and_closed_inventory(self, model):
        m, ctx = model, context(model)
        assert (ctx.contract_id, ctx.contract_version, ctx.projection_id, ctx.clinic_timezone) == (
            "kaosorders.current-day-orders", 1, "kaosorders-current-day-orders-v1", "Asia/Seoul",
        )
        assert tuple(s.value for s in m.EncounterState) == STATES
        assert tuple(s.value for s in m.OrderState) == ("ACTIVE", "CANCELLED")
        assert tuple(s.value for s in m.Flag) == ("Y", "N")
        assert [f.name for f in fields(order(m))] == ["key", *TEXT_FIELDS, *DECIMAL_FIELDS, "state", "qualifiers"]
        assert [f.name for f in fields(key(m))] == list(KEY_FIELDS)
        assert [f.name for f in fields(parent(m))] == ["encounter_id", "state"]
        assert [f.name for f in fields(order(m).qualifiers)] == ["dc_yn", "act_yn"]
        assert not hasattr(ctx, "mapping_revision")

    def test_complete_fact_known_answer(self, model):
        assert observed_order(model, order(model)) == (
            ("synthetic-parent", DAY, "1", "1"), "", None, "SYNTHETIC-CODE",
            "\ud569\uc131 \ucc98\ubc29", "SYNTHETIC-TYPE", "SYNTHETIC-DEPARTMENT",
            Decimal("1.250").as_tuple(), Decimal("3.00").as_tuple(), Decimal("7.0").as_tuple(),
            "ACTIVE", ("N", "N"),
        )

    @pytest.mark.parametrize("field", TEXT_FIELDS)
    @pytest.mark.parametrize("value", [None, "", " ", " padded ", "A\u00a0B", "\ud569\uc131", "e\u0301", "\u00e9"])
    def test_text_is_preserved(self, model, field, value):
        result = order(model, **{field: value})
        assert getattr(result, field) == value
        assert observed_order(model, result)[1 + TEXT_FIELDS.index(field)] == value

    @pytest.mark.parametrize("field", TEXT_FIELDS)
    @pytest.mark.parametrize("invalid", [1, True, b"PRIVATE", [], {}, "A\x00B", "A\tB", "A\nB", "A\x7fB", "A\x85B", "A\u202eB", "A\u200bB", "A\ud800B", "A\u2028B", "A\u2029B"])
    def test_invalid_text_fixed_errors(self, model, field, invalid):
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_order_text$"):
            order(model, **{field: invalid})

    @pytest.mark.parametrize("field", TEXT_FIELDS)
    def test_text_boundaries(self, model, field):
        limit = 256 if field.endswith("name") else 128
        assert getattr(order(model, **{field: "\ud569" * limit}), field) == "\ud569" * limit
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_order_text$"):
            order(model, **{field: "\ud569" * (limit + 1)})

    @pytest.mark.parametrize("field", DECIMAL_FIELDS)
    @pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("-0"), Decimal("-0.00"), Decimal("0E+17"), Decimal("1.0"), Decimal("1.00"), Decimal("-1.25"), Decimal("1E-12"), Decimal("1E+17"), Decimal("999999999999999999.999999999999"), Decimal("-999999999999999999.999999999999")])
    def test_exact_decimal_known_answers(self, model, field, value):
        with localcontext() as decimal_context:
            decimal_context.prec = 2
            result = order(model, **{field: value})
            actual = getattr(result, field)
            assert (None if actual is None else model.decimal_parts(actual)) == (None if value is None else value.as_tuple())

    @pytest.mark.parametrize("field", DECIMAL_FIELDS)
    @pytest.mark.parametrize("invalid", ["1.25", 1, True, False, 1.25, b"1", [], {}, Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("1E+18"), Decimal("0E+18"), Decimal("1E-13"), Decimal("0E-13"), Decimal("1E+999999"), Decimal("1E-999999")])
    def test_numeric_rejections(self, model, field, invalid):
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_exact_decimal$"):
            order(model, **{field: invalid})

    @pytest.mark.parametrize("field", DECIMAL_FIELDS)
    def test_scale_signed_zero_null_and_numbers_are_distinct_changes(self, model, field):
        store = memory(model)
        values = [None, Decimal("0"), Decimal("-0"), Decimal("-0.00"), Decimal("1.0"), Decimal("1.00"), Decimal("2.00")]
        objects = [order(model, **{field: value}) for value in values]
        assert len(set(objects)) == len(objects)
        for index, item in enumerate(objects):
            result = store.replace((parent(model),), (item,), synthetic_fixture=True)
            assert changes(result) == ((1, 0, 0, 1, 0, 0) if index == 0 else (0, 0, 0, 0, 1, 0))
            assert observed_order(model, store.current().orders[0]) == observed_order(model, item)

    @pytest.mark.parametrize("field", ["key", *TEXT_FIELDS, *DECIMAL_FIELDS, "state", "qualifiers"])
    def test_every_order_field_must_be_explicit(self, model, field):
        values = order_values(model)
        del values[field]
        with pytest.raises(TypeError):
            model.SyntheticOrder(**values, synthetic_fixture=True)

    @pytest.mark.parametrize("field", ["hold_opd", "patient_name", "resident_id", "dob", "phone", "address", "diagnosis", "notes", "insurance", "credentials", "sql", "raw_rows", "payload", "category", "display_name", "visible", "pacs", "dicom", "mwl", "orthanc", "source_epoch", "revision", "observed_at", "unit", "total_quantity"])
    def test_forbidden_fields_not_accepted_or_retained(self, model, field):
        with pytest.raises(TypeError) as error:
            model.SyntheticOrder(**order_values(model), **{field: "PRIVATE-MARKER"}, synthetic_fixture=True)
        assert "PRIVATE-MARKER" not in str(error.value)
        assert not hasattr(order(model), field)
        with pytest.raises(AttributeError):
            object.__setattr__(order(model), field, "PRIVATE-MARKER")

    @pytest.mark.parametrize("state,dc,act", product(("ACTIVE", "CANCELLED"), ("Y", "N"), ("Y", "N")))
    def test_all_strict_flag_combinations_are_facts_not_interpretation(self, model, state, dc, act):
        item = order(model, state=model.OrderState(state), qualifiers=model.SyntheticOrderQualifiers(model.Flag(dc), model.Flag(act), synthetic_fixture=True))
        assert observed_order(model, item)[-2:] == (state, (dc, act))

    @pytest.mark.parametrize("field", ["dc_yn", "act_yn"])
    @pytest.mark.parametrize("bad", ["Y", "N", "y", "", None, True, 1])
    def test_qualifiers_require_typed_flags(self, model, field, bad):
        values = dict(dc_yn=model.Flag.NO, act_yn=model.Flag.NO)
        values[field] = bad
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_order_qualifiers$"):
            model.SyntheticOrderQualifiers(**values, synthetic_fixture=True)

    @pytest.mark.parametrize("bad", ["ACTIVE", "CANCELLED", "UNKNOWN", None, 1])
    def test_order_state_no_coercion(self, model, bad):
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_order_state$"):
            order(model, state=bad)

    @pytest.mark.parametrize("field,value", [("order_date", "2026-10-10"), ("order_date", datetime(2026, 10, 10)), ("order_number", 1), ("order_sequence", True), ("encounter_id", ""), ("encounter_id", " padded "), ("encounter_id", "x" * 129), ("order_number", "x\n")])
    def test_bad_key(self, model, field, value):
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_order_key$"):
            key(model, **{field: value})

    def test_all_four_key_parts_and_canonical_ordering(self, model):
        keys = [key(model)] + [key(model, **{field: value}) for field, value in (
            ("encounter_id", "synthetic-other"), ("order_date", date(2026, 10, 9)),
            ("order_number", "2"), ("order_sequence", "2"),
        )]
        children = tuple(order(model, key=value) for value in reversed(keys))
        result = collection(model, (parent(model, "synthetic-other"), parent(model)), children)
        assert tuple(item.encounter_id for item in result.encounters) == ("synthetic-other", "synthetic-parent")
        assert tuple(item.key.value for item in result.orders) == tuple(sorted(value.value for value in keys))
        assert len(result.orders) == 5

    def test_parent_scope_no_orders_and_all_children(self, model):
        parents = tuple(parent(model, f"synthetic-{i}", state) for i, state in enumerate(STATES))
        children = tuple(order(model, key=key(model, encounter_id=f"synthetic-{i}"), order_type=kind,
                               state=model.OrderState.CANCELLED if i == 2 else model.OrderState.ACTIVE)
                         for i, kind in ((0, "FEE"), (1, None), (2, "LAB"), (3, "UNCLASSIFIED"), (5, "EXCLUDED")))
        result = collection(model, tuple(reversed(parents)), tuple(reversed(children)))
        assert tuple((p.encounter_id, p.state.value) for p in result.encounters) == tuple((f"synthetic-{i}", s) for i, s in enumerate(STATES[:-1]))
        assert tuple(observed_order(model, o) for o in result.orders) == tuple(observed_order(model, o) for o in children[:-1])
        assert len(result.encounters) == 5 and len(result.orders) == 4

    def test_parent_lifecycle_is_set_replacement_not_event_inference(self, model):
        store, child = memory(model), order(model)
        for state in STATES:
            result = store.replace((parent(model, state=state),), (child,), synthetic_fixture=True)
            if state == "REGISTERED":
                assert changes(result) == (1, 0, 0, 1, 0, 0)
            elif state == "CANCELLED":
                assert changes(result) == (0, 0, 1, 0, 0, 1)
                assert store.current().encounters == store.current().orders == ()
            else:
                assert changes(result) == (0, 1, 0, 0, 0, 0)
        assert changes(store.replace((parent(model),), (child,), synthetic_fixture=True)) == (1, 0, 0, 1, 0, 0)
        assert not hasattr(result, "cancelled_at")

    def test_text_edits_reuse_cancellation_absence_and_return(self, model):
        store, p = memory(model), parent(model)
        store.replace((p,), (order(model),), synthetic_fixture=True)
        for field in TEXT_FIELDS:
            assert changes(store.replace((p,), (order(model, **{field: "Synthetic edit"}),), synthetic_fixture=True)) == (0, 0, 0, 0, 1, 0)
        reused = order(model, catalog_code=None, user_code="REUSED", user_name="Different facts", daily_quantity=None, frequency_count=Decimal("0.5"), day_count=Decimal("1"), state=model.OrderState.CANCELLED)
        assert changes(store.replace((p,), (reused,), synthetic_fixture=True)) == (0, 0, 0, 0, 1, 0)
        assert store.current().orders[0].state.value == "CANCELLED"
        assert changes(store.replace((p,), (), synthetic_fixture=True)) == (0, 0, 0, 0, 0, 1)
        assert store.current().encounters == (p,)
        assert changes(store.replace((p,), (order(model),), synthetic_fixture=True)) == (0, 0, 0, 1, 0, 0)

    @pytest.mark.parametrize("case,reason", [("parents", "duplicate_encounter"), ("orders", "duplicate_order"), ("orphan", "orphan_order"), ("parent_cap", "invalid_row_bound"), ("order_cap", "invalid_row_bound"), ("bad_excluded", "invalid_order_text")])
    def test_invalid_graph_rejects_before_filtering_and_preserves_state(self, model, case, reason):
        store, p, child = memory(model), parent(model), order(model)
        store.replace((p,), (child,), synthetic_fixture=True)
        before = store.current()
        parents, children = (p,), (child,)
        if case == "parents":
            parents = (p, p)
        elif case == "orders":
            children = (child, child)
        elif case == "orphan":
            parents = ()
        elif case == "parent_cap":
            parents = (parent(model, state="CANCELLED"),) * 10001
        elif case == "order_cap":
            children = (child,) * 100001
        else:
            parents = (parent(model, state="CANCELLED"),)
            object.__setattr__(child, "user_name", "PRIVATE\nMARKER")
        with pytest.raises(model.CurrentDayOrdersRejected, match=f"^{reason}$"):
            store.replace(parents, children, synthetic_fixture=True)
        assert store.current() == before

    @pytest.mark.parametrize("outcome", ["FAILED", "PARTIAL", "TIMED_OUT", "UNAVAILABLE", "UNVERIFIED"])
    @pytest.mark.parametrize("populated", [False, True])
    def test_failures_never_become_empty_snapshots(self, model, outcome, populated):
        store = memory(model)
        if populated:
            store.replace((parent(model),), (order(model),), synthetic_fixture=True)
        before = store.current()
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_collection$"):
            store.replace({"outcome": outcome}, (), synthetic_fixture=True)
        assert store.current() == before

    def test_explicit_synthetic_empty_is_distinct_from_unavailable_startup(self, model):
        store = memory(model)
        assert store.current() is None
        assert changes(store.replace((), (), synthetic_fixture=True)) == (0, 0, 0, 0, 0, 0)
        assert store.current() is not None and store.current().orders == ()

    def test_day_types_and_cross_day_comparison(self, model):
        for bad in (datetime(2026, 10, 10), "2026-10-10", None):
            with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_day_context$"):
                context(model, bad)
        with pytest.raises(model.CurrentDayOrdersRejected, match="^day_context_changed$"):
            model.compare_synthetic_collections(collection(model), collection(model, day=date(2026, 10, 11)))

    @pytest.mark.parametrize("permission", [False, None, 1, "yes"])
    def test_literal_synthetic_opt_in(self, model, permission):
        for operation in (
            lambda: model.SyntheticDayContext(DAY, synthetic_fixture=permission),
            lambda: model.SyntheticOrder(**order_values(model), synthetic_fixture=permission),
            lambda: model.SyntheticCollectionMemory(context(model), synthetic_fixture=permission),
            lambda: model.build_synthetic_collection(context(model), (), (), synthetic_fixture=permission),
        ):
            with pytest.raises(model.CurrentDayOrdersRejected, match="^synthetic_fixture_required$"):
                operation()

    def test_inputs_and_inspection_are_detached_and_invalid_mutation_rejected(self, model):
        p, child, store = parent(model), order(model), memory(model)
        store.replace((p,), (child,), synthetic_fixture=True)
        before = store.current()
        object.__setattr__(p, "encounter_id", "PRIVATE")
        object.__setattr__(child.key, "order_number", "PRIVATE")
        object.__setattr__(child, "daily_quantity", 1.25)
        assert store.current() == before
        with pytest.raises(model.CurrentDayOrdersRejected, match="^invalid_exact_decimal$"):
            store.replace((parent(model),), (child,), synthetic_fixture=True)
        assert store.current() == before
        with pytest.raises(FrozenInstanceError):
            before.orders[0].user_name = "PRIVATE"
        inspection = store.current()
        object.__setattr__(inspection.orders[0], "user_name", "PRIVATE")
        assert store.current() == before

    def test_redacted_facts_errors_and_silence(self, model, capsys, caplog):
        p, child = parent(model), order(model)
        result = collection(model, (p,), (child,))
        for value in (context(model), p, child.key, child.qualifiers, child, result, memory(model), model.compare_synthetic_collections(None, result)):
            assert repr(value) == str(value)
            assert "redacted" in repr(value)
            assert "synthetic-parent" not in repr(value)
            assert "SYNTHETIC-CODE" not in repr(value)
            assert "1.250" not in repr(value)
        with pytest.raises(model.CurrentDayOrdersRejected) as error:
            order(model, user_name="PRIVATE\nMARKER")
        assert str(error.value) == "invalid_order_text"
        assert "PRIVATE" not in repr(error.value)
        assert not caplog.records and capsys.readouterr() == ("", "")
