import sys


def test_default_data_path_is_stable_independent_of_cwd(monkeypatch, tmp_path) -> None:
    from KaosEghis.db import database

    monkeypatch.delenv(database.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))

    cwd_one = tmp_path / "launch-one"
    cwd_two = tmp_path / "launch-two"
    cwd_one.mkdir()
    cwd_two.mkdir()

    monkeypatch.chdir(cwd_one)
    first = database.get_database_path()
    monkeypatch.chdir(cwd_two)
    second = database.get_database_path()

    assert first == second
    assert first == (tmp_path / "localappdata" / "KaosEghis" / "KaosEghis.sqlite")


def test_kaoseghis_data_dir_overrides_default(monkeypatch, tmp_path) -> None:
    from KaosEghis.db import database

    override_dir = tmp_path / "custom-data-root"
    monkeypatch.setenv(database.DATA_DIR_ENV_VAR, str(override_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored-localappdata"))

    assert database.get_data_dir() == override_dir
    assert database.get_database_path() == override_dir / "KaosEghis.sqlite"


def test_diagnostic_helper_reports_active_settings_db_path_and_not_secret(
    monkeypatch, tmp_path, capsys
) -> None:
    from KaosEghis.tools import debug_pacs_poll

    db_path = tmp_path / "KaosEghis.sqlite"
    secret = "Host=x;Password=topsecret"

    monkeypatch.setattr(
        debug_pacs_poll,
        "load_app_settings",
        lambda _db_path=None: {
            "eghis_db_connection_string": secret,
            "eghis_db_image_study_query": "",
        },
    )
    monkeypatch.setattr(
        debug_pacs_poll,
        "run_debug_report",
        lambda settings, days=7: {"status": "no_db_config"},
    )
    monkeypatch.setattr(sys, "argv", ["python", "--db-path", str(db_path)])

    exit_code = debug_pacs_poll.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SQLite settings source:" in output
    assert str(db_path.resolve()) in output
    assert secret not in output
