from types import SimpleNamespace
import sys

import pytest

from KaosEghis.core import eghis_connector, uia_inspector, vaccine_patient_context, wait_engine
from KaosEghis.db.repositories import UiTargetRecord


def _target(**changes):
    fields = dict(
        id=1, target_id="test.field", parent_target_id=None, parent_automation_id=None,
        automation_id=None, name="wanted", control_type="Edit", class_name=None,
        created_at="now",
    )
    fields.update(changes)
    return UiTargetRecord(**fields)


def test_handleless_grid_does_not_trigger_win32_fallback(monkeypatch):
    calls = []
    element = SimpleNamespace(handle=0)
    monkeypatch.setattr(eghis_connector, "_CACHED_GRID_ELEMENTS", {})

    def resolve(scope, backend, automation_id):
        calls.append(backend)
        eghis_connector._remember_cached_grid_element(scope, automation_id, element)
        return None

    monkeypatch.setattr(eghis_connector, "_resolve_cached_grid_handle_for_backend", resolve)
    assert eghis_connector._resolve_cached_grid_handle(77, "grid") is None
    assert calls == ["uia"]
    assert eghis_connector._cached_grid_element_for_scope(77, "grid") is element


def test_missing_grid_still_tries_win32(monkeypatch):
    calls = []
    monkeypatch.setattr(eghis_connector, "_CACHED_GRID_ELEMENTS", {})

    def resolve(_scope, backend, _automation_id):
        calls.append(backend)
        return 88 if backend == "win32" else None

    monkeypatch.setattr(eghis_connector, "_resolve_cached_grid_handle_for_backend", resolve)
    assert eghis_connector._resolve_cached_grid_handle(77, "grid") == 88
    assert calls == ["uia", "win32"]


def test_grid_parent_is_enumerated_only_once():
    element = SimpleNamespace(element_info=SimpleNamespace(
        automation_id="", name="wanted", control_type="Edit", class_name="",
    ))

    class Parent:
        calls = 0

        def children(self):
            return []

        def descendants(self):
            self.calls += 1
            return [element]

    parent = Parent()
    found, parent_found, _message = uia_inspector._resolve_target_inside_parent_scope(
        parent, _target(), scope_description="test", ancestor_path=None,
        parent_anchor_name=None,
    )
    assert found is element
    assert parent_found is True
    assert parent.calls == 1


def test_exact_uia_child_lookup_does_not_enumerate_python_descendants(monkeypatch):
    scope = SimpleNamespace(element_info=SimpleNamespace(_get_elements=lambda: None))
    expected = object()
    calls = []

    def find(ids, **kwargs):
        calls.append((ids, kwargs))
        return {"field": [expected]}

    monkeypatch.setattr(uia_inspector, "find_uia_elements_by_automation_ids", find)
    assert uia_inspector._quick_child_wrapper(scope, auto_id="field") is expected
    assert calls == [(("field",), {"root_element": scope})]


@pytest.mark.parametrize("matches", [[], [object(), object()]])
def test_exact_uia_child_lookup_rejects_missing_or_ambiguous(monkeypatch, matches):
    scope = SimpleNamespace(element_info=SimpleNamespace(_get_elements=lambda: None))
    monkeypatch.setattr(
        uia_inspector, "find_uia_elements_by_automation_ids", lambda *_a, **_k: {"field": matches},
    )
    with pytest.raises(LookupError):
        uia_inspector._quick_child_wrapper(scope, auto_id="field")


@pytest.mark.parametrize("condition, method", [
    ("keyboard_focus", "has_keyboard_focus"), ("visible", "is_visible"),
    ("enabled", "is_enabled"), ("exists", None), ("text_non_empty", "get_value"),
])
def test_resolved_wait_reads_only_required_property(condition, method):
    calls = []

    class Element:
        def __getattr__(self, name):
            calls.append(name)
            if name == method:
                return lambda: "ready" if name == "get_value" else True
            raise AttributeError(name)

    result = wait_engine.wait_for_target_condition(
        {}, _target(), condition, timeout_ms=0, resolved_element=Element(),
    )
    assert result.success
    if condition != "text_non_empty":
        assert calls == ([] if method is None else [method])
    else:
        assert "has_keyboard_focus" not in calls
        assert "is_enabled" not in calls
        assert "is_visible" not in calls


def test_readiness_still_waits_for_actual_focus():
    element = SimpleNamespace(has_keyboard_focus=lambda: False)
    result = wait_engine.wait_for_target_condition(
        {}, _target(), "keyboard_focus", timeout_ms=0, resolved_element=element,
    )
    assert not result.success
    assert "Timed out" in result.message


def test_native_window_filter_ignores_other_apps_hidden_and_closed_windows(monkeypatch):
    windows = (11, 22, 33, 44, 55)

    def owner(handle):
        if handle == 55:
            raise RuntimeError("closed")
        return 1, {11: 100, 22: 200, 33: 300, 44: 100}[handle]

    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        EnumWindows=lambda callback, context: [callback(h, context) for h in windows],
        IsWindowVisible=lambda h: h != 44,
    ))
    monkeypatch.setitem(sys.modules, "win32process", SimpleNamespace(GetWindowThreadProcessId=owner))
    assert vaccine_patient_context._visible_process_window_handles((100, 200)) == (11, 22)


def test_fetch_native_query_is_scoped_to_each_trusted_window(monkeypatch):
    monkeypatch.setattr(
        vaccine_patient_context, "_visible_process_window_handles", lambda _pids: (11, 22),
    )
    calls = []
    element = SimpleNamespace(
        handle=88, is_visible=lambda: True, get_value=lambda: "1234", parent=lambda: None,
    )

    def find(ids, **kwargs):
        calls.append((ids, kwargs))
        return {"chart": [element] if kwargs["root_handle"] == 22 else []}

    monkeypatch.setattr(vaccine_patient_context, "find_uia_elements_by_automation_ids", find)
    result = vaccine_patient_context._find_exact_uia_edit_in_processes("chart", (100, 200))
    assert result.element is element
    assert calls == [
        (("chart",), {"root_handle": h, "process_ids": (100, 200), "control_type": "Edit"})
        for h in (11, 22)
    ]


def test_fetch_does_not_query_desktop_when_no_trusted_window_exists(monkeypatch):
    monkeypatch.setattr(
        vaccine_patient_context, "_visible_process_window_handles", lambda _pids: (),
    )
    calls = []
    monkeypatch.setattr(
        vaccine_patient_context, "find_uia_elements_by_automation_ids",
        lambda *_a, **_k: calls.append(True),
    )
    assert vaccine_patient_context._find_exact_uia_edit_in_processes("chart", (100,)) is None
    assert not calls


def test_fetch_keeps_ambiguity_checks_across_trusted_windows(monkeypatch):
    monkeypatch.setattr(
        vaccine_patient_context, "_visible_process_window_handles", lambda _pids: (11, 22),
    )

    def find(_ids, **kwargs):
        return {"chart": [SimpleNamespace(
            handle=kwargs["root_handle"], is_visible=lambda: True, get_value=lambda: "1234",
            parent=lambda: None,
        )]}

    monkeypatch.setattr(vaccine_patient_context, "find_uia_elements_by_automation_ids", find)
    assert vaccine_patient_context._find_exact_uia_edit_in_processes("chart", (100, 200)) is None


def test_timing_probe_records_only_counts_not_values():
    from KaosEghis.tools.measure_emr_uia import TARGET_IDS, measure_window

    class Element:
        def __getattr__(self, name):
            raise AssertionError("Timing probe must not read control properties")

    def find(ids, **kwargs):
        assert ids == TARGET_IDS
        assert kwargs == {"root_handle": 77, "process_ids": (100,)}
        return {ids[0]: [Element()], "unrequested_sensitive_text": [Element()]}

    result = measure_window(77, 100, find)
    assert set(result) == {"window_handle", "process_id", "lookup_ms", "counts"}
    assert set(result["counts"]) == set(TARGET_IDS)
    assert result["counts"][TARGET_IDS[0]] == 1


def test_patient_timing_probe_uses_cache_without_reading_patient_text(monkeypatch):
    from KaosEghis.tools.measure_emr_uia import CHART_ID, PATIENT_IDS, measure_patient_window
    from KaosEghis.core import vaccine_patient_control_cache

    class Control:
        def is_visible(self):
            return True

        def __getattr__(self, _name):
            raise AssertionError("Probe must not read patient text")

    chart, scope = Control(), Control()
    controls = {key: Control() for key in PATIENT_IDS}
    controls[CHART_ID] = chart
    cache_calls = []

    class Cache:
        @staticmethod
        def create(pid, handle, actual_scope, elements, selectors):
            assert (pid, handle, actual_scope) == (100, 77, scope)
            assert elements == controls
            assert selectors["chart_no"] == (CHART_ID,)
            cache_calls.append("create")
            return Cache()

        def resolve(self, _desktop, pid, handle, _selectors):
            assert (pid, handle) == (100, 77)
            cache_calls.append("resolve")
            return scope, controls

    monkeypatch.setattr(vaccine_patient_control_cache, "PatientControlCache", Cache)
    monkeypatch.setattr(vaccine_patient_context, "_nearest_patient_information_scope", lambda c: scope)
    monkeypatch.setattr("pywinauto.Desktop", lambda **_kwargs: object())

    def find(ids, **kwargs):
        assert kwargs["process_ids"] == (100,)
        assert kwargs.get("root_handle") == 77 or kwargs.get("root_element") is scope
        return {key: [controls[key]] for key in ids}

    result = measure_patient_window(77, 100, find)
    assert result["patient_scope"] == "unique"
    assert cache_calls == ["create", "resolve", "resolve", "resolve"]
    assert all(sample["cache_valid"] for sample in result["samples"])
    assert all(sample["cached_control_count"] == len(PATIENT_IDS) for sample in result["samples"])


@pytest.mark.parametrize("count", [0, 2])
def test_patient_timing_probe_rejects_missing_or_ambiguous_scope(monkeypatch, count):
    from KaosEghis.tools.measure_emr_uia import CHART_ID, measure_patient_window
    monkeypatch.setattr(vaccine_patient_context, "_nearest_patient_information_scope", lambda _c: object())
    chart = SimpleNamespace(is_visible=lambda: True)
    result = measure_patient_window(77, 100, lambda *_a, **_k: {CHART_ID: [chart] * count})
    assert result["patient_scope"] == "missing_or_ambiguous"
    assert "samples" not in result
