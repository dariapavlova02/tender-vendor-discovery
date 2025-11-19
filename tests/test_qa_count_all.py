"""Count all Q&A tables across OPP-1984 addenda."""
from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier

base_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda")
parser = DocumentParser()
classifier = TableClassifier()

addendum_dirs = [d for d in base_path.iterdir() if d.is_dir()]
pdf_files = []

for addendum_dir in sorted(addendum_dirs):
    pdfs = list(addendum_dir.glob("*.pdf"))
    pdf_files.extend(pdfs)

print(f"Processing {len(pdf_files)} PDF files from {len(addendum_dirs)} addendum directories\n")

total_qa_tables = 0
total_tables = 0

for pdf_file in sorted(pdf_files):
    sections = parser.parse([pdf_file])
    tables = [s for s in sections if s.section_type == "table"]
    
    qa_tables = []
    for table in tables:
        table_type = classifier.classify(table)
        if table_type == "qa":
            qa_tables.append(table)
    
    total_tables += len(tables)
    total_qa_tables += len(qa_tables)
    
    if qa_tables:
        print(f"✓ {pdf_file.parent.name}/{pdf_file.name}")
        print(f"  Tables: {len(tables)}, Q&A tables: {len(qa_tables)}")

print(f"\n{'='*80}")
print(f"Total tables found: {total_tables}")
print(f"Total Q&A tables found: {total_qa_tables}")
print(f"{'='*80}")
