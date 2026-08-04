import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_launcher_collection_hides_member_macros_from_direct_launcher(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        add_macro_to_launcher_collection,
        create_item,
        create_launcher_collection,
        list_launcher_entries,
        list_launcher_items,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "First Macro", "macro", True)
        second = create_item(connection, "Second Macro", "macro", True)
        collection = create_launcher_collection(connection, "Grouped", "Macro", 1)
        add_macro_to_launcher_collection(connection, collection.id, first.id)
        add_macro_to_launcher_collection(connection, collection.id, second.id)

        direct_items = list_launcher_items(connection, "Macro")
        entries = list_launcher_entries(connection, "Macro")

    assert [item.name for item in direct_items] == []
    assert [(entry.entry_type, entry.name) for entry in entries] == [
        ("collection", "Grouped")
    ]


def test_launcher_collection_activation_runs_selected_macro(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from types import SimpleNamespace

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        add_macro_to_launcher_collection,
        create_item,
        create_launcher_collection,
    )
    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "First Macro", "macro", True)
        second = create_item(connection, "Second Macro", "macro", True)
        collection = create_launcher_collection(connection, "Grouped", "Macro", 1)
        add_macro_to_launcher_collection(connection, collection.id, first.id)
        add_macro_to_launcher_collection(connection, collection.id, second.id)

    class FakeDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self):
            from PySide6.QtWidgets import QDialog

            return QDialog.DialogCode.Accepted

        def selected_macro_id(self):
            return second.id

    monkeypatch.setattr(tab_module, "LauncherCollectionChooserDialog", FakeDialog)
    monkeypatch.setattr(
        tab_module.MacroRunner,
        "execute_macro",
        lambda self, item_id, dry_run=False: SimpleNamespace(
            success=True,
            executed_steps=1,
            failed_step=None,
            message=f"ran {item_id}",
        ),
    )

    page = tab_module.LauncherPage(db_path)
    macro_list = page.launcher_lists["Macro"]

    assert macro_list.count() == 1
    assert macro_list.item(0).text() == "Grouped >"

    page.activate_launcher_item(macro_list, macro_list.item(0))

    assert "Completed 'Second Macro'." in page.log.toPlainText()


def test_launcher_collection_drop_target_prefers_item_center(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtCore import QPoint, QRect

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_item(connection, "First Macro", "macro", True)
        create_item(connection, "Second Macro", "macro", True)

    page = LauncherPage(db_path)
    macro_list = page.launcher_lists["Macro"]
    item = macro_list.item(0)
    rect = QRect(0, 0, 200, 40)
    monkeypatch.setattr(macro_list, "itemAt", lambda _pos: item)
    monkeypatch.setattr(macro_list, "visualItemRect", lambda _item: rect)

    center_target = macro_list._target_item_for_collection_drop(rect.center())
    edge_target = macro_list._target_item_for_collection_drop(
        QPoint(rect.left() + 1, rect.top() + 1)
    )

    assert center_target is item
    assert edge_target is None
