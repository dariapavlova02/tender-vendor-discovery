#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

print("="*60)
print("Testing NAICS Extraction Pipeline")
print("="*60)
print(f"File: {pdf_path.name}")

print("\n[1/2] Extracting tender profile...")
extractor = RequirementExtractor(llm_provider=None)

from vendor_ai_agent.modules.document_parser import DocumentParser
parser = DocumentParser()
sections = parser.parse([pdf_path])
print(f"      Parsed {len(sections)} sections from PDF")

tender_profile = extractor.extract(sections)
structured = tender_profile.doc_extracted.structured

print(f"\n[2/2] Checking NAICS extraction...")
print(f"      NAICS codes in structured data: {structured.naics_codes}")
print(f"      NAICS codes in profile.api_metadata: {tender_profile.api_metadata.codes.naics}")

print("\n" + "="*60)
if tender_profile.api_metadata.codes.naics:
    print("✓ SUCCESS: NAICS Extraction Working!")
    print("="*60)
    for code in tender_profile.api_metadata.codes.naics:
        print(f"  ✓ Extracted NAICS: {code}")
    print(f"\n  SAM API will be called with {len(tender_profile.api_metadata.codes.naics)} NAICS code(s)")
else:
    print("✗ FAILED: No NAICS codes extracted")
    print("="*60)
    print("\nDEBUG: Searching for 'NAICS' in sections...")
    doc_sections = tender_profile.doc_extracted.sections
    for field_name in ["scope_of_work", "technical_requirements", "mandatory_requirements"]:
        field_value = getattr(doc_sections, field_name, "")
        if "NAICS" in field_value.upper():
            print(f"\n  Found in {field_name}:")
            for line in field_value.split("\n"):
                if "NAICS" in line.upper():
                    print(f"    {line.strip()[:200]}")
print()
