"""Test set-aside filtering with 8(a), WOSB, HUBZone requirements."""
import pytest
from pathlib import Path

from vendor_ai_agent.models import (
    TenderProfile,
    VendorRecord,
    APIMetadata,
    SetAsideMetadata,
    EstimatedValue,
)
from vendor_ai_agent.modules.filtering.eligibility_checker import EligibilityChecker


def test_8a_set_aside_filtering():
    profile = TenderProfile(
        tender_id="TEST_8A",
        api_metadata=APIMetadata(
            title="8(a) Set-Aside Contract",
            set_aside=SetAsideMetadata(code="8A", description="8(a) Small Business"),
        ),
    )
    
    vendors = [
        VendorRecord(
            company_name="8(a) Certified Company",
            source="sam_entity",
            business_types=["8(a)", "Small Business"],
        ),
        VendorRecord(
            company_name="Regular Small Business",
            source="sam_entity",
            business_types=["Small Business"],
        ),
        VendorRecord(
            company_name="No Business Types",
            source="sam_entity",
            business_types=[],
        ),
    ]
    
    checker = EligibilityChecker(enable_set_aside=True)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert eligible[0].company_name == "8(a) Certified Company"
    assert filter_reasons["set_aside_mismatch_8A"] == 1
    assert filter_reasons["set_aside_missing_8A"] == 1


def test_wosb_set_aside_filtering():
    profile = TenderProfile(
        tender_id="TEST_WOSB",
        api_metadata=APIMetadata(
            title="WOSB Set-Aside Contract",
            set_aside=SetAsideMetadata(code="WOSB", description="Women Owned Small Business"),
        ),
    )
    
    vendors = [
        VendorRecord(
            company_name="WOSB Certified Company",
            source="sam_entity",
            business_types=["Women Owned Small Business", "Small Business"],
        ),
        VendorRecord(
            company_name="WOSB Shorthand",
            source="sam_entity",
            business_types=["WOSB"],
        ),
        VendorRecord(
            company_name="Non-WOSB Company",
            source="sam_entity",
            business_types=["Small Business"],
        ),
    ]
    
    checker = EligibilityChecker(enable_set_aside=True)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 2
    assert eligible[0].company_name == "WOSB Certified Company"
    assert eligible[1].company_name == "WOSB Shorthand"
    assert filter_reasons["set_aside_mismatch_WOSB"] == 1


def test_hubzone_set_aside_filtering():
    profile = TenderProfile(
        tender_id="TEST_HUBZONE",
        api_metadata=APIMetadata(
            title="HUBZone Set-Aside Contract",
            set_aside=SetAsideMetadata(code="HZC", description="HUBZone"),
        ),
    )
    
    vendors = [
        VendorRecord(
            company_name="HUBZone Certified",
            source="sam_entity",
            business_types=["HUBZone", "Small Business"],
        ),
        VendorRecord(
            company_name="Non-HUBZone",
            source="sam_entity",
            business_types=["Small Business"],
        ),
    ]
    
    checker = EligibilityChecker(enable_set_aside=True)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert eligible[0].company_name == "HUBZone Certified"
    assert filter_reasons["set_aside_mismatch_HZC"] == 1


def test_no_set_aside():
    profile = TenderProfile(
        tender_id="TEST_UNRESTRICTED",
        api_metadata=APIMetadata(
            title="Unrestricted Contract",
            set_aside=SetAsideMetadata(code="NONE"),
        ),
    )
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity", business_types=["Small Business"]),
        VendorRecord(company_name="Company B", source="sam_entity", business_types=["Large Business"]),
        VendorRecord(company_name="Company C", source="sam_entity", business_types=[]),
    ]
    
    checker = EligibilityChecker(enable_set_aside=True)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 3
    assert len(filter_reasons) == 0


def test_set_aside_disabled():
    profile = TenderProfile(
        tender_id="TEST_8A_DISABLED",
        api_metadata=APIMetadata(
            title="8(a) Contract",
            set_aside=SetAsideMetadata(code="8A"),
        ),
    )
    
    vendors = [
        VendorRecord(company_name="Non-8(a) Company", source="sam_entity", business_types=["Small Business"]),
    ]
    
    checker = EligibilityChecker(enable_set_aside=False)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert len(filter_reasons) == 0


def test_case_insensitive_business_types():
    profile = TenderProfile(
        tender_id="TEST_CASE",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A"),
        ),
    )
    
    vendors = [
        VendorRecord(company_name="Lowercase", source="sam_entity", business_types=["8(a)"]),
        VendorRecord(company_name="Uppercase", source="sam_entity", business_types=["8(A)"]),
        VendorRecord(company_name="NonMatch", source="sam_entity", business_types=["Small Business"]),
    ]
    
    checker = EligibilityChecker(enable_set_aside=True)
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 2
    assert filter_reasons["set_aside_mismatch_8A"] == 1


def test_size_capacity_filtering():
    profile = TenderProfile(
        tender_id="TEST_SIZE",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0, currency="USD"),
        ),
    )
    
    vendors = [
        VendorRecord(
            company_name="Large Contractor",
            source="sam_entity",
            total_contract_value=2000000.0,
        ),
        VendorRecord(
            company_name="Medium Contractor",
            source="sam_entity",
            total_contract_value=500000.0,
        ),
        VendorRecord(
            company_name="Small Contractor",
            source="sam_entity",
            total_contract_value=50000.0,
        ),
        VendorRecord(
            company_name="No History",
            source="sam_entity",
            total_contract_value=0,
        ),
    ]
    
    checker = EligibilityChecker(
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1,
    )
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 3
    assert "Small Contractor" not in [v.company_name for v in eligible]
    assert filter_reasons.get("insufficient_contract_history", 0) == 1


def test_combined_filtering():
    profile = TenderProfile(
        tender_id="TEST_COMBINED",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A"),
            estimated_value=EstimatedValue(amount=500000.0),
        ),
    )
    
    vendors = [
        VendorRecord(
            company_name="8(a) Large Contractor",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=1000000.0,
        ),
        VendorRecord(
            company_name="8(a) Small Contractor",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=10000.0,
        ),
        VendorRecord(
            company_name="Non-8(a) Large Contractor",
            source="sam_entity",
            business_types=["Small Business"],
            total_contract_value=1000000.0,
        ),
    ]
    
    checker = EligibilityChecker(
        enable_set_aside=True,
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1,
    )
    eligible, filter_reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert eligible[0].company_name == "8(a) Large Contractor"
    assert filter_reasons["set_aside_mismatch_8A"] == 1
    assert filter_reasons["insufficient_contract_history"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
