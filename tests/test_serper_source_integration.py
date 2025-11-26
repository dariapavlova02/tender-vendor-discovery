#!/usr/bin/env python3
"""
Test: Serper Discovery Source Integration
Validates that SerperVendorSource can be imported and initialized
"""

import os
from dotenv import load_dotenv

load_dotenv()


def test_import():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    print("✓ SerperVendorSource imported successfully")


def test_initialization():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    
    api_key = os.getenv("SERPER_API_KEY")
    
    source = SerperVendorSource(
        api_key=api_key,
        query_limit=5,
        config=config
    )
    
    print(f"✓ SerperVendorSource initialized")
    print(f"  Name: {source.name}")
    print(f"  API Key configured: {bool(source.api_key)}")
    print(f"  Query limit: {source.query_limit}")
    print(f"  Client initialized: {bool(source.client)}")


def test_query_generation():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import (
        TenderProfile,
        DynamicTenderContext,
        APIMetadata,
        PlaceOfPerformance,
        CodesMetadata
    )
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    
    source = SerperVendorSource(api_key="dummy", query_limit=10, config=config)
    
    profile = TenderProfile(
        country="US",
        dynamic_context=DynamicTenderContext(
            country="US",
            sector="uniforms",
            search_terms=["law enforcement uniforms", "tactical apparel"]
        ),
        api_metadata=APIMetadata(
            place_of_performance=PlaceOfPerformance(
                city="Glynco",
                state_province="GA",
                country="US"
            ),
            codes=CodesMetadata(
                naics=["315210"]
            )
        )
    )
    
    queries = source._generate_queries(profile)
    
    print(f"✓ Query generation successful")
    print(f"  Generated {len(queries)} queries")
    for i, query in enumerate(queries[:5], 1):
        print(f"  {i}. {query}")


def test_filters_non_company_results():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import TenderProfile, DynamicTenderContext

    class FakeClient:
        def __init__(self, payload):
            self.payload = payload

        def discovery_search(self, query, num_results=10):  # noqa: ARG002
            return self.payload

    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    source = SerperVendorSource(api_key="dummy", query_limit=1, config=config)
    source.client = FakeClient(
        {
            "organic": [
                {
                    "link": "https://www.thefirearmblog.com/blog/federal-ammunition",
                    "title": "Federal Ammunition Wins Canadian Government Contracts",
                    "snippet": "News article covering ammunition contract awards",
                },
                {
                    "link": "https://ploughshares.ca/canadas-largest-defence-contracts-to-the-us-fy2024/",
                    "title": "Canada's largest defence contracts to the US: FY2024",
                    "snippet": "Analytical report",
                },
                {
                    "link": "https://supportontariomade.ca/explore-products/ammunition",
                    "title": "Ammunition | IMT Defence - Ontario Made",
                    "snippet": "Directory listing",
                },
                {
                    "link": "https://ammoterra.com/canadian-ammunition-manufacturer-makers",
                    "title": "Canadian Ammunition manufacturers & makers - AmmoTerra",
                    "snippet": "Marketplace catalog",
                },
                {
                    "link": "https://alphaammo.example.com",
                    "title": "Alpha Ammunition Inc. | Official Site",
                    "snippet": "Canadian manufacturer of 9mm and 5.56 ammunition",
                },
            ]
        }
    )

    source._generate_queries = lambda _: ["ammunition manufacturers canada"]

    profile = TenderProfile(
        dynamic_context=DynamicTenderContext(country="Canada"),
    )

    vendors = source.search(profile)

    assert len(vendors) == 1
    assert vendors[0].company_name.startswith("Alpha Ammunition")


def test_is_company_result_known_domains():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig

    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    source = SerperVendorSource(api_key="dummy", config=config)

    non_company_cases = [
        ("Canada contact", "Government contact center", "canada.ca", "https://www.canada.ca/en/contact.html"),
        ("CanadaBuys record", "Contract history listing", "canadabuys.canada.ca", "https://canadabuys.canada.ca/en/tender-opportunities/contract-history/ep750-192338/001/fk-026"),
        ("IMT Defence directory", "Ontario Made directory listing", "supportontariomade.ca", "https://supportontariomade.ca/explore-products/ammunition"),
        ("AmmoTerra listing", "Marketplace catalog", "ammoterra.com", "https://ammoterra.com/canadian-ammunition-manufacturer-makers"),
        ("Ammobin price list", "Price aggregator", "ammobin.ca", "https://ammobin.ca/en/centerfire/9MM"),
        ("GovConExec article", "News article", "govconexec.com", "https://www.govconexec.com/2025/06/canadian-business-secures-army-cartridge-packing-deal/"),
        ("Yellow Pages listing", "Directory entry", "yellowpages.ca", "https://www.yellowpages.ca/bus/Ontario/Hamilton/Rockland-Variety/7967245.html"),
        ("Tripadvisor page", "Review portal", "tripadvisor.com", "https://www.tripadvisor.com/Restaurant_Review-g154990-d686990-Reviews-Maple_Leaf_Pancake_House-Hamilton_Ontario.html"),
        ("Rural Routes directory", "Regional listing", "ruralroutes.com", "https://www.ruralroutes.com/7832.html"),
        ("211 Ontario service", "Government service listing", "211ontario.ca", "https://211ontario.ca/service/70722972/governors-manor-assisted-living-residential-services/"),
        ("Archive document", "Historical PDF", "archive.org", "https://archive.org/stream/lincoln-star-1976-04-10/lincoln-star-1976-04-10_djvu.txt"),
        ("PDFCoffee scrape", "Document mirror", "pdfcoffee.com", "https://pdfcoffee.com/sourcing-by-country-2018-pdf-free.html"),
        ("Norwalk Patriot mirror", "Squarespace article", "norwalkpatriot.squarespace.com", "https://norwalkpatriot.squarespace.com/s/2024-08-30.pdf"),
        ("Revize document", "Municipal PDF", "webgen1files1.revize.com", "https://webgen1files1.revize.com/amesareametroplanningorgia/Planning%20Docs/PTP/FINAL_AAMPO_FY2025-2029_PTP.pdf"),
        ("CanPages listing", "Directory entry", "canpages.ca", "https://www.canpages.ca/page/ON/hamilton/endless-beer-shop/102765837"),
        ("Government portal", "GC main site", "gc.ca", "https://travel.gc.ca"),
    ]

    company_cases = [
        ("Green Peak Wholesale", "Distributor site", "greenpeakwholesale.com", "https://greenpeakwholesale.com/"),
        ("G4C Gun Store", "Retail store", "g4cgunstore.com", "https://g4cgunstore.com/"),
    ]

    for title, snippet, domain, url in non_company_cases:
        assert not source._is_company_result(title, snippet, domain, url)

    for title, snippet, domain, url in company_cases:
        assert source._is_company_result(title, snippet, domain, url)


def test_compatibility():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import TenderProfile, DynamicTenderContext
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    
    api_key = os.getenv("SERPER_API_KEY")
    source = SerperVendorSource(api_key=api_key, config=config)
    
    us_profile = TenderProfile(
        country="US",
        dynamic_context=DynamicTenderContext(country="US")
    )
    
    canada_profile = TenderProfile(
        country="Canada",
        dynamic_context=DynamicTenderContext(country="Canada")
    )
    
    us_compatible = source.is_compatible(us_profile)
    canada_compatible = source.is_compatible(canada_profile)
    
    print(f"✓ Compatibility check successful")
    print(f"  US tender compatible: {us_compatible}")
    print(f"  Canada tender compatible: {canada_compatible}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SERPER DISCOVERY SOURCE - INTEGRATION TEST")
    print("="*60 + "\n")
    
    try:
        print("[1/4] Testing import...")
        test_import()
        print()
        
        print("[2/4] Testing initialization...")
        test_initialization()
        print()
        
        print("[3/4] Testing query generation...")
        test_query_generation()
        print()
        
        print("[4/4] Testing compatibility...")
        test_compatibility()
        print()
        
        print("="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
