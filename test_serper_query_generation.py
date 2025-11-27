import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO)

from src.vendor_ai_agent.models import TenderProfile, APIMetadata, PlaceOfPerformance, DynamicTenderContext
from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.sources.serper_search import SerperVendorSource

def test_service_contract_waterloo():
    print("\n" + "="*80)
    print("TEST 1: Waterloo Grounds Maintenance (Service Contract)")
    print("="*80)
    
    profile = TenderProfile()
    profile.dynamic_context = DynamicTenderContext(
        sector="grounds maintenance",
        contract_type="service",
        fulfillment_model="contractor",
        industry_description="Municipal grounds maintenance services",
        search_terms=[
            "commercial grounds maintenance contractors",
            "winter grounds maintenance services",
            "municipal grounds maintenance providers",
            "snow removal lawn care contractors",
            "property maintenance municipal contracts",
            "salt supplier",
            "equipment rental grounds maintenance",
            "landscaping equipment suppliers"
        ],
        country="Canada"
    )
    profile.api_metadata = APIMetadata(
        place_of_performance=PlaceOfPerformance(
            city="Waterloo",
            state_province="Ontario",
            country="Canada"
        )
    )
    
    config = RuntimeConfig()
    source = SerperVendorSource(api_key="dummy", config=config)
    
    queries = source._generate_queries(profile)
    
    print(f"\nGenerated {len(queries)} total queries")
    print("\nFirst 15 queries (what would execute with query_limit=15):")
    for idx, q in enumerate(queries[:15], 1):
        print(f"  {idx:2d}. {q}")
    
    print("\n" + "-"*80)
    print("FILTERED OUT (should NOT appear in output):")
    filtered = ["salt supplier", "equipment rental", "landscaping equipment suppliers"]
    for term in filtered:
        if any(term.lower() in q.lower() for q in queries):
            print(f"  ❌ FOUND: {term}")
        else:
            print(f"  ✅ BLOCKED: {term}")

def test_product_contract():
    print("\n" + "="*80)
    print("TEST 2: Hospital Beds (Product Contract)")
    print("="*80)
    
    profile = TenderProfile()
    profile.dynamic_context = DynamicTenderContext(
        sector="medical equipment",
        contract_type="product",
        fulfillment_model="manufacturer",
        industry_description="Hospital bed procurement",
        search_terms=[
            "adjustable hospital bed manufacturers",
            "medical furniture OEM producers",
            "healthcare equipment distributors",
            "hospital bed suppliers certified",
            "hospital bed maintenance services"
        ],
        country="Canada"
    )
    profile.api_metadata = APIMetadata(
        place_of_performance=PlaceOfPerformance(
            city="Toronto",
            state_province="Ontario",
            country="Canada"
        )
    )
    
    config = RuntimeConfig()
    source = SerperVendorSource(api_key="dummy", config=config)
    
    queries = source._generate_queries(profile)
    
    print(f"\nGenerated {len(queries)} total queries")
    print("\nFirst 12 queries:")
    for idx, q in enumerate(queries[:12], 1):
        print(f"  {idx:2d}. {q}")
    
    print("\n" + "-"*80)
    print("FILTERED OUT (should NOT appear in product contract):")
    filtered = ["maintenance services", "contractor"]
    for term in filtered:
        if any(term in q.lower() for q in queries):
            print(f"  ❌ FOUND: {term}")
        else:
            print(f"  ✅ BLOCKED: {term}")

def test_geographic_sequencing():
    print("\n" + "="*80)
    print("TEST 3: Geographic Sequencing Order")
    print("="*80)
    
    profile = TenderProfile()
    profile.dynamic_context = DynamicTenderContext(
        sector="IT services",
        contract_type="service",
        industry_description="IT managed services",
        search_terms=[
            "IT managed services provider",
            "cloud infrastructure contractor",
            "cybersecurity services"
        ],
        country="Canada"
    )
    profile.api_metadata = APIMetadata(
        place_of_performance=PlaceOfPerformance(
            city="Ottawa",
            state_province="Ontario",
            country="Canada"
        )
    )
    
    config = RuntimeConfig()
    source = SerperVendorSource(api_key="dummy", config=config)
    
    queries = source._generate_queries(profile)
    
    print(f"\nGenerated {len(queries)} total queries")
    print("\nExpected order: City → Region → Country → Global")
    print("\nFirst 15 queries:")
    for idx, q in enumerate(queries[:15], 1):
        if "Ottawa" in q:
            geo_level = "🏙️  CITY"
        elif "Ontario" in q:
            geo_level = "🌐 REGION"
        elif "Canada" in q:
            geo_level = "🌎 COUNTRY"
        else:
            geo_level = "🔵 GLOBAL"
        print(f"  {idx:2d}. {geo_level} | {q}")

def test_feature_flags():
    print("\n" + "="*80)
    print("TEST 4: Feature Flags (Disabled)")
    print("="*80)
    
    profile = TenderProfile()
    profile.dynamic_context = DynamicTenderContext(
        sector="grounds maintenance",
        contract_type="service",
        industry_description="Grounds maintenance",
        search_terms=[
            "grounds maintenance contractors",
            "salt supplier",
            "equipment rental"
        ],
        country="Canada"
    )
    profile.api_metadata = APIMetadata(
        place_of_performance=PlaceOfPerformance(
            city="Waterloo",
            state_province="Ontario",
            country="Canada"
        )
    )
    
    config = RuntimeConfig()
    config.discovery.serper_contract_aware_queries = False
    config.discovery.serper_geo_query_expansion = False
    
    source = SerperVendorSource(api_key="dummy", config=config)
    
    queries = source._generate_queries(profile)
    
    print(f"\nWith features DISABLED:")
    print(f"Generated {len(queries)} queries")
    print("\nFirst 10 queries:")
    for idx, q in enumerate(queries[:10], 1):
        print(f"  {idx:2d}. {q}")
    
    print("\n" + "-"*80)
    if any("salt supplier" in q.lower() for q in queries):
        print("✅ Toxic terms NOT filtered (as expected)")
    if not any("Ottawa" in q for q in queries):
        print("✅ Geographic expansion disabled (as expected)")

if __name__ == "__main__":
    test_service_contract_waterloo()
    test_product_contract()
    test_geographic_sequencing()
    test_feature_flags()
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
