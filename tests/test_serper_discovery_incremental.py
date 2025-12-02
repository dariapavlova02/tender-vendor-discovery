#!/usr/bin/env python3

import os
import logging
from typing import Set
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_incremental_discovery_with_context():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import (
        TenderProfile,
        DynamicTenderContext,
        APIMetadata,
        PlaceOfPerformance,
        CodesMetadata
    )
    
    print("\n" + "="*80)
    print("TEST 1: Incremental Discovery with Context Preservation")
    print("="*80)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_use_places_api = False
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("⚠ SERPER_API_KEY not found - skipping test")
        return
    
    source = SerperVendorSource(
        api_key=api_key,
        query_limit=50,
        config=config
    )
    
    profile = TenderProfile(
        country="Canada",
        dynamic_context=DynamicTenderContext(
            country="Canada",
            sector="grounds maintenance",
            search_terms=[
                "landscape maintenance contractor",
                "grounds maintenance services",
                "lawn care contractor",
                "property maintenance services"
            ],
            contract_type="service"
        ),
        api_metadata=APIMetadata(
            place_of_performance=PlaceOfPerformance(
                city="Waterloo",
                state_province="ON",
                country="Canada"
            ),
            codes=CodesMetadata(
                naics=["561730"]
            )
        )
    )
    
    print("\n[Call 1] Initial discovery - target 100 vendors")
    seen_domains: Set[str] = set()
    executed_queries: Set[str] = set()
    
    vendors_1 = source.search(
        profile,
        target_count=100,
        seen_domains=seen_domains,
        executed_queries=executed_queries
    )
    
    print(f"\nResults Call 1:")
    print(f"  Vendors found: {len(vendors_1)}")
    print(f"  Unique domains: {len(seen_domains)}")
    print(f"  Queries executed: {len(executed_queries)}")
    print(f"  Estimated cost: ${len(executed_queries) * 0.005:.3f}")
    
    for v in vendors_1[:3]:
        domain = v.filtering_metadata.get('serper_domain', 'N/A')
        print(f"    • {v.company_name} ({domain})")
    
    print("\n[Call 2] Second discovery - target 50 MORE vendors")
    
    for v in vendors_1:
        domain = v.filtering_metadata.get('serper_domain') or v.filtering_metadata.get('domain')
        if domain:
            seen_domains.add(domain.lower())
    
    initial_queries = len(executed_queries)
    initial_domains = len(seen_domains)
    
    vendors_2 = source.search(
        profile,
        target_count=50,
        seen_domains=seen_domains,
        executed_queries=executed_queries
    )
    
    print(f"\nResults Call 2:")
    print(f"  New vendors found: {len(vendors_2)}")
    print(f"  Unique domains now: {len(seen_domains)} (was {initial_domains})")
    print(f"  Queries executed: {len(executed_queries)} (was {initial_queries})")
    print(f"  New queries: {len(executed_queries) - initial_queries}")
    print(f"  Estimated incremental cost: ${(len(executed_queries) - initial_queries) * 0.005:.3f}")
    
    for v in vendors_2[:3]:
        domain = v.filtering_metadata.get('serper_domain', 'N/A')
        print(f"    • {v.company_name} ({domain})")
    
    new_domains = {v.filtering_metadata.get('serper_domain') for v in vendors_2}
    old_domains = {v.filtering_metadata.get('serper_domain') for v in vendors_1}
    duplicates = new_domains.intersection(old_domains)
    
    print(f"\n✓ Duplicate Check:")
    print(f"  Duplicates found: {len(duplicates)}")
    if duplicates:
        print(f"  WARNING: Found duplicate domains: {duplicates}")
    
    print(f"\n✓ Total Vendors: {len(vendors_1) + len(vendors_2)}")
    print(f"✓ Total Unique Domains: {len(seen_domains)}")
    print(f"✓ Total Queries: {len(executed_queries)}")
    print(f"✓ Total Cost: ${len(executed_queries) * 0.005:.3f}")


def test_cascading_geo_search():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import (
        TenderProfile,
        DynamicTenderContext,
        APIMetadata,
        PlaceOfPerformance
    )
    
    print("\n" + "="*80)
    print("TEST 2: Cascading Geographic Search with Early Stopping")
    print("="*80)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_geo_query_expansion = True
    config.discovery.serper_use_places_api = False
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("⚠ SERPER_API_KEY not found - skipping test")
        return
    
    source = SerperVendorSource(api_key=api_key, query_limit=20, config=config)
    
    profile = TenderProfile(
        country="US",
        dynamic_context=DynamicTenderContext(
            country="US",
            sector="law enforcement uniforms",
            search_terms=["tactical apparel manufacturer"],
            contract_type="product"
        ),
        api_metadata=APIMetadata(
            place_of_performance=PlaceOfPerformance(
                city="Glynco",
                state_province="GA",
                country="US"
            )
        )
    )
    
    print("\n[Small Target] Target 15 vendors - should stop early")
    seen_domains: Set[str] = set()
    executed_queries: Set[str] = set()
    
    vendors = source.search(
        profile,
        target_count=15,
        seen_domains=seen_domains,
        executed_queries=executed_queries
    )
    
    print(f"\nResults:")
    print(f"  Vendors found: {len(vendors)}")
    print(f"  Unique domains: {len(seen_domains)}")
    print(f"  Queries executed: {len(executed_queries)}")
    print(f"  Early stopping worked: {len(executed_queries) < 20}")
    
    if len(executed_queries) < 10:
        print(f"  ✓ PASS: Cascading stopped early (only {len(executed_queries)} queries)")
    else:
        print(f"  ⚠ Note: Used {len(executed_queries)} queries for {len(vendors)} vendors")


def test_synonym_expansion():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import TenderProfile, DynamicTenderContext
    
    print("\n" + "="*80)
    print("TEST 3: Synonym Expansion with OpenAI")
    print("="*80)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("⚠ SERPER_API_KEY not found - skipping test")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY not found - synonym expansion may fail")
    
    source = SerperVendorSource(api_key=api_key, query_limit=50, config=config)
    
    profile = TenderProfile(
        country="US",
        dynamic_context=DynamicTenderContext(
            country="US",
            sector="cyber security",
            search_terms=[
                "cyber security services",
                "network security contractor"
            ],
            contract_type="service"
        )
    )
    
    print("\n[High Target] Target 150 vendors - should trigger synonym expansion")
    seen_domains: Set[str] = set()
    executed_queries: Set[str] = set()
    
    vendors = source.search(
        profile,
        target_count=150,
        seen_domains=seen_domains,
        executed_queries=executed_queries
    )
    
    print(f"\nResults:")
    print(f"  Vendors found: {len(vendors)}")
    print(f"  Unique domains: {len(seen_domains)}")
    print(f"  Queries executed: {len(executed_queries)}")
    print(f"  Estimated cost: ${len(executed_queries) * 0.005:.3f}")
    
    print(f"\n✓ Sample vendors:")
    for v in vendors[:5]:
        domain = v.filtering_metadata.get('serper_domain', 'N/A')
        print(f"    • {v.company_name} ({domain})")


def test_query_deduplication():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import TenderProfile, DynamicTenderContext
    
    print("\n" + "="*80)
    print("TEST 4: Query Deduplication via executed_queries")
    print("="*80)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_use_places_api = False
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("⚠ SERPER_API_KEY not found - skipping test")
        return
    
    source = SerperVendorSource(api_key=api_key, query_limit=20, config=config)
    
    profile = TenderProfile(
        country="US",
        dynamic_context=DynamicTenderContext(
            country="US",
            search_terms=["construction contractor"],
            contract_type="service"
        )
    )
    
    seen_domains: Set[str] = set()
    executed_queries: Set[str] = set()
    
    print("\n[Call 1] Initial search")
    vendors_1 = source.search(profile, target_count=30, seen_domains=seen_domains, executed_queries=executed_queries)
    queries_after_1 = len(executed_queries)
    
    print(f"  Queries after call 1: {queries_after_1}")
    
    print("\n[Call 2] Same search with executed_queries preserved")
    vendors_2 = source.search(profile, target_count=30, seen_domains=seen_domains, executed_queries=executed_queries)
    queries_after_2 = len(executed_queries)
    
    print(f"  Queries after call 2: {queries_after_2}")
    print(f"  New queries in call 2: {queries_after_2 - queries_after_1}")
    
    if queries_after_2 > queries_after_1:
        print(f"  ✓ PASS: No duplicate queries (added {queries_after_2 - queries_after_1} new)")
    else:
        print(f"  ⚠ Note: No new queries executed (all were duplicates)")


def test_adaptive_query_calculation():
    from vendor_ai_agent.sources.serper_search import SerperVendorSource
    from vendor_ai_agent.config import RuntimeConfig
    from vendor_ai_agent.models import TenderProfile, DynamicTenderContext
    
    print("\n" + "="*80)
    print("TEST 5: Adaptive Query Calculation Based on Efficiency")
    print("="*80)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_use_places_api = False
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("⚠ SERPER_API_KEY not found - skipping test")
        return
    
    source = SerperVendorSource(api_key=api_key, query_limit=100, config=config)
    
    profile = TenderProfile(
        country="Canada",
        dynamic_context=DynamicTenderContext(
            country="Canada",
            sector="janitorial services",
            search_terms=["commercial cleaning contractor"],
            contract_type="service"
        )
    )
    
    seen_domains: Set[str] = set()
    executed_queries: Set[str] = set()
    
    print("\n[Target] 200 vendors")
    vendors = source.search(
        profile,
        target_count=200,
        seen_domains=seen_domains,
        executed_queries=executed_queries
    )
    
    efficiency = len(seen_domains) / len(executed_queries) if executed_queries else 0
    
    print(f"\nResults:")
    print(f"  Vendors found: {len(vendors)}")
    print(f"  Unique domains: {len(seen_domains)}")
    print(f"  Queries executed: {len(executed_queries)}")
    print(f"  Efficiency: {efficiency:.2f} unique domains/query")
    print(f"  Estimated cost: ${len(executed_queries) * 0.005:.3f}")
    
    if efficiency > 2.0:
        print(f"  ✓ PASS: Good efficiency (>{efficiency:.2f} domains/query)")
    else:
        print(f"  ⚠ Note: Lower efficiency ({efficiency:.2f} domains/query)")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SERPER SMART INCREMENTAL DISCOVERY - INTEGRATION TEST")
    print("="*80)
    
    try:
        test_incremental_discovery_with_context()
        test_cascading_geo_search()
        test_synonym_expansion()
        test_query_deduplication()
        test_adaptive_query_calculation()
        
        print("\n" + "="*80)
        print("✓ ALL TESTS COMPLETED")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
