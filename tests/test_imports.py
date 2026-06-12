def test_core_modules_import() -> None:
    import KaosEghis.config
    import KaosEghis.core.clipboard_service
    import KaosEghis.core.credential_store
    import KaosEghis.core.emr_detector
    import KaosEghis.core.macro_models
    import KaosEghis.core.macro_runner
    import KaosEghis.core.safety_gate
    import KaosEghis.db.database
    import KaosEghis.db.repositories


def test_settings_repository_can_save_and_load(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "eghis_process_name": "Example.exe",
                "eghis_window_title_contains": "Example",
                "kaosgdd_url": "https://kaosgdd.net",
                "credential_reference_name": "test-reference",
            },
        )
        settings = get_settings(connection)

    assert settings["eghis_process_name"] == "Example.exe"
    assert settings["eghis_window_title_contains"] == "Example"
    assert settings["credential_reference_name"] == "test-reference"


def test_detector_and_clipboard_imports() -> None:
    from KaosEghis.core import clipboard_service, emr_detector

    assert callable(emr_detector.check_process_running)
    assert callable(emr_detector.find_window_by_title_contains)
    assert callable(emr_detector.get_active_window_title)
    assert callable(emr_detector.is_target_window_active)
    assert callable(clipboard_service.copy_text)
