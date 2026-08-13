from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_socl_defaults_are_seeded_exactly_once(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import list_socl_collections, list_socl_findings
    from KaosEghis.db.socl_defaults import SOCL_DEFAULT_COLLECTIONS

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    initialize_database(db_path)

    with connect(db_path) as connection:
        collections = list_socl_collections(connection)
        actual = [
            (
                collection.domain,
                collection.name,
                tuple(
                    finding.label
                    for finding in list_socl_findings(connection, collection.id)
                ),
            )
            for collection in collections
        ]
        rendered_phrases = [
            finding.render_text
            for collection in collections
            for finding in list_socl_findings(connection, collection.id)
        ]

    assert actual == list(SOCL_DEFAULT_COLLECTIONS)
    assert rendered_phrases == [
        label
        for _domain, _collection_name, findings in SOCL_DEFAULT_COLLECTIONS
        for label in findings
    ]


def test_socl_vocabulary_crud_reorder_and_restore(tmp_path) -> None:
    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        create_socl_collection,
        create_socl_finding,
        delete_socl_collection,
        delete_socl_finding,
        list_socl_collections,
        list_socl_findings,
        move_socl_collection,
        move_socl_finding,
        restore_default_socl_vocabulary,
        update_socl_collection,
        update_socl_finding,
    )
    from KaosEghis.db.socl_defaults import SOCL_DEFAULT_COLLECTIONS

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        collection = create_socl_collection(connection, "subjective", "Custom")
        renamed = update_socl_collection(connection, collection.id, "Custom history")
        first = create_socl_finding(connection, collection.id, "first")
        second = create_socl_finding(connection, collection.id, "second", "second phrase")
        updated = update_socl_finding(
            connection,
            first.id,
            "first edited",
            "first rendered",
        )
        move_socl_finding(connection, second.id, -1)
        move_socl_collection(connection, collection.id, -1)

        assert renamed is not None and renamed.name == "Custom history"
        assert updated is not None and updated.render_text == "first rendered"
        assert [item.id for item in list_socl_findings(connection, collection.id)] == [
            second.id,
            first.id,
        ]
        assert delete_socl_finding(connection, first.id) is True
        assert delete_socl_collection(connection, collection.id) is True

        restore_default_socl_vocabulary(connection)
        restored = list_socl_collections(connection)

    assert [(item.domain, item.name) for item in restored] == [
        (domain, name) for domain, name, _findings in SOCL_DEFAULT_COLLECTIONS
    ]


def test_socl_renderer_uses_only_explicit_selections_and_details() -> None:
    from KaosEghis.core.socl import SoclSelectedFinding, render_socl_note

    rendered = render_socl_note(
        [
            SoclSelectedFinding(
                "subjective",
                "Constitutional",
                "fever",
                "fever",
                "3 days",
            ),
            SoclSelectedFinding(
                "subjective",
                "Constitutional",
                "fatigue",
                "fatigue",
            ),
            SoclSelectedFinding(
                "objective",
                "Respiratory",
                "breath sounds",
                "breath sounds",
                "clear bilaterally",
            ),
        ]
    )

    assert rendered.subjective == "S) Constitutional: fever: 3 days; fatigue."
    assert rendered.objective == "O) Respiratory: breath sounds: clear bilaterally."
    assert "normal" not in rendered.combined


def test_socl_tab_composes_editable_preview_and_copies_edited_text(
    tmp_path,
    monkeypatch,
) -> None:
    _app()

    import KaosEghis.ui.tabs.socl_tab as socl_tab_module
    from KaosEghis.ui.tabs.socl_tab import FINDING_ID_ROLE, SoclTab

    db_path = tmp_path / "KaosEghis.sqlite"
    tab = SoclTab(db_path)
    captured: list[str] = []
    monkeypatch.setattr(socl_tab_module, "copy_text", lambda text: captured.append(text))

    assert tab.subjective_tree.topLevelItemCount() == 20
    assert tab.objective_tree.topLevelItemCount() == 15
    assert tab.selected_findings() == []

    constitutional = next(
        tab.subjective_tree.topLevelItem(index)
        for index in range(tab.subjective_tree.topLevelItemCount())
        if tab.subjective_tree.topLevelItem(index).text(0) == "Constitutional"
    )
    fever = next(
        constitutional.child(index)
        for index in range(constitutional.childCount())
        if constitutional.child(index).text(0) == "fever"
    )
    fever.setCheckState(0, socl_tab_module.Qt.CheckState.Checked)
    tab._detail_inputs[fever.data(0, FINDING_ID_ROLE)].setText("3 days")

    tab.generate_preview()
    assert tab.subjective_preview.toPlainText() == (
        "S) Constitutional: fever: 3 days."
    )

    tab.subjective_preview.setPlainText("S) Physician-edited wording.")
    tab.copy_combined()
    assert captured == ["S) Physician-edited wording."]


def test_socl_encounter_selections_are_not_persisted(tmp_path) -> None:
    _app()

    from PySide6.QtCore import Qt

    from KaosEghis.ui.tabs.socl_tab import SoclTab

    db_path = tmp_path / "KaosEghis.sqlite"
    first = SoclTab(db_path)
    first.subjective_tree.topLevelItem(1).child(0).setCheckState(
        0,
        Qt.CheckState.Checked,
    )
    first.generate_preview()
    assert first.subjective_preview.toPlainText()

    reopened = SoclTab(db_path)
    assert reopened.selected_findings() == []
    assert reopened.subjective_preview.toPlainText() == ""
    assert reopened.objective_preview.toPlainText() == ""


def test_socl_vocabulary_editor_exposes_edit_controls(tmp_path) -> None:
    _app()

    from KaosEghis.ui.tabs.socl_tab import SoclVocabularyEditor

    editor = SoclVocabularyEditor(tmp_path / "KaosEghis.sqlite")

    assert editor.domain_combo.count() == 2
    assert editor.collection_list.count() == 20
    assert editor.add_collection_button.text() == "Add collection"
    assert editor.add_finding_button.text() == "Add finding"
    assert editor.edit_finding_button.text() == "Edit"
    assert editor.restore_button.text() == "Restore reviewed defaults"


def test_launcher_socl_panel_uses_s_and_o_tabs_and_shared_vocabulary(
    tmp_path,
) -> None:
    _app()

    from KaosEghis.ui.tabs.socl_tab import SoclLauncherPanel

    panel = SoclLauncherPanel(tmp_path / "KaosEghis.sqlite")

    assert [panel.pages.tabText(index) for index in range(panel.pages.count())] == [
        "S",
        "O",
    ]
    assert panel.subjective_tree.topLevelItemCount() == 20
    assert panel.objective_tree.topLevelItemCount() == 15


def test_launcher_socl_panel_generates_only_current_domain(tmp_path) -> None:
    _app()

    from PySide6.QtCore import Qt

    from KaosEghis.ui.tabs.socl_tab import SoclLauncherPanel

    panel = SoclLauncherPanel(tmp_path / "KaosEghis.sqlite")
    subjective_finding = panel.subjective_tree.topLevelItem(0).child(0)
    objective_finding = panel.objective_tree.topLevelItem(0).child(0)
    subjective_finding.setCheckState(0, Qt.CheckState.Checked)
    objective_finding.setCheckState(0, Qt.CheckState.Checked)

    panel.generate_preview("subjective")

    assert panel.subjective_preview.toPlainText().startswith("S)")
    assert panel.objective_preview.toPlainText() == ""
