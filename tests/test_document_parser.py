from pathlib import Path

from vendor_ai_agent.modules.document_parser import DocumentParser


CANADIAN_TENDER_DIR = Path(
    "data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda"
)


def test_parser_extracts_sections_from_canadian_tender() -> None:
    parser = DocumentParser()
    sections = parser.parse([CANADIAN_TENDER_DIR])

    assert sections, "Parser must return sections for the provided tender folder"

    pdf_sections = [s for s in sections if s.source_path and s.source_path.suffix.lower() == ".pdf"]
    table_sections = [s for s in sections if s.section_type == "table"]

    assert pdf_sections, "Should detect and parse PDF addenda"
    assert table_sections, "Should extract at least one table from Excel pricing forms"
    assert any("Addendum" in section.title for section in pdf_sections), "Addendum headings expected"
