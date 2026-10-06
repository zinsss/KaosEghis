from functools import partial
import hashlib
import json
from pathlib import Path
import re

import pytest

from KaosEghis.core import eghis_db
from KaosEghis.core.emr_source import EghisSourceDayReader, ReadStatus, SnapshotRejected
from KaosEghis.core.emr_source_v2 import normalize_source_day_v2
from tests import source_order_storage as probe
from tests.test_emr_read_queue import isolated_coordinator
from tests.test_normalized_source_v2 import policy
from tests.test_source_evidence_inspection import database, DAY


def candidate(name="h2opd_doct_ord", **changes):
    values = dict(section="candidate", label=name, kind="r", recept_no="varchar",
                  ord_ymd="bpchar", ord_no="int4", ord_seq_no="int4", ord_cd="varchar",
                  selectable=True, n=1)
    values.update(changes)
    return tuple(values.values())


def summary(key, count):
    return ("summary", key, "", "", "", "", "", "", False, count)


def rows(*extra):
    return [summary("candidate_relations", 1 + len(extra)), summary("unreviewed_names", 0),
            summary("known_order_relations", 1), candidate(), *extra]


def inspect(**kwargs):
    return probe.inspect_catalog(partial(eghis_db.run_verified_evidence_query, "mock-secret"),
                                 approved=True, **kwargs)


def test_exact_catalog_query_closes_before_validation(database, monkeypatch, policy):
    database.rows = rows(candidate("h2synthetic_ord", ord_seq_no="MISSING", selectable=False))
    original = probe.validate_catalog
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        assert all(connection.closed for connection in database.connections)
        return original(data)
    monkeypatch.setattr(probe, "validate_catalog", after_close)
    report = inspect()
    assert report["status"] == "storage_metadata_observed"
    assert report["findings"]["candidate_count"] == 2
    assert not report["findings"]["candidates"]["h2synthetic_ord"]["selectable"]
    assert report["findings"]["candidates"]["h2synthetic_ord"]["ord_seq_no"] == "MISSING"
    assert database.statements[-1] == (probe.CATALOG_QUERY, probe.catalog_parameters())
    assert len(database.statements) == 3 and not report["authoritative_snapshot"]
    assert all(report["closure"][key] for key in probe.PROOF_FIELDS)
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)
    assert EghisSourceDayReader().read_day(DAY, None).status is ReadStatus.UNAVAILABLE
    assert len(database.connections) == 1


@pytest.mark.parametrize("approved", [None, False, 0, 1, "yes"])
def test_explicit_approval_and_hash_before_access(database, approved):
    report = probe.inspect_catalog(partial(eghis_db.run_verified_evidence_query, "mock-secret"), approved=approved)
    assert report["status"] == "approval_required" and not database.connections


def test_changed_sql_requires_review(database, monkeypatch):
    monkeypatch.setattr(probe, "CATALOG_QUERY", probe.CATALOG_QUERY + "\n")
    assert inspect()["status"] == "query_changed" and not database.connections


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query",
    "fetch", "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_failure_is_fixed_no_retry_and_no_empty(database, stage, caplog, capsys):
    database.rows, database.stage = rows(), stage
    report = inspect()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert report["status"] == "reader_safety_stop"
        assert inspect()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert not caplog.records and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("mode", [None, ("off", "2s", "read committed"), ("on", "0", "read committed")])
def test_session_proof_before_source(database, mode):
    database.mode = mode
    assert inspect()["status"] == "session_unverified" and len(database.statements) == 2


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_closure_proof_required_before_interpretation(field, monkeypatch):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return rows()
    monkeypatch.setattr(probe, "validate_catalog", lambda *_: pytest.fail("Unverified cleanup"))
    assert probe.inspect_catalog(run, approved=True)["status"] == "cleanup_or_session_unverified"


@pytest.mark.parametrize("change", [
    {"label": "PRIVATE_MARKER"}, {"label": "h2patient123"}, {"kind": "v"}, {"kind": None},
    {"recept_no": "MISSING"}, {"ord_no": "MISSING", "ord_cd": "MISSING"},
    {"ord_no": 1}, {"ord_no": []}, {"ord_cd": "PRIVATE_MARKER"},
    {"n": True}, {"n": -1}, {"n": 2}, {"selectable": 1}, {"section": "unknown"},
])
def test_unallowlisted_metadata_rejected_redacted(database, change):
    database.rows = rows()[:-1] + [candidate(**change)]
    report = inspect()
    assert "findings" not in report and "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("change", [{"label": "UNREVIEWED"}, {"ord_no": "UNREVIEWED"}])
def test_server_masked_unknown_not_disclosed(database, change):
    database.rows = rows()[:-1] + [candidate(**change)]
    assert inspect()["status"] == "metadata_unreviewed"


@pytest.mark.parametrize("data", [None, [], rows()[:-1], rows() + [candidate()], rows() + [rows()[0]],
    rows()[:-1] + [("bad",)], rows()[1:] + [summary("unknown", 0)],
    [summary("candidate_relations", 2), *rows()[1:]],
    [summary("candidate_relations", 65), *rows()[1:]],
    [rows()[0], summary("unreviewed_names", 1), *rows()[2:]],
    [*rows()[:2], summary("known_order_relations", 0), rows()[3]],
])
def test_partial_overflow_inconsistent_reports_never_findings(database, data):
    database.rows = data
    assert "findings" not in inspect()


def test_exact_candidate_cap_and_extra_sentinel():
    names = [f"h2synthetic_{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(64)]
    assert probe.validate_catalog(rows(*(candidate(name) for name in names[:63])))["candidate_count"] == 64
    with pytest.raises(probe.StorageRejected, match="^metadata_overflow$"):
        probe.validate_catalog(rows(*(candidate(name) for name in names)))


@pytest.mark.parametrize("code,reason", [("57014", "query_timed_out"), ("42501", "permission_denied"),
    ("42703", "schema_mismatch"), ("42P01", "schema_mismatch"), (None, "read_failed")])
def test_provider_error_redacted(code, reason):
    def run(*args, **kwargs):
        error = RuntimeError("PRIVATE_MARKER")
        error.pgcode = code
        raise error
    report = probe.inspect_catalog(run, approved=True)
    assert report["status"] == reason and "PRIVATE_MARKER" not in json.dumps(report)


@pytest.mark.parametrize("elapsed", [True, -1, float("nan"), float("inf"), "PRIVATE_MARKER", 10**400])
def test_closure_output_allowlist(elapsed):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof.update(elapsed_seconds=elapsed, PRIVATE_MARKER="PRIVATE_MARKER")
        return rows()
    report = probe.inspect_catalog(run, approved=True)
    assert set(report["closure"]) == set(probe.PROOF_FIELDS)
    assert "PRIVATE_MARKER" not in json.dumps(report, allow_nan=False)


def test_catalog_only_sql_allowlists_and_no_application_importer():
    sql = probe.CATALOG_QUERY
    assert hashlib.sha256(sql.encode()).hexdigest() == probe.CATALOG_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert set(re.findall(r"pg_catalog\.(\w+)", sql)) == {"pg_class", "pg_namespace", "pg_attribute", "pg_type"}
    assert set(re.findall(r"%\((\w+)\)s", sql)) == set(probe.catalog_parameters())
    assert "LIMIT %(candidate_limit)s" in sql and "LIMIT 69" in sql
    assert "ELSE 'UNREVIEWED'" in sql and "has_table_privilege(oid, 'SELECT')" in sql
    for text in ("public.", "hold_opd", "birth", "ptnt_no", "pg_get", "pg_description", "pg_proc"):
        assert text not in sql
    for path in (Path(__file__).parents[1] / "KaosEghis").rglob("*.py"):
        assert "source_order_storage" not in path.read_text(encoding="utf-8-sig")


def inventory_rows(*extra, omitted_names=0, omitted_types=0):
    return rows(*extra) + [summary("total_candidates", 1 + len(extra) + omitted_names + omitted_types),
                          summary("omitted_names", omitted_names), summary("omitted_types", omitted_types)]


def inventory():
    return probe.inspect_inventory(partial(eghis_db.run_verified_evidence_query, "mock-secret"), approved=True)


@pytest.mark.parametrize("omitted", [0, 1, 12])
def test_inventory_is_explicitly_partial_when_any_candidates_masked(database, monkeypatch, omitted, policy):
    database.rows = inventory_rows(omitted_names=omitted, omitted_types=omitted)
    original = probe.validate_inventory
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_inventory", after_close)
    report = inventory()
    assert report["status"] == "storage_metadata_observed" and not report["authoritative_snapshot"]
    assert report["findings"]["inventory_complete"] is (omitted == 0)
    assert report["findings"]["total_candidates"] == 1 + 2 * omitted
    assert set(report["findings"]["candidates"]) == {"h2opd_doct_ord"}
    assert database.statements[-1] == (probe.INVENTORY_QUERY, probe.catalog_parameters())
    assert len(database.statements) == 3
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)


@pytest.mark.parametrize("data", [[], inventory_rows()[:-1], inventory_rows() + [summary("total_candidates", 1)],
    rows() + [summary("total_candidates", 65), summary("omitted_names", 64), summary("omitted_types", 0)],
    rows() + [summary("total_candidates", 2), summary("omitted_names", 0), summary("omitted_types", 0)],
    rows() + [summary("total_candidates", 1), summary("omitted_names", True), summary("omitted_types", 0)],
    inventory_rows(candidate("h2synthetic_ord", ord_no="UNREVIEWED")),
    inventory_rows(candidate("h2patient123")),
])
def test_inventory_does_not_relax_profile_or_summary_validator(database, data):
    database.rows = data
    assert "findings" not in inventory()


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query",
    "fetch", "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_inventory_failure_paths_no_retry_no_empty(database, stage, caplog, capsys):
    database.rows, database.stage = inventory_rows(), stage
    report = inventory()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report) and "mock-secret" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert inventory()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert not caplog.records and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_inventory_requires_physical_closure_before_validation(field, monkeypatch):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return inventory_rows()
    monkeypatch.setattr(probe, "validate_inventory", lambda *_: pytest.fail("Unverified cleanup"))
    assert probe.inspect_inventory(run, approved=True)["status"] == "cleanup_or_session_unverified"


def test_inventory_hash_and_permission_and_strict_original_preserved(database, monkeypatch):
    assert probe.inspect_inventory(None)["status"] == "approval_required"
    sql = probe.INVENTORY_QUERY
    assert hashlib.sha256(sql.encode()).hexdigest() == probe.INVENTORY_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql and "LIMIT 72" in sql
    assert sql.count("WHERE name_reviewed AND types_reviewed") == 3
    assert "WHERE NOT name_reviewed" in sql and "WHERE name_reviewed AND NOT types_reviewed" in sql
    for text in ("public.", "hold_opd", "birth", "ptnt_no", "pg_get", "pg_description", "pg_proc"):
        assert text not in sql
    assert hashlib.sha256(probe.CATALOG_QUERY.encode()).hexdigest() == "51228a1824143b04761280d2ea6eb813b6c1c230ce38c19166af937389da0933"
    with pytest.raises(probe.StorageRejected, match="^metadata_unreviewed$"):
        probe.validate_catalog(rows(candidate(ord_no="UNREVIEWED")))
    monkeypatch.setattr(probe, "INVENTORY_QUERY", sql + "\n")
    assert inventory()["status"] == "query_changed" and not database.connections


def access_rows(**changes):
    counts = dict.fromkeys(sorted(probe.ACCESS_FIELDS), 0)
    counts.update(candidate_relations=4, known_relations=1, known_table_select=1,
                  known_any_column_select=1, other_relations=3, other_four_part_keys=2)
    counts.update(changes)
    return list(counts.items())


def access():
    return probe.inspect_access(partial(eghis_db.run_verified_evidence_query, "mock-secret"), approved=True)


def test_access_counts_include_masked_objects_without_names(database, monkeypatch, policy):
    database.rows = access_rows(other_any_column_select=1, other_reception_select=1)
    original = probe.validate_access
    def after_close(data):
        assert database.events == ["connected", "cursor_closed", "connection_closed"]
        return original(data)
    monkeypatch.setattr(probe, "validate_access", after_close)
    report = access()
    assert report["findings"]["other_any_column_select"] == 1
    assert report["findings"]["other_table_select"] == 0
    assert not report["authoritative_snapshot"]
    assert database.statements[-1][0] == probe.ACCESS_QUERY and len(database.statements) == 3
    assert set(database.statements[-1][1]) == {"schema", "columns", "candidate_limit", "known_order"}
    with pytest.raises(SnapshotRejected, match="^invalid_snapshot$"):
        normalize_source_day_v2(report, policy, synthetic_fixture=True)


@pytest.mark.parametrize("stage", ["connect", "readonly", "cursor", "timeout_setup", "mode", "query",
    "fetch", "cursor_close", "cursor_still_open", "connection_close", "connection_still_open"])
def test_access_failure_stops_no_retry_or_findings(database, stage, capsys, caplog):
    database.rows, database.stage = access_rows(), stage
    report = access()
    assert "findings" not in report and not report["authoritative_snapshot"]
    assert "PRIVATE_MARKER" not in json.dumps(report)
    assert len(database.connections) <= 1
    if stage.startswith("connection_"):
        assert access()["status"] == "reader_safety_stop" and len(database.connections) == 1
    assert not caplog.records and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("field", probe.ACCESS_FIELDS)
def test_access_overflow_on_any_count(field):
    with pytest.raises(probe.StorageRejected, match="^metadata_overflow$"):
        probe.validate_access(access_rows(**{field: 65}))


@pytest.mark.parametrize("changes", [{"known_relations": 0}, {"candidate_relations": 5},
    {"known_any_column_select": 0}, {"other_table_select": 1}, {"other_reception_select": 1},
    {"other_four_part_select": 1}, {"other_code_select": 1}, {"other_four_part_keys": 4},
    {"other_any_column_select": True}, {"other_any_column_select": -1}])
def test_access_inconsistent_or_invalid_counts_rejected(database, changes):
    database.rows = access_rows(**changes)
    assert "findings" not in access()


@pytest.mark.parametrize("field", probe.PROOF_FIELDS)
def test_access_unverified_cleanup_not_processed(field, monkeypatch):
    def run(*args, proof, **kwargs):
        proof.update(dict.fromkeys(probe.PROOF_FIELDS, True))
        proof[field] = False
        return access_rows()
    monkeypatch.setattr(probe, "validate_access", lambda *_: pytest.fail("Unverified cleanup"))
    assert probe.inspect_access(run, approved=True)["status"] == "cleanup_or_session_unverified"


@pytest.mark.parametrize("data", [[], access_rows()[:-1], access_rows() + [("unknown", 0)],
    access_rows()[:-1] + [access_rows()[0]], access_rows()[:-1] + [("PRIVATE_MARKER", 0)]])
def test_access_partial_unknown_duplicate_not_findings(database, data):
    database.rows = data
    report = access()
    assert "findings" not in report and "PRIVATE_MARKER" not in json.dumps(report)


def test_access_query_catalog_only_no_write_or_names_in_report(database, monkeypatch):
    sql = probe.ACCESS_QUERY
    assert hashlib.sha256(sql.encode()).hexdigest() == probe.ACCESS_HASH
    assert not eghis_db._WRITE_SQL_PATTERN.search(sql) and ";" not in sql
    assert "has_any_column_privilege(oid, 'SELECT')" in sql
    assert "has_column_privilege(oid, 'recept_no', 'SELECT')" in sql
    assert "SELECT metric, n FROM report ORDER BY metric" in sql and "LIMIT 12" in sql
    assert set(re.findall(r"SELECT '([a-z_]+)'", sql)) == probe.ACCESS_FIELDS
    for text in ("public.", "hold_opd", "birth", "ptnt_no", "pg_get", "pg_description", "pg_proc"):
        assert text not in sql
    assert probe.inspect_access(None)["status"] == "approval_required"
    monkeypatch.setattr(probe, "ACCESS_QUERY", sql + "\n")
    assert access()["status"] == "query_changed" and not database.connections
