import ast
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import normalize_source_day_v2
from tests import source_metadata_followup as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import policy
from tests.test_source_evidence_inspection import DAY, database


def values(operation, **changes):
    counts = dict.fromkeys(probe.FIELDS[operation], 0)
    counts.update(relations=2, ordinary_relations=2)
    if operation == "views":
        counts.update(scope_view_links=7, reception_views=4, order_views=3,
                      unique_views=5, shared_views=2, ordinary_views=5,
                      relation_links=9, reception_relation_links=4,
                      order_relation_links=3, other_ordinary_relation_links=2)
    else:
        counts.update(own_roles=1, reachable_roles=1, schemas=1,
                      usable_schemas=1, selectable_relations=2)
    counts.update(changes)
    return list(counts.items())


def inspect(operation, **kwargs):
    return probe.inspect_metadata(
        operation, partial(eghis_db.run_verified_evidence_query, "mock-secret"), **kwargs,
    )


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_fixed_parameterized_operation_closes_before_interpretation(database, monkeypatch, operation):
    database.rows = values(operation)
    original = probe.validate_rows
    def after_close(name, rows):
        assert database.events[-2:] == ["cursor_closed", "connection_closed"]
        assert all(connection.closed for connection in database.connections)
        return original(name, rows)
    monkeypatch.setattr(probe, "validate_rows", after_close)
    report = inspect(operation, approved=True)
    assert report["status"] == "metadata_observed"
    assert report["findings"] == dict(values(operation))
    assert report["authoritative_snapshot"] is False
    assert all(report["closure"][field] is True for field in probe.PROOF_FIELDS)
    assert database.statements[-1] == (probe.QUERIES[operation], probe.parameters(operation))
    assert len(database.statements) == 3


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("approved", [False, None, 0, 1, "yes"])
def test_no_implicit_approval(database, operation, approved):
    assert inspect(operation, approved=approved)["status"] == "approval_required"
    assert not database.connections


@pytest.mark.parametrize("operation", [None, [], {}, "unknown", 1])
def test_unknown_operation_does_not_connect(database, operation):
    assert inspect(operation, approved=True)["status"] == "invalid_operation"
    assert not database.connections


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_sql_change_requires_review(database, monkeypatch, operation):
    monkeypatch.setitem(probe.QUERIES, operation, probe.QUERIES[operation] + "\n")
    assert inspect(operation, approved=True)["status"] == "query_changed"
    assert not database.connections


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("stage", [
    "connect", "readonly", "cursor", "timeout_setup", "mode", "query", "fetch",
    "cursor_close", "cursor_still_open", "connection_close", "connection_still_open",
])
def test_failure_is_redacted_non_authoritative_and_never_retried(database, operation, stage, capsys, caplog):
    database.rows, database.stage = values(operation), stage
    report = inspect(operation, approved=True)
    assert report["status"] != "metadata_observed"
    assert "findings" not in report and report["authoritative_snapshot"] is False
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        opened = len(database.connections)
        assert inspect(operation, approved=True)["status"] == "reader_safety_stop"
        assert len(database.connections) == opened
    assert capsys.readouterr() == ("", "") and not caplog.records


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"),
                                  ("on", "0", "read committed"), ("on", "2s", "serializable")])
def test_session_check_precedes_catalog_query(database, operation, mode):
    database.mode = mode
    report = inspect(operation, approved=True)
    assert report["status"] == "session_unverified" and "findings" not in report
    assert len(database.statements) == 2
    assert report["closure"]["connection_closed"] is True


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_unverified_cleanup_cannot_be_interpreted(operation, field, monkeypatch):
    def runner(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return values(operation)
    def forbidden(*args):
        pytest.fail("Unverified results must not be processed")
    monkeypatch.setattr(probe, "validate_rows", forbidden)
    report = probe.inspect_metadata(operation, runner, approved=True)
    assert report["status"] == "cleanup_or_session_unverified" and "findings" not in report


@pytest.mark.parametrize("operation,field,cap", [
    (operation, field, cap) for operation, fields in probe.FIELDS.items() for field, cap in fields.items()
])
def test_every_cap_plus_one_is_rejected(operation, field, cap):
    with pytest.raises(probe.MetadataRejected, match="^metadata_overflow$"):
        probe.validate_rows(operation, values(operation, **{field: cap + 1}))


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("bad", [None, True, -1, 0.0, "PRIVATE_MARKER", [], {}])
def test_non_integer_metadata_is_rejected(operation, bad):
    with pytest.raises(probe.MetadataRejected, match="^invalid_result$"):
        probe.validate_rows(operation, values(operation, relations=bad))


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("mutation", ["empty", "missing", "extra", "duplicate", "unknown", "shape"])
def test_missing_unknown_or_partial_report_is_not_empty_authority(database, operation, mutation):
    rows = values(operation)
    if mutation == "empty":
        rows = []
    elif mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append(("PRIVATE_MARKER", 1))
    elif mutation == "duplicate":
        rows[-1] = rows[0]
    elif mutation == "unknown":
        rows[-1] = ("PRIVATE_MARKER", 1)
    else:
        rows[-1] = ("PRIVATE_MARKER",)
    database.rows = rows
    report = inspect(operation, approved=True)
    assert report["status"] in {"invalid_result", "report_overflow_or_incomplete"}
    assert "findings" not in report and report["authoritative_snapshot"] is False
    assert "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("change", [{"relations": 0}, {"relations": 1}, {"ordinary_relations": 1}])
def test_wrong_or_missing_source_relation_rejected(operation, change):
    with pytest.raises(probe.MetadataRejected, match="^source_scope_unverified$"):
        probe.validate_rows(operation, values(operation, **change))


@pytest.mark.parametrize("change", [
    {"scope_view_links": 6}, {"shared_views": 1}, {"shared_views": 4},
    {"unique_views": 4}, {"ordinary_views": 4}, {"relation_links": 8},
    {"reception_relation_links": 3, "relation_links": 8},
    {"order_relation_links": 2, "relation_links": 8},
])
def test_view_crosschecks_fail_closed(change):
    with pytest.raises(probe.MetadataRejected, match="^inconsistent_result$"):
        probe.validate_rows("views", values("views", **change))


def test_zero_dependencies_are_only_metadata_not_verified_empty_day(database, policy):
    database.rows = list(dict.fromkeys(probe.VIEW_FIELDS, 0).items())
    database.rows[:2] = [("relations", 2), ("ordinary_relations", 2)]
    report = inspect("views", approved=True)
    assert report["status"] == "metadata_observed" and report["authoritative_snapshot"] is False
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_success_does_not_enable_source_reader_or_normalization(database, policy, operation):
    database.rows = values(operation)
    report = inspect(operation, approved=True)
    assert report["status"] == "metadata_observed"
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    opened = len(database.connections)
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == opened


@pytest.mark.parametrize("change", [
    {"own_roles": 0}, {"schemas": 0}, {"reachable_roles": 0},
    {"reachable_privileged_roles": 2}, {"executable_definer_routines": 1},
])
def test_privilege_crosschecks_fail_closed(change):
    with pytest.raises(probe.MetadataRejected, match="^inconsistent_result$"):
        probe.validate_rows("privileges", values("privileges", **change))


def test_high_privileges_are_reported_without_exercising_them(database):
    database.rows = values("privileges", superuser_roles=1, role_admin_roles=1,
                           database_admin_roles=1, reachable_privileged_roles=1,
                           nonselect_relations=2, nonselect_column_relations=2,
                           owner_role_relations=2, writable_schemas=1)
    report = inspect("privileges", approved=True)
    assert report["status"] == "metadata_observed"
    assert report["findings"]["nonselect_relations"] == 2
    assert report["authoritative_snapshot"] is False
    assert len(database.statements) == 3
    assert all(not eghis_db._WRITE_SQL_PATTERN.search(sql) for sql, _ in database.statements)


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_result_order_not_significant(operation):
    assert probe.validate_rows(operation, values(operation)[::-1]) == dict(values(operation))


@pytest.mark.parametrize("operation", probe.QUERIES)
@pytest.mark.parametrize("code,reason", [("42501", "permission_denied"), ("57014", "query_timed_out"),
    ("42703", "schema_mismatch"), ("42P01", "schema_mismatch"), ("unknown", "read_failed")])
def test_provider_errors_fixed_redacted_no_retry(operation, code, reason):
    calls = []
    def runner(*args, **kwargs):
        calls.append(True)
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    report = probe.inspect_metadata(operation, runner, approved=True)
    assert report["status"] == reason and calls == [True]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "findings" not in report


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_shared_fifo_prevents_overlapping_connections(database, operation):
    database.rows = values(operation)
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: inspect(operation, approved=True), range(4)))
    assert all(report["status"] == "metadata_observed" for report in reports)
    assert database.events == ["connected", "cursor_closed", "connection_closed"] * 4


@pytest.mark.parametrize("operation", probe.QUERIES)
def test_sql_catalog_allowlist_hash_and_bounded_fixed_outputs(operation):
    sql = probe.QUERIES[operation]
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() == probe.HASHES[operation]
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    expected = {"pg_class", "pg_namespace"} | ({"pg_depend", "pg_rewrite", "pg_proc"}
                if operation == "views" else {"pg_roles", "pg_has_role", "pg_proc"})
    assert set(re.findall(r"pg_catalog\.(pg_[a-z_]+)", sql)) == expected
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.parameters(operation))
    assert "LIMIT 3" in sql and "LIMIT 65" in sql and "LIMIT 129" in sql
    assert f"LIMIT {len(probe.FIELDS[operation]) + 1}\n" in sql
    final = sql[sql.index("SELECT 'relations'"):]
    assert set(re.findall(r"SELECT '([a-z_]+)'", final)) == set(probe.FIELDS[operation])
    for forbidden in ("hold_opd", "birth", "ptnt_no", "recept_no", "pg_attribute", "pg_description",
                      "pg_get_", "ev_action", "ev_qual", "prosrc", "probin", "rolpassword",
                      "pg_authid", "FOR UPDATE", "FOR SHARE", "pg_sleep", "SELECT *",
                      "FROM public.", "JOIN public.", "SET ROLE"):
        assert forbidden not in sql


def test_no_runtime_importer_driver_or_settings_access():
    root = Path(__file__).parents[1]
    source = Path(probe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        "pathlib", "KaosEghis.core.eghis_db", "KaosEghis.core.emr_read_queue",
    }
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names} == {"hashlib"}
    for path in (root / "KaosEghis").rglob("*.py"):
        assert "source_metadata_followup" not in path.read_text(encoding="utf-8-sig")
    for forbidden in ("psycopg2", "settings", "connection_string", "getenv", "logging", "http"):
        assert forbidden not in source
