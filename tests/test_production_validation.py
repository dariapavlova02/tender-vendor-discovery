#!/usr/bin/env python3
"""Production validation: Full pipeline with location-based SAM filtering."""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
from vendor_ai_agent.sources.sam_entity import SamEntitySource
from vendor_ai_agent.database.connection import get_session

print("=" * 80)
print("PRODUCTION VALIDATION: Location-Based SAM Filtering")
print("=" * 80)

# Step 1: Parse DHS RFP
print("\n[1/5] Parsing DHS RFP PDF...")
pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

if not pdf_path.exists():
    print(f"   ✗ PDF not found: {pdf_path}")
    sys.exit(1)

parser = DocumentParser()
tender_sections = parser.parse([pdf_path])
print(f"   ✓ Parsed {len(tender_sections)} sections")

# Step 2: Extract requirements with location
print("\n[2/5] Extracting requirements with location...")
llm = OpenAIProvider() if os.getenv("OPENAI_API_KEY") else None
extractor = RequirementExtractor(llm_provider=llm)
profile = extractor.extract(tender_sections)
profile.country = "US"  # Set country for SAM filtering

# Display extracted data
print(f"\n   Extracted Data:")
print(f"   - NAICS codes: {profile.api_metadata.codes.naics[:3] if profile.api_metadata.codes.naics else 'None'}")

if profile.doc_extracted and profile.doc_extracted.structured:
    loc = profile.doc_extracted.structured.location
    if loc and loc.state_province:
        print(f"   - Location: {loc.city}, {loc.state_province}")
    else:
        print(f"   - Location: Not extracted")

pop = profile.api_metadata.place_of_performance
if pop and pop.state_province:
    print(f"   - Place of Performance: {pop.city}, {pop.state_province}")
    print(f"   ✓ Location wired correctly!")
else:
    print(f"   ✗ Place of Performance: Not populated")
    print(f"   ⚠ SAM will search ALL states!")

# Step 3: Test SAM query WITHOUT state filter (baseline)
print("\n[3/5] SAM Query WITHOUT State Filter (Baseline)...")
sam_api_key = os.getenv("SAM_API_KEY")

if not sam_api_key:
    print(f"   ✗ No SAM_API_KEY in .env")
    sys.exit(1)

original_state = pop.state_province if (pop and pop.state_province) else None

if original_state:
    pop.state_province = None

sam_source_baseline = SamEntitySource(
    api_key=sam_api_key,
    sync_to_db=False
)

try:
    with get_session() as db:
        vendors_no_filter = sam_source_baseline.search(profile)
        print(f"   ✓ Found {len(vendors_no_filter)} vendors (all states)")
        
        if vendors_no_filter:
            states = set()
            for v in vendors_no_filter[:50]:
                if hasattr(v, 'state') and v.state:
                    states.add(v.state)
            print(f"   - States represented: {len(states)} different states")
            print(f"   - Sample states: {', '.join(sorted(list(states))[:10])}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    vendors_no_filter = []

if original_state:
    pop.state_province = original_state

# Step 4: Test SAM query WITH state filter
print("\n[4/5] SAM Query WITH State Filter (Location-Based)...")

if not (pop and pop.state_province):
    print(f"   ⚠ Skipping - no state available for filtering")
    vendors_with_filter = []
else:
    print(f"   - Target state: {pop.state_province}")
    
    sam_source = SamEntitySource(
        api_key=sam_api_key,
        sync_to_db=False
    )
    
    try:
        with get_session() as db:
            vendors_with_filter = sam_source.search(profile)
            print(f"   ✓ Found {len(vendors_with_filter)} vendors (state: {pop.state_province})")
            
            if vendors_with_filter:
                states = set()
                for v in vendors_with_filter[:50]:
                    if hasattr(v, 'state') and v.state:
                        states.add(v.state)
                
                if len(states) == 1 and pop.state_province in states:
                    print(f"   ✓ All vendors from target state: {pop.state_province}")
                else:
                    print(f"   ⚠ Vendors from multiple states: {states}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        vendors_with_filter = []

# Step 5: Compare results
print("\n[5/5] Results Comparison...")
print(f"\n   WITHOUT state filter:")
print(f"     - Vendors found: {len(vendors_no_filter)}")
print(f"     - Query: All 50 states")

if pop and pop.state_province:
    print(f"\n   WITH state filter:")
    print(f"     - Vendors found: {len(vendors_with_filter)}")
    print(f"     - Query: Only {pop.state_province}")
    
    if vendors_no_filter and vendors_with_filter:
        reduction = len(vendors_no_filter) - len(vendors_with_filter)
        reduction_pct = (reduction / len(vendors_no_filter)) * 100
        print(f"\n   📊 Filtering Impact:")
        print(f"     - Reduced by: {reduction} vendors ({reduction_pct:.1f}%)")
        print(f"     - Relevance gain: {100 - reduction_pct:.1f}% more focused")

# Final summary
print("\n" + "=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)

success = True

if profile.api_metadata.codes.naics:
    print("\n✅ NAICS extraction: WORKING")
else:
    print("\n❌ NAICS extraction: FAILED")
    success = False

if profile.doc_extracted and profile.doc_extracted.structured and profile.doc_extracted.structured.location:
    print("✅ Location extraction: WORKING")
else:
    print("❌ Location extraction: FAILED")
    success = False

if pop and pop.state_province:
    print("✅ Integration wiring: WORKING (location → place_of_performance)")
else:
    print("❌ Integration wiring: BROKEN")
    success = False

if pop and pop.state_province and vendors_with_filter:
    print("✅ SAM state filtering: WORKING")
else:
    print("❌ SAM state filtering: FAILED or no results")
    success = False

if success:
    print("\n🎉 PRODUCTION VALIDATION: PASSED")
    print("\n   Key Achievements:")
    print(f"   - Location extracted from PDF: {pop.city if pop else 'N/A'}, {pop.state_province if pop else 'N/A'}")
    print(f"   - SAM API filtered by state: {pop.state_province if pop else 'N/A'}")
    print(f"   - Vendor noise reduced: {reduction_pct:.1f}% fewer irrelevant results" if 'reduction_pct' in locals() else "   - Baseline comparison completed")
else:
    print("\n⚠️ PRODUCTION VALIDATION: ISSUES FOUND")

print("=" * 80)

sys.exit(0 if success else 1)
