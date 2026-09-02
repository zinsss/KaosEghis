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

        def selected_item_id(self):
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
    assert macro_list.item(0).text() == "[+] Grouped"

    page.activate_launcher_item(macro_list, macro_list.item(0))

    assert "Completed 'Second Macro'." in page.log.toPlainText()


def test_launcher_uses_native_same_list_drag_mode(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractItemView

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

    assert macro_list.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove
    assert macro_list.dragEnabled() is True
    assert macro_list.acceptDrops() is True
    assert macro_list.item(0).flags() & Qt.ItemFlag.ItemIsDropEnabled


def test_launcher_mouse_gesture_starts_native_drag() -> None:
    app = _app()

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QListWidgetItem, QWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherListWidget

    class _Page(QWidget):
        def persist_launcher_layout(self) -> None:
            pass

        def show_collection_context_menu(self, *_args) -> None:
            pass

    class _ProbeList(LauncherListWidget):
        def __init__(self) -> None:
            super().__init__("Macro", _Page())
            self.drag_starts = 0

        def startDrag(self, _supported_actions) -> None:
            self.drag_starts += 1

    launcher_list = _ProbeList()
    launcher_list.addItem(QListWidgetItem("First"))
    launcher_list.addItem(QListWidgetItem("Second"))
    launcher_list.resize(300, 160)
    launcher_list.show()
    launcher_list.setFocus()
    app.processEvents()

    start = launcher_list.visualItemRect(launcher_list.item(0)).center()
    end = start + QPoint(app.startDragDistance() + 5, 0)
    QTest.mousePress(
        launcher_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start,
    )
    QTest.mouseMove(launcher_list.viewport(), end, 10)
    QTest.mouseRelease(
        launcher_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        end,
    )
    app.processEvents()

    assert launcher_list.drag_starts == 1


def test_launcher_comment_collection_hides_member_items_from_direct_comments_list(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        add_item_to_launcher_collection,
        create_item,
        create_launcher_collection,
        list_launcher_entries,
        list_launcher_items,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "Comment A", "clipboard", True)
        second = create_item(connection, "Comment B", "randomized_clipboard", True)
        collection = create_launcher_collection(connection, "Comment Pack", "Comments", 1)
        add_item_to_launcher_collection(connection, collection.id, first.id)
        add_item_to_launcher_collection(connection, collection.id, second.id)

        direct_items = list_launcher_items(connection, "Comments")
        entries = list_launcher_entries(connection, "Comments")

    assert [item.name for item in direct_items] == []
    assert [(entry.entry_type, entry.name) for entry in entries] == [
        ("collection", "Comment Pack")
    ]


def test_launcher_same_list_drop_reorders_instead_of_creating_collection(
    tmp_path, monkeypatch
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

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
    source_item = macro_list.item(0)
    target_item = macro_list.item(1)
    macro_list._move_item(0, 1)

    assert macro_list.item(0).text() == target_item.text()
    assert macro_list.item(1).text() == source_item.text()


def test_launcher_cross_list_drop_is_ignored(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_item(connection, "Macro A", "macro", True)
        create_item(connection, "Comment A", "clipboard", True)

    page = LauncherPage(db_path)
    macro_list = page.launcher_lists["Macro"]
    comments_list = page.launcher_lists["Comments"]

    class _FakeDropEvent:
        def __init__(self) -> None:
            self._accepted = False
            self._ignored = False

        def source(self):
            return comments_list

        def ignore(self):
            self._ignored = True

        def isAccepted(self):
            return self._accepted

    event = _FakeDropEvent()
    macro_list.dropEvent(event)

    assert event.isAccepted() is False
    assert event._ignored is True
    assert macro_list.count() == 1
    assert comments_list.count() == 1


def test_existing_items_migrate_as_exposed_in_launcher(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import sqlite3

    from KaosEghis.db.database import initialize_database

    db_path = tmp_path / "KaosEghis.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                emr_target_profile_id INTEGER,
                launcher_section TEXT NOT NULL DEFAULT 'Macro',
                launcher_position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT INTO items (name, item_type) VALUES ('Existing', 'macro')"
        )

    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(items)")
        }
        exposed = connection.execute(
            "SELECT is_launcher_exposed FROM items WHERE name = 'Existing'"
        ).fetchone()[0]

    assert "is_launcher_exposed" in columns
    assert exposed == 1


def test_launcher_exposure_is_persisted_and_filters_direct_items(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, list_launcher_items, update_item

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        visible = create_item(
            connection,
            "Visible text",
            "clipboard",
            launcher_section="Comments",
        )
        hidden = create_item(
            connection,
            "Hidden text",
            "clipboard",
            launcher_section="Comments",
            is_launcher_exposed=False,
        )
        assert visible.is_launcher_exposed is True
        assert hidden.is_launcher_exposed is False
        assert [item.name for item in list_launcher_items(connection, "Comments")] == [
            "Visible text"
        ]

        updated = update_item(
            connection,
            visible.id,
            visible.name,
            visible.item_type,
            visible.is_enabled,
            launcher_section="Comments",
            is_launcher_exposed=False,
        )
        assert updated is not None
        assert updated.is_launcher_exposed is False
        assert list_launcher_items(connection, "Comments") == []


def test_hiding_collection_member_removes_it_from_launcher_collection(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import (
        add_item_to_launcher_collection,
        create_item,
        create_launcher_collection,
        get_launcher_collection,
        list_launcher_entries,
        update_item,
    )

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "Comment A", "clipboard", True)
        second = create_item(connection, "Comment B", "clipboard", True)
        collection = create_launcher_collection(connection, "Comment Pack", "Comments")
        add_item_to_launcher_collection(connection, collection.id, first.id)
        add_item_to_launcher_collection(connection, collection.id, second.id)

        update_item(
            connection,
            first.id,
            first.name,
            first.item_type,
            first.is_enabled,
            launcher_section="Comments",
            is_launcher_exposed=False,
        )
        entries = list_launcher_entries(connection, "Comments")

        assert get_launcher_collection(connection, collection.id) is None
        assert [(entry.entry_type, entry.name) for entry in entries] == [
            ("item", "Comment B")
        ]


def test_preset_text_collection_can_be_created_from_macrotexts_page(
    tmp_path, monkeypatch
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, list_launcher_entries
    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        first = create_item(connection, "Comment A", "clipboard", True)
        second = create_item(connection, "Comment B", "randomized_clipboard", True)

    class _CreateDialog(tab_module.LauncherCollectionCreateDialog):
        def exec(self):
            self.name_input.setText("Comment Pack")
            for row in range(self.items_list.count()):
                self.items_list.item(row).setCheckState(Qt.CheckState.Checked)
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(tab_module, "LauncherCollectionCreateDialog", _CreateDialog)
    page = tab_module.MacroTextsPage(db_path)
    page.create_collection()

    with connect(db_path) as connection:
        entries = list_launcher_entries(connection, "Comments")

    assert {first.id, second.id}
    assert [(entry.entry_type, entry.name) for entry in entries] == [
        ("collection", "Comment Pack")
    ]
    assert page.collections_table.rowCount() == 1


def test_macro_and_macrotext_dialogs_expose_launcher_checkbox(
    tmp_path, monkeypatch
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog
    from KaosEghis.ui.tabs.kaoseghis_tab import MacroTextDialog

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    macro_dialog = MacroEditorDialog(None, db_path=db_path)
    macrotext_dialog = MacroTextDialog(None)

    assert macro_dialog.launcher_exposed.isChecked() is True
    assert macro_dialog.values()["is_launcher_exposed"] is True
    assert macrotext_dialog.launcher_exposed.isChecked() is True

    macro_label = macro_dialog.layout().itemAt(0).layout().labelForField(
        macro_dialog.launcher_exposed
    )
    macrotext_label = macrotext_dialog.layout().itemAt(0).layout().labelForField(
        macrotext_dialog.launcher_exposed
    )
    assert macro_label.text() == "Show in Launcher"
    assert macrotext_label.text() == "Show in Launcher"


def test_launcher_drop_on_item_routes_to_collection_creation() -> None:
    app = _app()

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QAbstractItemView, QListWidgetItem, QWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherListWidget

    class _Page(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.created = None

        def create_collection_from_drop(
            self, source_id, target_id, section, position
        ) -> bool:
            self.created = (source_id, target_id, section, position)
            return True

        def add_item_to_collection_from_drop(self, *_args) -> bool:
            return False

        def persist_launcher_layout(self) -> None:
            pass

        def show_collection_context_menu(self, *_args) -> None:
            pass

    class _OnItemList(LauncherListWidget):
        def dropIndicatorPosition(self):
            return QAbstractItemView.DropIndicatorPosition.OnItem

    class _DropEvent:
        def __init__(self, source, position) -> None:
            self._source = source
            self._position = QPointF(position)
            self.accepted = False
            self.ignored = False
            self.drop_action = None

        def source(self):
            return self._source

        def position(self):
            return self._position

        def setDropAction(self, action) -> None:
            self.drop_action = action

        def accept(self) -> None:
            self.accepted = True

        def ignore(self) -> None:
            self.ignored = True

    page = _Page()
    launcher_list = _OnItemList("Comments", page)
    for item_id, name in ((11, "First text"), (12, "Second text")):
        item = QListWidgetItem(name)
        item.setData(launcher_list.ITEM_ID_ROLE, item_id)
        item.setData(launcher_list.ITEM_TYPE_ROLE, "clipboard")
        item.setData(launcher_list.ENTRY_KIND_ROLE, "item")
        launcher_list.addItem(item)
    launcher_list.resize(300, 160)
    launcher_list.show()
    launcher_list.setCurrentRow(0)
    app.processEvents()

    target_position = launcher_list.visualItemRect(launcher_list.item(1)).center()
    event = _DropEvent(launcher_list, target_position)
    launcher_list.dropEvent(event)

    assert page.created == (11, 12, "Comments", 2)
    assert event.accepted is True
    assert event.drop_action == Qt.DropAction.MoveAction


def test_launcher_drop_on_collection_routes_to_add_item() -> None:
    app = _app()

    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QAbstractItemView, QListWidgetItem, QWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherListWidget

    class _Page(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.added = None

        def create_collection_from_drop(self, *_args) -> bool:
            return False

        def add_item_to_collection_from_drop(self, item_id, collection_id) -> bool:
            self.added = (item_id, collection_id)
            return True

        def persist_launcher_layout(self) -> None:
            pass

        def show_collection_context_menu(self, *_args) -> None:
            pass

    class _OnItemList(LauncherListWidget):
        def dropIndicatorPosition(self):
            return QAbstractItemView.DropIndicatorPosition.OnItem

    class _DropEvent:
        def __init__(self, source, position) -> None:
            self._source = source
            self._position = QPointF(position)
            self.accepted = False

        def source(self):
            return self._source

        def position(self):
            return self._position

        def setDropAction(self, _action) -> None:
            pass

        def accept(self) -> None:
            self.accepted = True

        def ignore(self) -> None:
            pass

    page = _Page()
    launcher_list = _OnItemList("Macro", page)
    source = QListWidgetItem("Macro")
    source.setData(launcher_list.ITEM_ID_ROLE, 21)
    source.setData(launcher_list.ITEM_TYPE_ROLE, "macro")
    source.setData(launcher_list.ENTRY_KIND_ROLE, "item")
    collection = QListWidgetItem("[+] Collection")
    collection.setData(launcher_list.ITEM_ID_ROLE, 31)
    collection.setData(launcher_list.ENTRY_KIND_ROLE, "collection")
    launcher_list.addItem(source)
    launcher_list.addItem(collection)
    launcher_list.resize(300, 160)
    launcher_list.show()
    launcher_list.setCurrentItem(source)
    app.processEvents()

    event = _DropEvent(
        launcher_list,
        launcher_list.visualItemRect(collection).center(),
    )
    launcher_list.dropEvent(event)

    assert page.added == (21, 31)
    assert event.accepted is True
