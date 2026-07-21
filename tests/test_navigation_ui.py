import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_theme_keeps_selected_button_text_from_changing_size() -> None:
    from KaosEghis.ui.theme import NORD_QSS

    assert "min-height: 24px;" in NORD_QSS
    assert "padding: 8px 12px;" in NORD_QSS
    assert "font-weight: 700;" not in NORD_QSS


def test_main_window_top_level_tabs_are_exact(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    import KaosEghis.ui.plugins.pacs_panel as pacs_panel_module

    monkeypatch.setattr(pacs_panel_module, "check_kaospacs_health", lambda settings: True)
    monkeypatch.setattr(pacs_panel_module, "run_readonly_query", lambda *_args, **_kwargs: (["?column?"], [(1,)]))

    from KaosEghis.ui.main_window import MainWindow

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Macros",
        "KaosGdd",
        "Vaccine",
        "PACS",
        "Flu-Report",
        "Scan",
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

    assert list(tab.nav_buttons.keys()) == ["Launcher", "Builder", "MacroTexts", "EMR"]
    assert isinstance(tab.stacked_widget, QStackedWidget)
    assert tab.stacked_widget.currentWidget() is tab.launcher_page
    assert tab.nav_buttons["Launcher"].isChecked() is True
    assert list(tab.launcher_page.launcher_lists.keys()) == [
        "Favorite",
        "Macro",
        "Comments",
    ]
    assert not hasattr(tab.launcher_page, "summary_label")


def test_kaoseghis_top_nav_pages_are_reachable() -> None:
    _app()

    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    tab = KaosEghisTab()

    tab.nav_buttons["Builder"].click()
    assert tab.stacked_widget.currentWidget() is tab.builder_page

    tab.nav_buttons["MacroTexts"].click()
    assert tab.stacked_widget.currentWidget() is tab.macrotexts_page

    tab.nav_buttons["EMR"].click()
    assert tab.stacked_widget.currentWidget() is tab.emr_page

    tab.nav_buttons["Launcher"].click()
    assert tab.stacked_widget.currentWidget() is tab.launcher_page


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
        docs = create_item(connection, "Print Referral", "macro", True)
        etc = create_item(connection, "Misc Action", "macro", True)
        update_item_launcher_placement(connection, docs.id, "Comments", 1)
        update_item_launcher_placement(connection, etc.id, "Favorite", 1)

    page = LauncherPage(db_path)

    assert page.launcher_lists["Macro"].count() == 1
    assert page.launcher_lists["Comments"].count() == 1
    assert page.launcher_lists["Favorite"].count() == 1
    assert page.launcher_lists["Macro"].item(0).text() == "Open Chart"
    assert page.launcher_lists["Comments"].item(0).text() == "Print Referral"
    assert page.launcher_lists["Favorite"].item(0).text() == "Misc Action"


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
    monkeypatch.setattr(tab_module, "copy_text", lambda text: copied.append(text))
    monkeypatch.setattr(tab_module.random, "choice", lambda values: values[1])

    page = tab_module.LauncherPage(db_path)
    comments = page.launcher_lists["Comments"]
    assert [comments.item(index).text() for index in range(comments.count())] == [
        "Referral comment",
        "Greeting",
    ]

    page.activate_launcher_item(comments, comments.item(0))
    page.activate_launcher_item(comments, comments.item(1))

    assert copied == ["fixed text", "two"]
    assert page.log.toPlainText() == "Copied 'Greeting' to clipboard."


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


def test_launcher_emr_connection_has_distinct_theme_states() -> None:
    from KaosEghis.ui.theme import NORD_QSS

    assert 'QPushButton[emrConnectionState="connected"]' in NORD_QSS
    assert "background-color: #a3be8c;" in NORD_QSS
    assert 'QPushButton[emrConnectionState="stale"]' in NORD_QSS
    assert "background-color: #d08770;" in NORD_QSS


def test_kaosgdd_vaccine_pacs_and_flu_report_tabs_instantiate(tmp_path, monkeypatch) -> None:
    _app()

    monkeypatch.setenv("KAOSEGHIS_DATA_DIR", str(tmp_path))

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.plugins.flu_panel import FluPanel
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel
    from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
    from KaosEghis.ui.tabs.kaosgdd_tab import KaosGddTab
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    kaosgdd_tab = KaosGddTab()
    vaccine_tab = VaccineTab()
    pacs_panel = PacsPanel()
    flu_report_tab = FluReportTab()

    assert kaosgdd_tab is not None
    assert vaccine_tab is not None
    assert pacs_panel is not None
    assert flu_report_tab.findChild(FluPanel) is not None
    assert "KaosEghis-flu Report" in [
        label.text() for label in flu_report_tab.findChildren(QLabel)
    ]


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

    tab_module._configure_persistent_profile(profile)

    assert profile.storage_path == str(tmp_path / "web" / "kaosgdd" / "storage")
    assert profile.cache_path == str(tmp_path / "web" / "kaosgdd" / "cache")
    assert profile.cookies_policy == "force-cookies"
    assert profile.cache_type == "disk-cache"
    assert (tmp_path / "web" / "kaosgdd" / "storage").is_dir()
    assert (tmp_path / "web" / "kaosgdd" / "cache").is_dir()


def test_vaccine_tab_placeholder_text() -> None:
    _app()

    from PySide6.QtWidgets import QLabel

    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    tab = VaccineTab()
    labels = [label.text() for label in tab.findChildren(QLabel)]

    assert "Vaccine" in labels
    assert "Status: planned plugin" in labels
    assert "Vaccine plugin is planned. No workflow is active yet." in labels
