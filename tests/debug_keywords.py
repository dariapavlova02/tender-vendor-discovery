import sys
sys.path.insert(0, 'src')

from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier
from vendor_ai_agent.modules.document_processing.field_extractor import FieldExtractor
from vendor_ai_agent.modules.document_processing.keywords import TECHNICAL_KEYWORDS

appendix_pdf = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf")

parser = DocumentParser()
classifier = TableClassifier()
extractor = FieldExtractor()

sections_list = parser.parse([appendix_pdf])
tables = [s for s in sections_list if s.section_type == "table"]

print("=" * 80)
print("KEYWORD MATCHING DEBUG")
print("=" * 80)

print(f"\nAmmo supply keywords defined ({len(TECHNICAL_KEYWORDS.get('ammo_supply', []))}):")
for kw in TECHNICAL_KEYWORDS.get("ammo_supply", [])[:15]:
    print(f"  - '{kw}'")

print("\n" + "=" * 80)
print("TABLE CONTENT SAMPLE")
print("=" * 80)

table = tables[0]
content_lower = table.content.lower()
print(f"\nFirst 500 chars of table content (lowercase):")
print(content_lower[:500])

print("\n" + "=" * 80)
print("MATCHING RESULTS")
print("=" * 80)

found = []
for group_keywords in TECHNICAL_KEYWORDS.values():
    for keyword in group_keywords:
        if keyword in content_lower:
            found.append(keyword)
            print(f"✅ Found: '{keyword}'")

print(f"\n✅ Total keywords found: {len(found)}")
print(f"Found keywords: {found[:20]}")

print("\n" + "=" * 80)
print("TESTING EXTRACTOR METHOD")
print("=" * 80)

classified = extractor._classify_and_sort_tables(tables)
keywords_from_extractor = extractor._collect_keywords_from_tables(classified)
print(f"\nExtractor found {len(keywords_from_extractor)} keywords:")
print(keywords_from_extractor[:20])
