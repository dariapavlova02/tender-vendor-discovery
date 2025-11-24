import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
from vendor_ai_agent.sources.canada_contracts import CanadaContractsVendorSource
from vendor_ai_agent.database.connection import init_db

load_dotenv()

AMMUNITION_TENDER_PATH = Path("/Users/dariapavlova/Documents/vendor_ai_agent/data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #1- tender_20070 - Supply and Delivery of Ammunition.pdf")

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()

def test_ammunition_tender_canada_vendor_discovery():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set, skipping test")
        return
    
    llm_provider = OpenAIProvider(api_key=api_key, default_model="gpt-4o-mini")
    
    print(f"📄 Parsing PDF: {AMMUNITION_TENDER_PATH.name}")
    parser = DocumentParser()
    sections = parser.parse([AMMUNITION_TENDER_PATH])
    print(f"✓ Extracted {len(sections)} sections")
    
    print("\n🤖 Running LLM-powered extraction...")
    extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = extractor.extract(sections)
    
    print("\n=== TENDER PROFILE ===")
    print(f"Sector: {profile.dynamic_context.sector}")
    print(f"Country: {profile.dynamic_context.country}")
    print(f"Province: {profile.dynamic_context.province}")
    print(f"Technical Keywords: {profile.dynamic_context.technical_keywords}")
    print(f"GSIN Codes: {profile.dynamic_context.gsin_codes}")
    print(f"UNSPSC Codes: {profile.dynamic_context.unspsc_codes}")
    
    assert profile.dynamic_context.country == "Canada", \
        f"Expected country='Canada', got '{profile.dynamic_context.country}'"
    
    canada_source = CanadaContractsVendorSource()
    
    print("\n=== COMPATIBILITY CHECK ===")
    is_compatible = canada_source.is_compatible(profile)
    print(f"Canada source compatible: {is_compatible}")
    
    assert is_compatible, "Canada source should be compatible with Canada tender"
    
    print("\n=== VENDOR DISCOVERY ===")
    vendors = canada_source.search(profile)
    
    print(f"Found {len(vendors)} vendors")
    
    assert len(vendors) > 0, "Should find at least some Canadian vendors"
    assert len(vendors) >= 10, f"Should find at least 10 vendors for ammunition tender, found {len(vendors)}"
    
    print("\n=== TOP 10 VENDORS ===")
    for i, vendor_record in enumerate(vendors[:10], 1):
        print(f"{i}. {vendor_record.company_name}")
        print(f"   Location: {vendor_record.location or 'N/A'}")
        print(f"   City: {vendor_record.city or 'N/A'}")
        print(f"   State: {vendor_record.state or 'N/A'}")
        print(f"   Source: {vendor_record.source}")
        print()
    
    source_breakdown = {}
    for v in vendors:
        source_breakdown[v.source] = source_breakdown.get(v.source, 0) + 1
    
    print(f"\n=== SOURCE BREAKDOWN ===")
    for source, count in sorted(source_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")
    
    odbus_vendors = [v for v in vendors if v.source == 'canada_odbus']
    if odbus_vendors:
        print(f"\n=== SAMPLE CANADA_ODBUS VENDORS ===")
        for i, v in enumerate(odbus_vendors[:5], 1):
            print(f"{i}. {v.company_name} ({v.state})")
    
    print(f"\n=== SUMMARY ===")
    print(f"✓ Country correctly extracted: {profile.dynamic_context.country}")
    print(f"✓ Source compatibility: {is_compatible}")
    print(f"✓ Vendors discovered: {len(vendors)}")
    print(f"✓ canada_odbus vendors: {len(odbus_vendors)}")
    print(f"✓ Test PASSED")

if __name__ == "__main__":
    test_ammunition_tender_canada_vendor_discovery()
