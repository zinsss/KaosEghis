import pytest

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication

from KaosEghis.db.database import connect
from KaosEghis.db.repositories import delete_vaccine_type, list_vaccine_records
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
    assert page.vaccine_types_list.selectedItems() == []
    assert page.selected_vaccine_label.text() == "No vaccine selected"
    assert page.selected_vaccine_label.property("hasSelection") is False
    assert page.chart_note_preview.toPlainText() == ""
    assert page.charting_text_preview.toPlainText() == ""
    assert "(no vaccine selected)" in page.label_preview.toPlainText()
    assert not page.save_button.isEnabled()
    assert not page.print_button.isEnabled()
    assert not page.prepare_flu_covid_button.isEnabled()


def test_no_default_on_startup_or_refresh(page):
    assert page.vaccine_types_list.count() > 0
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


def test_current_row_without_selection_does_not_choose_a_vaccine(page):
    page.vaccine_types_list.setCurrentRow(0, QItemSelectionModel.SelectionFlag.NoUpdate)
    assert page.vaccine_types_list.currentItem() is not None
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
    assert page.selected_vaccine_label.text() == "Selected vaccine: COVID-19 (Moderna)"
    assert page.selected_vaccine_label.property("hasSelection") is True
    assert page.save_button.isEnabled()
    assert page.print_button.isEnabled()
    assert page.prepare_flu_covid_button.isEnabled()
    for index in range(page.vaccine_types_list.count()):
        item = page.vaccine_types_list.item(index)
        assert item.font().bold() == (item is selected)
    page.refresh_view()
    assert page._selected_vaccine_item().text() == "COVID-19 (Moderna)"
    page._select_vaccine_type(None, "Influenza")
    assert page.selected_vaccine_label.text() == "Selected vaccine: Influenza"
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
    assert page.selected_vaccine_label.text() == "Selected vaccine: Influenza"
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
    assert "QListWidget#vaccineTypesList::item:selected:!active" in NORD_QSS
    assert "QListWidget#vaccineTypesList::item:selected:hover" in NORD_QSS
    assert "border-left: 6px solid #ebcb8b" in NORD_QSS
    assert 'QLabel#selectedVaccineLabel[hasSelection="true"]' in NORD_QSS
