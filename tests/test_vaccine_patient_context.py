from types import SimpleNamespace


class _Element:
    def __init__(
        self,
        value: str,
        automation_id: str = "",
        *,
        visible: bool = True,
    ) -> None:
        self._value = value
        self.element_info = SimpleNamespace(automation_id=automation_id)
        self._visible = visible

    def get_value(self) -> str:
        return self._value

    def is_visible(self) -> bool:
        return self._visible


class _Specification:
    def __init__(self, element) -> None:
        self._element = element

    def wrapper_object(self):
        if isinstance(self._element, Exception):
            raise self._element
        return self._element


class _Root:
    def __init__(self, handle: int, values: dict[str, str]) -> None:
        self.handle = handle
        self._values = values

    def child_window(self, *, auto_id: str):
        if auto_id not in self._values:
            return _Specification(LookupError(auto_id))
        return _Specification(_Element(self._values[auto_id]))


class _Desktop:
    def __init__(self, main_root: _Root, patient_root: _Root) -> None:
        self._main_root = main_root
        self._patient_root = patient_root

    def window(self, *, handle: int):
        assert handle == self._main_root.handle
        return _Specification(self._main_root)

    def windows(self, *, process: int):
        assert process == 100
        return [self._patient_root]


class _ProcessFamilyDesktop:
    def __init__(self, main_root: _Root, helper_root: _Root) -> None:
        self._main_root = main_root
        self._helper_root = helper_root
        self.process_calls: list[int] = []

    def window(self, *, handle: int):
        assert handle == self._main_root.handle
        return _Specification(self._main_root)

    def windows(self, *, process: int):
        self.process_calls.append(process)
        if process == 100:
            return [self._main_root]
        if process == 200:
            return [self._helper_root]
        return []


class _LegacyValueChartElement:
    def __init__(self, patient_root, value: str, parent_scope=None) -> None:
        self._patient_root = patient_root
        self._value = value
        self._parent_scope = parent_scope
        self.value_reads = 0

    def top_level_parent(self):
        return self._patient_root

    def parent(self):
        return self._parent_scope

    def legacy_properties(self) -> dict[str, str]:
        self.value_reads += 1
        return {"Value": self._value if self.value_reads == 1 else ""}


class _WrapperRoot:
    """Model the API exposed by a real pywinauto UIAWrapper."""

    def __init__(self, handle: int, values: dict[str, str]) -> None:
        self.handle = handle
        self.element_info = SimpleNamespace(automation_id="")
        self._elements = [
            _Element(value, automation_id)
            for automation_id, value in values.items()
        ]
        self.descendant_calls = 0

    def descendants(self):
        self.descendant_calls += 1
        return list(self._elements)


TARGET_IDS = {
    "chart_no": "txtPatientNo",
    "resident_id": "txtResidentNo",
    "patient_name": "txtPatientName",
    "sex_age": "lblSexAge",
    "birth_date": "dateBirth",
    "mobile_phone": "txtMobile",
    "telephone": "txtTelephone",
    "address": "txtAddress",
}


def _ready_state():
    return SimpleNamespace(
        status="green",
        pid=100,
        main_window_handle=1,
        window_handle=1,
    )


def test_fetch_opens_patient_info_and_reads_all_fields() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    clicks: list[tuple[int, int]] = []
    closes: list[bool] = []
    desktop = _Desktop(
        _Root(1, {}),
        _Root(
            2,
            {
                "txtPatientNo": "1170",
                "txtResidentNo": "700101-1234567",
                "txtPatientName": "Test Patient",
                "lblSexAge": "M / 56 years",
                "dateBirth": "1970-01-01",
                "txtMobile": "010-1111-2222",
                "txtTelephone": "054-000-0000",
                "txtAddress": "Test address",
            },
        ),
    )

    result = fetch_vaccine_patient_context(
        {},
        TARGET_IDS,
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        clicker=clicks.append,
        closer=lambda: closes.append(True),
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert result.context.resident_id == "700101-1234567"
    assert result.context.patient_name == "Test Patient"
    assert result.context.patient_sex == "M"
    assert result.context.patient_age == "56"
    assert result.context.patient_birth_date == "1970-01-01"
    assert result.context.patient_phone == "010-1111-2222"
    assert clicks == [(210, 115)]
    assert closes == [True]


def test_resident_id_formatting_preserves_label_and_normalizes_system_input() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        resident_id_for_label,
        resident_id_for_vaccine_system,
    )

    captured = " 700101-1234567 "

    assert resident_id_for_label(captured) == "700101-1234567"
    assert resident_id_for_vaccine_system(captured) == "7001011234567"
    assert captured == " 700101-1234567 "


def test_fetch_uses_real_uia_wrapper_descendants_once_for_all_fields() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    main_root = _WrapperRoot(1, {})
    patient_root = _WrapperRoot(
        2,
        {
            "txtPatientNo": "1170",
            "txtResidentNo": "700101-1234567",
            "txtPatientName": "Test Patient",
            "lblSexAge": "M / 56",
            "dateBirth": "1970-01-01",
            "txtMobile": "010-1111-2222",
            "txtTelephone": "",
            "txtAddress": "Test address",
        },
    )
    desktop = _Desktop(main_root, patient_root)

    result = fetch_vaccine_patient_context(
        {},
        TARGET_IDS,
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        clicker=lambda _coords: None,
        closer=lambda: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert result.context.resident_id == "700101-1234567"
    # One scan verifies readiness and one scan indexes every configured field.
    assert patient_root.descendant_calls == 2


def test_fetch_prefers_unique_visible_chart_target_over_hidden_duplicate() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    class DuplicateChartRoot(_WrapperRoot):
        def __init__(self) -> None:
            super().__init__(
                2,
                {
                    "txtPatientNo": "1170",
                    "txtPatientName": "Test Patient",
                },
            )
            self._elements.insert(
                0,
                _Element(
                    "stale-hidden-value",
                    "txtPatientNo",
                    visible=False,
                ),
            )

    desktop = _Desktop(_WrapperRoot(1, {}), DuplicateChartRoot())

    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo", "patient_name": "txtPatientName"},
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        clicker=lambda _coords: None,
        closer=lambda: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert result.context.patient_name == "Test Patient"


def test_fetch_searches_verified_eghis_child_process_for_patient_window() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    desktop = _ProcessFamilyDesktop(
        _Root(1, {}),
        _Root(
            2,
            {
                "txtPatientNo": "1170",
                "txtPatientName": "Test Patient",
            },
        ),
    )

    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo", "patient_name": "txtPatientName"},
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        process_family_provider=lambda _root_pid: (100, 200),
        clicker=lambda _coords: None,
        closer=lambda: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert desktop.process_calls == [100, 200]


def test_fetch_refreshes_process_family_until_new_helper_appears() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    desktop = _ProcessFamilyDesktop(
        _Root(1, {}),
        _Root(2, {"txtPatientNo": "1170"}),
    )
    process_family_calls: list[int] = []

    def process_family_provider(root_pid: int) -> tuple[int, ...]:
        process_family_calls.append(root_pid)
        return (100,) if len(process_family_calls) == 1 else (100, 200)

    ticks = iter((0.0, 0.0, 0.1))
    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo"},
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        process_family_provider=process_family_provider,
        process_target_finder=lambda _automation_id, _process_ids: None,
        clicker=lambda _coords: None,
        closer=lambda: None,
        clock=lambda: next(ticks),
        sleeper=lambda _seconds: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert process_family_calls == [100, 100]
    assert desktop.process_calls == [100, 100, 200]


def test_fetch_uses_exact_process_scoped_edit_when_window_enumeration_misses_it() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    patient_root = _WrapperRoot(
        2,
        {
            "txtPatientName": "Test Patient",
        },
    )
    patient_root.element_info.name = "환자 기초 정보"
    desktop = _ProcessFamilyDesktop(_WrapperRoot(1, {}), _WrapperRoot(2, {}))
    finder_calls: list[tuple[str, tuple[int, ...]]] = []

    def find_exact_edit(automation_id: str, process_ids: tuple[int, ...]):
        finder_calls.append((automation_id, process_ids))
        return _LegacyValueChartElement(
            _WrapperRoot(3, {}),
            "829",
            parent_scope=patient_root,
        )

    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo", "patient_name": "txtPatientName"},
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        process_family_provider=lambda _root_pid: (100, 200),
        process_target_finder=find_exact_edit,
        clicker=lambda _coords: None,
        closer=lambda: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "829"
    assert result.context.patient_name == "Test Patient"
    assert finder_calls == [("txtPatientNo", (100, 200))]


def test_process_family_accepts_only_eghis_named_descendants(monkeypatch) -> None:
    from KaosEghis.core import vaccine_patient_context

    class Child:
        def __init__(self, pid: int, name: str) -> None:
            self.pid = pid
            self._name = name

        def name(self) -> str:
            return self._name

    class RootProcess:
        def children(self, *, recursive: bool):
            assert recursive is True
            return [
                Child(200, "eGhis.Forms.exe"),
                Child(201, "eGhis.Chart.Interaction.exe"),
                Child(202, "chrome.exe"),
            ]

    monkeypatch.setattr(
        "psutil.Process",
        lambda pid: RootProcess() if pid == 100 else None,
    )

    assert vaccine_patient_context._trusted_eghis_process_ids(100) == (
        100,
        200,
        201,
    )


def test_fetch_rejects_multiple_visible_chart_targets() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    class AmbiguousChartRoot(_WrapperRoot):
        def __init__(self) -> None:
            super().__init__(2, {"txtPatientNo": "1170"})
            self._elements.append(_Element("2200", "txtPatientNo", visible=True))

    ticks = iter((0.0, 0.0, 1.0))
    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo"},
        timeout_seconds=0.1,
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: _Desktop(
            _WrapperRoot(1, {}),
            AmbiguousChartRoot(),
        ),
        clicker=lambda _coords: None,
        closer=lambda: None,
        clock=lambda: next(ticks),
        sleeper=lambda _seconds: None,
    )

    assert result.success is False
    assert "chart-number target was not found" in result.message


def test_fetch_uses_telephone_when_mobile_is_blank() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    desktop = _Desktop(
        _Root(1, {}),
        _Root(
            2,
            {
                "txtPatientNo": "1170",
                "txtResidentNo": "",
                "txtPatientName": "Test Patient",
                "lblSexAge": "F / 40",
                "dateBirth": "1986-01-01",
                "txtMobile": "",
                "txtTelephone": "054-000-0000",
                "txtAddress": "Test address",
            },
        ),
    )

    result = fetch_vaccine_patient_context(
        {},
        TARGET_IDS,
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        clicker=lambda _coords: None,
        closer=lambda: None,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.patient_phone == "054-000-0000"


def test_fetch_does_not_click_when_emr_is_not_connected() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    clicks: list[tuple[int, int]] = []
    result = fetch_vaccine_patient_context(
        {},
        TARGET_IDS,
        connection_checker=lambda _settings: SimpleNamespace(status="red", pid=None),
        clicker=clicks.append,
    )

    assert result.success is False
    assert result.message == "EMR connection is not ready. Reconnect EMR and retry."
    assert clicks == []


def test_fetch_rejects_missing_chart_target_without_clicking() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    clicks: list[tuple[int, int]] = []
    result = fetch_vaccine_patient_context(
        {},
        {},
        connection_checker=lambda _settings: _ready_state(),
        clicker=clicks.append,
    )

    assert result.success is False
    assert result.message == "Vaccine patient chart target is not configured."
    assert clicks == []


def test_fetch_keeps_context_when_escape_close_fails() -> None:
    from KaosEghis.core.vaccine_patient_context import (
        fetch_vaccine_patient_context,
    )

    desktop = _Desktop(
        _Root(1, {}),
        _Root(2, {"txtPatientNo": "1170"}),
    )

    def fail_close() -> None:
        raise RuntimeError("keyboard unavailable")

    result = fetch_vaccine_patient_context(
        {},
        {"chart_no": "txtPatientNo"},
        connection_checker=lambda _settings: _ready_state(),
        desktop_factory=lambda **_kwargs: desktop,
        clicker=lambda _coords: None,
        closer=fail_close,
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.chart_no == "1170"
    assert "Close the Patient Information window manually." in result.message
