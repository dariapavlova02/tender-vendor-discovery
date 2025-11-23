#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing import SectionExtractor

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

print(f"Parsed {len(sections)} TenderSections\n")
print("First 3 sections:")
for idx, section in enumerate(sections[:3]):
    print(f"\n{idx}. Title: {section.title}")
    print(f"   Type: {section.section_type}")
    print(f"   Content preview: {section.content[:200]}")
    if "315210" in section.content or "NAICS" in section.content.upper():
        print(f"   *** FOUND NAICS DATA ***")

print("\n" + "="*60)
print("Now checking DocSections aggregation...")
print("="*60)

extractor = SectionExtractor()
doc_sections = extractor.extract(sections)

print(f"\nScope of Work preview: {doc_sections.scope_of_work[:500]}")
print(f"\nTechnical Requirements preview: {doc_sections.technical_requirements[:500]}")
print(f"\nMandatory Requirements preview: {doc_sections.mandatory_requirements[:500]}")

# Search for NAICS in all fields
for field_name in dir(doc_sections):
    if field_name.startswith("_"):
        continue
    field_value = getattr(doc_sections, field_name, None)
    if isinstance(field_value, str) and ("315210" in field_value or "COMPETITIVE NAICS" in field_value.upper()):
        print(f"\n✓ FOUND '315210' or 'COMPETITIVE NAICS' in field: {field_name}")
        for line in field_value.split("\n")[:10]:
            if "315210" in line or "NAICS" in line.upper():
                print(f"  {line.strip()}")
