import base64
import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess, QPoint, QRect, QRectF, QSizeF, Qt
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from KaosEghis.core.scan_ocr import ScanOcrError, encode_ocr_request, parse_ocr_response
from KaosEghis.ui.dialogs import scan_text_dialog


class FakeDocument:
    def pageCount(self):
        return 2

    def pagePointSize(self, _page):
        return QSizeF(300, 400)

    def render(self, page, size):
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill("white" if page == 0 else "yellow")
        return image


class FakeProcess:
    def __init__(self):
        self.program = ""
        self.arguments = []
        self.writes = []
        self.closed = False
        self.started = False
        self.killed = False
        self.output = b'{"ok":true,"text":"Glucose 123 mg/dL"}'

    def setProgram(self, value):
        self.program = value

    def setArguments(self, value):
        self.arguments = value

    def start(self):
        self.started = True

    def write(self, value):
        self.writes.append(value)

    def closeWriteChannel(self):
        self.closed = True

    def kill(self):
        self.killed = True

    def waitForFinished(self, _timeout):
        self.started = False
        return True

    def state(self):
        return QProcess.ProcessState.Running if self.started and not self.killed else QProcess.ProcessState.NotRunning

    def readAllStandardOutput(self):
        return self.output

    def readAllStandardError(self):
        return b""


@pytest.fixture
def dialog(monkeypatch):
    app = QApplication.instance() or QApplication([])
    widget = scan_text_dialog.ScanTextDialog(FakeDocument())
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.process = FakeProcess()
    monkeypatch.setattr(scan_text_dialog, "ocr_process_command", lambda: ("local-ocr", ["static-script"]))
    copied = []
    monkeypatch.setattr(scan_text_dialog.QApplication, "clipboard", lambda: SimpleNamespace(setText=copied.append))
    yield widget, copied
    widget.done(0)
    widget.deleteLater()
    app.processEvents()


def finish(dialog, text="Glucose 123 mg/dL"):
    dialog.process.output = json.dumps({"ok": True, "text": text}).encode()
    dialog._recognition_finished(0, QProcess.ExitStatus.NormalExit)


def test_request_uses_json_stdin_pixels_not_shell_code():
    data = json.loads(encode_ocr_request(b"\xff" * 24, 3, 2, "ko"))
    assert data == {"width": 3, "height": 2, "language": "ko", "pixels": base64.b64encode(b"\xff" * 24).decode()}


@pytest.mark.parametrize("width,height,pixels,language", [(0, 1, b"", "ko"), (2401, 1, b"", "ko"),
                                                        (2, 2, b"invalid", "ko"), (1, 1, b"1234", "bad;command")])
def test_bad_request_is_rejected(width, height, pixels, language):
    with pytest.raises(ScanOcrError):
        encode_ocr_request(pixels, width, height, language)


def test_response_preserves_numbers_signs_and_units_without_correction():
    text = "Glucose 123 mg/dL\nHbA1c 5.7 %\nT-score -2.1"
    assert parse_ocr_response(json.dumps({"ok": True, "text": text}).encode()) == text


def test_columns_are_reassembled_by_visible_rows_not_engine_column_order():
    words = [
        {"text": text, "x": x, "y": y, "width": width, "height": 20}
        for text, x, y, width in [
            ("Glucose", 0, 0, 70), ("HbA1c", 0, 50, 50),
            ("123", 200, 1, 30), ("5.7", 200, 52, 30),
            ("mg/dL", 300, 0, 50), ("%", 300, 50, 15),
        ]
    ]
    response = {"ok": True, "text": "column order", "words": words}
    assert parse_ocr_response(json.dumps(response).encode()) == "Glucose  123  mg/dL\nHbA1c  5.7  %"


@pytest.mark.parametrize("words", [[None], [{"text": "bad"}], "bad", [{"text": "bad", "x": 0, "y": float('nan'), "width": 2, "height": 2}]])
def test_invalid_word_geometry_is_rejected(words):
    with pytest.raises(ScanOcrError, match="word positions"):
        parse_ocr_response(json.dumps({"ok": True, "text": "not used", "words": words}).encode())


@pytest.mark.parametrize("response", [b"private provider details", b"null", b'[]', b'{"ok":true,"text":123}',
                                     b'{"ok":false,"error":"private provider details"}'])
def test_bad_response_has_safe_error_without_raw_details(response):
    with pytest.raises(ScanOcrError) as error:
        parse_ocr_response(response)
    assert "private provider details" not in str(error.value)


def test_missing_language_has_actionable_error():
    with pytest.raises(ScanOcrError, match="language is not installed"):
        parse_ocr_response(b'{"ok":false,"error":"language_unavailable"}')


def test_selection_starts_one_local_process_and_keeps_clipboard_unchanged(dialog):
    widget, copied = dialog
    widget.recognize_area(QRect(10, 20, 300, 150))
    assert widget._busy
    assert not widget.copy_button.isEnabled()
    assert not widget.page_number.isEnabled()
    assert widget.process.started
    widget._send_request()
    request = json.loads(widget.process.writes[0])
    assert (request["width"], request["height"], request["language"]) == (300, 150, "ko")
    assert widget.process.arguments == ["static-script"]
    assert widget.process.closed and widget._request == b""
    finish(widget)
    assert widget.text_edit.toPlainText() == "Glucose 123 mg/dL"
    assert widget.copy_button.isEnabled()
    assert copied == []


def test_copy_uses_reviewed_text_or_highlighted_subset(dialog):
    widget, copied = dialog
    widget.text_edit.setPlainText("Glucose 123\nHbA1c 5.7")
    widget.copy_text()
    assert copied[-1] == "Glucose 123\nHbA1c 5.7"
    cursor = widget.text_edit.textCursor()
    cursor.setPosition(8)
    cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
    widget.text_edit.setTextCursor(cursor)
    widget.copy_text()
    assert copied[-1] == "123\nHbA1c 5.7"


def test_second_selection_replaces_unless_append_is_checked(dialog):
    widget, _copied = dialog
    widget.text_edit.setPlainText("OLD")
    widget.recognize_area(QRect(0, 0, 300, 100))
    assert widget.text_edit.toPlainText() == ""
    finish(widget, "NEW")
    widget.append_check.setChecked(True)
    widget.recognize_area(QRect(0, 100, 300, 100))
    finish(widget, "NEXT")
    assert widget.text_edit.toPlainText() == "NEW\nNEXT"


def test_page_change_clears_previous_text(dialog):
    widget, _copied = dialog
    widget.text_edit.setPlainText("PREVIOUS PAGE")
    widget.page_number.setValue(2)
    assert not widget.copy_button.isEnabled()
    assert widget.text_edit.toPlainText() == ""
    assert not widget.next_button.isEnabled()
    assert widget.previous_button.isEnabled()


@pytest.mark.parametrize("stop", ["manual", "timeout", "close"])
def test_stop_discards_late_results_and_never_copies(dialog, stop):
    widget, copied = dialog
    widget.recognize_area(QRect(0, 0, 300, 100))
    if stop == "manual":
        widget.stop_recognition()
    elif stop == "timeout":
        widget._timed_out()
    else:
        widget.done(0)
    assert widget.process.killed and widget._request == b""
    finish(widget, "LATE RESULT")
    assert widget.text_edit.toPlainText() == ""
    assert copied == []
    assert not widget._busy


def test_failure_clears_busy_and_does_not_restore_previous_text(dialog):
    widget, _copied = dialog
    widget.text_edit.setPlainText("OLD")
    widget.recognize_area(QRect(0, 0, 300, 100))
    widget.process.output = b'{"ok":false,"error":"ocr_failed"}'
    widget._recognition_finished(1, QProcess.ExitStatus.NormalExit)
    assert "failed" in widget.status_label.text()
    assert not widget._busy and not widget.copy_button.isEnabled()


def test_start_error_and_empty_result_are_visible(dialog):
    widget, _copied = dialog
    widget.recognize_area(QRect(0, 0, 300, 100))
    widget._process_error(QProcess.ProcessError.FailedToStart)
    assert "could not start" in widget.status_label.text()
    assert not widget._busy
    widget.recognize_area(QRect(0, 0, 300, 100))
    finish(widget, "")
    assert "No text found" in widget.status_label.text()
    assert not widget.copy_button.isEnabled()


def test_area_drag_maps_back_to_source_pixels_at_zoom_and_scroll(dialog):
    widget, _copied = dialog
    widget.show()
    QApplication.processEvents()
    view = widget.area_view
    view.area_selected.disconnect()
    selected = []
    view.area_selected.connect(selected.append)
    view.zoom_by(1.25)
    view.verticalScrollBar().setValue(130)
    QApplication.processEvents()
    start = QPoint(30, 40)
    end = QPoint(200, 180)
    expected = QRectF(view.mapToScene(start), view.mapToScene(end)).normalized().toAlignedRect()
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert selected == [expected]
    image = view.selected_image(selected[0])
    assert image.size() == expected.size()


def test_small_drag_does_not_start_recognition(dialog):
    widget, _copied = dialog
    widget.show()
    QApplication.processEvents()
    QTest.mouseClick(widget.area_view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
    assert not widget.process.started


def test_cleanup_is_deferred_during_text_review(tmp_path):
    from KaosEghis.ui.tabs.scan_tab import ScanTab

    app = QApplication.instance() or QApplication([])
    tab = ScanTab(tmp_path / "test.sqlite")
    sample = tab.output_dir / "sample.pdf"
    sample.write_bytes(b"test")
    tab._text_dialog = object()
    tab._automatic_cleanup()
    assert sample.exists()
    assert "text is being reviewed" in tab.status_label.text()
    tab._text_dialog = None
    tab.cleanup_timer.stop()
    tab.deleteLater()
    app.processEvents()


def test_scan_button_disabled_without_readable_pdf(tmp_path):
    from KaosEghis.ui.tabs.scan_tab import ScanTab

    app = QApplication.instance() or QApplication([])
    tab = ScanTab(tmp_path / "test.sqlite")
    assert not tab.select_text_button.isEnabled()
    tab.select_scan_text()
    assert "readable PDF" in tab.status_label.text()
    tab.cleanup_timer.stop()
    tab.deleteLater()
    app.processEvents()


def test_text_review_prevents_scan_or_document_replacement(tmp_path, monkeypatch):
    from KaosEghis.ui.tabs.scan_tab import ScanTab

    app = QApplication.instance() or QApplication([])
    tab = ScanTab(tmp_path / "test.sqlite")
    tab._text_dialog = object()
    monkeypatch.setattr(tab, "_close_preview", lambda: pytest.fail("Must retain the reviewed document"))
    tab.start_scan()
    assert "Close text review" in tab.status_label.text()
    tab.refresh_files()
    assert tab.scan_process.state() == QProcess.ProcessState.NotRunning
    tab._text_dialog = None
    tab.cleanup_timer.stop()
    tab.deleteLater()
    app.processEvents()


def test_scanning_blocks_text_review_of_old_pdf(tmp_path):
    from KaosEghis.ui.tabs.scan_tab import ScanTab

    app = QApplication.instance() or QApplication([])
    tab = ScanTab(tmp_path / "test.sqlite")
    tab._pdf_document = FakeDocument()
    tab.scan_process = SimpleNamespace(state=lambda: QProcess.ProcessState.Running)
    tab._update_text_button()
    assert not tab.select_text_button.isEnabled()
    tab.select_scan_text()
    assert tab._text_dialog is None
    assert "Wait for the current scan" in tab.status_label.text()
    tab.cleanup_timer.stop()
    tab.deleteLater()
    app.processEvents()


def test_real_pdf_preview_opens_text_review_and_keeps_original_bytes(tmp_path, monkeypatch):
    from PySide6.QtCore import QBuffer, QIODevice, QTimer
    from PySide6.QtGui import QPainter, QPdfWriter
    from KaosEghis.ui.tabs.scan_tab import ScanTab

    app = QApplication.instance() or QApplication([])
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    writer = QPdfWriter(buffer)
    writer.setResolution(72)
    painter = QPainter(writer)
    painter.drawText(40, 50, "Synthetic report: Glucose 123 mg/dL")
    painter.end()
    del writer
    original = bytes(buffer.data())
    buffer.close()

    tab = ScanTab(tmp_path / "test.sqlite")
    path = tab.output_dir / "sample.pdf"
    path.write_bytes(original)
    tab.refresh_files(select_path=path)
    app.processEvents()
    assert tab.select_text_button.isEnabled()
    opened = []
    real_dialog = scan_text_dialog.ScanTextDialog

    class HiddenReview(real_dialog):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            opened.append(self.page_number.value())
            assert not self.area_view._image.isNull()
            QTimer.singleShot(0, self.reject)

    monkeypatch.setattr(scan_text_dialog, "ScanTextDialog", HiddenReview)
    tab.select_scan_text()
    assert opened == [1] and tab._text_dialog is None
    assert tab._pdf_document.pageCount() == 1
    assert path.read_bytes() == original
    tab._close_preview()
    assert not tab.select_text_button.isEnabled()
    tab.cleanup_timer.stop()
    tab.deleteLater()
    app.processEvents()
