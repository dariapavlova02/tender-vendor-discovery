"""Check the merging of Q&A pairs."""
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

for i, table in enumerate(tables, 1):
    table_type = classifier.classify(table)
    if table_type == "qa":
        pairs = qa_handler.extract_qa_pairs(table)
        if pairs:
            print(f"\nTable {i}: {len(pairs)} pairs")
            for j, pair in enumerate(pairs, 1):
                q_preview = pair.question[:40] if pair.question else "NO Q"
                a_preview = pair.answer[:40] if pair.answer else "NO A"
                print(f"  {pair.question_id}: Q={bool(pair.question)} A={bool(pair.answer)}")
