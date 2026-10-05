"""Aggregate observations are not production authority or v2 source snapshots."""

from dataclasses import fields, replace
from datetime import datetime

import pytest

from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import EmrDayReadV2, normalize_source_day_v2
from KaosEghis.core.kaosorders_normalized_source_v2 import serialize_normalized_source_v2
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import metadata, policy, read
from tests.test_source_evidence_inspection import (
    DAY, database, empty_rows, inspect, populated_rows,
)


OBSERVED_AT = datetime.fromisoformat("2026-10-02T12:00:00+09:00")
PROOFS = (
    "keys_verified", "states_verified", "whole_day", "untruncated",
    "consistent_snapshot", "connection_closed", "structured_fields_verified",
)


@pytest.mark.parametrize("case,status", [
    ("empty", "observed_empty_scope"),
    ("populated", "observed_populated_scope"),
    ("partial", "incomplete_result"),
    ("failed", "read_failed"),
    ("timed_out", "query_timed_out"),
    ("inconsistent", "inconsistent_result"),
    ("source_overflow", "source_overflow"),
    ("result_overflow", "result_overflow_or_incomplete"),
    ("unverified_session", "session_unverified"),
    ("unverified_cursor", "cursor_close_unverified"),
    ("unverified_connection", "reader_safety_stop"),
    ("unapproved", "approval_required"),
])
def test_mocked_probe_never_crosses_v2_or_reader_authority_boundary(
    database, policy, metadata, case, status, capsys, caplog,
):
    arguments = {}
    if case == "populated":
        database.rows = populated_rows()
        arguments["expectation"] = "populated"
    elif case == "partial":
        database.rows = empty_rows()[:-1]
    elif case == "failed":
        database.stage = "connect"
    elif case == "timed_out":
        database.stage = "query"
    elif case == "inconsistent":
        database.rows = empty_rows(no_order_encounters=1)
    elif case == "source_overflow":
        database.rows = empty_rows(encounters=10001)
    elif case == "result_overflow":
        database.rows = [empty_rows()[0]] * 257
    elif case == "unverified_session":
        database.mode = ("off", "2s", "read committed")
    elif case == "unverified_cursor":
        database.stage = "cursor_still_open"
    elif case == "unverified_connection":
        database.stage = "connection_still_open"
    elif case == "unapproved":
        arguments["approved"] = False

    report = inspect(**arguments)
    assert report["status"] == status
    assert report["authoritative_snapshot"] is False
    assert not set(PROOFS) & report.keys()
    if case not in {"empty", "populated"}:
        assert "findings" not in report
    else:
        assert report["closure"]["readonly_verified"] is True
        assert report["closure"]["cursor_closed"] is True
        assert report["closure"]["connection_closed"] is True
        assert all(connection.closed for connection in database.connections)

    # Neither aggregate success nor cleanup proof is a typed v2 source read.
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        serialize_normalized_source_v2(report, metadata, synthetic_fixture=True)

    before = list(database.events), list(database.statements)
    blocked = EghisSourceDayReader().read_day(DAY, OBSERVED_AT)
    assert blocked.status is ReadStatus.UNAVAILABLE
    assert blocked.encounters == blocked.orders == ()
    assert all(getattr(blocked, name) is False for name in PROOFS)
    assert (database.events, database.statements) == before
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


@pytest.mark.parametrize("status", list(ReadStatus))
def test_closed_candidate_empty_scope_cannot_certify_an_empty_v2_day(
    database, read, policy, status,
):
    report = inspect()
    assert report["status"] == "observed_empty_scope"
    assert report["findings"]["counts"]["encounters"] == 0
    assert report["findings"]["counts"]["orders"] == 0

    candidate = EmrDayReadV2(
        read.source_id, read.projection_id, DAY, OBSERVED_AT, status,
        connection_closed=report["closure"]["connection_closed"],
    )
    assert candidate.encounters == candidate.orders == ()
    with pytest.raises(SnapshotRejected, match="^incomplete_source$"):
        normalize_source_day_v2(candidate, policy, synthetic_fixture=True)


@pytest.mark.parametrize("code", ["10", "20", "25", "30", "40", "50"])
@pytest.mark.parametrize("hold", ["Y", "N"])
def test_sampled_codes_and_retained_flags_do_not_create_a_production_state_policy(
    database, read, policy, code, hold,
):
    database.rows = populated_rows()
    report = inspect(expectation="populated")
    assert report["status"] == "observed_populated_scope"

    # Samples in an aggregate report must not create default production mappings.
    row = dict(read.encounters[0], state_code=code, qualifiers={"hold_yn": hold})
    candidate = replace(read, encounters=(row,), orders=())
    with pytest.raises(SnapshotRejected, match="^unknown_reception_state$"):
        normalize_source_day_v2(candidate, policy, synthetic_fixture=True)
    assert "hold_opd" not in row["qualifiers"]
    assert "hold_opd" not in {field.name for field in fields(EmrDayReadV2)}
