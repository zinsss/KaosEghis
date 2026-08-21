from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.socl import SoclSelectedFinding, render_socl_note
from KaosEghis.db.database import connect, get_database_path, initialize_database
from KaosEghis.db.repositories import (
    SoclCollectionRecord,
    SoclFindingRecord,
    create_socl_collection,
    create_socl_finding,
    delete_socl_collection,
    delete_socl_finding,
    get_socl_collection,
    get_socl_finding,
    list_socl_collections,
    list_socl_findings,
    move_socl_collection,
    move_socl_finding,
    restore_default_socl_vocabulary,
    update_socl_collection,
    update_socl_finding,
)


FINDING_ID_ROLE = Qt.ItemDataRole.UserRole
RENDER_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1
COLLECTION_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
DOMAIN_ROLE = Qt.ItemDataRole.UserRole + 3


class _CheckboxLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _create_socl_selection_tree(accessible_name: str) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setAccessibleName(accessible_name)
    tree.setColumnCount(2)
    tree.setHeaderLabels(["Finding", "Encounter detail (optional)"])
    tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    return tree


def _populate_socl_tree(
    db_path: Path,
    domain: str,
    tree: QTreeWidget,
    detail_inputs: dict[int, QLineEdit],
) -> None:
    tree.clear()
    with connect(db_path) as connection:
        for collection in list_socl_collections(connection, domain):
            collection_item = QTreeWidgetItem([collection.name, ""])
            collection_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            tree.addTopLevelItem(collection_item)
            collection_item.setFirstColumnSpanned(True)
            for finding in list_socl_findings(connection, collection.id):
                child = QTreeWidgetItem([finding.label, ""])
                child.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, FINDING_ID_ROLE, finding.id)
                child.setData(0, RENDER_TEXT_ROLE, finding.render_text)
                child.setData(0, COLLECTION_NAME_ROLE, collection.name)
                child.setData(0, DOMAIN_ROLE, domain)
                collection_item.addChild(child)
                detail_input = QLineEdit()
                detail_input.setPlaceholderText("Optional value or wording")
                tree.setItemWidget(child, 1, detail_input)
                detail_inputs[finding.id] = detail_input
    tree.collapseAll()
    if tree.topLevelItemCount():
        tree.topLevelItem(0).setExpanded(True)


def _selected_findings_from_tree(
    tree: QTreeWidget,
    detail_inputs: dict[int, QLineEdit],
) -> list[SoclSelectedFinding]:
    selections: list[SoclSelectedFinding] = []
    for collection_index in range(tree.topLevelItemCount()):
        collection_item = tree.topLevelItem(collection_index)
        for finding_index in range(collection_item.childCount()):
            item = collection_item.child(finding_index)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            finding_id = item.data(0, FINDING_ID_ROLE)
            detail_input = detail_inputs.get(finding_id)
            selections.append(
                SoclSelectedFinding(
                    domain=str(item.data(0, DOMAIN_ROLE)),
                    collection_name=str(item.data(0, COLLECTION_NAME_ROLE)),
                    finding_label=item.text(0),
                    render_text=str(item.data(0, RENDER_TEXT_ROLE)),
                    detail=detail_input.text() if detail_input is not None else "",
                )
            )
    return selections


class SoclLauncherPanel(QWidget):
    """Compact S/O composer for the daily Launcher surface."""

    notification_requested = Signal(str, str)

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._detail_inputs: dict[int, QLineEdit] = {}
        self._finding_checkboxes: dict[int, QCheckBox] = {}
        self._finding_metadata: dict[int, tuple[str, str, str, str]] = {}
        self.pages = QTabWidget()
        self.status_label = QLabel("Ready. Nothing is selected by default.")

        self.subjective_findings = QWidget()
        self.objective_findings = QWidget()
        self.subjective_findings.setAccessibleName("Subjective findings")
        self.objective_findings.setAccessibleName("Physical examination")
        self.subjective_preview = QPlainTextEdit()
        self.objective_preview = QPlainTextEdit()
        self.subjective_preview.setPlaceholderText("Editable Subjective preview")
        self.objective_preview.setPlaceholderText("Editable Objective preview")

        self.pages.addTab(
            self._build_domain_page(
                "subjective", self.subjective_findings, self.subjective_preview
            ),
            "S",
        )
        self.pages.addTab(
            self._build_domain_page(
                "objective", self.objective_findings, self.objective_preview
            ),
            "O",
        )
        self.pages.setTabToolTip(0, "Subjective")
        self.pages.setTabToolTip(1, "Objective")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pages, 1)
        layout.addWidget(self.status_label)
        self.reload_vocabulary()

    def _build_domain_page(
        self,
        domain: str,
        findings_widget: QWidget,
        preview: QPlainTextEdit,
    ) -> QWidget:
        page = QWidget()
        generate_button = QPushButton("Generate")
        generate_button.clicked.connect(lambda: self.generate_preview(domain))
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(lambda: self.copy_preview(domain))
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda: self.clear_domain(domain))

        controls = QHBoxLayout()
        controls.addWidget(generate_button)
        controls.addWidget(copy_button)
        controls.addWidget(clear_button)
        controls.addStretch()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(findings_widget)
        layout.addWidget(scroll, 3)
        layout.addLayout(controls)
        layout.addWidget(preview, 1)
        return page

    def _effective_path(self) -> Path:
        return self._db_path or get_database_path()

    def reload_vocabulary(self) -> None:
        path = self._effective_path()
        initialize_database(path)
        self._detail_inputs.clear()
        self._finding_checkboxes.clear()
        self._finding_metadata.clear()
        self._populate_compact_domain("subjective", self.subjective_findings)
        self._populate_compact_domain("objective", self.objective_findings)
        self.subjective_preview.clear()
        self.objective_preview.clear()
        self.status_label.setText("Vocabulary loaded. Selections were cleared.")

    def generate_preview(self, domain: str) -> None:
        selections = self._selected_findings(domain)
        rendered = render_socl_note(selections)
        preview = self._preview_for_domain(domain)
        preview.setPlainText(
            rendered.subjective if domain == "subjective" else rendered.objective
        )
        self.status_label.setText(
            f"Generated {self._short_label(domain)} from {len(selections)} findings."
        )

    def copy_preview(self, domain: str) -> None:
        label = self._short_label(domain)
        value = self._preview_for_domain(domain).toPlainText().strip()
        if not value:
            self.status_label.setText(f"Nothing to copy for {label}.")
            return
        try:
            copy_text(value)
        except Exception:
            self.status_label.setText("Clipboard copy failed.")
            self.notification_requested.emit("SOCL clipboard copy failed", "error")
            return
        self.status_label.setText(f"Copied {label}.")
        self.notification_requested.emit(f"SOCL: Copied {label}", "success")

    def clear_domain(self, domain: str) -> None:
        for finding_id, checkbox in self._finding_checkboxes.items():
            metadata = self._finding_metadata.get(finding_id)
            if metadata is None or metadata[0] != domain:
                continue
            checkbox.setChecked(False)
            detail_input = self._detail_inputs.get(finding_id)
            if detail_input is not None:
                detail_input.clear()
        self._preview_for_domain(domain).clear()
        self.status_label.setText(f"Cleared {self._short_label(domain)}.")

    def finding_checkbox(self, finding_id: int) -> QCheckBox | None:
        return self._finding_checkboxes.get(finding_id)

    def finding_count(self, domain: str) -> int:
        return sum(
            1 for metadata in self._finding_metadata.values() if metadata[0] == domain
        )

    def _populate_compact_domain(self, domain: str, container: QWidget) -> None:
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(6)
        else:
            self._clear_layout(layout)
        with connect(self._effective_path()) as connection:
            collections = list_socl_collections(connection, domain)
            for collection in collections:
                group = QGroupBox(collection.name)
                grid = QGridLayout(group)
                grid.setContentsMargins(6, 6, 6, 6)
                grid.setHorizontalSpacing(10)
                grid.setVerticalSpacing(3)
                findings = list_socl_findings(connection, collection.id)
                for index, finding in enumerate(findings):
                    row, column = divmod(index, 2)
                    grid.addWidget(
                        self._create_compact_finding(
                            domain,
                            collection.name,
                            finding,
                        ),
                        row,
                        column,
                    )
                grid.setColumnStretch(0, 1)
                grid.setColumnStretch(1, 1)
                layout.addWidget(group)
        layout.addStretch()

    def _create_compact_finding(
        self,
        domain: str,
        collection_name: str,
        finding: SoclFindingRecord,
    ) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        checkbox = QCheckBox()
        checkbox.setAccessibleName(finding.label)
        checkbox.setToolTip(finding.label)
        finding_label = _CheckboxLabel(finding.label)
        finding_label.setWordWrap(True)
        finding_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        finding_label.setCursor(Qt.CursorShape.PointingHandCursor)
        finding_label.clicked.connect(checkbox.toggle)
        detail_input = QLineEdit()
        detail_input.setPlaceholderText("detail")
        detail_input.setMaximumWidth(130)
        detail_input.setVisible(self._is_free_text_finding(finding.label))
        checkbox.toggled.connect(
            lambda checked, editor=detail_input, label=finding.label: editor.setVisible(
                checked or self._is_free_text_finding(label)
            )
        )
        detail_input.textEdited.connect(
            lambda text, option=checkbox: option.setChecked(bool(text.strip()))
        )

        row.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(finding_label, 1, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(detail_input, 0, Qt.AlignmentFlag.AlignVCenter)
        self._finding_checkboxes[finding.id] = checkbox
        self._detail_inputs[finding.id] = detail_input
        self._finding_metadata[finding.id] = (
            domain,
            collection_name,
            finding.label,
            finding.render_text,
        )
        return container

    def _selected_findings(self, domain: str) -> list[SoclSelectedFinding]:
        selected: list[SoclSelectedFinding] = []
        for finding_id, checkbox in self._finding_checkboxes.items():
            metadata = self._finding_metadata.get(finding_id)
            if metadata is None or metadata[0] != domain or not checkbox.isChecked():
                continue
            _domain, collection_name, finding_label, render_text = metadata
            detail_input = self._detail_inputs.get(finding_id)
            selected.append(
                SoclSelectedFinding(
                    domain=domain,
                    collection_name=collection_name,
                    finding_label=finding_label,
                    render_text=render_text,
                    detail=detail_input.text() if detail_input is not None else "",
                )
            )
        return selected

    @staticmethod
    def _is_free_text_finding(label: str) -> bool:
        normalized = label.casefold()
        return any(
            marker in normalized
            for marker in ("custom", "own wording", "unrestricted", "other")
        )

    @classmethod
    def _clear_layout(cls, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                cls._clear_layout(child_layout)
            if widget is not None:
                widget.deleteLater()

    def _preview_for_domain(self, domain: str) -> QPlainTextEdit:
        return (
            self.subjective_preview
            if domain == "subjective"
            else self.objective_preview
        )

    @staticmethod
    def _short_label(domain: str) -> str:
        return "S" if domain == "subjective" else "O"


class SoclTab(QWidget):
    notification_requested = Signal(str, str)

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._detail_inputs: dict[int, QLineEdit] = {}

        title = QLabel("SOCL")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Subjective & Objective Composer. Only explicitly checked findings are "
            "rendered; unchecked items are omitted."
        )
        subtitle.setWordWrap(True)

        self.pages = QTabWidget()
        self.compose_page = self._build_compose_page()
        self.vocabulary_page = SoclVocabularyEditor(db_path)
        self.vocabulary_page.vocabulary_changed.connect(self.reload_vocabulary)
        self.pages.addTab(self.compose_page, "Compose")
        self.pages.addTab(self.vocabulary_page, "Edit vocabulary")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.pages, 1)

        self.reload_vocabulary()

    def _build_compose_page(self) -> QWidget:
        page = QWidget()
        self.subjective_tree = self._create_selection_tree("Subjective findings")
        self.objective_tree = self._create_selection_tree("Physical examination")

        selection_splitter = QSplitter(Qt.Orientation.Horizontal)
        selection_splitter.setChildrenCollapsible(False)
        selection_splitter.addWidget(self.subjective_tree)
        selection_splitter.addWidget(self.objective_tree)
        selection_splitter.setSizes([700, 700])

        self.generate_button = QPushButton("Generate preview")
        self.generate_button.clicked.connect(self.generate_preview)
        self.clear_button = QPushButton("New / Clear")
        self.clear_button.clicked.connect(self.clear_note)
        selection_controls = QHBoxLayout()
        selection_controls.addWidget(self.generate_button)
        selection_controls.addWidget(self.clear_button)
        selection_controls.addStretch()

        self.subjective_preview = QPlainTextEdit()
        self.subjective_preview.setPlaceholderText("Editable Subjective preview")
        self.objective_preview = QPlainTextEdit()
        self.objective_preview.setPlaceholderText("Editable Objective preview")
        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.setChildrenCollapsible(False)
        preview_splitter.addWidget(self._labeled_widget("Subjective preview", self.subjective_preview))
        preview_splitter.addWidget(self._labeled_widget("Objective preview", self.objective_preview))
        preview_splitter.setSizes([700, 700])

        self.copy_subjective_button = QPushButton("Copy S")
        self.copy_subjective_button.clicked.connect(
            lambda: self._copy_preview(self.subjective_preview.toPlainText(), "S")
        )
        self.copy_objective_button = QPushButton("Copy O")
        self.copy_objective_button.clicked.connect(
            lambda: self._copy_preview(self.objective_preview.toPlainText(), "O")
        )
        self.copy_combined_button = QPushButton("Copy S/O")
        self.copy_combined_button.clicked.connect(self.copy_combined)
        self.status_label = QLabel("Ready. Nothing is selected by default.")
        preview_controls = QHBoxLayout()
        preview_controls.addWidget(self.copy_subjective_button)
        preview_controls.addWidget(self.copy_objective_button)
        preview_controls.addWidget(self.copy_combined_button)
        preview_controls.addWidget(self.status_label, 1)

        layout = QVBoxLayout(page)
        layout.addWidget(selection_splitter, 3)
        layout.addLayout(selection_controls)
        layout.addWidget(preview_splitter, 2)
        layout.addLayout(preview_controls)
        return page

    @staticmethod
    def _create_selection_tree(accessible_name: str) -> QTreeWidget:
        return _create_socl_selection_tree(accessible_name)

    @staticmethod
    def _labeled_widget(label: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)
        return container

    def reload_vocabulary(self) -> None:
        effective_path = self._db_path or get_database_path()
        initialize_database(effective_path)
        self.subjective_tree.clear()
        self.objective_tree.clear()
        self._detail_inputs.clear()
        _populate_socl_tree(
            effective_path,
            "subjective",
            self.subjective_tree,
            self._detail_inputs,
        )
        _populate_socl_tree(
            effective_path,
            "objective",
            self.objective_tree,
            self._detail_inputs,
        )
        self.subjective_preview.clear()
        self.objective_preview.clear()
        self.status_label.setText("Vocabulary loaded. Selections were cleared.")

    def selected_findings(self) -> list[SoclSelectedFinding]:
        return [
            *_selected_findings_from_tree(
                self.subjective_tree, self._detail_inputs
            ),
            *_selected_findings_from_tree(
                self.objective_tree, self._detail_inputs
            ),
        ]

    def generate_preview(self) -> None:
        selections = self.selected_findings()
        rendered = render_socl_note(selections)
        self.subjective_preview.setPlainText(rendered.subjective)
        self.objective_preview.setPlainText(rendered.objective)
        self.status_label.setText(f"Generated from {len(selections)} selected findings.")

    def clear_note(self) -> None:
        for tree in (self.subjective_tree, self.objective_tree):
            for collection_index in range(tree.topLevelItemCount()):
                collection_item = tree.topLevelItem(collection_index)
                for finding_index in range(collection_item.childCount()):
                    collection_item.child(finding_index).setCheckState(
                        0, Qt.CheckState.Unchecked
                    )
        for detail_input in self._detail_inputs.values():
            detail_input.clear()
        self.subjective_preview.clear()
        self.objective_preview.clear()
        self.status_label.setText("New empty note.")

    def copy_combined(self) -> None:
        combined = "\n\n".join(
            text
            for text in (
                self.subjective_preview.toPlainText().strip(),
                self.objective_preview.toPlainText().strip(),
            )
            if text
        )
        self._copy_preview(combined, "S/O")

    def _copy_preview(self, text: str, label: str) -> None:
        value = text.strip()
        if not value:
            self.status_label.setText(f"Nothing to copy for {label}.")
            return
        try:
            copy_text(value)
        except Exception:
            self.status_label.setText("Clipboard copy failed.")
            self.notification_requested.emit("SOCL clipboard copy failed", "error")
            return
        self.status_label.setText(f"Copied {label}.")
        self.notification_requested.emit(f"SOCL: Copied {label}", "success")


class SoclVocabularyEditor(QWidget):
    vocabulary_changed = Signal()

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        self.domain_combo = QComboBox()
        self.domain_combo.addItem("Subjective", "subjective")
        self.domain_combo.addItem("Physical Exam", "objective")
        self.domain_combo.currentIndexChanged.connect(self.reload_collections)

        self.collection_list = QListWidget()
        self.collection_list.currentItemChanged.connect(self.reload_findings)
        self.add_collection_button = QPushButton("Add collection")
        self.add_collection_button.clicked.connect(self.add_collection)
        self.rename_collection_button = QPushButton("Rename")
        self.rename_collection_button.clicked.connect(self.rename_collection)
        self.delete_collection_button = QPushButton("Delete")
        self.delete_collection_button.clicked.connect(self.delete_collection)
        self.collection_up_button = QPushButton("Move up")
        self.collection_up_button.clicked.connect(lambda: self.move_collection(-1))
        self.collection_down_button = QPushButton("Move down")
        self.collection_down_button.clicked.connect(lambda: self.move_collection(1))

        self.finding_table = QTableWidget(0, 2)
        self.finding_table.setHorizontalHeaderLabels(["Display label", "Rendered phrase"])
        self.finding_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.finding_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.finding_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.finding_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.add_finding_button = QPushButton("Add finding")
        self.add_finding_button.clicked.connect(self.add_finding)
        self.edit_finding_button = QPushButton("Edit")
        self.edit_finding_button.clicked.connect(self.edit_finding)
        self.delete_finding_button = QPushButton("Delete")
        self.delete_finding_button.clicked.connect(self.delete_finding)
        self.finding_up_button = QPushButton("Move up")
        self.finding_up_button.clicked.connect(lambda: self.move_finding(-1))
        self.finding_down_button = QPushButton("Move down")
        self.finding_down_button.clicked.connect(lambda: self.move_finding(1))

        self.restore_button = QPushButton("Restore reviewed defaults")
        self.restore_button.clicked.connect(self.restore_defaults)
        self.editor_status = QLabel("Changes are saved locally.")

        collection_buttons = QHBoxLayout()
        for button in (
            self.add_collection_button,
            self.rename_collection_button,
            self.delete_collection_button,
            self.collection_up_button,
            self.collection_down_button,
        ):
            collection_buttons.addWidget(button)
        collection_buttons.addStretch()

        finding_buttons = QHBoxLayout()
        for button in (
            self.add_finding_button,
            self.edit_finding_button,
            self.delete_finding_button,
            self.finding_up_button,
            self.finding_down_button,
        ):
            finding_buttons.addWidget(button)
        finding_buttons.addStretch()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Domain"))
        left_layout.addWidget(self.domain_combo)
        left_layout.addWidget(QLabel("Collections"))
        left_layout.addWidget(self.collection_list, 1)
        left_layout.addLayout(collection_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Findings"))
        right_layout.addWidget(self.finding_table, 1)
        right_layout.addLayout(finding_buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([480, 900])

        footer = QHBoxLayout()
        footer.addWidget(self.restore_button)
        footer.addWidget(self.editor_status, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Edit the local vocabulary and rendered wording. This does not change "
                "existing EMR data or create clinical recommendations."
            )
        )
        layout.addWidget(splitter, 1)
        layout.addLayout(footer)

        initialize_database(self._effective_path())
        self.reload_collections()

    def _effective_path(self) -> Path:
        return self._db_path or get_database_path()

    def reload_collections(self, *_args, select_id: int | None = None) -> None:
        current_id = select_id if select_id is not None else self._selected_collection_id()
        with connect(self._effective_path()) as connection:
            collections = list_socl_collections(
                connection,
                str(self.domain_combo.currentData()),
            )
        self.collection_list.clear()
        for collection in collections:
            item = QListWidgetItem(collection.name)
            item.setData(Qt.ItemDataRole.UserRole, collection.id)
            self.collection_list.addItem(item)
            if collection.id == current_id:
                self.collection_list.setCurrentItem(item)
        if self.collection_list.currentRow() < 0 and self.collection_list.count():
            self.collection_list.setCurrentRow(0)
        self.reload_findings()

    def reload_findings(self, *_args, select_id: int | None = None) -> None:
        collection_id = self._selected_collection_id()
        findings: list[SoclFindingRecord] = []
        if collection_id is not None:
            with connect(self._effective_path()) as connection:
                findings = list_socl_findings(connection, collection_id)
        self.finding_table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            label_item = QTableWidgetItem(finding.label)
            label_item.setData(Qt.ItemDataRole.UserRole, finding.id)
            self.finding_table.setItem(row, 0, label_item)
            self.finding_table.setItem(row, 1, QTableWidgetItem(finding.render_text))
            if finding.id == select_id:
                self.finding_table.selectRow(row)

    def add_collection(self) -> None:
        dialog = CollectionEditorDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with connect(self._effective_path()) as connection:
                created = create_socl_collection(
                    connection,
                    str(self.domain_combo.currentData()),
                    dialog.collection_name(),
                )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid collection", str(error))
            return
        self._after_change("Collection added.", collection_id=created.id)

    def rename_collection(self) -> None:
        collection = self._selected_collection()
        if collection is None:
            self.editor_status.setText("Select a collection.")
            return
        dialog = CollectionEditorDialog(collection.name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with connect(self._effective_path()) as connection:
                update_socl_collection(connection, collection.id, dialog.collection_name())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid collection", str(error))
            return
        self._after_change("Collection renamed.", collection_id=collection.id)

    def delete_collection(self) -> None:
        collection = self._selected_collection()
        if collection is None:
            self.editor_status.setText("Select a collection.")
            return
        if QMessageBox.question(
            self,
            "Delete collection",
            f"Delete '{collection.name}' and all of its findings?",
        ) != QMessageBox.StandardButton.Yes:
            return
        with connect(self._effective_path()) as connection:
            delete_socl_collection(connection, collection.id)
        self._after_change("Collection deleted.")

    def move_collection(self, direction: int) -> None:
        collection = self._selected_collection()
        if collection is None:
            self.editor_status.setText("Select a collection.")
            return
        with connect(self._effective_path()) as connection:
            move_socl_collection(connection, collection.id, direction)
        self._after_change("Collection order saved.", collection_id=collection.id)

    def add_finding(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            self.editor_status.setText("Select a collection first.")
            return
        dialog = FindingEditorDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with connect(self._effective_path()) as connection:
                created = create_socl_finding(
                    connection,
                    collection_id,
                    dialog.finding_label(),
                    dialog.render_text(),
                )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid finding", str(error))
            return
        self._after_change("Finding added.", finding_id=created.id)

    def edit_finding(self) -> None:
        finding = self._selected_finding()
        if finding is None:
            self.editor_status.setText("Select a finding.")
            return
        dialog = FindingEditorDialog(finding.label, finding.render_text, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with connect(self._effective_path()) as connection:
                update_socl_finding(
                    connection,
                    finding.id,
                    dialog.finding_label(),
                    dialog.render_text(),
                )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid finding", str(error))
            return
        self._after_change("Finding updated.", finding_id=finding.id)

    def delete_finding(self) -> None:
        finding = self._selected_finding()
        if finding is None:
            self.editor_status.setText("Select a finding.")
            return
        if QMessageBox.question(
            self,
            "Delete finding",
            f"Delete '{finding.label}'?",
        ) != QMessageBox.StandardButton.Yes:
            return
        with connect(self._effective_path()) as connection:
            delete_socl_finding(connection, finding.id)
        self._after_change("Finding deleted.")

    def move_finding(self, direction: int) -> None:
        finding = self._selected_finding()
        if finding is None:
            self.editor_status.setText("Select a finding.")
            return
        with connect(self._effective_path()) as connection:
            move_socl_finding(connection, finding.id, direction)
        self._after_change("Finding order saved.", finding_id=finding.id)

    def restore_defaults(self) -> None:
        if QMessageBox.question(
            self,
            "Restore reviewed defaults",
            "Replace all edited SOCL collections and findings with the reviewed defaults?",
        ) != QMessageBox.StandardButton.Yes:
            return
        with connect(self._effective_path()) as connection:
            restore_default_socl_vocabulary(connection)
        self._after_change("Reviewed defaults restored.")

    def _after_change(
        self,
        message: str,
        *,
        collection_id: int | None = None,
        finding_id: int | None = None,
    ) -> None:
        self.reload_collections(select_id=collection_id)
        if finding_id is not None:
            self.reload_findings(select_id=finding_id)
        self.editor_status.setText(message)
        self.vocabulary_changed.emit()

    def _selected_collection_id(self) -> int | None:
        item = self.collection_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None

    def _selected_collection(self) -> SoclCollectionRecord | None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            return None
        with connect(self._effective_path()) as connection:
            return get_socl_collection(connection, collection_id)

    def _selected_finding_id(self) -> int | None:
        row = self.finding_table.currentRow()
        if row < 0:
            return None
        item = self.finding_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None

    def _selected_finding(self) -> SoclFindingRecord | None:
        finding_id = self._selected_finding_id()
        if finding_id is None:
            return None
        with connect(self._effective_path()) as connection:
            return get_socl_finding(connection, finding_id)


class CollectionEditorDialog(QDialog):
    def __init__(self, name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SOCL collection")
        self.name_input = QLineEdit(name)
        form = QFormLayout()
        form.addRow("Collection name", self.name_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def collection_name(self) -> str:
        return self.name_input.text().strip()

    def _validate(self) -> None:
        if not self.collection_name():
            QMessageBox.warning(self, "Invalid collection", "Collection name is required.")
            return
        self.accept()


class FindingEditorDialog(QDialog):
    def __init__(
        self,
        label: str = "",
        render_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SOCL finding")
        self.label_input = QLineEdit(label)
        self.render_input = QLineEdit(render_text or label)
        form = QFormLayout()
        form.addRow("Display label", self.label_input)
        form.addRow("Rendered phrase", self.render_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def finding_label(self) -> str:
        return self.label_input.text().strip()

    def render_text(self) -> str:
        return self.render_input.text().strip()

    def _validate(self) -> None:
        if not self.finding_label():
            QMessageBox.warning(self, "Invalid finding", "Display label is required.")
            return
        if not self.render_text():
            QMessageBox.warning(self, "Invalid finding", "Rendered phrase is required.")
            return
        self.accept()
