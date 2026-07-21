from datetime import datetime
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_scan_output_dir_uses_stable_data_temp_folder(monkeypatch, tmp_path) -> None:
    from KaosEghis.core.scan_service import get_scan_output_dir

    data_dir = tmp_path / "data"
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(data_dir))

    assert get_scan_output_dir() == data_dir / "temp"


def test_scan_command_uses_saved_native_profile_and_timestamp(tmp_path) -> None:
    from KaosEghis.core.scan_service import prepare_scan_command

    output_dir = tmp_path / "temp"
    executable = tmp_path / "NAPS2.Console.exe"
    executable.write_bytes(b"console")

    command = prepare_scan_command(
        output_dir,
        executable=executable,
        now=datetime(2026, 7, 16, 14, 35),
    )

    assert command.output_path == output_dir / "202607161435.pdf"
    assert command.arguments == (
        "-o",
        str(command.output_path),
        "-p",
        "Canon DR-C125 Native",
        "-v",
    )
    assert "--noprofile" not in command.arguments
    assert "--force" not in command.arguments


def test_scan_command_does_not_overwrite_same_minute_file(tmp_path) -> None:
    import pytest

    from KaosEghis.core.scan_service import timestamped_pdf_path

    output_dir = tmp_path / "temp"
    output_dir.mkdir()
    existing = output_dir / "202607161435.pdf"
    existing.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        timestamped_pdf_path(
            output_dir,
            now=datetime(2026, 7, 16, 14, 35),
        )


def test_cleanup_removes_direct_files_but_not_nested_content(tmp_path) -> None:
    from KaosEghis.core.scan_service import clean_scan_output_dir

    output_dir = tmp_path / "temp"
    output_dir.mkdir()
    (output_dir / "scan.pdf").write_bytes(b"pdf")
    (output_dir / "partial.tmp").write_bytes(b"partial")
    nested = output_dir / "nested"
    nested.mkdir()
    nested_file = nested / "keep.pdf"
    nested_file.write_bytes(b"nested")

    result = clean_scan_output_dir(output_dir)

    assert result.deleted == 2
    assert result.skipped == 1
    assert result.failed == 0
    assert nested_file.exists()


def test_list_scanned_pdfs_only_lists_pdf_files_newest_first(tmp_path) -> None:
    from KaosEghis.core.scan_service import list_scanned_pdfs

    output_dir = tmp_path / "temp"
    output_dir.mkdir()
    older = output_dir / "202607161400.pdf"
    newer = output_dir / "202607161500.PDF"
    ignored = output_dir / "partial.tmp"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    ignored.write_bytes(b"ignored")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    assert list_scanned_pdfs(output_dir) == [newer, older]


def test_scan_tab_instantiates_with_controls_and_running_cleanup_timer(
    tmp_path,
) -> None:
    _app()

    from KaosEghis.ui.tabs.scan_tab import ScanTab

    db_path = tmp_path / "KaosEghis.sqlite"
    tab = ScanTab(db_path)

    assert tab.scan_button.text() == "Scan to PDF"
    assert tab.clean_button.text() == "Clean now"
    assert tab.view_folder_button.text() == "View folder"
    assert tab.output_dir == tmp_path / "temp"
    assert tab.cleanup_interval.value() == 30
    assert tab.cleanup_timer.isActive() is True
    assert tab.cleanup_timer.interval() == 30 * 60 * 1000
    assert tab.file_list.dragEnabled() is True


def test_scan_preview_starts_wider_than_file_list(tmp_path) -> None:
    app = _app()

    from KaosEghis.ui.tabs.scan_tab import ScanTab

    tab = ScanTab(tmp_path / "KaosEghis.sqlite")
    tab.resize(1260, 800)
    tab.show()
    app.processEvents()

    file_width, preview_width = tab.content_splitter.sizes()

    assert file_width <= 300
    assert preview_width > file_width * 2


def test_cleanup_interval_is_loaded_and_persisted(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, set_settings
    from KaosEghis.ui.tabs.scan_tab import SCAN_CLEANUP_INTERVAL_KEY, ScanTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(connection, {SCAN_CLEANUP_INTERVAL_KEY: "7"})

    tab = ScanTab(db_path)
    assert tab.cleanup_interval.value() == 7
    assert tab.cleanup_timer.interval() == 7 * 60 * 1000

    tab.cleanup_interval.setValue(12)
    tab.apply_cleanup_interval()

    with connect(db_path) as connection:
        settings = get_settings(connection)
    assert settings[SCAN_CLEANUP_INTERVAL_KEY] == "12"
    assert tab.cleanup_timer.interval() == 12 * 60 * 1000


def test_clean_now_removes_visible_temporary_files(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.scan_tab import ScanTab

    tab = ScanTab(tmp_path / "KaosEghis.sqlite")
    pdf_path = tab.output_dir / "202607161500.pdf"
    pdf_path.write_bytes(b"pdf")
    tab.refresh_files()
    assert tab.file_list.count() == 1

    tab.clean_now()

    assert pdf_path.exists() is False
    assert tab.file_list.count() == 0
    assert "removed 1" in tab.status_label.text()


def test_pdf_drag_mime_contains_local_file_url(tmp_path) -> None:
    from KaosEghis.ui.tabs.scan_tab import pdf_file_mime_data

    path = tmp_path / "scan.pdf"
    path.write_bytes(b"pdf")

    urls = pdf_file_mime_data(path).urls()

    assert len(urls) == 1
    assert Path(urls[0].toLocalFile()) == path
