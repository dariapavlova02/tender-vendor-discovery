"""Unit tests for duplicate detection and deduplication."""
import pytest

from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.modules.filtering.duplicate_detector import DuplicateDetector


def test_exact_name_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(company_name="Acme Corporation", source="sam_entity"),
        VendorRecord(company_name="Acme Corporation", source="canada_contracts"),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1
    assert deduplicated[0].company_name == "Acme Corporation"


def test_normalized_name_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(company_name="Acme Corporation", source="sam_entity"),
        VendorRecord(company_name="Acme Corp.", source="canada_contracts"),
        VendorRecord(company_name="ACME INC", source="static_directory"),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 2


def test_website_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            website="https://www.example.com",
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company B",
            website="http://example.com",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1


def test_uei_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            uei="ABC123DEF456",
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company B",
            uei="ABC123DEF456",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1


def test_duns_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            duns="123456789",
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company B",
            duns="123456789",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1


def test_cage_code_duplicate():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            cage_code="1ABC2",
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company B",
            cage_code="1ABC2",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1


def test_no_duplicates():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity"),
        VendorRecord(company_name="Company B", source="sam_entity"),
        VendorRecord(company_name="Company C", source="canada_contracts"),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 3
    assert count == 0


def test_merge_duplicates_enabled():
    detector = DuplicateDetector(merge_duplicates=True)
    
    vendors = [
        VendorRecord(
            company_name="Acme Corporation",
            website="https://acme.com",
            email=None,
            phone=None,
            source="sam_entity",
            is_past_winner=False,
            enrichment_flags=["flag_a"],
            business_types=["Small Business"],
        ),
        VendorRecord(
            company_name="Acme Corp.",
            website=None,
            email="contact@acme.com",
            phone="555-1234",
            source="canada_contracts",
            is_past_winner=True,
            enrichment_flags=["flag_b"],
            business_types=["8(a)"],
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1
    
    merged = deduplicated[0]
    assert merged.website == "https://acme.com"
    assert merged.email == "contact@acme.com"
    assert merged.phone == "555-1234"
    assert merged.is_past_winner is True
    assert "flag_a" in merged.enrichment_flags
    assert "flag_b" in merged.enrichment_flags
    assert "Small Business" in merged.business_types
    assert "8(a)" in merged.business_types
    assert "canada_contracts" in merged.filtering_metadata.get("merged_sources", [])


def test_merge_location_data():
    detector = DuplicateDetector(merge_duplicates=True)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            city=None,
            state=None,
            country=None,
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company A",
            city="Washington",
            state="DC",
            country="United States",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    merged = deduplicated[0]
    assert merged.city == "Washington"
    assert merged.state == "DC"
    assert merged.country == "United States"


def test_merge_contract_values():
    detector = DuplicateDetector(merge_duplicates=True)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            total_contract_value=100000.0,
            contract_count=5,
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company A",
            total_contract_value=200000.0,
            contract_count=10,
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    merged = deduplicated[0]
    assert merged.total_contract_value == 200000.0
    assert merged.contract_count == 10


def test_multiple_duplicates_same_company():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity"),
        VendorRecord(company_name="Company A", source="canada_contracts"),
        VendorRecord(company_name="Company A Inc.", source="static_directory"),
        VendorRecord(company_name="Company B", source="sam_entity"),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 2
    assert count == 2


def test_empty_list():
    detector = DuplicateDetector(merge_duplicates=False)
    
    deduplicated, count = detector.deduplicate([])
    
    assert len(deduplicated) == 0
    assert count == 0


def test_priority_order_identifier_over_website():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(
            company_name="Company A",
            uei="UEI123",
            website="https://example-a.com",
            source="sam_entity"
        ),
        VendorRecord(
            company_name="Company B",
            uei="UEI123",
            website="https://example-b.com",
            source="canada_contracts"
        ),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 1


def test_name_normalization_removes_suffixes():
    detector = DuplicateDetector(merge_duplicates=False)
    
    vendors = [
        VendorRecord(company_name="Tech Solutions LLC", source="sam_entity"),
        VendorRecord(company_name="Tech Solutions Ltd.", source="canada_contracts"),
        VendorRecord(company_name="Tech Solutions Corporation", source="static_directory"),
        VendorRecord(company_name="Tech Solutions Co", source="sam_entity"),
    ]
    
    deduplicated, count = detector.deduplicate(vendors)
    
    assert len(deduplicated) == 1
    assert count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
