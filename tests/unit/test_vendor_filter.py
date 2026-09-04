"""Unit tests for multi-stage vendor filter orchestration."""
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


def test_complete_pipeline():
    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        enable_local_first=True,
        log_filtering_decisions=True,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(
        tender_id="TEST",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="Boston", state_province="MA", country="United States")
            )
        ),
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A"),
            estimated_value=EstimatedValue(amount=1000000.0)
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="MA 8(a) Contractor",
            city="Boston",
            state="MA",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=2000000.0
        ),
        VendorRecord(
            company_name="MA 8(a) Contractor",
            city="Cambridge",
            state="MA",
            source="canada_contracts",
            business_types=["8(a)"],
            total_contract_value=1500000.0
        ),
        VendorRecord(
            company_name="CT 8(a) Contractor",
            city="Hartford",
            state="CT",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=1500000.0
        ),
        VendorRecord(
            company_name="CA Non-8(a) Contractor",
            city="Los Angeles",
            state="CA",
            source="sam_entity",
            business_types=["Small Business"],
            total_contract_value=3000000.0
        ),
        VendorRecord(
            company_name="MA Too Small",
            city="Boston",
            state="MA",
            source="sam_entity",
            business_types=["8(a)"],
            total_contract_value=50000.0
        ),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 2
    assert result[0].company_name == "MA 8(a) Contractor"
    assert result[1].company_name == "CT 8(a) Contractor"
    
    metrics = filter_engine.get_metrics()
    assert metrics.total_input == 5
    assert metrics.duplicates_removed == 1
    assert metrics.local_vendors == 2
    assert metrics.national_vendors == 1
    assert metrics.eligibility_filtered == 2
    assert metrics.final_count == 2


def test_duplicate_removal_stage():
    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=False,
        enable_eligibility_checks=False,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(tender_id="TEST")
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity"),
        VendorRecord(company_name="Company A Inc.", source="canada_contracts"),
        VendorRecord(company_name="Company B", source="sam_entity"),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 2
    metrics = filter_engine.get_metrics()
    assert metrics.duplicates_removed == 1


def test_geographic_filtering_stage():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=True,
        enable_eligibility_checks=False,
        enable_local_first=True,
        national_expansion_threshold=2,
        enable_geographic_sorting=False,
    )
    
    filter_engine = VendorFilter(config)
    
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
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 2
    assert result[0].company_name == "MA Local"
    assert result[1].company_name == "CT Regional"
    
    metrics = filter_engine.get_metrics()
    assert metrics.local_vendors == 1
    assert metrics.national_vendors == 1


def test_eligibility_filtering_stage():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=False,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(
        tender_id="TEST",
        api_metadata=APIMetadata(
            set_aside=SetAsideMetadata(code="8A")
        )
    )
    
    vendors = [
        VendorRecord(company_name="8(a) Company", source="sam_entity", business_types=["8(a)"]),
        VendorRecord(company_name="Non-8(a) Company", source="sam_entity", business_types=["Small Business"]),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 1
    assert result[0].company_name == "8(a) Company"
    
    metrics = filter_engine.get_metrics()
    assert metrics.eligibility_filtered == 1


def test_preliminary_ranking_stage():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=False,
        enable_eligibility_checks=False,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(tender_id="TEST")
    
    vendors = [
        VendorRecord(company_name="Low Score", source="sam_entity"),
        VendorRecord(
            company_name="High Score",
            source="sam_entity",
            is_past_winner=True,
            enrichment_flags=["high_value_supplier"]
        ),
        VendorRecord(company_name="Medium Score", source="sam_entity", is_past_winner=True),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 3
    assert result[0].company_name == "High Score"
    assert result[1].company_name == "Medium Score"
    assert result[2].company_name == "Low Score"


def test_max_candidates_limit():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=False,
        enable_eligibility_checks=False,
        max_candidates=2,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(tender_id="TEST")
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity"),
        VendorRecord(company_name="Company B", source="sam_entity"),
        VendorRecord(company_name="Company C", source="sam_entity"),
        VendorRecord(company_name="Company D", source="sam_entity"),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 2


def test_national_expansion_threshold():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=True,
        enable_eligibility_checks=False,
        enable_local_first=True,
        national_expansion_threshold=50,
    )
    
    filter_engine = VendorFilter(config)
    
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
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 2


def test_all_stages_disabled():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=False,
        enable_eligibility_checks=False,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(tender_id="TEST")
    
    vendors = [
        VendorRecord(company_name="Company A", source="sam_entity"),
        VendorRecord(company_name="Company A", source="canada_contracts"),
        VendorRecord(company_name="Company B", source="sam_entity"),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert len(result) == 3


def test_empty_vendor_list():
    config = FilteringConfig()
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(tender_id="TEST")
    result = filter_engine.filter(profile, [])
    
    assert len(result) == 0
    metrics = filter_engine.get_metrics()
    assert metrics.total_input == 0
    assert metrics.final_count == 0


def test_geo_score_combined_with_preliminary_score():
    config = FilteringConfig(
        enable_duplicate_removal=False,
        enable_geographic=True,
        enable_eligibility_checks=False,
        enable_local_first=False,
        local_preference_boost=20.0,
    )
    
    filter_engine = VendorFilter(config)
    
    profile = TenderProfile(
        tender_id="TEST",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="Boston", state_province="MA", country="United States")
            )
        )
    )
    
    vendors = [
        VendorRecord(
            company_name="CA High Performer",
            city="Los Angeles",
            state="CA",
            source="sam_entity",
            is_past_winner=True,
            enrichment_flags=["high_value_supplier", "frequent_supplier"]
        ),
        VendorRecord(
            company_name="MA Average",
            city="Boston",
            state="MA",
            source="sam_entity"
        ),
    ]
    
    result = filter_engine.filter(profile, vendors)
    
    assert result[0].company_name == "CA High Performer"
    assert result[0].preliminary_score == 90.0
    assert result[0].geo_score == 0.0
    
    assert result[1].company_name == "MA Average"
    assert result[1].preliminary_score == 55.0
    assert result[1].geo_score == 20.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
