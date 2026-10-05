import ast
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import normalize_source_day_v2
from tests import source_structure_proposal as proposal
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import policy
from tests.test_source_evidence_inspection import DAY, database


def rows(*, relationships=0):
    return [("summary", "relations", "", 2),
            ("summary", "relationships", "", relationships)] + [
        ("relation", scope, "r", 1) for scope in proposal.SCOPES
    ] + [("links", scope, metric, relationships if (scope, metric) ==
           ("receptions", "child_links") else 0)
          for scope in proposal.SCOPES for metric in proposal.METRICS]


def inspect(**kwargs):
    return proposal.inspect_structure(
        partial(eghis_db.run_verified_evidence_query, "mock-secret"), **kwargs,
    )


@pytest.mark.parametrize("count", [0, 1, 64])
def test_one_fixed_catalog_read_closes_before_interpretation(database, monkeypatch, count):
    database.rows = rows(relationships=count)
    validate = proposal.validate_rows
    def after_close(values):
        assert database.events[-2:] == ["cursor_closed", "connection_closed"]
        assert all(c.closed for c in database.connections)
        return validate(values)
    monkeypatch.setattr(proposal, "validate_rows", after_close)
    report = inspect(approved=True)
    assert report["status"] == "structure_observed"
    assert report["findings"]["relationship_count"] == count
    assert report["authoritative_snapshot"] is False
    assert database.statements[-1] == (proposal.QUERY, {
        "schema": "public", "reception_table": "h1opdin", "order_table": "h2opd_doct_ord",
    })
    assert len(database.statements) == 3
    assert all(report["closure"][name] is True for name in (
        "connection_opened", "readonly_verified", "cursor_closed", "connection_closed",
    ))


@pytest.mark.parametrize("approved", [False, None, 0, 1, "yes"])
def test_no_implicit_approval_or_connection(database, approved):
    assert inspect(approved=approved)["status"] == "approval_required"
    assert not database.connections and not database.statements


def test_changed_query_requires_a_new_review_before_connecting(database, monkeypatch):
    monkeypatch.setattr(proposal, "QUERY", proposal.QUERY + "\n")
    assert inspect(approved=True)["status"] == "query_changed"
    assert not database.connections and not database.statements


@pytest.mark.parametrize("stage", [
    "connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open",
])
def test_every_failure_is_redacted_and_not_empty_evidence(database, stage, capsys, caplog):
    database.rows, database.stage = rows(), stage
    report = inspect(approved=True)
    assert report["status"] != "structure_observed"
    assert report["authoritative_snapshot"] is False and "findings" not in report
    assert "PRIVATE_MARKER" not in json.dumps(report)
    assert "mock-secret" not in json.dumps(report)
    if stage == "query":
        assert report["status"] == "query_timed_out"
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect(approved=True)["status"] == "reader_safety_stop"
        assert len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"),
                                  ("on", "0", "read committed"),
                                  ("on", "2s", "serializable")])
def test_unverified_session_never_reaches_catalog_query(database, mode):
    database.mode = mode
    result = inspect(approved=True)
    assert result["status"] == "session_unverified" and "findings" not in result
    assert len(database.statements) == 2
    assert result["closure"]["connection_closed"] is True


@pytest.mark.parametrize("data,reason", [
    ([], "report_overflow_or_incomplete"),
    (rows()[:-1], "incomplete_result"),
    (rows() + [rows()[0]], "report_overflow_or_incomplete"),
    (rows(relationships=65), "relationship_overflow"),
    (rows()[:2], "incomplete_result"),
    (rows()[1:], "incomplete_result"),
    ([("summary", "relations", "", 1)] + rows()[1:], "inconsistent_result"),
    ([("summary", "relations", "", 3)] + rows()[1:], "inconsistent_result"),
    (rows()[:1] + [("summary", "relationships", "", 2)] + rows()[2:], "inconsistent_result"),
    (rows()[:-1] + [rows()[0]], "invalid_result"),
    ([("summary", "relations", "", True)] + rows()[1:], "invalid_result"),
    ([("summary", "relations", "", -1)] + rows()[1:], "invalid_result"),
    ([("summary", "relations", "", "PRIVATE_MARKER")] + rows()[1:], "invalid_result"),
    ([("PRIVATE_MARKER", "relations", "", 2)] + rows()[1:], "invalid_result"),
    ([("summary", "PRIVATE_MARKER", "", 2)] + rows()[1:], "invalid_result"),
    ([("summary", "relations", "PRIVATE_MARKER", 2)] + rows()[1:], "invalid_result"),
    ([("summary", "relations")], "invalid_result"),
])
def test_partial_overflow_unknown_and_inconsistent_reports_fail_closed(database, data, reason):
    database.rows = data
    result = inspect(approved=True)
    assert result["status"] == reason and "findings" not in result
    assert result["authoritative_snapshot"] is False
    assert "PRIVATE_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("kind", ["r", "p", "v", "m", "f"])
def test_relation_kind_is_metadata_not_source_authority(database, kind, policy):
    database.rows = rows()
    database.rows[2] = ("relation", "receptions", kind, 1)
    report = inspect(approved=True)
    assert report["status"] == "structure_observed"
    assert report["findings"]["relations"]["receptions"]["kind"] == kind
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    opened = len(database.connections)
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == opened


@pytest.mark.parametrize("kind", ["UNREVIEWED", "PRIVATE_MARKER", "", None])
def test_unknown_kind_is_fixed_failure(database, kind):
    database.rows = rows()
    database.rows[2] = ("relation", "receptions", kind, 1)
    report = inspect(approved=True)
    assert report["status"] in {"invalid_result", "relation_scope_unverified"}
    assert "findings" not in report and "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("code,expected", [("42501", "permission_denied"),
                                          ("42703", "schema_mismatch"),
                                          ("42P01", "schema_mismatch"),
                                          ("UNKNOWN", "read_failed")])
def test_provider_errors_never_leak_text_or_trigger_retry(code, expected):
    calls = []
    def runner(*args, **kwargs):
        calls.append(True)
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    result = proposal.inspect_structure(runner, approved=True)
    assert result["status"] == expected and len(calls) == 1
    assert "findings" not in result and "PRIVATE_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("field", ["connection_opened", "readonly_verified",
                                  "cursor_closed", "connection_closed"])
def test_missing_cleanup_proof_blocks_processing(monkeypatch, field):
    def runner(*args, proof, **kwargs):
        proof.update(connection_opened=True, readonly_verified=True,
                     cursor_closed=True, connection_closed=True)
        proof[field] = False
        return rows()
    def forbidden(*args):
        pytest.fail("Unverified results must not be interpreted")
    monkeypatch.setattr(proposal, "validate_rows", forbidden)
    report = proposal.inspect_structure(runner, approved=True)
    assert report["status"] == "cleanup_or_session_unverified"
    assert "findings" not in report


def test_proposal_uses_shared_fifo_and_exclusive_physical_connection(database):
    database.rows = rows()
    with ThreadPoolExecutor(max_workers=4) as callers:
        reports = list(callers.map(lambda _: inspect(approved=True), range(4)))
    assert all(report["status"] == "structure_observed" for report in reports)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4


@pytest.mark.parametrize("metric", proposal.METRICS)
def test_each_metric_is_an_uninterpreted_catalog_count(database, metric, capsys, caplog):
    database.rows = rows()
    database.rows[1] = ("summary", "relationships", "", 3)
    index = database.rows.index(("links", "orders", metric, 0))
    database.rows[index] = ("links", "orders", metric, 3)
    result = inspect(approved=True)
    assert result["status"] == "structure_observed"
    assert result["findings"] == {"relationship_count": 3, "relations": {
        scope: {"kind": "r", **{name: 3 if (scope, name) == ("orders", metric) else 0
                                for name in proposal.METRICS}}
        for scope in proposal.SCOPES}}
    assert result["authoritative_snapshot"] is False
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("replacement", [
    ("links", "PRIVATE_MARKER", "child_links", 0),
    ("links", "orders", "PRIVATE_MARKER", 0),
    ("relation", "receptions", "v", 1),
    ("links", "orders", "child_links", 66),
])
def test_extra_metadata_and_duplicate_scope_cannot_escape_allowlist(database, replacement):
    database.rows = rows()
    database.rows[-1] = replacement
    result = inspect(approved=True)
    assert result["status"] in {"invalid_result", "relation_scope_unverified"}
    assert "findings" not in result and "PRIVATE_MARKER" not in json.dumps(result)


def test_sql_is_one_bounded_catalog_only_statement_with_no_raw_definitions():
    sql = proposal.QUERY
    assert ";" not in sql and not eghis_db._WRITE_SQL_PATTERN.search(sql)
    assert set(re.findall(r"pg_catalog\.(pg_[a-z_]+)", sql)) == {
        "pg_class", "pg_namespace", "pg_inherits", "pg_constraint", "pg_depend", "pg_rewrite",
    }
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(proposal.parameters())
    assert "LIMIT 3" in sql and "LIMIT 65" in sql and "LIMIT 17" in sql
    assert "UNION\n" in sql  # Deduplicate per-column view dependencies before counting.
    assert "FROM public." not in sql and "JOIN public." not in sql
    for forbidden in ("hold_opd", "ptnt_no", "recept_no", "ord_ymd", "pg_attribute",
                      "pg_description", "pg_get_", "conkey", "consrc", "ev_action",
                      "ev_qual", "conname", "rulename", "FOR UPDATE", "FOR SHARE",
                      "pg_sleep", "SELECT *"):
        assert forbidden not in sql
    final_select = sql[sql.index("SELECT 'summary'"):]
    for forbidden in ("object_id AS", "c.oid", "v.oid", "relname", "relation_name"):
        assert forbidden not in final_select


def test_proposal_has_no_runtime_importer_or_default_connection():
    root = Path(__file__).parents[1]
    source = Path(proposal.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        "pathlib", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue",
    }
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names} == {"hashlib"}
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_structure_proposal" not in path.read_text(encoding="utf-8-sig")
    for forbidden in ("psycopg2", "settings", "connection_string", "getenv", "logging", "http"):
        assert forbidden not in source
