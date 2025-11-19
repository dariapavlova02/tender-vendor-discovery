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
        field_contents = {}
        
        for section in sections_list:
            if section.section_type == 'table':
                if self._is_important_table(section):
                    aggregated.tables.append(section)
            else:
                heading = self._match_heading(section.title)
                if heading:
                    current_field = heading
                field_to_use = current_field or self._match_context(section.content)
                if field_to_use:
                    if field_to_use not in field_contents:
                        field_contents[field_to_use] = []
                    field_contents[field_to_use].append(section.content)
        
        for field, contents in field_contents.items():
            setattr(aggregated, field, "\n\n".join(contents))
        
        if not aggregated.scope_of_work and sections_list:
            for section in sections_list:
                if section.content.strip() and section.section_type != 'table':
                    aggregated.scope_of_work = section.content
                    break
        aggregated.table_summaries = self._summarize_tables(aggregated.tables)
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

    def _is_important_table(self, section: TenderSection) -> bool:
        """Filter tables that likely contain critical procurement info."""
        content = section.content.lower()
        title = section.title.lower()
        
        critical_indicators = [
            'price', 'amount', 'cost', '$', 'cad',
            'quantity', 'qty', 'volume', 'unit',
            'item', 'line', 'specification', 'requirement',
            'deadline', 'delivery', 'date', 'timeline',
            'supplier', 'vendor', 'contractor',
            'category', 'type', 'description'
        ]
        
        return any(indicator in content or indicator in title for indicator in critical_indicators)

    def _summarize_tables(self, tables: List[TenderSection]) -> str:
        """Generate compact description of tables for LLM context."""
        if not tables:
            return ""
        
        summaries = []
        for i, table in enumerate(tables, 1):
            lines = [l.strip() for l in table.content.split('\n') if l.strip()]
            header_line = next((l for l in lines if '|' in l), "")
            row_count = len([l for l in lines if l.strip().startswith('|')]) - 2
            
            source_name = Path(table.source_path).name if table.source_path else "Unknown"
            
            summaries.append(
                f"Table {i} [{table.title}] from {source_name}: "
                f"{max(0, row_count)} data rows, columns: {header_line[:100]}"
            )
        
        return "\n".join(summaries)
