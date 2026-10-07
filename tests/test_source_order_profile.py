from copy import deepcopy
from datetime import datetime, timedelta
from functools import partial
import json

import pytest

from KaosEghis.core import eghis_db
from tests import source_order_profile as profile
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_source_evidence_inspection import database


NOW = datetime(2026, 10, 7, 12, tzinfo=profile.coverage.KST)


def plan():
    return [{"Total Runtime": 12.5, "Plan": {
        "Node Type": "Limit", "Actual Rows": len(profile.coverage.BOUNDS), "Actual Loops": 1,
        "Actual Total Time": 10.2, **dict.fromkeys(profile.BLOCKS, 0), "Shared Hit Blocks": 20,
        "Plans": [{"Node Type": "Index Scan", "Index Cond": "PRIVATE_MARKER",
                   "Shared Hit Blocks": 20}],
    }}]


def inspect(**kwargs):
    args = dict(clinic_day=NOW.date(), now=lambda: NOW, approved=True)
    args.update(kwargs)
    return profile.inspect_profile(partial(eghis_db.run_verified_evidence_query, "mock-secret"), **args)


def test_profile_uses_pinned_select_and_closes_before_numeric_output(database, monkeypatch, capsys, caplog):
    database.rows = [(plan(),)]
    summarize = profile.summarize_plan
    def closed(rows):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return summarize(rows)
    monkeypatch.setattr(profile, "summarize_plan", closed)
    report = inspect()
    assert report["status"] == "profile_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["buffers"]["Shared Hit Blocks"] == 20
    assert report["findings"]["scan_node_counts"]["Index Scan"] == 1
    assert len(database.connections) == 1
    assert database.statements[-1] == (profile.PREFIX + profile.coverage.QUERY,
                                      profile.coverage.parameters(NOW.date()))
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("encoded", [False, True])
def test_json_string_and_decoded_plan(encoded):
    data = json.dumps(plan()) if encoded else plan()
    assert profile.summarize_plan([(data,)])["server_execution_ms"] == 12.5


@pytest.mark.parametrize("bad", [None, True, -1, float("nan"), float("inf"), "PRIVATE_MARKER"])
def test_invalid_timing_redacted(bad):
    data = plan()
    data[0]["Total Runtime"] = bad
    with pytest.raises(profile.ProfileRejected, match="^invalid_profile$"):
        profile.summarize_plan([(data,)])


@pytest.mark.parametrize("bad", [None, True, -1, 1.5, "PRIVATE_MARKER"])
def test_invalid_buffer_rejected(bad):
    data = plan()
    data[0]["Plan"]["Shared Read Blocks"] = bad
    with pytest.raises(profile.ProfileRejected, match="^invalid_profile$"):
        profile.summarize_plan([(data,)])


@pytest.mark.parametrize("rows", [[], [(None,)], [("PRIVATE_MARKER",)], [("[]",)], [(plan(),)] * 2])
def test_incomplete_profiles_reject(rows):
    with pytest.raises(profile.ProfileRejected, match="^invalid_profile$"):
        profile.summarize_plan(rows)


@pytest.mark.parametrize("field", profile.coverage.PROOF_FIELDS)
def test_cleanup_and_session_required(field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(profile.coverage.PROOF_FIELDS, True))
        proof[field] = False
        return [(plan(),)]
    monkeypatch.setattr(profile, "summarize_plan", lambda rows: pytest.fail("Unclosed interpretation"))
    report = profile.inspect_profile(runner, clinic_day=NOW.date(), now=lambda: NOW, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("approved", [False, None, 1, "yes"])
def test_approval_required(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required"
    assert not database.connections


def test_changed_sql_requires_review(database, monkeypatch):
    monkeypatch.setattr(profile.coverage, "QUERY", profile.coverage.QUERY + " ")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("stage", ["connect", "readonly", "mode", "query", "fetch", "cursor_close",
                                  "cursor_still_open", "connection_close", "connection_still_open"])
def test_failures_do_not_retry_or_expose_provider_text(database, stage):
    database.rows, database.stage = [(plan(),)], stage
    report = inspect()
    assert "findings" not in report and len(database.connections) <= 1
    assert "PRIVATE_MARKER" not in json.dumps(report)


def test_rollover_discards_profile_after_connection_closed(database):
    database.rows = [(plan(),)]
    clock = iter([NOW, NOW + timedelta(days=1)])
    report = inspect(now=lambda: next(clock))
    assert report["status"] == "current_day_unverified" and "findings" not in report
    assert report["closure"]["connection_closed"]


def test_cyclic_or_oversized_tree_rejected():
    data = plan()
    data[0]["Plan"]["Plans"] = [data[0]["Plan"]]
    with pytest.raises(profile.ProfileRejected, match="^invalid_profile$"):
        profile.summarize_plan([(data,)])
    data = plan()
    data[0]["Plan"]["Plans"] = [deepcopy(data[0]["Plan"])] * 1001
    with pytest.raises(profile.ProfileRejected, match="^invalid_profile$"):
        profile.summarize_plan([(data,)])
