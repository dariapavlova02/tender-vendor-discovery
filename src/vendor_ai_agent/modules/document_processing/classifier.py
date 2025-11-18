"""Naive document classifier for tender files."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class DocumentType(str, Enum):
    CORE_SCOPE = "core_scope"
    TECH_SPEC = "tech_spec"
    ADDENDUM = "addendum"
    LEGAL = "legal"
    OTHER = "other"


@dataclass
class ClassifiedDocument:
    path: Path
    doc_type: DocumentType
    title_hint: Optional[str] = None


class DocumentClassifier:
    """Classify documents based on filename heuristics."""

    CORE_KEYWORDS = ["solicitation", "rfp", "rfq", "sow", "scope", "bid document"]
    TECH_KEYWORDS = ["spec", "technical", "appendix", "boq", "schedule"]
    ADDENDUM_KEYWORDS = ["addendum", "addenda"]
    LEGAL_KEYWORDS = ["terms", "agreement", "contract", "legal"]

    def classify(self, path: Path) -> ClassifiedDocument:
        name = path.name.lower()
        doc_type = DocumentType.OTHER
        title_hint = path.stem

        if any(keyword in name for keyword in self.CORE_KEYWORDS):
            doc_type = DocumentType.CORE_SCOPE
        elif any(keyword in name for keyword in self.TECH_KEYWORDS):
            doc_type = DocumentType.TECH_SPEC
        elif any(keyword in name for keyword in self.ADDENDUM_KEYWORDS):
            doc_type = DocumentType.ADDENDUM
        elif any(keyword in name for keyword in self.LEGAL_KEYWORDS):
            doc_type = DocumentType.LEGAL

        return ClassifiedDocument(path=path, doc_type=doc_type, title_hint=title_hint)
