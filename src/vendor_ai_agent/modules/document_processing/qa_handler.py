"""Q&A table handler for extracting clarifications from addenda."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from ...models import TenderSection


@dataclass
class QAPair:
    question_id: str
    question: str
    answer: str
    source_file: str


class QAHandler:
    """Extract question-answer pairs from Q&A tables in tender addenda."""
    
    def extract_qa_pairs(self, table: TenderSection) -> List[QAPair]:
        """Extract Q&A pairs from markdown table."""
        content = table.content
        source = table.source_path.name if table.source_path else "unknown"
        
        lines = [l.strip() for l in content.split('\n') if '|' in l and '---' not in l]
        
        if len(lines) < 2:
            return []
        
        headers = self._parse_row(lines[0])
        
        qa_pairs = []
        
        for row in lines[1:]:
            cells = self._parse_row(row)
            
            if not cells:
                continue
            
            qa_pair = self._extract_pair_from_row(cells, headers, source)
            if qa_pair:
                qa_pairs.append(qa_pair)
        
        qa_pairs = self._merge_multirow_pairs(qa_pairs)
        
        return qa_pairs
    
    def _parse_row(self, row: str) -> List[str]:
        """Parse markdown table row into cells."""
        parts = row.split('|')[1:-1]
        return [p.strip() for p in parts]
    
    def _extract_pair_from_row(self, cells: List[str], headers: List[str], source: str) -> QAPair | None:
        """Extract Q&A pair from a single row."""
        if len(cells) < 2:
            return None
        
        first_cell = cells[0]
        
        q_match = re.match(r'^Q(\d+)', first_cell, re.IGNORECASE)
        a_match = re.match(r'^A(\d+)', first_cell, re.IGNORECASE)
        
        if q_match:
            q_id = f"Q{q_match.group(1)}"
            question_text = ' '.join(cells[1:]).strip()
            
            if not question_text:
                question_text = first_cell[len(q_id):].strip()
            
            return QAPair(
                question_id=q_id,
                question=question_text,
                answer="",
                source_file=source
            )
        
        if a_match:
            a_id = f"Q{a_match.group(1)}"
            answer_text = ' '.join(cells[1:]).strip()
            
            if not answer_text:
                answer_text = first_cell[len(a_match.group(0)):].strip()
            
            return QAPair(
                question_id=a_id,
                question="",
                answer=answer_text,
                source_file=source
            )
        
        if len(cells) >= 2:
            q_pattern = r'\bquestion\b'
            a_pattern = r'\banswer\b'
            
            header_str = ' '.join(headers).lower()
            
            if re.search(q_pattern, header_str) and re.search(a_pattern, header_str):
                return QAPair(
                    question_id=f"Q{len(cells)}",
                    question=cells[0],
                    answer=cells[1] if len(cells) > 1 else "",
                    source_file=source
                )
        
        return None
    
    def _merge_multirow_pairs(self, pairs: List[QAPair]) -> List[QAPair]:
        """Merge questions and answers that span multiple rows."""
        merged = []
        pending_question = None
        
        for pair in pairs:
            if pair.question and not pair.answer:
                if pending_question:
                    merged.append(pending_question)
                pending_question = pair
            
            elif pair.answer and not pair.question:
                if pending_question and pending_question.question_id == pair.question_id:
                    pending_question.answer = pair.answer
                    merged.append(pending_question)
                    pending_question = None
                else:
                    merged.append(pair)
            
            elif pair.question and pair.answer:
                if pending_question:
                    merged.append(pending_question)
                    pending_question = None
                merged.append(pair)
        
        if pending_question:
            merged.append(pending_question)
        
        return [p for p in merged if p.question or p.answer]
