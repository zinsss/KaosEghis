from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QMimeData, QProcess, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.scan_service import (
    DEFAULT_CLEANUP_INTERVAL_MINUTES,
    DEFAULT_NAPS2_PROFILE,
    clean_scan_output_dir,
    discard_failed_scan,
    get_scan_output_dir,
    list_scanned_pdfs,
    prepare_scan_command,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings, set_settings


SCAN_CLEANUP_INTERVAL_KEY = "scan_cleanup_interval_minutes"


class DraggablePdfList(QListWidget):
    drag_activity_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        if item is None:
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        if not path.is_file() or path.is_symlink():
            return

        mime_data = pdf_file_mime_data(path)
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        self.drag_activity_changed.emit(True)
        try:
            drag.exec(Qt.DropAction.CopyAction)
        finally:
            self.drag_activity_changed.emit(False)


def pdf_file_mime_data(path: Path) -> QMimeData:
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
    return mime_data


class ScanTab(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self.output_dir = get_scan_output_dir(db_path.parent if db_path else None)
        self._scan_output_path: Path | None = None
        self._drag_in_progress = False

        initialize_database(self._db_path)

        title = QLabel("KaosEghis-scan")
        title.setObjectName("pageTitle")
        self.folder_label = QLabel(f"Temporary PDF folder: {self.output_dir}")
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.scan_button = QPushButton("Scan to PDF")
        self.scan_button.clicked.connect(self.start_scan)
        self.clean_button = QPushButton("Clean now")
        self.clean_button.clicked.connect(self.clean_now)
        self.view_folder_button = QPushButton("View folder")
        self.view_folder_button.clicked.connect(self.view_folder)

        action_row = QHBoxLayout()
        action_row.addWidget(self.scan_button)
        action_row.addWidget(self.clean_button)
        action_row.addWidget(self.view_folder_button)
        action_row.addStretch()

        self.cleanup_interval = QSpinBox()
        self.cleanup_interval.setRange(1, 1440)
        self.cleanup_interval.setSuffix(" min")
        self.cleanup_interval.setValue(self._load_cleanup_interval())
        self.apply_cleanup_button = QPushButton("Apply cleanup interval")
        self.apply_cleanup_button.clicked.connect(self.apply_cleanup_interval)
        self.next_cleanup_label = QLabel()

        cleanup_row = QHBoxLayout()
        cleanup_row.addWidget(QLabel("Clean temporary folder every"))
        cleanup_row.addWidget(self.cleanup_interval)
        cleanup_row.addWidget(self.apply_cleanup_button)
        cleanup_row.addWidget(self.next_cleanup_label, 1)

        self.file_list = DraggablePdfList()
        self.file_list.setObjectName("scanPdfList")
        self.file_list.setMinimumWidth(220)
        self.file_list.currentItemChanged.connect(self._preview_selected_pdf)
        self.file_list.drag_activity_changed.connect(self._set_drag_in_progress)

        file_panel = QWidget()
        file_panel.setFixedWidth(260)
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(QLabel("Scanned PDFs - drag a file into the browser"))
        file_layout.addWidget(self.file_list, 1)

        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.addWidget(QLabel("PDF preview"))
        self._pdf_document = None
        self._pdf_view = None
        self._pdf_buffer = None
        self.preview_fallback = None
        self._build_pdf_preview()

        self.content_area = QWidget()
        content_layout = QHBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(file_panel)
        content_layout.addWidget(self.preview_container, 1)

        self.status_label = QLabel("Ready to scan.")
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.folder_label)
        layout.addLayout(action_row)
        layout.addLayout(cleanup_row)
        layout.addWidget(self.content_area, 1)
        layout.addWidget(self.status_label)

        self.scan_process = QProcess(self)
        self.scan_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.scan_process.finished.connect(self._scan_finished)
        self.scan_process.errorOccurred.connect(self._scan_start_error)

        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self._automatic_cleanup)
        self._restart_cleanup_timer()
        self.refresh_files()

    def start_scan(self) -> None:
        if self.scan_process.state() != QProcess.ProcessState.NotRunning:
            self.status_label.setText("A scan is already running.")
            return
        try:
            command = prepare_scan_command(
                self.output_dir,
                profile=DEFAULT_NAPS2_PROFILE,
            )
        except FileExistsError:
            self.status_label.setText(
                "A scan already exists for this minute. Wait for the next minute and retry."
            )
            return
        except (FileNotFoundError, ValueError):
            self.status_label.setText(
                "NAPS2 or the Canon DR-C125 Native profile is not available."
            )
            return

        self._scan_output_path = command.output_path
        self.scan_button.setEnabled(False)
        self.status_label.setText("Scanning from Canon DR-C125...")
        self.scan_process.setProgram(command.executable)
        self.scan_process.setArguments(list(command.arguments))
        self.scan_process.start()

    def refresh_files(self, select_path: Path | None = None) -> None:
        self._close_preview()
        self.file_list.clear()
        selected_item = None
        for path in list_scanned_pdfs(self.output_dir):
            modified = datetime.fromtimestamp(path.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            size_kb = max(path.stat().st_size // 1024, 1)
            item = QListWidgetItem(f"{path.name}\n{modified} | {size_kb:,} KB")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
            if select_path is not None and path == select_path:
                selected_item = item
        if selected_item is not None:
            self.file_list.setCurrentItem(selected_item)
        elif self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def apply_cleanup_interval(self) -> None:
        minutes = self.cleanup_interval.value()
        with connect(self._db_path) as connection:
            set_settings(
                connection,
                {SCAN_CLEANUP_INTERVAL_KEY: str(minutes)},
            )
        self._restart_cleanup_timer()
        self.status_label.setText(f"Cleanup interval set to {minutes} minute(s).")

    def clean_now(self) -> None:
        self._clean_folder(automatic=False)

    def view_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def _automatic_cleanup(self) -> None:
        self._clean_folder(automatic=True)

    def _clean_folder(self, *, automatic: bool) -> None:
        if self.scan_process.state() != QProcess.ProcessState.NotRunning:
            self.status_label.setText("Cleanup skipped while scanning is active.")
            return
        if self._drag_in_progress:
            self.status_label.setText("Cleanup skipped while a PDF is being dragged.")
            return

        self._close_preview()
        result = clean_scan_output_dir(self.output_dir)
        self.refresh_files()
        prefix = "Automatic cleanup" if automatic else "Cleanup"
        if result.failed:
            self.status_label.setText(
                f"{prefix}: deleted={result.deleted}, skipped={result.skipped}, failed={result.failed}."
            )
        elif result.deleted:
            self.status_label.setText(
                f"{prefix} removed {result.deleted} temporary file(s)."
            )
        else:
            self.status_label.setText(f"{prefix}: temporary folder is already clean.")
        if not automatic:
            self._restart_cleanup_timer()

    def _load_cleanup_interval(self) -> int:
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        try:
            minutes = int(
                settings.get(
                    SCAN_CLEANUP_INTERVAL_KEY,
                    str(DEFAULT_CLEANUP_INTERVAL_MINUTES),
                )
            )
        except (TypeError, ValueError):
            return DEFAULT_CLEANUP_INTERVAL_MINUTES
        return min(max(minutes, 1), 1440)

    def _restart_cleanup_timer(self) -> None:
        minutes = self.cleanup_interval.value()
        self.cleanup_timer.start(minutes * 60 * 1000)
        self.next_cleanup_label.setText(f"Every {minutes} minute(s)")

    def _scan_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        self.scan_process.readAllStandardOutput()
        self.scan_button.setEnabled(True)
        output_path = self._scan_output_path
        self._scan_output_path = None
        if (
            exit_code == 0
            and output_path is not None
            and output_path.is_file()
            and output_path.stat().st_size > 0
        ):
            self.refresh_files(select_path=output_path)
            self._restart_cleanup_timer()
            self.status_label.setText(f"Scan completed: {output_path.name}")
            return

        if output_path is not None:
            discard_failed_scan(output_path, self.output_dir)
        self.refresh_files()
        self.status_label.setText("Scan failed. No PDF was saved.")

    def _scan_start_error(self, _error: QProcess.ProcessError) -> None:
        self.scan_button.setEnabled(True)
        if self._scan_output_path is not None:
            discard_failed_scan(self._scan_output_path, self.output_dir)
        self._scan_output_path = None
        self.status_label.setText("NAPS2 scan process could not start.")

    def _build_pdf_preview(self) -> None:
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtPdfWidgets import QPdfView
        except ImportError:
            self.preview_fallback = QLabel("PDF preview is not available.")
            self.preview_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_layout.addWidget(self.preview_fallback, 1)
            return

        self._pdf_document = QPdfDocument(self)
        self._pdf_view = QPdfView()
        self._pdf_view.setDocument(self._pdf_document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.preview_layout.addWidget(self._pdf_view, 1)

    def _preview_selected_pdf(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if self._pdf_document is None:
            return
        self._pdf_document.close()
        if self._pdf_view is not None:
            self._pdf_view.setDocument(self._pdf_document)
        if current is None:
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole) or ""))
        if path.is_file() and not path.is_symlink():
            try:
                pdf_data = path.read_bytes()
            except OSError:
                return
            self._pdf_buffer = QBuffer(self)
            self._pdf_buffer.setData(pdf_data)
            self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self._pdf_document.load(self._pdf_buffer)

    def _close_preview(self) -> None:
        if self._pdf_document is not None:
            if self._pdf_view is not None:
                self._pdf_view.setDocument(None)
            self._pdf_document.close()
        if self._pdf_buffer is not None:
            self._pdf_buffer.close()
            self._pdf_buffer.deleteLater()
            self._pdf_buffer = None

    def _set_drag_in_progress(self, active: bool) -> None:
        self._drag_in_progress = active
