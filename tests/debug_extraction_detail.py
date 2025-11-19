import sys
sys.path.insert(0, 'src')

from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier
from vendor_ai_agent.modules.document_processing.field_extractor import FieldExtractor

test_dir = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/")
addendum_pdf = test_dir / "Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"
appendix_pdf = test_dir / "Appendix A Table A.2.pdf"

parser = DocumentParser()
classifier = TableClassifier()
extractor = FieldExtractor()

print("=" * 80)
print("TESTING APPENDIX A PDF (should have real line items)")
print("=" * 80)

sections_list = parser.parse([appendix_pdf])
tables = [s for s in sections_list if s.section_type == "table"]

print(f"\nFound {len(tables)} tables")

classified = extractor._classify_and_sort_tables(tables)
print(f"\nClassified tables:")
for i, (table, ttype) in enumerate(classified[:5], 1):
    print(f"  {i}. {ttype:15s} - {table.title[:60]}")

volumes = extractor._extract_volumes_from_tables(classified)
print(f"\n✅ Extracted {len(volumes)} volume items from Appendix A:")
for v in volumes[:10]:
    print(f"  - {v.item}: {v.quantity} {v.unit}")

print("\n" + "=" * 80)
print("TESTING ADDENDUM #7 PDF (has Q&A tables)")
print("=" * 80)

sections_list2 = parser.parse([addendum_pdf])
tables2 = [s for s in sections_list2 if s.section_type == "table"]

print(f"\nFound {len(tables2)} tables")

classified2 = extractor._classify_and_sort_tables(tables2)
print(f"\nClassified tables:")
for i, (table, ttype) in enumerate(classified2[:10], 1):
    print(f"  {i}. {ttype:15s} - {table.title[:60]}")

volumes2 = extractor._extract_volumes_from_tables(classified2)
print(f"\n✅ Extracted {len(volumes2)} volume items from Addendum #7:")
for v in volumes2[:10]:
    print(f"  - {v.item}: {v.quantity} {v.unit}")
