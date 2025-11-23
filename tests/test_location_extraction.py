#!/usr/bin/env python3
"""Test location extraction from DHS Uniforms III RFP."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.sections import SectionExtractor
from vendor_ai_agent.modules.document_processing.field_extractor import FieldExtractor

def test_location_extraction():
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    print("=" * 80)
    print("TESTING LOCATION EXTRACTION")
    print("=" * 80)
    
    print("\n1. Parsing PDF...")
    parser = DocumentParser()
    tender_sections = parser.parse([pdf_path])
    print(f"   ✓ Found {len(tender_sections)} sections")
    
    print("\n2. Extracting sections with SectionExtractor...")
    section_extractor = SectionExtractor()
    doc_sections = section_extractor.extract(tender_sections)
    
    print(f"\n3. Checking location_details:")
    print(f"   Length: {len(doc_sections.location_details)} chars")
    
    if doc_sections.location_details:
        print(f"\n   First 1500 characters:")
        print("   " + "-" * 76)
        preview = doc_sections.location_details[:1500].replace("\n", "\n   ")
        print(f"   {preview}")
        print("   " + "-" * 76)
        
        print(f"\n   Last 500 characters:")
        print("   " + "-" * 76)
        preview = doc_sections.location_details[-500:].replace("\n", "\n   ")
        print(f"   {preview}")
        print("   " + "-" * 76)
    else:
        print("   ⚠️  EMPTY - no location_details extracted!")
        
        print("\n   Checking scope_of_work for location mentions:")
        if doc_sections.scope_of_work:
            import re
            text = doc_sections.scope_of_work[:5000]
            
            location_patterns = [
                r'(?:place of performance|located at|located in|delivery to).{0,200}',
                r'[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}',
            ]
            
            matches = []
            for pattern in location_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matches.append(match.group(0))
            
            if matches:
                print(f"   ✓ Found {len(matches)} location mentions in scope_of_work:")
                for i, match in enumerate(matches[:3], 1):
                    print(f"      {i}. {match[:100]}")
    
    print("\n4. Testing FieldExtractor (current regex approach)...")
    field_extractor = FieldExtractor()
    structured = field_extractor.extract(doc_sections, tender_sections)
    
    print(f"\n   Extracted Location:")
    print(f"   - City: {structured.location.city}")
    print(f"   - State: {structured.location.state_province}")
    print(f"   - Country: {structured.location.country}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_location_extraction()
