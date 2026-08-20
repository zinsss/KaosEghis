import json
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _schedule(*, enabled=True, cap=100, allow_exception=False):
    return {
        "program_enabled": enabled,
        "allow_elderly_exception": allow_exception,
        "elderly_75_plus_start": "2026-10-11",
        "elderly_70_74_start": "2026-10-15",
        "elderly_65_69_start": "2026-10-18",
        "elderly_program_end": "2027-04-30",
        "child_two_dose_start": "2026-09-20",
        "child_two_dose_end": "2027-04-30",
        "child_one_dose_start": "2026-10-05",
        "child_one_dose_end": "2027-04-30",
        "daily_cap": cap,
    }


def _age_groups():
    return [
        {
            "key": "elderly_75_plus",
            "label": "Elderly 75+",
            "vaccine": "influenza",
            "birth_date_from": "19000101",
            "birth_date_to": "19511231",
        },
        {
            "key": "elderly_70_74",
            "label": "Elderly 70-74",
            "vaccine": "influenza",
            "birth_date_from": "19520101",
            "birth_date_to": "19561231",
        },
        {
            "key": "elderly_65_69",
            "label": "Elderly 65-69",
            "vaccine": "influenza",
            "birth_date_from": "19570101",
            "birth_date_to": "19611231",
        },
    ]


def _settings(*, enabled=True, cap=100, allow_exception=False):
    return {
        "vaccine_schedule_rules_json": json.dumps(
            {
                "influenza": _schedule(
                    enabled=enabled,
                    cap=cap,
                    allow_exception=allow_exception,
                )
            }
        ),
        "vaccine_age_groups_json": json.dumps(_age_groups()),
    }


def test_resident_id_birth_date_is_extracted_without_retaining_id() -> None:
    from KaosEghis.core.vaccine_eligibility import birth_date_from_resident_id

    assert birth_date_from_resident_id("500101-1234567") == date(1950, 1, 1)
    assert birth_date_from_resident_id("010101-3123456") == date(2001, 1, 1)
    assert birth_date_from_resident_id("not-a-resident-id") is None


def test_influenza_gate_includes_exact_birth_and_schedule_boundaries() -> None:
    from KaosEghis.core.vaccine_eligibility import (
        evaluate_influenza_program_for_birth_date,
    )

    start = evaluate_influenza_program_for_birth_date(
        _schedule(),
        _age_groups(),
        date(1951, 12, 31),
        on_date=date(2026, 10, 11),
        counted_today=99,
    )
    end = evaluate_influenza_program_for_birth_date(
        _schedule(),
        _age_groups(),
        date(1900, 1, 1),
        on_date=date(2027, 4, 30),
        counted_today=0,
    )

    assert start.allowed is True
    assert start.group_key == "elderly_75_plus"
    assert start.remaining == 1
    assert end.allowed is True


def test_influenza_gate_blocks_before_group_window_and_after_end() -> None:
    from KaosEghis.core.vaccine_eligibility import (
        evaluate_influenza_program_for_birth_date,
    )

    before = evaluate_influenza_program_for_birth_date(
        _schedule(),
        _age_groups(),
        date(1953, 1, 1),
        on_date=date(2026, 10, 14),
    )
    after = evaluate_influenza_program_for_birth_date(
        _schedule(),
        _age_groups(),
        date(1950, 1, 1),
        on_date=date(2027, 5, 1),
    )

    assert before.status == "blocked"
    assert after.status == "blocked"


def test_influenza_exception_requires_explicit_operator_review() -> None:
    from KaosEghis.core.vaccine_eligibility import (
        evaluate_influenza_program_for_birth_date,
    )

    result = evaluate_influenza_program_for_birth_date(
        _schedule(allow_exception=True),
        _age_groups(),
        date(1953, 1, 1),
        on_date=date(2026, 10, 12),
    )

    assert result.status == "review_required"
    assert result.allowed is False
    assert result.counted is False
    assert result.requires_operator_confirmation is True


def test_influenza_gate_blocks_at_daily_cap() -> None:
    from KaosEghis.core.vaccine_eligibility import (
        evaluate_influenza_program_for_birth_date,
    )

    result = evaluate_influenza_program_for_birth_date(
        _schedule(cap=100),
        _age_groups(),
        date(1950, 1, 1),
        on_date=date(2026, 10, 20),
        counted_today=100,
    )

    assert result.status == "cap_reached"
    assert result.allowed is False
    assert result.remaining == 0


def test_influenza_program_is_disabled_until_configuration_review() -> None:
    from KaosEghis.core.vaccine_eligibility import evaluate_influenza_program

    result = evaluate_influenza_program(
        _settings(enabled=False),
        "500101-1234567",
        on_date=date(2026, 10, 20),
    )

    assert result.status == "configuration_required"
    assert result.allowed is False


def test_invalid_influenza_cap_blocks_as_configuration_error() -> None:
    from KaosEghis.core.vaccine_eligibility import evaluate_influenza_program

    settings = _settings()
    payload = json.loads(settings["vaccine_schedule_rules_json"])
    payload["influenza"]["daily_cap"] = "invalid"
    settings["vaccine_schedule_rules_json"] = json.dumps(payload)

    result = evaluate_influenza_program(
        settings,
        "500101-1234567",
        on_date=date(2026, 10, 20),
    )

    assert result.status == "configuration_error"
    assert result.allowed is False


def test_overlapping_child_schedules_require_dose_selection() -> None:
    from KaosEghis.core.vaccine_eligibility import (
        evaluate_influenza_program_for_birth_date,
    )

    child_groups = [
        {
            "key": key,
            "label": label,
            "vaccine": "influenza",
            "birth_date_from": "20200101",
            "birth_date_to": "20260831",
        }
        for key, label in (
            ("child_two_dose", "Child two-dose"),
            ("child_one_dose", "Child one-dose"),
        )
    ]
    result = evaluate_influenza_program_for_birth_date(
        _schedule(),
        child_groups,
        date(2022, 1, 1),
        on_date=date(2026, 10, 20),
    )

    assert result.status == "review_required"
    assert "one-dose or two-dose" in result.message


def test_vaccine_page_can_preview_configured_influenza_gate(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    schedule = _schedule()
    schedule["elderly_75_plus_start"] = "2000-01-01"
    schedule["elderly_program_end"] = "2100-12-31"
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "vaccine_schedule_rules_json": json.dumps({"influenza": schedule}),
                "vaccine_age_groups_json": json.dumps(_age_groups()),
            },
        )

    page = VaccineTab(db_path)
    page.patient_resident_id_input.setText("500101-1234567")

    result = page.check_influenza_program()

    assert result.allowed is True
    assert "Eligible by configured rules" in page.influenza_check_result.text()
    assert page.influenza_check_result.property("resultState") == "success"
    assert "500101" not in page.influenza_check_result.text()
