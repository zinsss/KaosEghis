import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_theme_uses_compact_flat_bracketed_buttons() -> None:
    from KaosEghis.ui.theme import NORD_QSS, bracket_button_text

    assert bracket_button_text("Save") == "[ Save ]"
    assert bracket_button_text("[ Save ]") == "[ Save ]"
    assert bracket_button_text("  ") == ""
    assert "min-height: 18px;" in NORD_QSS
    assert "padding: 1px 3px;" in NORD_QSS
    assert "border: none;" in NORD_QSS
    assert "outline: none;" in NORD_QSS
    assert "font-weight: 700;" in NORD_QSS


def test_button_proxy_applies_explicit_brackets_and_reserves_width() -> None:
    _app()

    from PySide6.QtWidgets import QPushButton

    from KaosEghis.ui.theme import KaosEghisProxyStyle, bracket_button_text

    button = QPushButton("Save")
    style = KaosEghisProxyStyle()
    style.polish(button)

    assert button.text() == "[ Save ]"
    assert button.minimumWidth() >= button.fontMetrics().horizontalAdvance(
        button.text()
    )

    button.setText("Reconnect EMR")
    button.show()
    _app().processEvents()

    assert button.text() == "[ Reconnect EMR ]"


def test_theme_flattens_spinbox_stepper_buttons() -> None:
    from KaosEghis.ui.theme import NORD_QSS

    assert "QAbstractSpinBox::up-button" in NORD_QSS
    assert "QAbstractSpinBox::down-button" in NORD_QSS
    assert "background-color: transparent;" in NORD_QSS
    assert "border: none;" in NORD_QSS


def test_main_window_top_level_tabs_are_exact(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "KaosEghis",
        "Memos",
        "Workspace",
        "PACS",
        "Macros",
        "Settings",
    ]
    assert window.width() == 1438
    assert window.height() == 1194
    assert window.minimumWidth() == 1438
    assert window.maximumWidth() == 1438
    assert window.minimumHeight() == 1194
    assert window.maximumHeight() == 1194


def test_main_window_marks_pacs_tab_red_when_unhealthy(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: False)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    pacs_index = [window.tabs.tabText(index) for index in range(window.tabs.count())].index("PACS")
    assert window.tabs.tabBar().tabTextColor(pacs_index).name().lower() == "#bf616a"
    assert "KaosPACS unavailable" in window.tabs.tabBar().tabToolTip(pacs_index)


def test_kaoseghis_tab_has_compact_top_navigation_and_stacked_widget() -> None:
    _app()

    from PySide6.QtWidgets import QStackedWidget

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    assert list(tab.nav_buttons.keys()) == ["Launcher", "SOCL", "Procedures", "Vaccine"]
    assert isinstance(tab.stacked_widget, QStackedWidget)
    assert tab.stacked_widget.currentWidget() is tab.launcher_page
    assert tab.nav_buttons["Launcher"].isChecked() is True
    assert list(tab.launcher_page.launcher_lists.keys()) == [
        "Macro",
        "Comments",
        "Actions",
    ]
    assert tab.launcher_page.socl_label.text() == "SOCL"
    assert not hasattr(tab.launcher_page, "summary_label")


def test_launcher_page_gives_compact_socl_most_of_the_width() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    page = LauncherPage()

    assert page.LAUNCHER_COLUMN_STRETCH == 1
    assert page.SOCL_COLUMN_STRETCH == 3


def test_kaoseghis_top_nav_pages_are_reachable() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    tab.nav_buttons["SOCL"].click()
    assert tab.stacked_widget.currentWidget() is tab.socl_page

    tab.nav_buttons["Procedures"].click()
    assert tab.stacked_widget.currentWidget() is tab.procedures_page

    tab.nav_buttons["Vaccine"].click()
    assert tab.stacked_widget.currentWidget() is tab.vaccine_page

    tab.nav_buttons["Launcher"].click()
    assert tab.stacked_widget.currentWidget() is tab.launcher_page


def test_global_launcher_action_switches_to_kaoseghis_launcher(
    tmp_path, monkeypatch
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(
        pacs_panel_module,
        "run_readonly_query",
        lambda *_args, **_kwargs: (["?column?"], [(1,)]),
    )

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()
    window.tabs.setCurrentWidget(window.settings_tab)
    window.kaoseghis_tab.show_page(2)

    window._handle_launcher_hotkey()

    assert window.tabs.currentWidget() is window.kaoseghis_tab
    assert window.kaoseghis_tab.stacked_widget.currentWidget() is (
        window.kaoseghis_tab.launcher_page
    )
    assert window.kaoseghis_tab.nav_buttons["Launcher"].isChecked() is True
    assert "Ctrl+Alt+Shift+F11" in window.notification_area.text.text()


def test_macros_tab_pages_are_reachable(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.core.scheduler import SchedulerRuntime
    from KaosEghis.ui.tabs.kaoseghis_tab import MacrosTab

    runtime = SchedulerRuntime(parent=None)
    tab = MacrosTab(tmp_path / "KaosEghis.sqlite", scheduler_runtime=runtime)

    assert list(tab.nav_buttons.keys()) == ["Builder", "PresetText", "EMR", "Scheduler"]
    assert tab.stacked_widget.currentWidget() is tab.builder_page

    tab.nav_buttons["PresetText"].click()
    assert tab.stacked_widget.currentWidget() is tab.macrotexts_page

    tab.nav_buttons["EMR"].click()
    assert tab.stacked_widget.currentWidget() is tab.emr_page

    tab.nav_buttons["Scheduler"].click()
    assert tab.stacked_widget.currentWidget() is tab.scheduler_page


def test_workspace_tab_pages_are_reachable(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.ui.tabs.kaoseghis_tab import WorkspaceTab

    tab = WorkspaceTab(tmp_path / "KaosEghis.sqlite")

    assert list(tab.nav_buttons.keys()) == [
        "Mail",
        "Paperless",
        "PDF",
        "rHWP",
        "Flu-Report",
        "Scan",
        "Formatter",
    ]
    assert tab.stacked_widget.currentWidget() is tab.mail_page

    tab.nav_buttons["Flu-Report"].click()
    assert tab.stacked_widget.currentWidget() is tab.flu_report_page

    tab.nav_buttons["Scan"].click()
    assert tab.stacked_widget.currentWidget() is tab.scan_page

    tab.nav_buttons["Formatter"].click()
    assert tab.stacked_widget.currentWidget() is tab.formatter_page


def test_drag_hover_switch_helpers_only_accept_local_file_urls() -> None:
    from PySide6.QtCore import QMimeData, QUrl

    from KaosEghis.ui.drag_hover_switch import has_local_file_urls

    empty = QMimeData()
    assert has_local_file_urls(empty) is False

    local_files = QMimeData()
    local_files.setUrls([QUrl.fromLocalFile(r"C:\temp\scan.pdf")])
    assert has_local_file_urls(local_files) is True

    remote_urls = QMimeData()
    remote_urls.setUrls([QUrl("https://example.com/file.pdf")])
    assert has_local_file_urls(remote_urls) is False


def test_workspace_tab_nav_buttons_accept_drops_for_file_hover_switch(
    tmp_path, monkeypatch
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.ui.tabs.kaoseghis_tab import WorkspaceTab

    tab = WorkspaceTab(tmp_path / "KaosEghis.sqlite")

    assert all(button.acceptDrops() for button in tab.nav_buttons.values())


def test_launcher_page_places_macros_into_three_columns(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, update_item_launcher_placement
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        eghis = create_item(connection, "Open Chart", "macro", True)
        docs = create_item(connection, "Print Referral", "clipboard", True)
        update_item_launcher_placement(connection, docs.id, "Comments", 1)

    page = LauncherPage(db_path)

    assert page.launcher_lists["Macro"].count() == 1
    assert page.launcher_lists["Comments"].count() == 1
    assert page.launcher_lists["Actions"].count() == 2
    assert page.launcher_lists["Macro"].item(0).text() == "Open Chart"
    assert page.launcher_lists["Comments"].item(0).text() == "Print Referral"
    assert page.launcher_lists["Actions"].item(0).text() == "Current Date"
    assert (
        page.launcher_lists["Actions"].item(1).text()
        == "Fetch Pt. Info for Vaccination"
    )
    assert [
        page.socl_panel.pages.tabText(index)
        for index in range(page.socl_panel.pages.count())
    ] == ["S", "O"]

def test_launcher_compact_socl_panel_is_visible(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    page = LauncherPage(db_path)
    assert page.socl_label.text() == "SOCL"
    assert page.socl_panel.finding_count("subjective") > 0
    assert page.socl_panel.finding_count("objective") > 0


def test_launcher_cross_column_move_keeps_macro_out_of_actions_after_reload(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, get_item
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro = create_item(connection, "Move Me", "macro", True)

    page = LauncherPage(db_path)
    source = page.launcher_lists["Macro"]
    destination = page.launcher_lists["Actions"]
    destination.addItem(source.takeItem(0))
    page.persist_launcher_layout()

    with connect(db_path) as connection:
        saved = get_item(connection, macro.id)
    assert saved is not None
    assert saved.launcher_section == "Macro"
    assert saved.launcher_position == 1

    reloaded = LauncherPage(db_path)
    assert reloaded.launcher_lists["Macro"].count() == 1
    assert reloaded.launcher_lists["Macro"].item(0).text() == "Move Me"
    assert reloaded.launcher_lists["Actions"].count() == 2


def test_launcher_same_list_reorder_persists_after_reload(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, list_launcher_items
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_item(connection, "First Macro", "macro", True)
        create_item(connection, "Second Macro", "macro", True)
        create_item(connection, "Third Macro", "macro", True)

    page = LauncherPage(db_path)
    macro_list = page.launcher_lists["Macro"]

    assert [macro_list.item(index).text() for index in range(macro_list.count())] == [
        "First Macro",
        "Second Macro",
        "Third Macro",
    ]

    macro_list._move_item(2, 0)
    page.persist_launcher_layout()

    with connect(db_path) as connection:
        saved = [item.name for item in list_launcher_items(connection, "Macro")]

    assert saved == ["Third Macro", "First Macro", "Second Macro"]

    reloaded = LauncherPage(db_path)
    reloaded_list = reloaded.launcher_lists["Macro"]
    assert [reloaded_list.item(index).text() for index in range(reloaded_list.count())] == [
        "Third Macro",
        "First Macro",
        "Second Macro",
    ]


def test_launcher_comments_copy_simple_and_random_macrotexts(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, replace_clipboard_variants
    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        fixed = create_item(connection, "Referral comment", "clipboard", True)
        replace_clipboard_variants(connection, fixed.id, ["fixed text"])
        randomized = create_item(
            connection, "Greeting", "randomized_clipboard", True
        )
        replace_clipboard_variants(connection, randomized.id, ["one", "two"])

    copied: list[str] = []
    monkeypatch.setattr(
        tab_module,
        "_format_current_date_macrotext",
        lambda now=None: "2026년 07월 22일 오후",
    )
    monkeypatch.setattr(tab_module, "copy_text", lambda text: copied.append(text))
    monkeypatch.setattr(tab_module.random, "choice", lambda values: values[1])

    page = tab_module.LauncherPage(db_path)
    comments = page.launcher_lists["Comments"]
    actions = page.launcher_lists["Actions"]
    assert [comments.item(index).text() for index in range(comments.count())] == [
        "Referral comment",
        "Greeting",
    ]
    assert [actions.item(index).text() for index in range(actions.count())] == [
        "Current Date",
        "Fetch Pt. Info for Vaccination",
    ]

    page.activate_launcher_item(actions, actions.item(0))
    page.activate_launcher_item(comments, comments.item(0))
    page.activate_launcher_item(comments, comments.item(1))

    assert copied == ["2026년 07월 22일 오후", "fixed text", "two"]
    assert page.log.toPlainText() == "Copied 'Greeting' to clipboard."


def test_launcher_comments_include_dynamic_current_date(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item, replace_clipboard_variants
    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        fixed = create_item(connection, "Referral comment", "clipboard", True)
        replace_clipboard_variants(connection, fixed.id, ["fixed text"])

    copied: list[str] = []
    monkeypatch.setattr(
        tab_module,
        "_format_current_date_macrotext",
        lambda now=None: "2026년 07월 22일 오후",
    )
    monkeypatch.setattr(tab_module, "copy_text", lambda text: copied.append(text))

    page = tab_module.LauncherPage(db_path)
    actions = page.launcher_lists["Actions"]
    comments = page.launcher_lists["Comments"]

    assert [actions.item(index).text() for index in range(actions.count())] == [
        "Current Date",
        "Fetch Pt. Info for Vaccination",
    ]
    assert [comments.item(index).text() for index in range(comments.count())] == [
        "Referral comment",
    ]

    page.activate_launcher_item(actions, actions.item(0))

    assert copied == ["2026년 07월 22일 오후"]
    assert page.log.toPlainText() == "Copied current date to clipboard."


def test_launcher_hides_non_executable_macros_but_keeps_macrotexts(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_item(connection, "Executable Macro", "macro", True, launcher_section="Macro")
        create_item(connection, "Template Macro", "macro", False, launcher_section="Macro")
        create_item(connection, "MacroText", "clipboard", False, launcher_section="Comments")

    page = LauncherPage(db_path)

    macro_items = [
        page.launcher_lists["Macro"].item(index).text()
        for index in range(page.launcher_lists["Macro"].count())
    ]
    comment_items = [
        page.launcher_lists["Comments"].item(index).text()
        for index in range(page.launcher_lists["Comments"].count())
    ]
    action_items = [
        page.launcher_lists["Actions"].item(index).text()
        for index in range(page.launcher_lists["Actions"].count())
    ]

    assert macro_items == ["Executable Macro"]
    assert comment_items == ["MacroText"]
    assert action_items == ["Current Date", "Fetch Pt. Info for Vaccination"]


def test_launcher_runs_without_confirmation_and_shows_running_status(
    tmp_path,
    monkeypatch,
) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from types import SimpleNamespace

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import create_item
    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        macro = create_item(connection, "물치", "macro", True)

    page = tab_module.LauncherPage(db_path)

    def fail_if_confirmed(*_args, **_kwargs):
        raise AssertionError("Launcher macro execution must not ask for confirmation.")

    class FakeMacroRunner:
        def __init__(self, _db_path) -> None:
            pass

        def execute_macro(self, item_id, dry_run=False):
            assert item_id == macro.id
            assert dry_run is False
            assert page.log.toPlainText() == "Running '물치'..."
            return SimpleNamespace(
                success=True,
                message="Macro execution completed.",
                executed_steps=1,
                failed_step=None,
            )

    monkeypatch.setattr(tab_module.QMessageBox, "question", fail_if_confirmed)
    monkeypatch.setattr(tab_module, "MacroRunner", FakeMacroRunner)

    page._run_macro_by_id(macro.id)

    assert page.log.toPlainText().startswith("Completed '물치'.")


def test_launcher_page_has_emr_connection_toggle(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"

    class _State:
        status = "green"
        pid = 1234
        message = "Connected and active"
        process_name = "eGhis.exe"
        exe_path = r"C:\eghis\eGhis.exe"

    class _Profile:
        name = "eGHIS Production"
        process_name = "eGhis.exe"
        window_title_contains = "이지스 전자차트 2.0"
        executable_path = r"C:\eghis\eGhis.exe"

    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    monkeypatch.setattr(tab_module, "get_active_emr_target_profile", lambda connection: _Profile())
    monkeypatch.setattr(tab_module, "get_settings", lambda connection: {})
    monkeypatch.setattr(tab_module, "refresh_cached_eghis_state", lambda settings: _State())
    monkeypatch.setattr(tab_module, "get_cached_eghis_state", lambda: _State())

    page = LauncherPage(db_path)
    page.connection_toggle.click()

    assert page.connection_toggle.text() == "EMR Connected"
    assert page.connection_toggle.isChecked() is True
    assert page.connection_toggle.property("emrConnectionState") == "connected"
    assert "Connected and active" in page.connection_status_label.text()


def test_launcher_auto_connect_runs_once_on_startup_and_does_not_retry_after_failure(
    tmp_path,
    monkeypatch,
) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    db_path = tmp_path / "KaosEghis.sqlite"

    class _State:
        status = "red"
        pid = None
        message = "Eghis not found"
        process_name = None
        exe_path = None

    class _Profile:
        id = 1
        name = "eGHIS Production"
        process_name = "eGhis.exe"
        window_title_contains = "이지스 전자차트 2.0"
        executable_path = r"C:\eghis\eGhis.exe"

    import KaosEghis.ui.tabs.kaoseghis_tab as tab_module

    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(tab_module, "get_active_emr_target_profile", lambda connection: _Profile())
    monkeypatch.setattr(tab_module, "get_settings", lambda connection: {})
    monkeypatch.setattr(
        tab_module,
        "refresh_cached_eghis_state",
        lambda settings, **kwargs: calls.append(
            ("refresh", bool(kwargs.get("eager_grid_cache")))
        )
        or _State(),
    )
    monkeypatch.setattr(tab_module, "get_cached_eghis_state", lambda: None)

    page = LauncherPage(db_path)

    assert calls == [("refresh", True)]

    page.refresh_view()

    assert calls == [("refresh", True)]
    assert page.connection_toggle.isChecked() is False


def test_launcher_emr_connection_has_distinct_theme_states() -> None:
    from KaosEghis.ui.theme import NORD_QSS

    assert 'QPushButton[emrConnectionState="connected"]' in NORD_QSS
    assert "color: #a3be8c;" in NORD_QSS
    assert 'QPushButton[emrConnectionState="stale"]' in NORD_QSS
    assert "color: #d08770;" in NORD_QSS


def test_workspace_and_pacs_surfaces_instantiate(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QLabel, QTableWidget

    from KaosEghis.ui.plugins.flu_panel import FluPanel
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel
    from KaosEghis.ui.tabs.kaoseghis_tab import WorkspaceTab

    pacs_panel = PacsPanel()
    workspace_tab = WorkspaceTab(tmp_path / "KaosEghis.sqlite")

    assert pacs_panel is not None
    assert workspace_tab.findChild(FluPanel) is not None
    assert "KaosEghis-flu Report" in [
        label.text() for label in workspace_tab.findChildren(QLabel)
    ]
    flu_panel = workspace_tab.findChild(FluPanel)
    assert flu_panel is not None
    assert flu_panel.findChild(QTableWidget) is flu_panel.report_table
    assert flu_panel.report_table.columnCount() == 3
    assert flu_panel.status_label.text() == "Not loaded yet."


def test_main_window_starts_without_querying_flu_db(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.flu_panel as flu_panel_module
    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(
        flu_panel_module,
        "fetch_weekly_age_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Flu DB query should not run during startup")
        ),
    )
    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(
        pacs_panel_module,
        "run_readonly_query",
        lambda *_args, **_kwargs: (["?column?"], [(1,)]),
    )

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    workspace_tab = window.tabs.widget(2)
    flu_tab = workspace_tab.flu_report_page
    assert flu_tab is not None


def test_flu_panel_load_failure_updates_status_without_raising(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel(tmp_path / "KaosEghis.sqlite")

    def fake_start_report_worker(week_number, generation) -> None:
        panel.report_failed.emit(generation, "Flu report DB query failed.")

    monkeypatch.setattr(panel, "_start_report_worker", fake_start_report_worker)

    from KaosEghis.db.database import connect, initialize_database
    from KaosEghis.db.repositories import set_settings

    initialize_database(tmp_path / "KaosEghis.sqlite")
    with connect(tmp_path / "KaosEghis.sqlite") as connection:
        set_settings(
            connection,
            {
                "eghis_db_connection_string": "postgresql://readonly@db/eghis",
            },
        )

    panel.load_report()

    assert panel.status_label.text() == "Flu report DB query failed."
    assert panel.search_button.isEnabled() is True


def test_flu_panel_settings_lookup_runs_behind_worker_boundary(tmp_path, monkeypatch) -> None:
    _app()

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel(tmp_path / "KaosEghis.sqlite")
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        panel,
        "_start_report_worker",
        lambda week_number, generation: calls.append((week_number, generation)),
    )

    panel.load_report()

    assert calls == [(int(panel.week_input.text()), 1)]
    assert panel.status_label.text() == "Loading report..."


def test_flu_panel_unconfigured_worker_result_is_non_modal(tmp_path) -> None:
    _app()

    from KaosEghis.ui.plugins.flu_panel import FluPanel

    panel = FluPanel(tmp_path / "KaosEghis.sqlite")
    panel._loading = True
    panel._load_generation = 1
    panel.search_button.setEnabled(False)

    panel.report_unconfigured.emit(1)

    assert panel.status_label.text() == "No eGHIS DB connection configured."
    assert panel.total_visits_label.text() == "Total Visits(Practice) Count: 0"
    assert panel.search_button.isEnabled() is True

def test_kaosgdd_profile_persists_cookies_and_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.tabs.kaosgdd_tab as tab_module

    class FakeProfile:
        class PersistentCookiesPolicy:
            ForcePersistentCookies = "force-cookies"

        class HttpCacheType:
            DiskHttpCache = "disk-cache"

        def __init__(self) -> None:
            self.storage_path = None
            self.cache_path = None
            self.cookies_policy = None
            self.cache_type = None

        def setPersistentStoragePath(self, value) -> None:
            self.storage_path = value

        def setCachePath(self, value) -> None:
            self.cache_path = value

        def setPersistentCookiesPolicy(self, value) -> None:
            self.cookies_policy = value

        def setHttpCacheType(self, value) -> None:
            self.cache_type = value

    monkeypatch.setattr(tab_module, "QWebEngineProfile", FakeProfile)
    profile = FakeProfile()

    tab_module._configure_persistent_profile(profile, "memos")

    assert profile.storage_path == str(tmp_path / "web" / "kaosgdd" / "storage")
    assert profile.cache_path == str(tmp_path / "web" / "kaosgdd" / "cache")
    assert profile.cookies_policy == "force-cookies"
    assert profile.cache_type == "disk-cache"
    assert (tmp_path / "web" / "kaosgdd" / "storage").is_dir()
    assert (tmp_path / "web" / "kaosgdd" / "cache").is_dir()


def test_memos_tab_falls_back_without_webengine(monkeypatch) -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    import KaosEghis.ui.tabs.memos_tab as tab_module
    import KaosEghis.ui.tabs.service_web_tab as service_tab_module

    monkeypatch.setattr(service_tab_module, "QWebEngineView", None)
    monkeypatch.setattr(service_tab_module, "QWebEnginePage", None)
    monkeypatch.setattr(service_tab_module, "QWebEngineProfile", None)

    tab = tab_module.MemosTab()

    labels = [label.text() for label in tab.findChildren(QLabel)]
    assert "Memos webview not available." in labels


def test_memos_profile_persists_cookies_and_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.tabs.service_web_tab as tab_module

    class FakeProfile:
        class PersistentCookiesPolicy:
            ForcePersistentCookies = "force-cookies"

        class HttpCacheType:
            DiskHttpCache = "disk-cache"

        def __init__(self) -> None:
            self.storage_path = None
            self.cache_path = None
            self.cookies_policy = None
            self.cache_type = None

        def setPersistentStoragePath(self, value) -> None:
            self.storage_path = value

        def setCachePath(self, value) -> None:
            self.cache_path = value

        def setPersistentCookiesPolicy(self, value) -> None:
            self.cookies_policy = value

        def setHttpCacheType(self, value) -> None:
            self.cache_type = value

    monkeypatch.setattr(tab_module, "QWebEngineProfile", FakeProfile)

    profile = FakeProfile()

    tab_module._configure_persistent_profile(profile, "memos")

    assert profile.storage_path == str(tmp_path / "web" / "memos" / "storage")
    assert profile.cache_path == str(tmp_path / "web" / "memos" / "cache")
    assert profile.cookies_policy == "force-cookies"
    assert profile.cache_type == "disk-cache"
    assert (tmp_path / "web" / "memos" / "storage").is_dir()
    assert (tmp_path / "web" / "memos" / "cache").is_dir()


def test_default_settings_include_internal_memos_url() -> None:
    from KaosEghis.config import DEFAULT_CONFIG
    from KaosEghis.db.repositories import DEFAULT_SETTINGS

    assert DEFAULT_CONFIG.memos_url == "http://100.94.208.16:5230/"
    assert DEFAULT_SETTINGS["memos_url"] == "http://100.94.208.16:5230/"
    assert DEFAULT_SETTINGS["paperless_url"] == "http://100.94.208.16:8000/"
    assert DEFAULT_SETTINGS["stirling_pdf_url"] == "http://100.94.208.16:8082/"
    assert DEFAULT_SETTINGS["rhwp_url"] == "http://100.94.208.16:8085/rhwp/"
    assert DEFAULT_SETTINGS["wikijs_url"] == "http://100.94.208.16:3001/"
    assert DEFAULT_SETTINGS["sftpgo_url"] == "http://100.94.208.16:8081/web/client/login"


def test_vaccine_tab_instantiates_real_page(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    tab = VaccineTab(db_path)

    assert tab.fetch_button.text() == "Fetch from EMR"
    assert tab.records_table.columnCount() == 6
    assert tab.vaccine_types_list.count() >= 2
    assert tab.status_label.text() == "Ready."


def test_vaccine_fetch_action_switches_to_vaccine_and_calls_fetch(
    tmp_path, monkeypatch
) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from KaosEghis.db.database import initialize_database
    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    tab = KaosEghisTab(db_path)

    called: list[str] = []
    monkeypatch.setattr(
        tab.vaccine_page,
        "fetch_current_patient_from_emr",
        lambda: called.append("fetch") or True,
    )

    tab.launcher_page._run_launcher_action(-100)

    assert tab.stacked_widget.currentWidget() is tab.vaccine_page
    assert called == ["fetch"]
    assert tab.launcher_page.log.toPlainText() == "Loaded patient context for vaccination."
