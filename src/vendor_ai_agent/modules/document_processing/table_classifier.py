"""Universal table classification for tender documents."""
from __future__ import annotations

import re
from typing import Literal

from ...models import TenderSection

TableType = Literal["qa", "line_items", "technical_specs", "quality", "pricing", "unknown"]


class TableClassifier:
    
    PRIORITY_ORDER = {
        "line_items": 1,
        "technical_specs": 2,
        "quality": 3,
        "qa": 99,
        "pricing": 99,
        "unknown": 99,
    }
    
    def classify(self, table: TenderSection) -> TableType:
        content = table.content.lower()
        
        lines = [l.strip() for l in content.split('\n') if '|' in l]
        if len(lines) < 2:
            return "unknown"
        
        header = lines[0].lower()
        headers = [h.strip() for h in header.split('|')[1:-1]]
        
        first_rows = '\n'.join(lines[:5]).lower()
        
        if self._is_qa_table(headers, first_rows):
            return "qa"
        
        if self._is_line_items_table(headers, content):
            return "line_items"
        
        if self._is_technical_specs_table(headers, content):
            return "technical_specs"
        
        if self._is_quality_table(headers, content):
            return "quality"
        
        if self._is_pricing_table(headers):
            return "pricing"
        
        return "unknown"
    
    def _is_qa_table(self, headers: list[str], first_rows: str) -> bool:
        qa_patterns = [
            r'\bq\d+\b',
            r'\ba\d+\b',
            r'\bquestion\s*\d+\b',
            r'\banswer\s*\d+\b',
            r'questions\s+and\s+answers',
        ]
        
        for pattern in qa_patterns:
            if re.search(pattern, first_rows):
                return True
        
        qa_headers = ['question', 'answer', 'q&a', 'q/a']
        for h in headers:
            if any(qa in h for qa in qa_headers):
                return True
        
        return False
    
    def _is_line_items_table(self, headers: list[str], content: str) -> bool:
        line_item_keywords = [
            'line item',
            'line-item',
            'item no',
            'item #',
            'line no',
            'caliber',
            'calibre',
            'description',
            'product',
            'material',
            'specification',
        ]
        
        header_str = ' '.join(headers)
        
        match_count = sum(1 for keyword in line_item_keywords if keyword in header_str)
        
        if match_count >= 2:
            return True
        
        if 'line item' in header_str or 'line-item' in header_str:
            return True
        
        return False
    
    def _is_technical_specs_table(self, headers: list[str], content: str) -> bool:
        tech_keywords = [
            'specification',
            'requirement',
            'standard',
            'performance',
            'technical',
            'characteristic',
            'property',
            'parameter',
        ]
        
        header_str = ' '.join(headers)
        
        return any(keyword in header_str for keyword in tech_keywords)
    
    def _is_quality_table(self, headers: list[str], content: str) -> bool:
        quality_keywords = [
            'defect',
            'quality',
            'allowable',
            'aql',
            'acceptance',
            'inspection',
            'sampling',
        ]
        
        header_str = ' '.join(headers)
        content_lower = content.lower()
        
        if any(keyword in header_str for keyword in quality_keywords):
            return True
        
        if 'defect description' in content_lower and 'allowable' in content_lower:
            return True
        
        return False
    
    def _is_pricing_table(self, headers: list[str]) -> bool:
        pricing_keywords = [
            'price',
            'cost',
            'unit price',
            'total price',
            'amount',
            'rate',
            'bid price',
        ]
        
        header_str = ' '.join(headers)
        
        return any(keyword in header_str for keyword in pricing_keywords)
    
    @classmethod
    def get_priority(cls, table_type: TableType) -> int:
        return cls.PRIORITY_ORDER.get(table_type, 99)
