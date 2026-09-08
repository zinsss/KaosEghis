import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_vaccine_tables_and_seed_types_are_created(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_settings, list_vaccine_types

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        vaccine_types = list_vaccine_types(connection)
        settings = get_settings(connection)

    assert "vaccine_types" in tables
    assert "vaccine_records" in tables
    assert "vaccine_audit_events" in tables
    assert [entry.name for entry in vaccine_types[:2]] == ["Influenza", "COVID-19"]
    assert [entry.program_type for entry in vaccine_types[:2]] == [
        "national_influenza",
        "national_covid",
    ]
    assert '"influenza"' in settings["vaccine_schedule_rules_json"]
    assert '"elderly_75_plus"' in settings["vaccine_age_groups_json"]
    assert settings["vaccine_label_printer_name"] == "4BARCODE 4B-2054L"


def test_vaccine_label_printer_reports_unavailable_printer_without_printing(
    monkeypatch,
) -> None:
    from datetime import datetime

    import KaosEghis.core.printer_service as printer_service

    class _FakePrinter:
        class PrinterMode:
            HighResolution = object()

        class OutputFormat:
            NativeFormat = object()

        class Unit:
            DevicePixel = object()

        def __init__(self, _mode) -> None:
            self.begin_called = False

        def setPrinterName(self, _name) -> None:
            pass

        def setOutputFormat(self, _format) -> None:
            pass

        def setFullPage(self, _full_page) -> None:
            pass

        def setPageSize(self, _page_size) -> None:
            pass

        def setPageMargins(self, _margins, _unit) -> None:
            pass

        def isValid(self) -> bool:
            return False

    monkeypatch.setattr(printer_service, "QPrinter", _FakePrinter)
    content = printer_service.VaccineLabelContent(
        vaccine_name="Test vaccine",
        patient_name="Test patient",
        chart_no="1",
        resident_id="",
        phone="",
        printed_at=datetime(2026, 9, 8, 10, 0),
    )

    result = printer_service.print_vaccine_label(content, printer_name="Missing")

    assert result.success is False
    assert result.message == "Vaccine label printer is unavailable."


def test_vaccine_label_printer_renders_to_an_available_native_printer(monkeypatch) -> None:
    from datetime import datetime

    from PySide6.QtCore import QRect

    import KaosEghis.core.printer_service as printer_service

    class _FakePrinter:
        class PrinterMode:
            HighResolution = object()

        class OutputFormat:
            NativeFormat = object()

        class Unit:
            DevicePixel = object()

        def __init__(self, _mode) -> None:
            self.printer_name = ""
            self.page_size = None
            self.page_margins = None

        def setPrinterName(self, name) -> None:
            self.printer_name = name

        def setOutputFormat(self, _format) -> None:
            pass

        def setFullPage(self, _full_page) -> None:
            pass

        def setPageSize(self, page_size) -> None:
            self.page_size = page_size

        def setPageMargins(self, margins, unit) -> None:
            self.page_margins = (margins, unit)

        def isValid(self) -> bool:
            return True

        def pageRect(self, _unit):
            return QRect(0, 0, 800, 400)

    class _FakePainter:
        began = False
        ended = False

        def begin(self, _printer) -> bool:
            type(self).began = True
            return True

        def end(self) -> None:
            type(self).ended = True

    rendered = []
    monkeypatch.setattr(printer_service, "QPrinter", _FakePrinter)
    monkeypatch.setattr(printer_service, "QPainter", _FakePainter)
    monkeypatch.setattr(
        printer_service,
        "_paint_vaccine_label",
        lambda _painter, rect, content: rendered.append((rect, content)),
    )
    content = printer_service.VaccineLabelContent(
        vaccine_name="Influenza",
        patient_name="Test patient",
        chart_no="1",
        resident_id="000000-0000000",
        phone="010-0000-0000",
        printed_at=datetime(2026, 9, 8, 10, 0),
    )

    result = printer_service.print_vaccine_label(
        content,
        printer_name="4BARCODE 4B-2054L",
    )

    assert result.success is True
    assert _FakePainter.began is True
    assert _FakePainter.ended is True
    assert rendered[0][0].width() == 800
    assert rendered[0][0].height() == 400
    assert rendered[0][1] == content


def test_vaccine_label_layout_renders_korean_text() -> None:
    from datetime import datetime

    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from KaosEghis.core.printer_service import (
        VaccineLabelContent,
        _paint_vaccine_label,
    )

    _app()
    image = QImage(800, 400, QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    _paint_vaccine_label(
        painter,
        QRectF(0, 0, 800, 400),
        VaccineLabelContent(
            vaccine_name="인플루엔자",
            patient_name="홍길동",
            chart_no="2735",
            resident_id="700101-1234567",
            phone="010-0000-0000",
            printed_at=datetime(2026, 9, 8, 10, 0),
            count_summary="1/100",
        ),
    )
    painter.end()

    assert image.pixelColor(400, 190).alpha() == 255


def test_legacy_vaccine_records_migrate_without_becoming_completed(tmp_path) -> None:
    import sqlite3

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import get_today_vaccine_counts, list_vaccine_records

    db_path = tmp_path / "KaosEghis.sqlite"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE vaccine_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT,
            chart_note_template TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE vaccine_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaccine_type_id INTEGER,
            vaccine_type_name TEXT NOT NULL,
            patient_chart_no TEXT,
            patient_resident_id TEXT,
            patient_name TEXT,
            patient_sex TEXT,
            patient_age TEXT,
            patient_phone TEXT,
            patient_address TEXT,
            status TEXT NOT NULL DEFAULT 'prepared',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO vaccine_types (name, code, sort_order)
        VALUES ('Influenza', 'flu', 1);
        INSERT INTO vaccine_records (
            vaccine_type_id, vaccine_type_name, patient_name, status, created_at
        )
        VALUES (1, 'Influenza', 'Legacy Patient', 'prepared', '2026-09-08 09:00:00');
        """
    )
    connection.commit()
    connection.close()

    initialize_database(db_path)
    with connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(vaccine_records)"
            ).fetchall()
        }
        record = list_vaccine_records(connection)[0]
        counts = get_today_vaccine_counts(connection, "2026-09-08")

    assert {
        "program_type",
        "counts_toward_cap",
        "counted_bucket",
        "completed_on",
        "completed_at",
        "cancelled_at",
    } <= columns
    assert record.program_type == "national_influenza"
    assert record.status == "prepared"
    assert record.counts_toward_cap is False
    assert counts == {"flu": 0, "covid": 0}


def test_vaccine_type_and_record_crud(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        create_vaccine_type,
        delete_vaccine_record,
        delete_vaccine_type,
        get_vaccine_record,
        list_vaccine_records,
        list_vaccine_types,
        reorder_vaccine_types,
        update_vaccine_record,
        update_vaccine_type,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        vaccine_type = create_vaccine_type(
            connection,
            name="Tdap",
            code="tdap",
            chart_note_template="Tdap 시행함.",
        )
        updated_type = update_vaccine_type(
            connection,
            vaccine_type.id,
            name="Tdap Updated",
            code="tdap2",
            chart_note_template="Tdap updated.",
            is_active=False,
        )
        ordered = reorder_vaccine_types(
            connection,
            [entry.id for entry in reversed(list_vaccine_types(connection))],
        )
        record = create_vaccine_record(
            connection,
            vaccine_type_id=vaccine_type.id,
            vaccine_type_name="Tdap Updated",
            patient_chart_no="2735",
            patient_resident_id="700101-1234567",
            patient_name="홍길동",
            patient_sex="M",
            patient_age="56",
            patient_phone="010-1111-2222",
            patient_address="Seoul",
        )
        updated_record = update_vaccine_record(
            connection,
            record.id,
            vaccine_type_id=vaccine_type.id,
            vaccine_type_name="Tdap Updated",
            patient_chart_no="2735",
            patient_resident_id="700101-1234567",
            patient_name="김민수",
            patient_sex="M",
            patient_age="57",
            patient_phone="010-3333-4444",
            patient_address="Busan",
            status="prepared",
        )
        listed_records = list_vaccine_records(connection)
        fetched_record = get_vaccine_record(connection, record.id)
        deleted_record = delete_vaccine_record(connection, record.id)
        deleted_type = delete_vaccine_type(connection, vaccine_type.id)

    assert updated_type is not None
    assert updated_type.name == "Tdap Updated"
    assert updated_type.is_active is False
    assert ordered
    assert updated_record is not None
    assert updated_record.patient_name == "김민수"
    assert fetched_record is not None
    assert fetched_record.patient_phone == "010-3333-4444"
    assert listed_records
    assert deleted_record is True
    assert deleted_type is True


def test_vaccine_type_dialog_records_program_classification() -> None:
    _app()

    from KaosEghis.ui.tabs.vaccine_tab import VaccineTypeDialog

    dialog = VaccineTypeDialog()
    assert dialog.program_type_combo.currentData() == "general"

    dialog.program_type_combo.setCurrentIndex(
        dialog.program_type_combo.findData("national_influenza")
    )

    assert dialog.values()["program_type"] == "national_influenza"


def test_vaccine_tab_fetches_patient_context_from_emr_targets(tmp_path, monkeypatch) -> None:
    _app()

    from types import SimpleNamespace

    from KaosEghis.core.vaccine_patient_context import (
        VaccinePatientContext,
        VaccinePatientFetchResult,
    )
    from KaosEghis.db.database import initialize_database
    import KaosEghis.ui.tabs.vaccine_tab as vaccine_tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    class _Profile:
        id = 1
        process_name = "eGhis.exe"
        window_title_contains = "이지스 전자차트 2.0"
        executable_path = r"C:\eghis\eGhis.exe"
        main_window_automation_id = "MdiMain"
        patient_status_tab_automation_id = "tabProc"
        prescription_grid_automation_id = "tree처방"
        symptom_grid_automation_id = "grdSymp"
        diagnosis_grid_automation_id = "tree상병"
        patient_list_grid_automation_id = "grdOpdList"

    monkeypatch.setattr(
        vaccine_tab_module,
        "get_active_emr_target_profile",
        lambda connection: _Profile(),
    )
    monkeypatch.setattr(vaccine_tab_module, "get_settings", lambda connection: {})
    monkeypatch.setattr(
        vaccine_tab_module,
        "get_emr_ui_target_by_key",
        lambda connection, profile_id, target_key: SimpleNamespace(
            automation_id=f"id-{target_key}",
        ),
    )
    monkeypatch.setattr(
        vaccine_tab_module,
        "fetch_vaccine_patient_context",
        lambda settings, targets: VaccinePatientFetchResult(
            success=True,
            message="Loaded patient context from EMR.",
            context=VaccinePatientContext(
                chart_no="2735",
                resident_id="700101-1234567",
                patient_name="홍길동",
                patient_sex="M",
                patient_age="56",
                patient_birth_date="1970-01-01",
                patient_phone="010-1111-2222",
                patient_address="Seoul",
            ),
        ),
    )

    page = vaccine_tab_module.VaccineTab(db_path)

    assert page.fetch_current_patient_from_emr() is True
    assert page.patient_name_input.text() == "홍길동"
    assert page.patient_resident_id_input.text() == "700101-1234567"
    assert "Resident No: 700101-1234567" in page.label_preview.toPlainText()
    assert page.patient_birth_date_input.text() == "1970-01-01"
    assert page.patient_phone_input.text() == "010-1111-2222"


def test_today_vaccine_counts_use_only_today_rows(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        get_today_vaccine_counts,
        list_vaccine_types,
        mark_vaccine_record_completed,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    with connect(db_path) as connection:
        vaccine_types = {entry.name: entry for entry in list_vaccine_types(connection)}
        flu_type = vaccine_types["Influenza"]
        covid_type = vaccine_types["COVID-19"]
        flu_record = create_vaccine_record(
            connection,
            vaccine_type_id=flu_type.id,
            vaccine_type_name=flu_type.name,
            patient_name="홍길동",
        )
        covid_record = create_vaccine_record(
            connection,
            vaccine_type_id=covid_type.id,
            vaccine_type_name=covid_type.name,
            patient_name="김민수",
        )
        mark_vaccine_record_completed(
            connection,
            flu_record.id,
            completed_at="2026-08-09T08:00:00+09:00",
        )
        mark_vaccine_record_completed(
            connection,
            covid_record.id,
            completed_at="2026-08-10T08:00:00+09:00",
        )
        counts = get_today_vaccine_counts(connection, "2026-08-10")

    assert counts == {"flu": 0, "covid": 1}


def test_only_completed_counted_national_records_increment_daily_count(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        create_vaccine_type,
        get_today_vaccine_counts,
        list_vaccine_audit_events,
        list_vaccine_types,
        mark_vaccine_record_cancelled,
        mark_vaccine_record_completed,
        mark_vaccine_record_printed,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        vaccine_types = {entry.name: entry for entry in list_vaccine_types(connection)}
        flu_type = vaccine_types["Influenza"]
        covid_type = vaccine_types["COVID-19"]
        private_flu_type = create_vaccine_type(
            connection,
            name="Private Influenza",
            code="private-flu",
            program_type="general",
        )
        prepared_flu = create_vaccine_record(
            connection,
            vaccine_type_id=flu_type.id,
            vaccine_type_name=flu_type.name,
            patient_name="Prepared Patient",
        )
        completed_flu = create_vaccine_record(
            connection,
            vaccine_type_id=flu_type.id,
            vaccine_type_name=flu_type.name,
            patient_name="Counted Patient",
        )
        private_flu = create_vaccine_record(
            connection,
            vaccine_type_id=private_flu_type.id,
            vaccine_type_name=private_flu_type.name,
            patient_name="Private Patient",
        )
        completed_covid = create_vaccine_record(
            connection,
            vaccine_type_id=covid_type.id,
            vaccine_type_name=covid_type.name,
            patient_name="COVID Patient",
        )

        assert get_today_vaccine_counts(connection, "2026-09-08") == {
            "flu": 0,
            "covid": 0,
        }
        mark_vaccine_record_printed(connection, prepared_flu.id)
        mark_vaccine_record_completed(
            connection,
            completed_flu.id,
            completed_at="2026-09-08T09:00:00+09:00",
        )
        first_completion = mark_vaccine_record_completed(
            connection,
            completed_flu.id,
            completed_at="2026-09-09T09:00:00+09:00",
        )
        mark_vaccine_record_completed(
            connection,
            private_flu.id,
            completed_at="2026-09-08T09:05:00+09:00",
        )
        mark_vaccine_record_completed(
            connection,
            completed_covid.id,
            completed_at="2026-09-08T09:10:00+09:00",
        )
        counts_after_completion = get_today_vaccine_counts(connection, "2026-09-08")
        mark_vaccine_record_cancelled(
            connection,
            completed_flu.id,
            cancelled_at="2026-09-08T10:00:00+09:00",
        )
        counts_after_correction = get_today_vaccine_counts(connection, "2026-09-08")
        audit_events = list_vaccine_audit_events(connection, limit=100)

    assert first_completion is not None
    assert first_completion.completed_on == "2026-09-08"
    assert counts_after_completion == {"flu": 1, "covid": 1}
    assert counts_after_correction == {"flu": 0, "covid": 1}
    for patient_name in ("Prepared Patient", "Counted Patient", "Private Patient"):
        assert all(patient_name not in event.summary for event in audit_events)
    assert any(event.event_type == "completed" for event in audit_events)
    assert any(event.event_type == "cancelled" for event in audit_events)


def test_vaccine_db_actions_complete_and_cancel_explicitly(
    tmp_path,
    monkeypatch,
) -> None:
    _app()

    from PySide6.QtWidgets import QMessageBox

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_record,
        get_today_vaccine_counts,
        get_vaccine_record,
        list_vaccine_types,
    )
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        flu_type = next(
            entry for entry in list_vaccine_types(connection) if entry.name == "Influenza"
        )
        record = create_vaccine_record(
            connection,
            vaccine_type_id=flu_type.id,
            vaccine_type_name=flu_type.name,
            patient_name="Test Patient",
        )

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    page = VaccineTab(db_path)
    page.flu_records_table.selectRow(0)
    page.mark_selected_record_completed()

    with connect(db_path) as connection:
        completed = get_vaccine_record(connection, record.id)
        completed_counts = get_today_vaccine_counts(
            connection,
            completed.completed_on,
        )

    assert completed is not None
    assert completed.status == "completed"
    assert completed_counts["flu"] == 1

    page.flu_records_table.selectRow(0)
    page.cancel_selected_record()

    with connect(db_path) as connection:
        cancelled = get_vaccine_record(connection, record.id)
        cancelled_counts = get_today_vaccine_counts(
            connection,
            completed.completed_on,
        )

    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled_counts["flu"] == 0


def test_successful_label_print_completes_record_once_and_reprint_does_not_count(
    tmp_path,
    monkeypatch,
) -> None:
    _app()

    from KaosEghis.core.printer_service import VaccineLabelPrintResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_type,
        get_today_vaccine_counts,
        list_vaccine_records,
    )
    import KaosEghis.ui.tabs.vaccine_tab as vaccine_tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_vaccine_type(
            connection,
            name="Tdap",
            code="tdap",
            program_type="general",
        )

    printed = []
    monkeypatch.setattr(
        vaccine_tab_module,
        "print_vaccine_label",
        lambda content, *, printer_name: (
            printed.append((content, printer_name))
            or VaccineLabelPrintResult(True, "Vaccine label printed.")
        ),
    )
    page = vaccine_tab_module.VaccineTab(db_path)
    page._select_vaccine_type(None, "Tdap")
    page.patient_name_input.setText("Test patient")
    page.patient_chart_no_input.setText("2735")
    page.patient_resident_id_input.setText("700101-1234567")

    page.print_label()

    with connect(db_path) as connection:
        record = list_vaccine_records(connection)[0]
        counts_after_first_print = get_today_vaccine_counts(
            connection, record.completed_on
        )
    assert record.status == "completed"
    assert counts_after_first_print == {"flu": 0, "covid": 0}
    assert len(printed) == 1

    page.print_label()

    with connect(db_path) as connection:
        reprinted = list_vaccine_records(connection)[0]
        counts_after_reprint = get_today_vaccine_counts(
            connection, reprinted.completed_on
        )
    assert reprinted.status == "completed"
    assert counts_after_reprint == {"flu": 0, "covid": 0}
    assert len(printed) == 2


def test_failed_label_print_does_not_complete_or_count_record(tmp_path, monkeypatch) -> None:
    _app()

    from KaosEghis.core.printer_service import VaccineLabelPrintResult
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_vaccine_type,
        get_today_vaccine_counts,
        list_vaccine_records,
    )
    import KaosEghis.ui.tabs.vaccine_tab as vaccine_tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_vaccine_type(
            connection,
            name="Tdap",
            code="tdap",
            program_type="general",
        )
    monkeypatch.setattr(
        vaccine_tab_module,
        "print_vaccine_label",
        lambda *_args, **_kwargs: VaccineLabelPrintResult(
            False, "Vaccine label printer is unavailable."
        ),
    )
    page = vaccine_tab_module.VaccineTab(db_path)
    page._select_vaccine_type(None, "Tdap")
    page.patient_name_input.setText("Test patient")
    page.patient_chart_no_input.setText("2735")

    page.print_label()

    with connect(db_path) as connection:
        record = list_vaccine_records(connection)[0]
        counts = get_today_vaccine_counts(connection, "2026-09-08")
    assert record.status == "prepared"
    assert counts == {"flu": 0, "covid": 0}
    assert page.status_label.text() == "Vaccine label printer is unavailable."


def test_vaccine_tab_uses_single_structured_program_settings(tmp_path) -> None:
    _app()
    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineTab(db_path)

    settings_page = page.settings_page
    assert settings_page.tabs.tabText(0) == "Influenza schedule"
    assert settings_page.tabs.tabText(1) == "COVID schedule"
    assert not hasattr(settings_page.influenza_editor, "season_combo")
    assert not hasattr(settings_page.influenza_editor, "duplicate_button")


def test_vaccine_tab_uses_three_internal_pages(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    page = VaccineTab(db_path)

    assert page.TOP_PAGES == ["Main", "DB", "Settings"]
    assert page.stacked_widget.count() == 3
    assert set(page.nav_buttons) == {"Main", "DB", "Settings"}
    assert page.print_button.text() == "Print label"
    assert page.settings_page.printer_name_input.text() == "4BARCODE 4B-2054L"


def test_vaccine_tab_db_buckets_split_records_by_type(tmp_path) -> None:
    _app()

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_vaccine_record, create_vaccine_type
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_vaccine_record(
            connection,
            vaccine_type_id=None,
            vaccine_type_name="Influenza",
            patient_name="홍길동",
        )
        create_vaccine_record(
            connection,
            vaccine_type_id=None,
            vaccine_type_name="COVID-19",
            patient_name="김민수",
        )
        tdap = create_vaccine_type(connection, name="Tdap", code="tdap")
        create_vaccine_record(
            connection,
            vaccine_type_id=tdap.id,
            vaccine_type_name="Tdap",
            patient_name="박지훈",
        )

    page = VaccineTab(db_path)

    assert page.flu_records_table.rowCount() == 1
    assert page.covid_records_table.rowCount() == 1
    assert page.general_records_table.rowCount() == 1
