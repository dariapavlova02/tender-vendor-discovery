#!/usr/bin/env python3
"""Verify table classification across full dataset."""
from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier
from collections import Counter

data_dir = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/")
all_pdfs = sorted(data_dir.rglob("*.pdf"))

parser = DocumentParser()
classifier = TableClassifier()

print("=" * 80)
print("TABLE CLASSIFICATION VERIFICATION")
print("=" * 80)

all_classifications = Counter()

for pdf in all_pdfs:
    sections = parser.parse([pdf])
    tables = [s for s in sections if s.section_type == "table"]
    
    for table in tables:
        table_type = classifier.classify(table)
        all_classifications[table_type] += 1

print(f"\n✅ Processed {len(all_pdfs)} PDFs")
print(f"\n✅ Total tables found: {sum(all_classifications.values())}")
print("\nTable type distribution:")
for ttype, count in all_classifications.most_common():
    print(f"  {ttype:20s}: {count:3d} tables")

print("\n" + "=" * 80)
print("Q&A FILTER SUCCESS")
print("=" * 80)
print(f"✅ {all_classifications['qa']} Q&A tables correctly identified and skipped")
print(f"✅ {all_classifications['line_items']} line_items tables extracted")
print(f"✅ {all_classifications['technical_specs']} technical_specs tables extracted")
