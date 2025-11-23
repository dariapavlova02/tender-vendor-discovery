"""Test multi-stage vendor filtering with observability."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

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

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_multi_stage_filtering():
    profile = TenderProfile(
        tender_id="TEST-001",
        country="US",
        api_metadata=APIMetadata(
            title="Police Uniform Supply",
            description="Supply uniforms for police department",
            estimated_value=EstimatedValue(amount=500_000, currency="USD"),
            set_aside=SetAsideMetadata(code="8A", description="8(a) Business Development"),
        ),
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                location=Address(city="New York", state_province="NY", country="United States"),
                naics_codes=["315220", "315990"],
            )
        ),
    )

    vendors = [
        VendorRecord(
            company_name="NYC Uniforms Inc",
            source="sam_entity",
            city="New York",
            state="NY",
            country="US",
            business_types=["8(a)", "Women Owned Small Business"],
            total_contract_value=1_000_000,
            contract_count=15,
            is_past_winner=True,
            enrichment_flags=["high_value_supplier"],
        ),
        VendorRecord(
            company_name="Boston Police Gear",
            source="sam_entity",
            city="Boston",
            state="MA",
            country="US",
            business_types=["8(a)"],
            total_contract_value=800_000,
            contract_count=10,
        ),
        VendorRecord(
            company_name="California Clothing Corp",
            source="sam_entity",
            city="Los Angeles",
            state="CA",
            country="US",
            business_types=[],
            total_contract_value=5_000_000,
            contract_count=50,
        ),
        VendorRecord(
            company_name="NYC Uniforms Inc.",
            source="static_contacts",
            city="New York",
            state="NY",
            country="US",
            business_types=["8(a)"],
            total_contract_value=None,
            contract_count=None,
        ),
        VendorRecord(
            company_name="Small Local Shop",
            source="sam_entity",
            city="New York",
            state="NY",
            country="US",
            business_types=[],
            total_contract_value=10_000,
            contract_count=1,
        ),
    ]

    config = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_local_first=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        enable_size_heuristics=True,
        log_filtering_decisions=True,
        max_candidates=10,
    )

    vendor_filter = VendorFilter(config=config)

    filtered = vendor_filter.filter(profile, vendors)

    print("\n" + "=" * 60)
    print("FILTERED VENDORS:")
    print("=" * 60)
    for i, vendor in enumerate(filtered, 1):
        print(f"{i}. {vendor.company_name}")
        print(f"   Location: {vendor.city}, {vendor.state}")
        print(f"   Geo Score: {vendor.geo_score}")
        print(f"   Preliminary Score: {vendor.preliminary_score}")
        print(f"   Total Score: {vendor.geo_score + vendor.preliminary_score}")
        print()

    metrics = vendor_filter.get_metrics()
    print("\nTest completed successfully!")
    print(f"Total input: {metrics.total_input}")
    print(f"Final count: {metrics.final_count}")
    print(f"Duplicates removed: {metrics.duplicates_removed}")


if __name__ == "__main__":
    test_multi_stage_filtering()
