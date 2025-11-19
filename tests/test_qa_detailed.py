"""Detailed test to verify Q&A extraction quality."""
from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor

file_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf")

if not file_path.exists():
    print("File not found")
    exit(1)

print(f"Processing: {file_path.name}\n")

parser = DocumentParser()
extractor = RequirementExtractor()

sections = parser.parse([file_path])
profile = extractor.extract(sections)

clarifications = profile.doc_extracted.structured.clarifications

print(f"Total Q&A pairs extracted: {len(clarifications)}\n")

for i, c in enumerate(clarifications, 1):
    print(f"\n{'='*100}")
    print(f"Q&A PAIR #{i}")
    print(f"{'='*100}")
    if c.question_number:
        print(f"Question ID: {c.question_number}")
    if c.addendum_number:
        print(f"Addendum: {c.addendum_number}")
    print(f"\nQuestion:\n{c.question}\n")
    print(f"Answer:\n{c.answer}\n")
