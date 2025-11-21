"""Debug Q&A extraction to understand what's happening."""
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

print(f"Total tables: {len(tables)}\n")

qa_count = 0
for i, table in enumerate(tables, 1):
    table_type = classifier.classify(table)
    
    if table_type == "qa":
        qa_count += 1
        print(f"\n{'='*100}")
        print(f"Q&A TABLE #{qa_count} (Table #{i})")
        print(f"{'='*100}")
        print(f"Title: {table.title}")
        print(f"Content preview (first 300 chars):")
        print(table.content[:300])
        print("\n--- Extraction Result ---")
        
        qa_pairs = qa_handler.extract_qa_pairs(table)
        
        if qa_pairs:
            print(f"Extracted {len(qa_pairs)} Q&A pairs")
            for j, pair in enumerate(qa_pairs[:2], 1):
                print(f"\n  Pair {j}:")
                print(f"  ID: {pair.question_id}")
                print(f"  Q: {pair.question[:80]}...")
                print(f"  A: {pair.answer[:80]}...")
        else:
            print("⚠️  No Q&A pairs extracted from this table")

print(f"\n\nTotal Q&A tables found: {qa_count}")
