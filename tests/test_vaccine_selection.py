import pytest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from KaosEghis.db.database import connect
from KaosEghis.db.repositories import (
    create_vaccine_type, delete_vaccine_type, get_vaccine_type,
    list_vaccine_records, list_vaccine_types, update_vaccine_type,
)
from KaosEghis.ui.tabs import vaccine_tab
from KaosEghis.ui.theme import NORD_QSS


@pytest.fixture
def page(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    panel = vaccine_tab.VaccineTab(tmp_path / "test.sqlite")
    panel.patient_name_input.setText("Test Patient")
    monkeypatch.setattr(vaccine_tab, "print_vaccine_label", lambda *_a, **_kw: pytest.fail("No printing expected"))
    monkeypatch.setattr(panel, "_begin_post_print_handoff", lambda *_a: pytest.fail("No handoff expected"))
    yield panel
    panel.close()
    panel.deleteLater()
    app.processEvents()


def assert_unselected(page):
    assert page._selected_vaccine_item() is None
    assert page.vaccine_types_combo.currentIndex() == -1
    assert page.vaccine_types_combo.currentData() is None
    assert page.vaccine_types_combo.currentText() == ""
    assert page.vaccine_types_combo.toolTip() == ""
    assert page.chart_note_preview.toPlainText() == ""
    assert page.charting_text_preview.toPlainText() == ""
    assert "(no vaccine selected)" in page.label_preview.toPlainText()
    assert not page.save_button.isEnabled()
    assert not page.print_button.isEnabled()
    assert not page.prepare_flu_covid_button.isEnabled()


def test_no_default_on_startup_or_refresh(page):
    assert page.vaccine_types_combo.count() > 0
    assert not page.vaccine_types_combo.isEditable()
    assert page.vaccine_types_combo.placeholderText() == "Select vaccine"
    assert_unselected(page)
    page.refresh_view()
    page.activate_page()
    assert_unselected(page)
    assert page.save_record() is None
    assert page.prepare_flu_and_covid() is None
    page.print_label()
    assert page.status_label.text() == "Select a vaccine type first."
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == []


def test_popup_highlight_without_activation_does_not_choose_a_vaccine(page):
    combo = page.vaccine_types_combo
    combo.setFocus()
    combo.view().setCurrentIndex(combo.model().index(0, 0))
    page._refresh_previews()
    page._update_handoff_controls()
    assert_unselected(page)
    assert page.save_record() is None
    page.print_label()
    assert page.status_label.text() == "Select a vaccine type first."
    page.refresh_view()
    assert_unselected(page)


def test_explicit_selection_is_highlighted_and_survives_ordinary_refresh(page):
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    selected = page._selected_vaccine_item()
    assert selected.font().bold()
    assert page.vaccine_types_combo.currentText() == "COVID-19 (Moderna)"
    assert page.vaccine_types_combo.toolTip() == "COVID-19 (Moderna)"
    assert page.save_button.isEnabled()
    assert page.print_button.isEnabled()
    assert page.prepare_flu_covid_button.isEnabled()
    for index in range(page.vaccine_types_combo.count()):
        item = page.vaccine_types_combo.model().item(index)
        assert item.font().bold() == (item is selected)
    page.refresh_view()
    assert page._selected_vaccine_item().text() == "COVID-19 (Moderna)"
    page._select_vaccine_type(None, "Influenza")
    assert page.vaccine_types_combo.currentText() == "Influenza"
    assert not page.prepare_flu_covid_button.isEnabled()


@pytest.mark.parametrize("action", ["clear_form", "start_new_vaccine_record"])
def test_clear_and_new_record_require_new_selection(page, action):
    page._select_vaccine_type(None, "Influenza")
    getattr(page, action)()
    assert_unselected(page)
    page.refresh_view()
    assert_unselected(page)


def test_removing_selected_type_never_selects_neighbor(page):
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    type_id = page._selected_vaccine_item().data(Qt.ItemDataRole.UserRole)
    with connect(page._db_path) as connection:
        assert delete_vaccine_type(connection, type_id)
    page.refresh_view()
    assert_unselected(page)


def test_explicit_record_load_restores_its_type_but_missing_type_clears_choice(page):
    page._select_vaccine_type(None, "Influenza")
    record = page.save_record()
    page.clear_form()
    page._load_record_into_form(record)
    assert page._selected_vaccine_item().text() == "Influenza"
    assert page.vaccine_types_combo.currentText() == "Influenza"
    page._select_vaccine_type(-1, "Unavailable vaccine")
    assert_unselected(page)
    page.print_label()
    assert page.status_label.text() == "Select a vaccine type first."


@pytest.mark.parametrize("mismatch", ["other_type", "renamed_type"])
def test_print_rejects_different_visible_selection_than_saved_record(page, mismatch):
    page._select_vaccine_type(None, "Influenza")
    saved = page.save_record()
    if mismatch == "other_type":
        page._select_vaccine_type(None, "COVID-19 (Moderna)")
    else:
        page._selected_vaccine_item().setText("Renamed vaccine")
        page._refresh_chart_note_preview()
    page.print_label()
    assert "does not match the loaded record" in page.status_label.text()
    with connect(page._db_path) as connection:
        assert list_vaccine_records(connection) == [saved]


def test_busy_controls_do_not_override_selection_requirement(page):
    page._update_handoff_controls(external_busy=True)
    page._update_handoff_controls()
    assert_unselected(page)
    page._select_vaccine_type(None, "Influenza")
    page._update_handoff_controls(external_busy=True)
    assert not page.save_button.isEnabled()
    assert not page.print_button.isEnabled()
    page._update_handoff_controls()
    assert page.save_button.isEnabled()
    assert page.print_button.isEnabled()


def test_selection_style_remains_high_contrast_without_focus():
    base_style = NORD_QSS.split("QComboBox#vaccineTypesCombo {", 1)[1].split("}", 1)[0]
    focus_style = NORD_QSS.split("QComboBox#vaccineTypesCombo:focus {", 1)[1].split("}", 1)[0]
    assert "background-color: #ebcb8b" in base_style
    assert "color: #202630" in base_style
    assert "background-color: #ebcb8b" in focus_style
    assert "selectedVaccineLabel" not in NORD_QSS
    for name in ("vaccineFetchButton", "vaccinePrintButton"):
        assert f"QPushButton#{name} {{" in NORD_QSS
        assert f"QPushButton#{name}:disabled" in NORD_QSS


def test_dropdown_is_the_only_selection_display(page):
    assert page.findChild(vaccine_tab.QLabel, "selectedVaccineLabel") is None
    assert not hasattr(page, "selected_vaccine_label")


@pytest.mark.parametrize("selected", [False, True])
def test_closed_dropdown_ignores_scroll_wheel(page, selected):
    combo = page.vaccine_types_combo
    if selected:
        page._select_vaccine_type(None, "COVID-19 (Moderna)")
    index = combo.currentIndex()
    combo.setFocus()
    for delta in (-120, 120):
        event = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, delta),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        QApplication.sendEvent(combo, event)
        assert combo.currentIndex() == index
    if not selected:
        assert_unselected(page)


@pytest.mark.parametrize("confirm", [False, True])
def test_popup_requires_confirmation_of_highlighted_choice(page, confirm):
    page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    page.show()
    combo = page.vaccine_types_combo
    combo.view().window().setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    combo.showPopup()
    index = combo.findText("COVID-19 (Moderna)")
    combo.view().setCurrentIndex(combo.model().index(index, 0))
    assert_unselected(page)
    QTest.keyClick(combo.view(), Qt.Key.Key_Return if confirm else Qt.Key.Key_Escape)
    if confirm:
        assert combo.currentText() == "COVID-19 (Moderna)"
        assert page.print_button.isEnabled()
    else:
        assert_unselected(page)


@pytest.mark.parametrize("change", [
    {"name": "Updated vaccine"}, {"code": "NEW-CODE"},
    {"chart_note_template": "Updated chart note"},
    {"program_type": "general"}, {"is_active": False},
])
def test_material_catalog_edit_requires_reselection(page, change):
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    type_id = page.vaccine_types_combo.currentData()
    with connect(page._db_path) as connection:
        vaccine = get_vaccine_type(connection, type_id)
        values = {key: getattr(vaccine, key) for key in (
            "name", "code", "chart_note_template", "program_type", "is_active",
        )}
        values.update(change)
        update_vaccine_type(connection, type_id, **values)
    page.refresh_view()
    assert_unselected(page)


def test_catalog_changes_elsewhere_preserve_selection_by_id(page):
    page._select_vaccine_type(None, "COVID-19 (Moderna)")
    type_id = page.vaccine_types_combo.currentData()
    with connect(page._db_path) as connection:
        added = create_vaccine_type(connection, name="Another vaccine")
    page.refresh_view()
    assert page.vaccine_types_combo.findData(added.id) >= 0
    assert page.vaccine_types_combo.currentData() == type_id
    with connect(page._db_path) as connection:
        delete_vaccine_type(connection, added.id)
    page.refresh_view()
    assert page.vaccine_types_combo.findData(added.id) == -1
    assert page.vaccine_types_combo.currentData() == type_id


def test_missing_id_never_falls_back_to_same_name(page):
    page._select_vaccine_type(-1, "Influenza")
    assert_unselected(page)


def test_add_edit_delete_reload_dropdown_without_implicit_selection(page, monkeypatch):
    values = {"name": "New vaccine", "program_type": "general"}
    monkeypatch.setattr(vaccine_tab.VaccineTypeDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(vaccine_tab.VaccineTypeDialog, "values", lambda _self: dict(values))
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_kw: QMessageBox.StandardButton.Yes)
    page.add_vaccine_type()
    assert_unselected(page)
    index = page.vaccine_types_combo.findText("New vaccine")
    assert index >= 0
    page.vaccine_types_combo.setCurrentIndex(index)
    type_id = page.vaccine_types_combo.currentData()
    values["name"] = "Edited vaccine"
    page.edit_vaccine_type()
    assert_unselected(page)
    index = page.vaccine_types_combo.findData(type_id)
    assert page.vaccine_types_combo.itemText(index) == "Edited vaccine"
    page.vaccine_types_combo.setCurrentIndex(index)
    page.delete_vaccine_type()
    assert_unselected(page)
    assert page.vaccine_types_combo.findData(type_id) == -1


def test_order_arrows_persist_order_and_preserve_selected_id(page):
    combo = page.vaccine_types_combo
    assert not page.move_type_up_button.isEnabled()
    assert not page.move_type_down_button.isEnabled()
    combo.setCurrentIndex(1)
    type_id = combo.currentData()
    page.move_type_up_button.click()
    assert combo.currentIndex() == 0
    assert combo.currentData() == type_id
    assert not page.move_type_up_button.isEnabled()
    page.move_type_down_button.click()
    assert combo.currentIndex() == 1
    assert combo.currentData() == type_id
    with connect(page._db_path) as connection:
        assert [item.id for item in list_vaccine_types(connection)] == [
            combo.itemData(index) for index in range(combo.count())
        ]
    page._update_handoff_controls(external_busy=True)
    assert not page.move_type_up_button.isEnabled()
    assert not page.move_type_down_button.isEnabled()
    page.move_vaccine_type(-1)
    assert combo.currentIndex() == 1


def test_primary_actions_have_scoped_highlights(page):
    assert page.fetch_button.objectName() == "vaccineFetchButton"
    assert page.print_button.objectName() == "vaccinePrintButton"
    assert page.vaccine_types_combo.objectName() == "vaccineTypesCombo"


def test_primary_action_highlights_are_text_only_in_all_states():
    button_rules = [
        rule for rule in NORD_QSS.split("}")
        if "QPushButton#vaccineFetchButton" in rule or "QPushButton#vaccinePrintButton" in rule
    ]
    assert any("background-color: transparent" in rule for rule in button_rules)
    for rule in button_rules:
        assert "background-color:" not in rule or "background-color: transparent" in rule
    for name, color in (("vaccineFetchButton", "#88c0d0"), ("vaccinePrintButton", "#a3be8c")):
        style = next(
            rule.split("{", 1)[1] for rule in button_rules
            if rule.split("{", 1)[0].strip() == f"QPushButton#{name}"
        )
        assert f"color: {color}" in style
