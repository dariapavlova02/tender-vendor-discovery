#!/usr/bin/env python3
"""Integration test: Location extraction → place_of_performance → SAM vendor filtering."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from vendor_ai_agent.modules.llm_providers import OpenAIProvider

try:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY="):
                key = line.strip().split("=", 1)[1]
                os.environ["OPENAI_API_KEY"] = key
                break
except:
    pass

def test_integration():
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    print("=" * 80)
    print("LOCATION INTEGRATION TEST")
    print("=" * 80)
    
    print("\n1. Parsing PDF...")
    parser = DocumentParser()
    tender_sections = parser.parse([pdf_path])
    print(f"   ✓ Parsed {len(tender_sections)} sections")
    
    print("\n2. Extracting requirements with location...")
    llm = OpenAIProvider() if os.getenv("OPENAI_API_KEY") else None
    extractor = RequirementExtractor(llm_provider=llm)
    profile = extractor.extract(tender_sections)
    
    print(f"   ✓ Extracted profile")
    print(f"   - Country: {profile.country}")
    
    print("\n3. Checking location extraction...")
    if profile.doc_extracted and profile.doc_extracted.structured:
        loc = profile.doc_extracted.structured.location
        if loc:
            print(f"   ✓ Extracted location:")
            print(f"     - City: {loc.city}")
            print(f"     - State: {loc.state_province}")
            print(f"     - Country: {loc.country}")
        else:
            print(f"   ✗ No location extracted")
    else:
        print(f"   ✗ No structured data")
    
    print("\n4. Checking place_of_performance wiring...")
    pop = profile.api_metadata.place_of_performance
    if pop and pop.state_province:
        print(f"   ✓ Place of performance populated:")
        print(f"     - City: {pop.city}")
        print(f"     - State: {pop.state_province}")
        print(f"     - Country: {pop.country}")
    else:
        print(f"   ✗ Place of performance NOT populated")
    
    print("\n5. Checking NAICS codes...")
    naics = profile.api_metadata.codes.naics
    if naics:
        print(f"   ✓ NAICS codes: {naics[:3]}")
    else:
        print(f"   ✗ No NAICS codes")
    
    print("\n6. Testing SAM query preparation...")
    if pop and pop.state_province:
        state = pop.state_province
        print(f"   ✓ SAM query will use state filter: {state}")
        print(f"   ✓ This will limit vendors to: {state} only")
    else:
        print(f"   ⚠ SAM query will search ALL states (no filter)")
    
    print("\n" + "=" * 80)
    print("INTEGRATION TEST RESULTS")
    print("=" * 80)
    
    success = True
    
    if profile.doc_extracted and profile.doc_extracted.structured and profile.doc_extracted.structured.location:
        print("\n✅ Location extraction: WORKING")
    else:
        print("\n❌ Location extraction: FAILED")
        success = False
    
    if pop and pop.state_province:
        print("✅ Integration chain: WORKING (location → place_of_performance)")
    else:
        print("❌ Integration chain: BROKEN (location not wired)")
        success = False
    
    if pop and pop.state_province and naics:
        print("✅ SAM filtering ready: YES (state + NAICS codes available)")
    else:
        print("❌ SAM filtering ready: NO (missing state or NAICS)")
        success = False
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 ALL TESTS PASSED")
        print("\nExpected behavior:")
        print(f"  - SAM API will search NAICS {naics[0] if naics else 'N/A'}")
        print(f"  - Limited to state: {pop.state_province if pop else 'N/A'}")
        print(f"  - Result: Only vendors from {pop.state_province if pop else 'ALL STATES'}")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("\nPotential issues:")
        if not (profile.doc_extracted and profile.doc_extracted.structured and profile.doc_extracted.structured.location):
            print("  - Location not extracted from document")
        if not (pop and pop.state_province):
            print("  - Location not wired to place_of_performance")
        if not naics:
            print("  - No NAICS codes extracted")
    print("=" * 80)
    
    return success

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
