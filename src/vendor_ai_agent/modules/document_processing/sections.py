"""Section extraction using heading heuristics."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

from ...models import DocSections, TenderSection
from .keywords import SECTION_HEADING_PATTERNS, SECTION_CONTEXT_HINTS


class SectionExtractor:
    """Extracts text blocks for DocSections from classified TenderSections."""

    def extract(self, sections: Iterable[TenderSection]) -> DocSections:
        aggregated = DocSections()
        sections_list = list(sections)
        current_field = None
        for section in sections_list:
            heading = self._match_heading(section.title)
            if heading:
                current_field = heading
            field_to_use = current_field or self._match_context(section.content)
            if field_to_use and not getattr(aggregated, field_to_use):
                setattr(aggregated, field_to_use, section.content)
        if not aggregated.scope_of_work and sections_list:
            aggregated.scope_of_work = sections_list[0].content
        return aggregated

    def _match_heading(self, text: str) -> str | None:
        lowered = text.lower()
        for field, patterns in SECTION_HEADING_PATTERNS.items():
            for phrase in patterns:
                if phrase in lowered:
                    return field
        return None

    def _match_context(self, text: str) -> str | None:
        lowered = text.lower()
        best_field = None
        best_score = 0
        for field, hints in SECTION_CONTEXT_HINTS.items():
            score = sum(1 for hint in hints if hint in lowered)
            if score > best_score:
                best_field = field
                best_score = score
        return best_field
