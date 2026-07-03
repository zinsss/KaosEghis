from KaosEghis.core.inspector_import import (
    derive_ancestor_key,
    derive_target_key,
    list_meaningful_ancestors,
    parse_ancestor_hints,
    parse_inspector_text,
    serialize_ancestor_hints,
)


SAMPLE_TEXT = """How found:\tMouse move (499,113)
\thwnd=0x0000000000040DF0 64bit class="WindowsForms10.Window.8.app.0.2bf8098_r6_ad1" style=0x56000000 ex=0x0
Name:\t"PACS"
ControlType:\tUIA_ButtonControlTypeId (0xC350)
LocalizedControlType:\t"단추"
AutomationId:\t[Not supported]
ClassName:\t[Not supported]
Ancestors:\t"Tools" 도구 모음
\t"standaloneBarDockControl1" 그룹
\t"진료실" 창
\t"" 창
\t"이지스 전자차트 2.0" 창
\t"데스크톱 2" 창
\t[ No Parent ]
"""


def test_parse_inspector_text_extracts_target_fields() -> None:
    record = parse_inspector_text(SAMPLE_TEXT)

    assert record.name == '"PACS"'.strip('"') or record.name == "PACS"
    assert record.control_type == "Button"
    assert record.automation_id is None
    assert record.class_name is None


def test_parse_inspector_text_extracts_ancestors_root_to_leaf() -> None:
    record = parse_inspector_text(SAMPLE_TEXT)

    assert [ancestor.name for ancestor in record.ancestors] == [
        "데스크톱 2",
        "이지스 전자차트 2.0",
        "",
        "진료실",
        "standaloneBarDockControl1",
        "Tools",
    ]


def test_list_meaningful_ancestors_filters_desktop_and_empty_nodes() -> None:
    record = parse_inspector_text(SAMPLE_TEXT)
    meaningful = list_meaningful_ancestors(record)

    assert [ancestor.name for ancestor in meaningful] == [
        "이지스 전자차트 2.0",
        "진료실",
        "standaloneBarDockControl1",
        "Tools",
    ]


def test_derive_target_and_ancestor_keys() -> None:
    record = parse_inspector_text(SAMPLE_TEXT)
    meaningful = list_meaningful_ancestors(record)

    assert derive_target_key(record.name) == "pacs"
    assert derive_ancestor_key(meaningful[-1]) == "tools.toolbar"
    assert derive_ancestor_key(meaningful[1]) == "진료실.window"


def test_serialize_and_parse_ancestor_hints_round_trip() -> None:
    record = parse_inspector_text(SAMPLE_TEXT)
    meaningful = list_meaningful_ancestors(record)[1:]

    serialized = serialize_ancestor_hints(meaningful)
    parsed = parse_ancestor_hints(serialized)

    assert [(item.name, item.control_type) for item in parsed] == [
        ("진료실", "Window"),
        ("standaloneBarDockControl1", "Group"),
        ("Tools", "ToolBar"),
    ]
