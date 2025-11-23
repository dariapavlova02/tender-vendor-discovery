"""Unit tests for eligibility checker."""
import pytest

from vendor_ai_agent.models import (
    TenderProfile,
    VendorRecord,
    APIMetadata,
    SetAsideMetadata,
    EstimatedValue,
)
from vendor_ai_agent.modules.filtering.eligibility_checker import EligibilityChecker


def test_preliminary_score_base():
    checker = EligibilityChecker()
    profile = TenderProfile(tender_id="TEST")
    vendor = VendorRecord(company_name="Test Company", source="sam_entity")
    
    score = checker.calculate_preliminary_score(profile, vendor)
    
    assert score == 55.0


def test_preliminary_score_with_past_winner():
    checker = EligibilityChecker()
    profile = TenderProfile(tender_id="TEST")
    vendor = VendorRecord(
        company_name="Test Company",
        source="sam_entity",
        is_past_winner=True
    )
    
    score = checker.calculate_preliminary_score(profile, vendor)
    
    assert score == 70.0


def test_preliminary_score_with_enrichment_flags():
    checker = EligibilityChecker()
    profile = TenderProfile(tender_id="TEST")
    vendor = VendorRecord(
        company_name="Test Company",
        source="sam_entity",
        enrichment_flags=["high_value_supplier", "frequent_supplier"]
    )
    
    score = checker.calculate_preliminary_score(profile, vendor)
    
    assert score == 75.0


def test_preliminary_score_with_contract_value_match():
    checker = EligibilityChecker()
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    vendor = VendorRecord(
        company_name="Test Company",
        source="sam_entity",
        total_contract_value=1500000.0
    )
    
    score = checker.calculate_preliminary_score(profile, vendor)
    
    assert score == 65.0


def test_preliminary_score_full_bonuses():
    checker = EligibilityChecker()
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    vendor = VendorRecord(
        company_name="Test Company",
        source="sam_entity",
        is_past_winner=True,
        enrichment_flags=["high_value_supplier", "frequent_supplier"],
        total_contract_value=1500000.0
    )
    
    score = checker.calculate_preliminary_score(profile, vendor)
    
    assert score == 100.0


def test_size_capacity_filter_insufficient():
    checker = EligibilityChecker(
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1
    )
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="Large Contractor",
            source="sam_entity",
            total_contract_value=500000.0
        ),
        VendorRecord(
            company_name="Small Contractor",
            source="sam_entity",
            total_contract_value=50000.0
        ),
    ]
    
    eligible, reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert eligible[0].company_name == "Large Contractor"
    assert reasons["insufficient_contract_history"] == 1


def test_size_capacity_filter_no_vendor_history():
    checker = EligibilityChecker(
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1
    )
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    
    vendor = VendorRecord(
        company_name="No History",
        source="sam_entity",
        total_contract_value=None
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 1


def test_size_capacity_filter_no_tender_value():
    checker = EligibilityChecker(
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1
    )
    
    profile = TenderProfile(tender_id="TEST")
    
    vendor = VendorRecord(
        company_name="Company",
        source="sam_entity",
        total_contract_value=50000.0
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 1


def test_size_capacity_disabled():
    checker = EligibilityChecker(enable_size_heuristics=False)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    
    vendor = VendorRecord(
        company_name="Small Contractor",
        source="sam_entity",
        total_contract_value=10000.0
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 1
    assert len(reasons) == 0


def test_set_aside_8a_pass():
    checker = EligibilityChecker(enable_set_aside=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A")
        )
    )
    
    vendor = VendorRecord(
        company_name="8(a) Company",
        source="sam_entity",
        business_types=["8(a)"]
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 1
    assert len(reasons) == 0


def test_set_aside_8a_fail():
    checker = EligibilityChecker(enable_set_aside=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A")
        )
    )
    
    vendor = VendorRecord(
        company_name="Non-8(a) Company",
        source="sam_entity",
        business_types=["Small Business"]
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 0
    assert reasons["set_aside_mismatch_8A"] == 1


def test_set_aside_missing_business_types():
    checker = EligibilityChecker(enable_set_aside=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A")
        )
    )
    
    vendor = VendorRecord(
        company_name="No Types",
        source="sam_entity",
        business_types=[]
    )
    
    eligible, reasons = checker.filter_eligible(profile, [vendor])
    
    assert len(eligible) == 0
    assert reasons["set_aside_missing_8A"] == 1


def test_set_aside_multiple_codes():
    checker = EligibilityChecker(enable_set_aside=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="WOSB")
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="Full Name",
            source="sam_entity",
            business_types=["Women Owned Small Business"]
        ),
        VendorRecord(
            company_name="Shorthand",
            source="sam_entity",
            business_types=["WOSB"]
        ),
    ]
    
    eligible, reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 2


def test_combined_filtering():
    checker = EligibilityChecker(
        enable_set_aside=True,
        enable_size_heuristics=True,
        minimum_contract_value_ratio=0.1
    )
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A"),
            estimated_value=EstimatedValue(amount=500000.0)
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="Perfect Match",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=1000000.0
        ),
        VendorRecord(
            company_name="Wrong Set-Aside",
            source="sam_entity",
            business_types=["Small Business"],
            total_contract_value=1000000.0
        ),
        VendorRecord(
            company_name="Too Small",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=10000.0
        ),
    ]
    
    eligible, reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 1
    assert eligible[0].company_name == "Perfect Match"
    assert reasons["set_aside_mismatch_8A"] == 1
    assert reasons["insufficient_contract_history"] == 1


def test_filter_adds_exclusion_metadata():
    checker = EligibilityChecker(enable_set_aside=True)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A")
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="Filtered",
            source="sam_entity",
            business_types=["Small Business"]
        ),
    ]
    
    eligible, reasons = checker.filter_eligible(profile, vendors)
    
    assert len(eligible) == 0
    assert vendors[0].filtering_metadata["exclusion_reason"] == "set_aside_mismatch_8A"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
