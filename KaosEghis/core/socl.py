from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class SoclSelectedFinding:
    domain: str
    collection_name: str
    finding_label: str
    render_text: str
    detail: str = ""


@dataclass(frozen=True)
class SoclRenderedNote:
    subjective: str
    objective: str

    @property
    def combined(self) -> str:
        return "\n\n".join(
            section for section in (self.subjective, self.objective) if section.strip()
        )


def render_socl_note(
    selections: Iterable[SoclSelectedFinding],
) -> SoclRenderedNote:
    selected = tuple(selections)
    return SoclRenderedNote(
        subjective=_render_section(selected, "subjective", "S)"),
        objective=_render_section(selected, "objective", "O)"),
    )


def _render_section(
    selections: tuple[SoclSelectedFinding, ...],
    domain: str,
    prefix: str,
) -> str:
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for selection in selections:
        if selection.domain != domain:
            continue
        phrase = (selection.render_text or selection.finding_label).strip()
        if not phrase:
            continue
        detail = selection.detail.strip()
        rendered = f"{phrase}: {detail}" if detail else phrase
        grouped.setdefault(selection.collection_name.strip(), []).append(rendered)

    lines: list[str] = []
    for collection_name, findings in grouped.items():
        body = "; ".join(findings).rstrip(". ") + "."
        label = f"{collection_name}: " if collection_name else ""
        indentation = prefix if not lines else " " * len(prefix)
        lines.append(f"{indentation} {label}{body}")
    return "\n".join(lines)
