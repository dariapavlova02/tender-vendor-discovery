"""Document classifier with content-based detection fallback."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import pdfplumber


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
    """Classify documents based on filename + content analysis."""

    CORE_KEYWORDS = ["solicitation", "rfp", "rfq", "sow", "scope", "bid document", "request for"]
    TECH_KEYWORDS = ["spec", "technical", "appendix", "boq", "schedule", "attachment"]
    ADDENDUM_KEYWORDS = ["addendum", "addenda", "amendment"]
    LEGAL_KEYWORDS = ["terms", "agreement", "contract", "legal"]

    def classify(self, path: Path) -> ClassifiedDocument:
        name = path.name.lower()
        doc_type = DocumentType.OTHER
        title_hint = path.stem

        filename_hint = None
        if any(keyword in name for keyword in self.CORE_KEYWORDS):
            filename_hint = DocumentType.CORE_SCOPE
        elif any(keyword in name for keyword in self.TECH_KEYWORDS):
            filename_hint = DocumentType.TECH_SPEC
        elif any(keyword in name for keyword in self.ADDENDUM_KEYWORDS):
            filename_hint = DocumentType.ADDENDUM
        elif any(keyword in name for keyword in self.LEGAL_KEYWORDS):
            filename_hint = DocumentType.LEGAL

        content_type = self._peek_inside(path)
        
        if content_type:
            doc_type = content_type
        elif filename_hint:
            doc_type = filename_hint
        else:
            doc_type = DocumentType.OTHER

        return ClassifiedDocument(path=path, doc_type=doc_type, title_hint=title_hint)

    def _peek_inside(self, path: Path) -> Optional[DocumentType]:
        """Analyze content to detect document type."""
        suffix = path.suffix.lower()
        
        if suffix == '.pdf':
            return self._peek_pdf(path)
        elif suffix in {'.docx', '.doc'}:
            return self._peek_docx(path)
        
        return None
    
    def _peek_pdf(self, path: Path) -> Optional[DocumentType]:
        """Analyze first 2 pages of PDF."""
        try:
            with pdfplumber.open(path) as pdf:
                pages_to_read = min(2, len(pdf.pages))
                text_sample = ""
                
                for i in range(pages_to_read):
                    page_text = pdf.pages[i].extract_text()
                    if page_text:
                        text_sample += page_text[:1000]
                
                return self._classify_by_content(text_sample)
                
        except Exception:
            return None
    
    def _peek_docx(self, path: Path) -> Optional[DocumentType]:
        """Analyze first paragraphs of Word document."""
        try:
            from docx import Document
            
            doc = Document(path)
            text_sample = ""
            
            for para in doc.paragraphs[:20]:
                text_sample += para.text + "\n"
                if len(text_sample) > 2000:
                    break
            
            return self._classify_by_content(text_sample)
            
        except Exception:
            return None
    
    def _classify_by_content(self, text: str) -> Optional[DocumentType]:
        """Classify document based on text content."""
        if not text:
            return None
        
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["addendum no", "amendment no", "addenda"]):
            return DocumentType.ADDENDUM
        elif any(kw in text_lower for kw in ["request for proposal", "request for quotation", "rfp", "rfq", "solicitation"]):
            return DocumentType.CORE_SCOPE
        elif any(kw in text_lower for kw in ["technical specification", "appendix", "attachment", "schedule a", "schedule b"]):
            return DocumentType.TECH_SPEC
        elif any(kw in text_lower for kw in ["terms and conditions", "general conditions", "contract agreement"]):
            return DocumentType.LEGAL
        
        return None
