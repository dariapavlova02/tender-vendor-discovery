"""Performance benchmarking for multi-stage vendor filtering."""
import time
from typing import List

import pytest

from vendor_ai_agent.config import FilteringConfig
from vendor_ai_agent.models import (
    Address,
    APIMetadata,
    DocExtracted,
    EstimatedValue,
    SetAsideMetadata,
    StructuredDocData,
    TenderProfile,
    VendorRecord,
)
from vendor_ai_agent.modules.vendor_filter import VendorFilter


def generate_vendors(count: int) -> List[VendorRecord]:
    """Generate synthetic vendor dataset for benchmarking."""
    vendors = []
    states = ["NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
    cities = {
        "NY": ["New York", "Buffalo", "Rochester"],
        "CA": ["Los Angeles", "San Francisco", "San Diego"],
        "TX": ["Houston", "Dallas", "Austin"],
        "FL": ["Miami", "Tampa", "Orlando"],
        "IL": ["Chicago", "Aurora", "Naperville"],
    }
    
    business_types_options = [
        ["8(a)", "Small Business"],
        ["Women Owned Small Business"],
        ["HUBZone"],
        ["Service-Disabled Veteran-Owned"],
        [],
    ]
    
    for i in range(count):
        state = states[i % len(states)]
        city_list = cities.get(state, [state])
        city = city_list[i % len(city_list)]
        
        vendor = VendorRecord(
            company_name=f"Vendor {i} Inc" if i % 10 != 0 else f"Vendor {i // 10} Inc",
            source="sam_entity" if i % 3 == 0 else "canada_contracts",
            city=city,
            state=state,
            country="US" if i % 5 != 0 else "Canada",
            business_types=business_types_options[i % len(business_types_options)],
            total_contract_value=float(10_000 * (i % 100 + 1)),
            contract_count=i % 50 + 1,
            is_past_winner=(i % 7 == 0),
            enrichment_flags=["high_value_supplier"] if i % 5 == 0 else [],
            uei=f"UEI{i:06d}" if i % 20 == 0 else None,
            duns=f"DUNS{i:09d}" if i % 15 == 0 else None,
        )
        vendors.append(vendor)
    
    return vendors


def test_filtering_performance_1k():
    """Test filtering performance with 1,000 vendors."""
    profile = TenderProfile(
        tender_id="PERF-TEST-1K",
        country="US",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=500_000, currency="USD"),
            set_aside=SetAsideMetadata(code="8A"),
        ),
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="New York", state_province="NY", country="United States"),
            )
        ),
    )
    
    vendors = generate_vendors(1_000)
    
    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_local_first=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        max_candidates=50,
    )
    
    filter_engine = VendorFilter(config)
    
    start = time.time()
    result = filter_engine.filter(profile, vendors)
    duration = time.time() - start
    
    metrics = filter_engine.get_metrics()
    
    print(f"\n1K Vendors Performance:")
    print(f"  Duration: {duration:.3f}s")
    print(f"  Input: {metrics.total_input}")
    print(f"  Output: {metrics.final_count}")
    print(f"  Duplicates: {metrics.duplicates_removed}")
    print(f"  Throughput: {metrics.total_input / duration:.0f} vendors/sec")
    
    assert duration < 5.0, f"Performance regression: took {duration:.3f}s (expected < 5s)"
    assert len(result) > 0, "Filter should return at least some vendors"


def test_filtering_performance_10k():
    """Test filtering performance with 10,000 vendors."""
    profile = TenderProfile(
        tender_id="PERF-TEST-10K",
        country="US",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=500_000, currency="USD"),
            set_aside=SetAsideMetadata(code="8A"),
        ),
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="New York", state_province="NY", country="United States"),
            )
        ),
    )
    
    vendors = generate_vendors(10_000)
    
    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_local_first=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        max_candidates=50,
    )
    
    filter_engine = VendorFilter(config)
    
    start = time.time()
    result = filter_engine.filter(profile, vendors)
    duration = time.time() - start
    
    metrics = filter_engine.get_metrics()
    
    print(f"\n10K Vendors Performance:")
    print(f"  Duration: {duration:.3f}s")
    print(f"  Input: {metrics.total_input}")
    print(f"  Output: {metrics.final_count}")
    print(f"  Duplicates: {metrics.duplicates_removed}")
    print(f"  Throughput: {metrics.total_input / duration:.0f} vendors/sec")
    
    assert duration < 30.0, f"Performance regression: took {duration:.3f}s (expected < 30s)"
    assert len(result) > 0, "Filter should return at least some vendors"


@pytest.mark.slow
def test_filtering_performance_50k():
    """Test filtering performance with 50,000 vendors (marked as slow)."""
    profile = TenderProfile(
        tender_id="PERF-TEST-50K",
        country="US",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=500_000, currency="USD"),
            set_aside=SetAsideMetadata(code="8A"),
        ),
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="New York", state_province="NY", country="United States"),
            )
        ),
    )
    
    vendors = generate_vendors(50_000)
    
    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_local_first=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        max_candidates=50,
    )
    
    filter_engine = VendorFilter(config)
    
    start = time.time()
    result = filter_engine.filter(profile, vendors)
    duration = time.time() - start
    
    metrics = filter_engine.get_metrics()
    
    print(f"\n50K Vendors Performance:")
    print(f"  Duration: {duration:.3f}s")
    print(f"  Input: {metrics.total_input}")
    print(f"  Output: {metrics.final_count}")
    print(f"  Duplicates: {metrics.duplicates_removed}")
    print(f"  Throughput: {metrics.total_input / duration:.0f} vendors/sec")
    
    assert duration < 120.0, f"Performance regression: took {duration:.3f}s (expected < 120s)"
    assert len(result) > 0, "Filter should return at least some vendors"
