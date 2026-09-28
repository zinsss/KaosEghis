from types import SimpleNamespace

import pytest

from KaosEghis.core import vaccine_patient_context as patient
from KaosEghis.core import vaccine_patient_control_cache as cache


SELECTORS = {
    "chart_no": "chart", "patient_name": "name", "resident_id": "resident",
    "mobile_phone": "mobile", "sex_age": "lblSexAge",
}


class Control:
    def __init__(self, handle, automation_id, value="", *, parent=None, kind="Edit"):
        self.handle = handle
        self.value = value
        self.owner = parent
        self.visible = True
        self.cache_strategies = []
        self.on_read = lambda: None
        self.element_info = SimpleNamespace(
            handle=handle, automation_id=automation_id, process_id=100,
            runtime_id=(42, handle, 1), control_type=kind, name="",
            set_cache_strategy=self.cache_strategies.append,
        )

    def get_value(self):
        self.on_read()
        return self.value

    def is_visible(self):
        return self.visible

    def parent(self):
        return self.owner


class Scope(Control):
    def __init__(self, handle):
        super().__init__(handle, "patient_scope", kind="Pane")
        self.controls = []
        self.searches = 0

    def descendants(self):
        self.searches += 1
        return list(self.controls)


@pytest.fixture
def emr(monkeypatch):
    patient.clear_cached_patient_information_scopes()
    main, scope = Scope(1), Scope(2)
    controls = {
        "chart": Control(10, "chart", "1170", parent=scope),
        "name": Control(11, "name", "First Test Patient", parent=scope),
        "resident": Control(12, "resident", "700101-1234567", parent=scope),
        "mobile": Control(13, "mobile", "010-1111-2222", parent=scope),
        "txtSexAge": Control(14, "txtSexAge", "M/56", parent=scope),
    }
    scope.controls = list(controls.values())
    state = SimpleNamespace(
        main=main, scope=scope, controls=controls, pid=100, root_handle=1,
        lifetimes={100: 1.0}, windows_calls=0, handle_reads=[], closes=0, clicks=0, clock=0.0,
    )
    state.handles = {control.handle: control for control in [main, scope, *scope.controls]}

    def window(*, handle):
        state.handle_reads.append(handle)
        return SimpleNamespace(wrapper_object=lambda: state.handles[handle])

    def windows(**_kwargs):
        state.windows_calls += 1
        return [state.scope]

    state.desktop = SimpleNamespace(window=window, windows=windows)

    def belongs(handle, scope_handle):
        element = state.handles.get(handle)
        owner = state.handles.get(scope_handle)
        return element is not None and owner is not None and (element is owner or element.owner is owner)

    monkeypatch.setattr(cache, "_belongs_to_scope", belongs)
    monkeypatch.setattr(cache, "_process_lifetimes", lambda pids: tuple(
        (pid, state.lifetimes[pid]) for pid in sorted(set(pids))
    ))

    def fetch(selectors=None):
        def click(_coords):
            state.clicks += 1

        def close():
            state.closes += 1

        return patient.fetch_vaccine_patient_context(
            {}, SELECTORS if selectors is None else selectors,
            connection_checker=lambda _settings: SimpleNamespace(
                status="green", pid=state.pid, window_handle=state.root_handle, main_window_handle=1,
            ),
            desktop_factory=lambda **_kwargs: state.desktop,
            process_family_provider=lambda pid: (pid,),
            clicker=click, closer=close, timeout_seconds=0.25,
            clock=lambda: state.clock,
            sleeper=lambda seconds: setattr(state, "clock", state.clock + seconds),
        )

    state.fetch = fetch
    yield state
    patient.clear_cached_patient_information_scopes()


def test_first_fetch_builds_cache_and_second_reads_fresh_values_without_tree_search(emr):
    assert patient._PATIENT_INFORMATION_SCOPE_CACHE == {}
    assert emr.clicks == 0
    first = emr.fetch()
    assert first.success
    assert emr.scope.searches == 2
    assert emr.windows_calls == 1
    entry = patient._PATIENT_INFORMATION_SCOPE_CACHE[(100, "chart")]
    assert entry.controls is not None
    assert "First Test Patient" not in repr(entry)
    assert "700101-1234567" not in repr(entry)

    emr.controls["chart"].value = "2200"
    emr.controls["name"].value = "Second Test Patient"
    emr.controls["resident"].value = "800101-2234567"
    emr.controls["mobile"].value = ""
    emr.controls["txtSexAge"].value = "F/46"
    second = emr.fetch()
    assert second.success
    assert second.context.chart_no == "2200"
    assert second.context.patient_name == "Second Test Patient"
    assert second.context.resident_id == "800101-2234567"
    assert second.context.patient_phone == ""
    assert second.context.patient_sex == "F"
    assert second.context.patient_age == "46"
    assert emr.scope.searches == 2
    assert emr.windows_calls == 1
    assert emr.clicks == emr.closes == 2
    assert all(control.cache_strategies and not any(control.cache_strategies)
               for control in emr.scope.controls)


@pytest.mark.parametrize("replacement", ["new_handle", "reused_handle", "hidden_old", "detached_old"])
def test_recreated_field_is_rediscovered_and_replaces_cache(emr, replacement):
    assert emr.fetch().success
    old = emr.controls["name"]
    handle = old.handle if replacement == "reused_handle" else 21
    new = Control(handle, "name", "Replacement Test Patient", parent=emr.scope)
    new.element_info.runtime_id = (42, handle, 2)
    emr.scope.controls.remove(old)
    emr.scope.controls.append(new)
    emr.handles[new.handle] = new
    if replacement == "new_handle":
        del emr.handles[old.handle]
    elif replacement == "hidden_old":
        old.visible = False
    elif replacement == "detached_old":
        old.owner = emr.main
    result = emr.fetch()
    assert result.success
    assert result.context.patient_name == "Replacement Test Patient"
    searches = emr.scope.searches
    assert searches > 2
    assert emr.fetch().context.patient_name == "Replacement Test Patient"
    assert emr.scope.searches == searches


@pytest.mark.parametrize("reuse_handle", [False, True])
def test_recreated_popup_is_rediscovered(emr, reuse_handle):
    assert emr.fetch().success
    old = emr.scope
    new = Scope(old.handle if reuse_handle else 3)
    new.element_info.runtime_id = (42, new.handle, 2)
    new.controls = old.controls
    for control in new.controls:
        control.owner = new
    del emr.handles[old.handle]
    emr.handles[new.handle] = new
    emr.scope = new
    result = emr.fetch()
    assert result.success
    assert new.searches == 2
    assert patient._PATIENT_INFORMATION_SCOPE_CACHE[(100, "chart")].scope_handle == new.handle
    assert emr.fetch().success
    assert new.searches == 2


@pytest.mark.parametrize("change", ["pid", "process_lifetime", "scope_process", "runtime_id", "automation_id", "control_type"])
def test_identity_change_invalidates_control_cache(emr, change):
    assert emr.fetch().success
    if change == "pid":
        emr.pid = 200
        emr.lifetimes[200] = 2.0
    elif change == "process_lifetime":
        emr.lifetimes[100] = 2.0
    elif change == "scope_process":
        emr.scope.element_info.process_id = 200
        emr.lifetimes[200] = 2.0
        for control in emr.scope.controls:
            control.element_info.process_id = 200
    else:
        info = emr.controls["name"].element_info
        if change == "runtime_id":
            info.runtime_id = (42, 11, 3)
        elif change == "automation_id":
            info.automation_id = "obsolete"
        else:
            info.control_type = "Text"
    assert emr.fetch().success
    assert emr.scope.searches > 2
    if change == "pid":
        assert (100, "chart") not in patient._PATIENT_INFORMATION_SCOPE_CACHE


def test_changed_target_settings_rebuild_cache(emr):
    assert emr.fetch().success
    emr.controls["name"].element_info.automation_id = "new_name"
    changed = {**SELECTORS, "patient_name": "new_name"}
    result = emr.fetch(changed)
    assert result.success
    assert result.context.patient_name == "First Test Patient"
    assert emr.scope.searches == 4
    assert emr.fetch(changed).success
    assert emr.scope.searches == 4


def test_missing_control_is_not_negatively_cached(emr):
    missing = emr.controls["name"]
    emr.scope.controls.remove(missing)
    assert "patient_name" in emr.fetch().missing_fields
    emr.scope.controls.append(missing)
    result = emr.fetch()
    assert result.context.patient_name == "First Test Patient"
    assert emr.scope.searches == 3
    assert emr.fetch().success
    assert emr.scope.searches == 3


@pytest.mark.parametrize("warm", [False, True])
def test_patient_switch_during_read_rejects_mixed_context_and_drops_cache(emr, warm):
    if warm:
        assert emr.fetch().success
    emr.controls["name"].on_read = lambda: setattr(emr.controls["chart"], "value", "2200")
    result = emr.fetch()
    assert not result.success
    assert result.context is None
    assert "Patient changed" in result.message
    assert patient._PATIENT_INFORMATION_SCOPE_CACHE == {}
    assert emr.closes == (2 if warm else 1)


def test_cleared_chart_never_reuses_previous_patient_value(emr):
    assert emr.fetch().success
    emr.controls["chart"].value = ""
    result = emr.fetch()
    assert not result.success
    assert result.context is None
    assert patient._PATIENT_INFORMATION_SCOPE_CACHE == {}


def test_handleless_scope_keeps_existing_search_path(emr):
    emr.scope.element_info.handle = 0
    assert emr.fetch().success
    assert patient._PATIENT_INFORMATION_SCOPE_CACHE[(100, "chart")].controls is None
    assert emr.fetch().success
    assert emr.scope.searches == 4


def test_handleless_field_is_searched_again_but_other_fields_are_cached(emr):
    emr.controls["name"].element_info.handle = 0
    assert emr.fetch().success
    entry = patient._PATIENT_INFORMATION_SCOPE_CACHE[(100, "chart")]
    assert "name" not in dict(entry.controls.controls)
    assert emr.fetch().context.patient_name == "First Test Patient"
    assert emr.scope.searches == 3


@pytest.mark.parametrize("change", ["hidden_scope", "invalid_properties", "root_handle", "process_unavailable"])
def test_unverifiable_cache_is_rejected(emr, change):
    assert emr.fetch().success
    entry = patient._PATIENT_INFORMATION_SCOPE_CACHE[(100, "chart")].controls
    if change == "hidden_scope":
        emr.scope.visible = False
    elif change == "invalid_properties":
        emr.controls["name"].element_info.runtime_id = None
    elif change == "root_handle":
        emr.root_handle = 99
    else:
        del emr.lifetimes[100]
    assert entry.resolve(
        emr.desktop, emr.pid, emr.root_handle,
        {key: patient._field_automation_id_candidates(key, value) for key, value in SELECTORS.items()},
    ) is None
