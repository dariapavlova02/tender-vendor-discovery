#!/usr/bin/env python
"""
Simple E2E test for DuckDuckGo website enricher - verifies HubSpoke case
"""
import sys
from unittest.mock import Mock
from sqlalchemy.orm import Session

sys.path.insert(0, 'src')

from vendor_ai_agent.enrichment_providers.duckduckgo_website_enricher import DuckDuckGoWebsiteEnricher
from vendor_ai_agent.models import VendorRecord


def test_hubspoke():
    """Test HubSpoke website discovery (known working case from PoC)"""
    mock_db = Mock(spec=Session)
    mock_db.scalars().first.return_value = None
    mock_db.execute().scalar_one_or_none.return_value = None
    
    enricher = DuckDuckGoWebsiteEnricher(db_session=mock_db)
    
    vendor = VendorRecord(
        company_name="HubSpoke Inc.",
        city="Ottawa",
        country="Canada"
    )
    
    print(f"\n🔍 Searching for: {vendor.company_name} ({vendor.city}, {vendor.country})")
    
    result = enricher.enrich(vendor)
    
    if result.website:
        print(f"✅ SUCCESS: Found website: {result.website}")
        print(f"   Enrichment flags: {result.enrichment_flags}")
        assert "hubspoke" in result.website.lower()
    else:
        print(f"❌ FAILED: No website found")
        raise AssertionError("Expected to find HubSpoke website")


def test_sierra_systems():
    """Test Sierra Systems (harder case - acquired company)"""
    mock_db = Mock(spec=Session)
    mock_db.scalars().first.return_value = None
    mock_db.execute().scalar_one_or_none.return_value = None
    
    enricher = DuckDuckGoWebsiteEnricher(db_session=mock_db)
    
    vendor = VendorRecord(
        company_name="SIERRA SYSTEMS GROUP INC",
        city="Vancouver",
        country="Canada"
    )
    
    print(f"\n🔍 Searching for: {vendor.company_name} ({vendor.city}, {vendor.country})")
    
    result = enricher.enrich(vendor)
    
    if result.website:
        print(f"✅ SUCCESS: Found website: {result.website}")
        print(f"   Enrichment flags: {result.enrichment_flags}")
    else:
        print(f"⚠️  No website found (expected - acquired company)")


if __name__ == "__main__":
    import traceback
    
    print("=" * 60)
    print("DuckDuckGo Website Enricher - Simple E2E Test")
    print("=" * 60)
    
    try:
        test_hubspoke()
        test_sierra_systems()
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)
