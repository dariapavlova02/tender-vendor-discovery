"""See what pairs are being extracted from each table."""
from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier
from vendor_ai_agent.modules.document_processing.qa_handler import QAHandler

file_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf")

parser = DocumentParser()
classifier = TableClassifier()
qa_handler = QAHandler()

sections = parser.parse([file_path])
tables = [s for s in sections if s.section_type == "table"]

all_pairs = []
for table in tables:
    table_type = classifier.classify(table)
    if table_type == "qa":
        pairs = qa_handler.extract_qa_pairs(table)
        all_pairs.extend(pairs)

print(f"Total Q&A pairs extracted: {len(all_pairs)}\n")

for i, pair in enumerate(all_pairs, 1):
    print(f"\nPair {i}:")
    print(f"  ID: {pair.question_id}")
    print(f"  Has Q: {bool(pair.question)}, Has A: {bool(pair.answer)}")
    if pair.question:
        print(f"  Q: {pair.question[:80]}")
    if pair.answer:
        print(f"  A: {pair.answer[:80]}")
