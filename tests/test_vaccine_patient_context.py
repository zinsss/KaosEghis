from types import SimpleNamespace


class _Element:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_value(self) -> str:
        return self._value


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
    assert result.context.patient_name == "Test Patient"
    assert result.context.patient_sex == "M"
    assert result.context.patient_age == "56"
    assert result.context.patient_birth_date == "1970-01-01"
    assert result.context.patient_phone == "010-1111-2222"
    assert clicks == [(209, 155)]
    assert closes == [True]


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
