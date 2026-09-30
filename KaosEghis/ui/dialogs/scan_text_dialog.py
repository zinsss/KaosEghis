from __future__ import annotations

from PySide6.QtCore import QProcess, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
    QStyle, QToolButton, QVBoxLayout, QWidget,
)

from KaosEghis.core.scan_ocr import (
    MAX_OCR_DIMENSION, OCR_TIMEOUT_MS, ScanOcrError, encode_ocr_request,
    ocr_process_command, parse_ocr_response,
)


class ScanAreaView(QGraphicsView):
    area_selected = Signal(QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setBackgroundBrush(QColor("#777777"))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._image = QImage()
        self._start = None
        self._selection = None
        self._zoom = 1.0

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.scene().clear()
        self._start = None
        self._selection = None
        if not image.isNull():
            self.scene().addPixmap(QPixmap.fromImage(image))
        self.setSceneRect(QRectF(image.rect()))
        self._zoom = 1.0
        self._apply_zoom()
        self.verticalScrollBar().setValue(0)

    def zoom_by(self, multiplier: float) -> None:
        self._zoom = min(4.0, max(0.5, self._zoom * multiplier))
        self._apply_zoom()

    def fit_width(self) -> None:
        self._zoom = 1.0
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        if not self._image.isNull():
            scale = max(1, self.viewport().width() - 4) / self._image.width() * self._zoom
            self.setTransform(QTransform.fromScale(scale, scale))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_zoom()

    def mousePressEvent(self, event) -> None:
        point = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and self.sceneRect().contains(point):
            self._start = point
            if self._selection is not None:
                self.scene().removeItem(self._selection)
            pen = QPen(QColor("#147ba1"), 2)
            pen.setCosmetic(True)
            self._selection = self.scene().addRect(QRectF(point, point), pen, QColor(20, 123, 161, 40))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None:
            rect = QRectF(self._start, self.mapToScene(event.position().toPoint())).normalized()
            self._selection.setRect(rect.intersected(self.sceneRect()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            rect = QRectF(self._start, self.mapToScene(event.position().toPoint())).normalized()
            rect = rect.intersected(self.sceneRect()).toAlignedRect().intersected(self._image.rect())
            self._start = None
            self._selection.setRect(QRectF(rect))
            if rect.width() >= 8 and rect.height() >= 8:
                self.area_selected.emit(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def selected_image(self, rect: QRect) -> QImage:
        rect = rect.intersected(self._image.rect())
        return self._image.copy(rect) if not rect.isEmpty() else QImage()


class ScanTextDialog(QDialog):
    def __init__(self, document, initial_page: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select scan text")
        self.resize(1160, 820)
        self._document = document
        self._request = b""
        self._stopped = False
        self._busy = False

        self.page_number = QSpinBox()
        self.page_number.setRange(1, max(1, document.pageCount()))
        self.page_number.setValue(min(max(1, initial_page + 1), self.page_number.maximum()))
        self.previous_button = self._icon_button(QStyle.StandardPixmap.SP_ArrowLeft, "Previous page")
        self.next_button = self._icon_button(QStyle.StandardPixmap.SP_ArrowRight, "Next page")
        self.previous_button.clicked.connect(lambda: self.page_number.stepBy(-1))
        self.next_button.clicked.connect(lambda: self.page_number.stepBy(1))
        self.zoom_out_button = QToolButton()
        self.zoom_out_button.setText("-")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.setFixedSize(30, 30)
        self.zoom_in_button = QToolButton()
        self.zoom_in_button.setText("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.setFixedSize(30, 30)
        self.fit_button = self._icon_button(QStyle.StandardPixmap.SP_TitleBarMaxButton, "Fit page width")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Korean", "ko")
        self.language_combo.addItem("English", "en-US")

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.previous_button)
        toolbar.addWidget(self.next_button)
        toolbar.addWidget(QLabel("Page"))
        toolbar.addWidget(self.page_number)
        toolbar.addWidget(QLabel(f"/ {document.pageCount()}"))
        toolbar.addSpacing(12)
        toolbar.addWidget(self.zoom_out_button)
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addWidget(self.fit_button)
        toolbar.addStretch()
        toolbar.addWidget(self.language_combo)

        self.area_view = ScanAreaView()
        self.area_view.setMinimumWidth(280)
        self.area_view.area_selected.connect(self.recognize_area)
        self.zoom_out_button.clicked.connect(lambda: self.area_view.zoom_by(0.8))
        self.zoom_in_button.clicked.connect(lambda: self.area_view.zoom_by(1.25))
        self.fit_button.clicked.connect(self.area_view.fit_width)

        text_panel = QWidget()
        text_panel.setMinimumWidth(260)
        text_layout = QVBoxLayout(text_panel)
        text_layout.setContentsMargins(8, 0, 0, 0)
        text_layout.addWidget(QLabel("Recognized text"))
        warning = QLabel("Check values and units against the scan.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ebcb8b;")
        text_layout.addWidget(warning)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setMinimumWidth(0)
        text_font = self.text_edit.font()
        text_font.setPointSize(max(11, text_font.pointSize()))
        self.text_edit.setFont(text_font)
        text_layout.addWidget(self.text_edit, 1)
        self.append_check = QCheckBox("Append selections")
        text_layout.addWidget(self.append_check)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy selected text, or all recognized text")
        self.copy_button.clicked.connect(self.copy_text)
        self.clear_button = self._icon_button(QStyle.StandardPixmap.SP_TrashIcon, "Clear recognized text")
        self.clear_button.clicked.connect(self.text_edit.clear)
        row = QHBoxLayout()
        row.addWidget(self.copy_button)
        row.addWidget(self.clear_button)
        row.addStretch()
        text_layout.addLayout(row)
        self.text_edit.textChanged.connect(self._update_copy_button)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.area_view)
        self.splitter.addWidget(text_panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([800, 320])

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_recognition)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.stop_button)
        bottom.addWidget(self.close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(bottom)

        self.process = QProcess(self)
        self.process.started.connect(self._send_request)
        self.process.finished.connect(self._recognition_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(OCR_TIMEOUT_MS)
        self.timeout.timeout.connect(self._timed_out)
        self.page_number.valueChanged.connect(self._load_page)
        self._set_busy(False)
        self._load_page()

    def _icon_button(self, icon, tooltip: str) -> QToolButton:
        button = QToolButton()
        pixmap = self.style().standardIcon(icon).pixmap(18, 18)
        if icon != QStyle.StandardPixmap.SP_TrashIcon:
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor("#88c0d0"))
            painter.end()
        button.setIcon(QIcon(pixmap))
        button.setToolTip(tooltip)
        button.setFixedSize(30, 30)
        return button

    def _load_page(self, _value=None) -> None:
        if self._busy:
            return
        self.text_edit.clear()
        page = self.page_number.value() - 1
        points = self._document.pagePointSize(page)
        if points.isEmpty():
            self.area_view.set_image(QImage())
            self.status_label.setText("This PDF page could not be rendered.")
            return
        # Render the source, not a screen grab: small lab values need enough pixels.
        scale = min(300 / 72, 5000 / max(points.width(), points.height()))
        size = QSize(max(1, round(points.width() * scale)), max(1, round(points.height() * scale)))
        image = self._document.render(page, size)
        self.area_view.set_image(image)
        self.status_label.setText("Ready." if not image.isNull() else "This PDF page could not be rendered.")
        self._set_busy(False)

    def recognize_area(self, rect: QRect) -> None:
        if self._busy:
            return
        if not self.append_check.isChecked():
            self.text_edit.clear()
        image = self.area_view.selected_image(rect)
        if image.isNull():
            return
        if max(image.width(), image.height()) > MAX_OCR_DIMENSION:
            image = image.scaled(MAX_OCR_DIMENSION, MAX_OCR_DIMENSION,
                                 Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        try:
            program, arguments = ocr_process_command()
            self._request = encode_ocr_request(bytes(image.constBits()), image.width(), image.height(), self.language_combo.currentData())
        except ScanOcrError as exc:
            self.status_label.setText(str(exc))
            return
        self._stopped = False
        self._set_busy(True)
        self.status_label.setText("Recognizing selected area...")
        self.process.setProgram(program)
        self.process.setArguments(arguments)
        self.timeout.start()
        self.process.start()

    def _send_request(self) -> None:
        if self._stopped:
            self.process.kill()
            self._request = b""
            return
        self.process.write(self._request)
        self.process.closeWriteChannel()
        self._request = b""

    def _recognition_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.timeout.stop()
        output = bytes(self.process.readAllStandardOutput())
        self.process.readAllStandardError()
        self._request = b""
        self._set_busy(False)
        if self._stopped:
            return
        try:
            text = parse_ocr_response(output)
            if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
                raise ScanOcrError("Local OCR did not finish successfully. Try again.")
        except ScanOcrError as exc:
            self.status_label.setText(str(exc))
            return
        if not text:
            self.status_label.setText("No text found in this area.")
            return
        if self.append_check.isChecked() and self.text_edit.toPlainText().strip():
            self.text_edit.appendPlainText(text)
        else:
            self.text_edit.setPlainText(text)
        self.status_label.setText("Text recognized. Verify values before copying.")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self._request = b""
            self._set_busy(False)
            self.status_label.setText("Local OCR could not start. Windows PowerShell is required.")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (self.area_view, self.page_number, self.language_combo, self.append_check, self.text_edit,
                       self.zoom_in_button, self.zoom_out_button, self.fit_button, self.clear_button):
            widget.setEnabled(not busy)
        self.previous_button.setEnabled(not busy and self.page_number.value() > 1)
        self.next_button.setEnabled(not busy and self.page_number.value() < self.page_number.maximum())
        self.stop_button.setEnabled(busy)
        self._update_copy_button()

    def _update_copy_button(self) -> None:
        self.copy_button.setEnabled(not self._busy and bool(self.text_edit.toPlainText().strip()))

    def copy_text(self) -> None:
        if self._busy:
            return
        cursor = self.text_edit.textCursor()
        text = cursor.selectedText().replace("\u2029", "\n") if cursor.hasSelection() else self.text_edit.toPlainText()
        if text.strip():
            QApplication.clipboard().setText(text)
            self.status_label.setText("Copied.")

    def stop_recognition(self) -> None:
        self._stopped = True
        self._request = b""
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        self.status_label.setText("Recognition stopped.")

    def _timed_out(self) -> None:
        self.stop_recognition()
        self.status_label.setText("Recognition timed out. Try a smaller area.")

    def done(self, result: int) -> None:
        self.stop_recognition()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.waitForFinished(1000)
        self.text_edit.clear()
        self.area_view.set_image(QImage())
        super().done(result)
