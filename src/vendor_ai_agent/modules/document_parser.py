"""Deterministic parsers for tender documents."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List

try:
    from PyPDF2 import PdfReader  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - installation issue
    PdfReader = None

try:
    import openpyxl  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    openpyxl = None

from ..contracts import DocumentParserContract
from ..models import DocExtracted, TenderSection
from .document_processing import DocumentClassifier, FieldExtractor, SectionExtractor


class DocumentParser(DocumentParserContract):
    """Responsible for converting tender files into structured sections."""

    PDF_HEADING_PATTERN = re.compile(
        r"(?P<heading>(?:Addendum|Appendix|Table|Section)\s+[A-Za-z0-9#\.-]+[^\n]*)",
        flags=re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.classifier = DocumentClassifier()
        self.section_extractor = SectionExtractor()
        self.field_extractor = FieldExtractor()

    def parse(self, files: Iterable[Path]) -> List[TenderSection]:
        """Parse the provided list of files/directories into structured sections."""

        collected_paths = self._collect_paths(files)
        sections: List[TenderSection] = []
        for path in collected_paths:
            parser = self._select_parser(path)
            if parser is None:
                self.logger.debug("Unsupported file type for %s", path)
                continue
            try:
                parsed = parser(path)
                doc_type = self.classifier.classify(path).doc_type
                for section in parsed:
                    section.metadata["doc_type"] = doc_type.value
                sections.extend(parsed)
            except Exception as exc:  # pragma: no cover - logged for debugging
                self.logger.error("Failed to parse %s: %s", path, exc)
                sections.append(
                    TenderSection(
                        title=path.stem,
                        content="",
                        source_path=path,
                        section_type="error",
                        metadata={"error": str(exc)},
                    )
                )
        return sections

    # ------------------------------------------------------------------
    def _collect_paths(self, targets: Iterable[Path]) -> List[Path]:
        paths: List[Path] = []
        for target in targets:
            if target.is_dir():
                for nested in target.rglob("*"):
                    if nested.is_file():
                        paths.append(nested)
            elif target.is_file():
                paths.append(target)
        return paths

    def _select_parser(self, path: Path):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._parse_pdf
        if suffix in {".xlsx", ".xls"}:
            return self._parse_excel
        if suffix in {".txt", ".md", ".csv"}:
            return self._parse_text
        return None

    # ------------------------------------------------------------------
    def _parse_pdf(self, path: Path) -> List[TenderSection]:
        full_text = self._extract_pdf_text(path)
        segments = self._segment_pdf_text(full_text)

        sections: List[TenderSection] = []
        if not segments:
            sections.append(
                TenderSection(
                    title=path.stem,
                    content=full_text.strip(),
                    source_path=path,
                    section_type="text",
                    metadata={"file_type": "pdf"},
                )
            )
            return sections

        for heading, content in segments:
            title = f"{path.stem} – {heading.strip()}"
            sections.append(
                TenderSection(
                    title=title,
                    content=content.strip(),
                    source_path=path,
                    section_type="text",
                    metadata={"file_type": "pdf"},
                )
            )
        return sections

    def _extract_pdf_text(self, path: Path) -> str:
        if PdfReader is None:
            raise RuntimeError("PyPDF2 is required for PDF parsing but not installed")
        reader = PdfReader(path)
        texts: List[str] = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - corrupted pages
                self.logger.warning("Failed to extract page on %s: %s", path, exc)
        return "\n".join(texts)

    def _segment_pdf_text(self, text: str) -> List[tuple[str, str]]:
        matches = list(self.PDF_HEADING_PATTERN.finditer(text))
        if not matches:
            return []
        segments: List[tuple[str, str]] = []
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            heading = match.group("heading")
            content = text[start:end]
            segments.append((heading, content))
        return segments

    # ------------------------------------------------------------------
    def _parse_excel(self, path: Path) -> List[TenderSection]:
        sections: List[TenderSection] = []
        if openpyxl is None:
            raise RuntimeError("openpyxl is required for Excel parsing but not installed")
        workbook = openpyxl.load_workbook(path, data_only=True)
        for sheet in workbook.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if value is None else str(value) for value in row]
                rows.append(",".join(cells))
            sections.append(
                TenderSection(
                    title=f"{path.stem} – {sheet.title}",
                    content="\n".join(rows).strip(),
                    source_path=path,
                    section_type="table",
                    metadata={"file_type": "excel", "sheet": sheet.title},
                )
            )
        return sections

    def _parse_text(self, path: Path) -> List[TenderSection]:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return [
            TenderSection(
                title=path.stem,
                content=content.strip(),
                source_path=path,
                section_type="text",
                metadata={"file_type": "text"},
            )
        ]
