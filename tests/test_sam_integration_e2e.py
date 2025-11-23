#!/usr/bin/env python
"""Test full NAICS extraction → SAM API call → Vendor discovery flow"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.sources.sam_entity import SamEntitySource
from vendor_ai_agent.config import RuntimeConfig

print("="*70)
print("FULL SAM.GOV API INTEGRATION TEST")
print("="*70)

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

print(f"\n[1/4] Parsing PDF: {pdf_path.name}")
parser = DocumentParser()
sections = parser.parse([pdf_path])
print(f"      ✓ Parsed {len(sections)} sections")

print(f"\n[2/4] Extracting tender profile with NAICS...")
extractor = RequirementExtractor(llm_provider=None)
tender_profile = extractor.extract(sections)
naics_codes = tender_profile.api_metadata.codes.naics
print(f"      ✓ Extracted NAICS codes: {naics_codes}")

if not naics_codes:
    print("\n✗ FAILED: No NAICS codes extracted")
    sys.exit(1)

print(f"\n[3/4] Initializing SAM.gov API client...")
cfg = RuntimeConfig()
if not cfg.sam_api.api_key:
    print("\n✗ FAILED: SAM_API_KEY environment variable not set")
    print("  Set it with: export SAM_API_KEY='your-key-here'")
    sys.exit(1)

sam_source = SamEntitySource(
    api_key=cfg.sam_api.api_key,
    sync_to_db=False
)
print(f"      ✓ API Key: {cfg.sam_api.api_key[:20]}...")

print(f"\n[4/4] Calling SAM API for NAICS {naics_codes[0]}...")
print(f"      Note: This will make a real API call (counts toward daily limit)")
print(f"      Using Extract API (efficient for large result sets)")

vendors = sam_source.search(tender_profile)

print("\n" + "="*70)
print("RESULTS")
print("="*70)
print(f"✓ Vendors discovered: {len(vendors)}")

if vendors:
    print(f"\nFirst 5 vendors:")
    for i, vendor in enumerate(vendors[:5], 1):
        print(f"  {i}. {vendor.company_name}")
        print(f"     Location: {vendor.location}")
        print(f"     UEI: {vendor.uei}")
        if vendor.business_types:
            print(f"     Types: {', '.join(vendor.business_types[:3])}")
        print()
    
    print(f"✓ SUCCESS: SAM API integration working!")
    print(f"  Total vendors: {len(vendors)}")
    print(f"  NAICS code: {naics_codes[0]}")
    print(f"  Expected ~457 textile manufacturers for NAICS 315210")
else:
    print("⚠ WARNING: No vendors returned from SAM API")
    print("  This could mean:")
    print("  - API key issue")
    print("  - Network connectivity problem")
    print("  - Rate limit exceeded")
