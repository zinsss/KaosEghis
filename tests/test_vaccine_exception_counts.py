import pytest

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_vaccine_record,
    delete_vaccine_record,
    get_today_vaccine_counts,
    get_today_vaccine_exception_counts,
    mark_vaccine_record_cancelled,
    mark_vaccine_record_completed,
    mark_vaccine_record_printed,
    update_vaccine_record,
)


@pytest.fixture
def connection(tmp_path):
    path = tmp_path / "vaccine.sqlite"
    initialize_database(path)
    with connect(path) as database:
        yield database


def record(connection, program, name="Synthetic vaccine"):
    return create_vaccine_record(
        connection, vaccine_type_id=None, vaccine_type_name=name,
        program_type=program,
    )


@pytest.mark.parametrize("program", [
    "national_influenza", "national_covid", "general_influenza", "general",
])
@pytest.mark.parametrize("status", ["prepared", "printed", "completed", "cancelled", "error"])
def test_only_completed_national_exceptions_are_included(connection, program, status):
    entry = record(connection, program)
    if status == "printed":
        mark_vaccine_record_printed(connection, entry.id)
    elif status in {"completed", "cancelled", "error"}:
        mark_vaccine_record_completed(
            connection, entry.id, counts_toward_cap=False,
            completed_at="2026-10-06T09:00:00+09:00",
        )
        if status == "cancelled":
            mark_vaccine_record_cancelled(connection, entry.id)
        elif status == "error":
            # Simulate a failed local workflow with a leftover completion date.
            connection.execute(
                "UPDATE vaccine_records SET status = 'error' WHERE id = ?", (entry.id,),
            )
    expected = {"flu": 0, "covid": 0}
    if status == "completed" and program.startswith("national_"):
        expected["flu" if program == "national_influenza" else "covid"] = 1
    assert get_today_vaccine_exception_counts(connection, "2026-10-06") == expected
    assert get_today_vaccine_counts(connection, "2026-10-06") == {"flu": 0, "covid": 0}


def test_exception_counts_use_completion_date_and_share_covid_products(connection):
    assert get_today_vaccine_exception_counts(connection, "2026-10-06") == {"flu": 0, "covid": 0}
    for program, name in (
        ("national_influenza", "Influenza"),
        ("national_covid", "COVID-19 (Pfizer)"),
        ("national_covid", "COVID-19 (Moderna)"),
    ):
        for day, counted in (("05", False), ("06", False), ("06", True), ("07", False)):
            entry = record(connection, program, name)
            mark_vaccine_record_completed(
                connection, entry.id, counts_toward_cap=counted,
                completed_at=f"2026-10-{day}T09:00:00+09:00",
            )
    assert get_today_vaccine_exception_counts(connection, "2026-10-06") == {"flu": 1, "covid": 2}
    assert get_today_vaccine_counts(connection, "2026-10-06") == {"flu": 1, "covid": 2}
    assert get_today_vaccine_exception_counts(connection, "2026-10-08") == {"flu": 0, "covid": 0}


@pytest.mark.parametrize("program,bucket", [("national_influenza", "flu"), ("national_covid", "covid")])
@pytest.mark.parametrize("correction", [mark_vaccine_record_cancelled, delete_vaccine_record])
def test_completion_retries_edits_and_corrections_do_not_inflate_exceptions(connection, program, bucket, correction):
    entry = record(connection, program)
    mark_vaccine_record_completed(
        connection, entry.id, counts_toward_cap=False,
        completed_at="2026-10-06T09:00:00+09:00",
    )
    mark_vaccine_record_completed(
        connection, entry.id, counts_toward_cap=True,
        completed_at="2026-10-07T09:00:00+09:00",
    )
    update_vaccine_record(
        connection, entry.id, vaccine_type_id=None,
        vaccine_type_name="Renamed synthetic vaccine", program_type="general",
    )
    assert get_today_vaccine_exception_counts(connection, "2026-10-06")[bucket] == 1
    assert get_today_vaccine_exception_counts(connection, "2026-10-07")[bucket] == 0
    assert get_today_vaccine_counts(connection, "2026-10-06")[bucket] == 0
    correction(connection, entry.id)
    assert get_today_vaccine_exception_counts(connection, "2026-10-06")[bucket] == 0
