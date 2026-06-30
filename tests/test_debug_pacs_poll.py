from KaosEghis.tools.debug_pacs_poll import PacsPollDiagnosis, diagnose_bmd_exclusion


def test_diagnose_bmd_exclusion_points_to_proc_dept_filter() -> None:
    diagnosis = diagnose_bmd_exclusion(
        {
            "bmd_like_rows": 3,
            "bmd_like_rows_passing_current_filters": 0,
            "bmd_like_rows_excluded_by_proc_dept": 3,
            "bmd_like_rows_excluded_by_status": 0,
            "bmd_like_rows_excluded_by_join": 0,
        }
    )

    assert isinstance(diagnosis, PacsPollDiagnosis)
    assert diagnosis.primary_reason == "BMD-like rows are excluded by o.proc_dept_cd = 'XRAY'"
    assert "allow BMD rows" in diagnosis.recommendation
    assert "HC342" in diagnosis.recommendation


def test_diagnose_bmd_exclusion_points_to_status_filter() -> None:
    diagnosis = diagnose_bmd_exclusion(
        {
            "bmd_like_rows": 2,
            "bmd_like_rows_passing_current_filters": 0,
            "bmd_like_rows_excluded_by_proc_dept": 0,
            "bmd_like_rows_excluded_by_status": 2,
            "bmd_like_rows_excluded_by_join": 0,
        }
    )

    assert diagnosis.primary_reason == "BMD-like rows are excluded by m.scheduled_proc_status = '100'"
    assert "allowed-status list" in diagnosis.recommendation


def test_diagnose_bmd_exclusion_points_to_join_failure() -> None:
    diagnosis = diagnose_bmd_exclusion(
        {
            "bmd_like_rows": 1,
            "bmd_like_rows_passing_current_filters": 0,
            "bmd_like_rows_excluded_by_proc_dept": 0,
            "bmd_like_rows_excluded_by_status": 0,
            "bmd_like_rows_excluded_by_join": 1,
        }
    )

    assert diagnosis.primary_reason == (
        "BMD-like rows are excluded because the mwl -> h2opd_doct_ord join fails"
    )
    assert "Do not add a fallback join" in diagnosis.recommendation
