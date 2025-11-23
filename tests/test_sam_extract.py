import os
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("Testing SAM Extract API Implementation")
print("=" * 60)

source = SamEntitySource()

print(f"\nAPI Key configured: {bool(source.api_key)}")
print(f"API Key (first 10 chars): {source.api_key[:10] if source.api_key else 'None'}...")

print("\n\nTest 1: NAICS 315210 (Cut and Sew Apparel Contractors)")
print("-" * 60)

try:
    results = source.search_by_naics(naics_code="315210", limit=100)
    print(f"\n✓ Success! Retrieved {len(results)} entities")
    
    if results:
        print(f"\nFirst 3 entities:")
        for i, entity in enumerate(results[:3], 1):
            entity_reg = entity.get("entityRegistration", {})
            core_data = entity.get("coreData", {})
            print(f"\n{i}. {entity_reg.get('legalBusinessName', 'N/A')}")
            print(f"   UEI: {entity_reg.get('ueiSAM', 'N/A')}")
            print(f"   CAGE: {entity_reg.get('cageCode', 'N/A')}")
            addr = core_data.get("physicalAddress", {})
            print(f"   Location: {addr.get('city', 'N/A')}, {addr.get('stateOrProvinceCode', 'N/A')}")
    
except Exception as e:
    print(f"\n✗ Error: {e}")

print("\n" + "=" * 60)
