"""Unit tests for geographic matching and scoring."""
import pytest

from vendor_ai_agent.models import Address, TenderProfile, VendorRecord, DocExtracted, StructuredDocData
from vendor_ai_agent.modules.filtering.geographic_matcher import GeographicMatcher


def test_exact_city_match():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Washington",
        state_province="DC",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="DC Local Company",
        city="Washington",
        state="DC",
        country="United States",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 20.0
    assert matcher.is_local_vendor(tender_location, vendor) is True


def test_same_state_different_city():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Austin",
        state_province="TX",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="Texas Company",
        city="Dallas",
        state="TX",
        country="United States",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 20.0
    assert matcher.is_local_vendor(tender_location, vendor) is True


def test_neighboring_states():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Boston",
        state_province="MA",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="Connecticut Company",
        city="Hartford",
        state="CT",
        country="United States",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 10.0
    assert matcher.is_local_vendor(tender_location, vendor) is False
    assert matcher.is_regional_vendor(tender_location, vendor) is True


def test_non_neighboring_states():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Seattle",
        state_province="WA",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="Florida Company",
        city="Miami",
        state="FL",
        country="United States",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 0.0
    assert matcher.is_local_vendor(tender_location, vendor) is False
    assert matcher.is_regional_vendor(tender_location, vendor) is False


def test_canada_provinces():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Toronto",
        state_province="ON",
        country="Canada"
    )
    
    local_vendor = VendorRecord(
        company_name="Ontario Company",
        city="Ottawa",
        state="ON",
        country="Canada",
        source="canada_contracts"
    )
    
    regional_vendor = VendorRecord(
        company_name="Quebec Company",
        city="Montreal",
        state="QC",
        country="Canada",
        source="canada_contracts"
    )
    
    national_vendor = VendorRecord(
        company_name="BC Company",
        city="Vancouver",
        state="BC",
        country="Canada",
        source="canada_contracts"
    )
    
    assert matcher.calculate_geo_score(tender_location, local_vendor) == 20.0
    assert matcher.calculate_geo_score(tender_location, regional_vendor) == 10.0
    assert matcher.calculate_geo_score(tender_location, national_vendor) == 0.0


def test_no_vendor_location():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="New York",
        state_province="NY",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="No Location Company",
        city=None,
        state=None,
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 0.0


def test_no_tender_location():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address()
    
    vendor = VendorRecord(
        company_name="Company",
        city="New York",
        state="NY",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 0.0


def test_nationwide_tender():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Nationwide",
        state_province="Multiple",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="Company",
        city="New York",
        state="NY",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 0.0


def test_state_normalization():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0)
    
    tender_location = Address(
        city="Los Angeles",
        state_province="California",
        country="United States"
    )
    
    vendor = VendorRecord(
        company_name="CA Company",
        city="Los Angeles",
        state="ca",
        source="sam_entity"
    )
    
    score = matcher.calculate_geo_score(tender_location, vendor)
    assert score == 20.0


def test_filter_by_geography_local_first():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0, enable_local_first=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="Boston", state_province="MA", country="United States")
            )
        )
    )
    
    vendors = [
        VendorRecord(company_name="MA Local", city="Boston", state="MA", source="sam_entity"),
        VendorRecord(company_name="CT Regional", city="Hartford", state="CT", source="sam_entity"),
        VendorRecord(company_name="CA National", city="Los Angeles", state="CA", source="sam_entity"),
    ]
    
    filtered, local_count, national_count = matcher.filter_by_geography(profile, vendors)
    
    assert len(filtered) == 2
    assert local_count == 1
    assert national_count == 1
    assert filtered[0].company_name == "MA Local"
    assert filtered[1].company_name == "CT Regional"


def test_filter_by_geography_expansion_mode():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0, enable_local_first=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="Boston", state_province="MA", country="United States")
            )
        )
    )
    
    vendors = [
        VendorRecord(company_name="MA Local", city="Boston", state="MA", source="sam_entity"),
        VendorRecord(company_name="CT Regional", city="Hartford", state="CT", source="sam_entity"),
        VendorRecord(company_name="CA National", city="Los Angeles", state="CA", source="sam_entity"),
    ]
    
    filtered, local_count, national_count = matcher.filter_by_geography(profile, vendors, expansion_mode=True)
    
    assert len(filtered) == 3
    assert local_count == 1
    assert national_count == 1


def test_filter_no_local_first():
    matcher = GeographicMatcher(local_boost=20.0, regional_boost=10.0, enable_local_first=False)
    
    profile = TenderProfile(
        tender_id="TEST",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="Boston", state_province="MA", country="United States")
            )
        )
    )
    
    vendors = [
        VendorRecord(company_name="MA Local", city="Boston", state="MA", source="sam_entity"),
        VendorRecord(company_name="CA National", city="Los Angeles", state="CA", source="sam_entity"),
    ]
    
    filtered, local_count, national_count = matcher.filter_by_geography(profile, vendors)
    
    assert len(filtered) == 2
    assert local_count == 0
    assert national_count == 2
    assert filtered[0].geo_score == 20.0
    assert filtered[1].geo_score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
