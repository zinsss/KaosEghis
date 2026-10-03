import json
from types import SimpleNamespace
import time

from KaosEghis.tools.inspect_reception_status import (
    PANE_NAME, describe_grid, reception_ancestor, safe_header, status_label,
)


def test_status_labels_only_return_known_states():
    assert status_label("\ubcf4\ub958") == "\ubcf4\ub958"
    assert status_label("\ubcf4\ub958 (12)") == "\ubcf4\ub958"
    assert status_label("\uc644\ub8cc 20\uba85") == "\uc644\ub8cc"
    assert status_label("\ubcf4\ub958 private-name") is None
    assert status_label("private-name") is None


def test_headers_never_return_values_or_unrecognized_text():
    assert safe_header("\ud658\uc790\ubc88\ud638 row 1") == "\ud658\uc790\ubc88\ud638"
    assert safe_header("private-name") is None
    assert safe_header("123456") is None
    assert safe_header("\ud658\uc790\ubc88\ud638 123456") is None


def test_devexpress_header_caption_is_allowlisted():
    header = SimpleNamespace(element_info=SimpleNamespace(control_type="Header", name="\uc0c1\ud0dc"), children=lambda: [])
    grid = SimpleNamespace(children=lambda: [header])
    report = describe_grid(grid, [], time.monotonic() + 1)
    assert report["headers"] == ["\uc0c1\ud0dc"]


def test_point_ancestor_requires_same_emr_process():
    pane = SimpleNamespace(element_info=SimpleNamespace(process_id=10, name=PANE_NAME))
    assert reception_ancestor(pane, 10) is pane
    assert reception_ancestor(pane, 11) is None
    leaf = SimpleNamespace(element_info=SimpleNamespace(process_id=10, name="private-value"), parent=lambda: pane)
    assert reception_ancestor(leaf, 10) is pane


def test_point_ancestor_walk_is_bounded():
    node = SimpleNamespace(element_info=SimpleNamespace(process_id=10, name="private-value"))
    calls = []
    node.parent = lambda: calls.append(1) or node
    assert reception_ancestor(node, 10) is None
    assert len(calls) == 20


def test_grid_report_does_not_expand_patient_rows_or_export_unknown_headers():
    class Node:
        def __init__(self, kind, name, children=()):
            self.element_info = SimpleNamespace(control_type=kind, name=name)
            self._children = children

        def children(self):
            if self.element_info.control_type == "ListItem":
                raise AssertionError("Patient rows must not be expanded")
            return self._children

    grid = Node("Table", "MainView", (
        Node("Header", "", (
            Node("HeaderItem", "\ud658\uc790\ubc88\ud638"),
            Node("HeaderItem", "private-name"),
        )),
        Node("Custom", "Data Panel", (Node("ListItem", "private-row-value"),)),
    ))
    grid.iface_grid = SimpleNamespace(CurrentRowCount=1, CurrentColumnCount=2)
    result = describe_grid(grid, ["\uc678\ub798\ub9ac\uc2a4\ud2b8"], time.monotonic() + 1)
    assert result["headers"] == ["\ud658\uc790\ubc88\ud638"]
    assert "private" not in json.dumps(result)
