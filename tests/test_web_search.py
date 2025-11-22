"""Test web search vendor source."""
from __future__ import annotations

import logging

from vendor_ai_agent.models import (
    Address,
    DocExtracted,
    DocSections,
    DynamicTenderContext,
    StructuredDocData,
    TenderProfile,
)
from vendor_ai_agent.sources.web_search import WebSearchVendorSource

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")


def create_mock_profile() -> TenderProfile:
    location = Address(
        city="Toronto",
        state_province="Ontario",
        country="Canada",
    )
    
    structured = StructuredDocData(
        sector="Ammunition Supply",
        location=location,
    )
    
    sections = DocSections(
        scope_of_work="Ammunition supply requirements",
    )
    
    extraction = DocExtracted(
        sections=sections,
        structured=structured,
    )
    
    context = DynamicTenderContext(
        sector="Ammunition Supply",
        search_terms=[
            "ammunition suppliers ontario",
            "frangible bullet manufacturers canada",
        ],
        technical_keywords=[
            "9mm frangible ammunition",
            "12 gauge duty ammunition",
        ],
    )
    
    profile = TenderProfile(
        doc_extracted=extraction,
        dynamic_context=context,
    )
    
    return profile


def test_query_generation():
    print("\n=== Testing Query Generation ===")
    source = WebSearchVendorSource(max_queries=5, search_delay=0.5)
    profile = create_mock_profile()
    
    queries = source._build_queries(profile)
    
    print(f"\nGenerated {len(queries)} queries:")
    for i, query in enumerate(queries, 1):
        print(f"{i}. {query}")
    
    assert len(queries) > 0, "Should generate at least one query"
    assert any("ontario" in q.lower() for q in queries), "Should include location"


def test_web_search():
    print("\n=== Testing Web Search ===")
    source = WebSearchVendorSource(
        max_results_per_query=10,
        max_queries=2,
        search_delay=2.0,
    )
    
    profile = create_mock_profile()
    
    print("\nExecuting search (this may take ~5 seconds)...")
    vendors = source.search(profile)
    
    print(f"\n=== Results ===")
    print(f"Found {len(vendors)} unique vendors after filtering")
    
    for i, vendor in enumerate(vendors, 1):
        print(f"\n{i}. {vendor.company_name}")
        print(f"   Website: {vendor.website}")
        print(f"   Source: {vendor.source}")
    
    print(f"\nNote: DuckDuckGo may return limited/variable results.")
    print(f"Found {len(vendors)} vendors from {source.max_queries} queries.")
    
    websites = [v.website for v in vendors]
    assert len(websites) == len(set(websites)), "Should have no duplicate websites"
    
    for vendor in vendors:
        assert vendor.company_name, "Should have company name"
        assert vendor.website.startswith("http"), "Should have valid URL"
        assert vendor.source == "web_search", "Should have correct source"


def test_domain_filtering():
    print("\n=== Testing Domain Filtering ===")
    source = WebSearchVendorSource()
    
    mock_results = [
        {"title": "Wikipedia - Ammunition", "href": "https://wikipedia.org/ammunition"},
        {"title": "LinkedIn Job", "href": "https://linkedin.com/jobs/ammunition"},
        {"title": "Valid Vendor", "href": "https://ammocompany.com"},
        {"title": "Merx Tender", "href": "https://merx.com/tender/123"},
        {"title": "Another Valid", "href": "https://supplierco.ca"},
    ]
    
    vendors = source._filter_and_convert(mock_results)
    
    print(f"\nFiltered results: {len(vendors)} from {len(mock_results)} original")
    for vendor in vendors:
        print(f"  - {vendor.company_name}: {vendor.website}")
    
    assert len(vendors) == 2, "Should filter out unwanted domains"
    assert all("ammocompany.com" in v.website or "supplierco.ca" in v.website for v in vendors)


if __name__ == "__main__":
    test_query_generation()
    test_domain_filtering()
    test_web_search()
    print("\n=== All Tests Passed ===")
