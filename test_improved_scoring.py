"""Test improved capability matching with NAICS similarity and tiered scoring."""
from vendor_ai_agent.config import CapabilityMatchingConfig
from vendor_ai_agent.models import (
    TenderProfile,
    VendorRecord,
    DocExtracted,
    StructuredDocData,
)
from vendor_ai_agent.modules.capability_matching import CapabilityMatcher


def test_improved_scoring():
    config = CapabilityMatchingConfig(
        enable_llm_assessment=False,
        fallback_to_rule_based=True,
    )
    matcher = CapabilityMatcher(llm_provider=None, config=config)
    
    tender_profile = TenderProfile(
        tender_id="DHS-UNIFORMS",
        country="USA",
        source_system="test",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                naics_codes=["315220"],
                project_type="Uniform Procurement",
            ),
        ),
    )
    
    print("\n" + "="*80)
    print("Testing Improved Capability Scoring")
    print("Tender: DHS Uniforms III (NAICS: 315220 - Men's/Boys' Cut/Sew Apparel)")
    print("="*80)
    
    vendors = [
        VendorRecord(
            company_name="Relevant Uniform Manufacturer",
            website="https://uniforms.com",
            filtering_metadata={
                "website_content": "We manufacture tactical uniforms",
                "naics_codes": ["315220"],
            },
            enrichment_flags=["high_value_supplier"],
            is_past_winner=True,
            email="contact@uniforms.com",
            phone="555-1234",
        ),
        VendorRecord(
            company_name="Related Apparel Company",
            website="https://apparel.com",
            filtering_metadata={
                "naics_codes": ["315990"],
            },
            email="info@apparel.com",
        ),
        VendorRecord(
            company_name="Construction Company (Irrelevant)",
            website="https://construction.com",
            filtering_metadata={
                "naics_codes": ["236220"],
            },
            email="info@construction.com",
        ),
        VendorRecord(
            company_name="Unknown Industry Vendor (No NAICS)",
            website="https://unknown.com",
            filtering_metadata={},
            email="contact@unknown.com",
        ),
        VendorRecord(
            company_name="No Website No Contact (Worst Case)",
            website=None,
            filtering_metadata={},
        ),
    ]
    
    results = matcher.score(tender_profile, vendors)
    
    print("\n{:<45} {:>10} {}".format("Vendor", "Score", "Rationale"))
    print("-" * 120)
    
    for result in results:
        vendor = result.vendor
        score = result.capability_match_score
        rationale = result.rationale[:60]
        
        naics_codes = vendor.filtering_metadata.get("naics_codes", [])
        has_website = "✓" if vendor.website else "✗"
        has_content = "✓" if vendor.filtering_metadata.get("website_content") else "✗"
        has_contact = "✓" if (vendor.email or vendor.phone) else "✗"
        
        print(f"{vendor.company_name:<45} {score:>10.1f} {rationale}")
        print(f"  └─ Website: {has_website} | Content: {has_content} | Contact: {has_contact} | NAICS: {', '.join(naics_codes) if naics_codes else 'None'}")
        print()
    
    print("\nExpected Behavior:")
    print("  1. Relevant Uniform Manufacturer (exact NAICS match) should score highest (85-95 pts)")
    print("  2. Related Apparel Company (same sector) should score moderately (40-50 pts)")
    print("  3. Construction Company should score lower (30-40 pts)")
    print("  4. No Website/Contact vendor should score lowest (15-25 pts)")
    print()
    
    assert results[0].vendor.company_name == "Relevant Uniform Manufacturer"
    assert results[0].capability_match_score >= 85, f"Expected >= 85, got {results[0].capability_match_score}"
    
    assert results[-1].vendor.company_name == "No Website No Contact (Worst Case)"
    assert results[-1].capability_match_score <= 25, f"Expected <= 25, got {results[-1].capability_match_score}"
    
    construction_result = next(r for r in results if "Construction" in r.vendor.company_name)
    assert construction_result.capability_match_score < 40, f"Construction company scored too high: {construction_result.capability_match_score}"
    
    print("✅ All assertions passed!")


if __name__ == "__main__":
    test_improved_scoring()
