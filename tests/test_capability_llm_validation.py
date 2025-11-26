"""
Validation test for the updated LLM capability matching prompt.
Tests that the new prompt correctly handles:
1. Lobbying offices/associations (should score low)
2. Actual suppliers (should score high)
3. Metadata doesn't overwhelm content quality
"""
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(message)s')

from vendor_ai_agent.config import CapabilityMatchingConfig
from vendor_ai_agent.models import TenderProfile, VendorRecord
from vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from vendor_ai_agent.modules.llm_providers import OpenAIProvider

def create_test_vendor(name: str, website: str, content: str, 
                       is_past_winner: bool = False, 
                       contract_value: float = 0) -> VendorRecord:
    vendor = VendorRecord(
        company_name=name,
        website=website,
        location="Canada",
        is_past_winner=is_past_winner,
        total_contract_value=contract_value,
        contract_count=int(contract_value / 100000) if contract_value > 0 else 0,
        enrichment_flags=["high_value_supplier"] if contract_value > 100000000 else [],
    )
    vendor.filtering_metadata["website_content"] = content
    vendor.filtering_metadata["content_source"] = website
    vendor.filtering_metadata["scrape_status"] = "success"
    return vendor

def main():
    print("=" * 80)
    print("CAPABILITY MATCHING LLM VALIDATION TEST")
    print("=" * 80)
    
    tender = TenderProfile(
        tender_id="TEST-VEHICLES",
        country="Canada",
        source_system="test",
    )
    tender.vendor_capability_profile.summary = "Ontario Parks requires 5 utility vehicles for park operations"
    
    test_vendors = [
        create_test_vendor(
            "Canadian Natural Gas Vehicle Alliance",
            "https://lobbycanada.gc.ca/app/secure/ocl/lrs/do/vwRg?cno=366429",
            "Canadian Natural Gas Vehicle Alliance (CNGVA) is a lobbying office registered with the Canadian government. "
            "CNGVA advocates for natural gas vehicle policies and regulations. Contact: lobbyist@cngva.org",
            is_past_winner=True,
            contract_value=5500000,
        ),
        
        create_test_vendor(
            "Vehicle Supply Company",
            "https://vehiclesupply.ca",
            "Vehicle Supply Company is a leading Canadian supplier of utility vehicles, trucks, and fleet equipment. "
            "We provide commercial vehicles to government agencies, municipalities, and parks. "
            "Our product line includes Ford, GMC, and RAM utility vehicles with 4x4 capability suitable for park operations.",
            is_past_winner=False,
            contract_value=500000,
        ),
        
        create_test_vendor(
            "Canadian Vehicle Manufacturers Association",
            "https://cvma.ca",
            "CVMA is the industry association representing major vehicle manufacturers in Canada. "
            "We conduct research, publish reports, and advocate for automotive industry policies. "
            "Our members include Ford, GM, Toyota, and Honda. We do not sell vehicles directly.",
            is_past_winner=True,
            contract_value=3200000,
        ),
        
        create_test_vendor(
            "Ontario Fleet Solutions",
            "https://ontariofleetsolutions.com",
            "Ontario Fleet Solutions specializes in commercial vehicle sales, leasing, and fleet management. "
            "We serve Ontario government agencies and have supplied over 200 utility vehicles to provincial parks. "
            "Our services include vehicle sourcing, customization, and maintenance programs.",
            is_past_winner=True,
            contract_value=15000000,
        ),
    ]
    
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini")
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        llm_model="gpt-4o-mini",
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    print("\n" + "=" * 80)
    print("SCORING VENDORS")
    print("=" * 80)
    
    results = matcher.score(tender, test_vendors)
    results_sorted = sorted(results, key=lambda r: r.capability_match_score, reverse=True)
    
    print(f"\n{'Rank':<5} {'Score':<6} {'Company':<45} {'Type':<15}")
    print("-" * 80)
    
    for i, result in enumerate(results_sorted, 1):
        website = result.vendor.website or ""
        vendor_type = "LOBBYING" if "lobby" in website.lower() or "Alliance" in result.vendor.company_name else \
                     "ASSOCIATION" if "Association" in result.vendor.company_name else \
                     "SUPPLIER"
        
        print(f"{i:<5} {result.capability_match_score:<6.0f} {result.vendor.company_name:<45} {vendor_type:<15}")
        print(f"      Rationale: {result.rationale}")
        print()
    
    print("=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)
    
    checks_passed = 0
    checks_total = 4
    
    lobbying_scores = [r.capability_match_score for r in results if "Alliance" in r.vendor.company_name]
    if lobbying_scores and lobbying_scores[0] < 30:
        print("✅ CHECK 1: Lobbying office scored < 30")
        checks_passed += 1
    else:
        print(f"❌ CHECK 1: Lobbying office scored {lobbying_scores[0] if lobbying_scores else 'N/A'} (expected < 30)")
    
    association_scores = [r.capability_match_score for r in results if "Manufacturers Association" in r.vendor.company_name]
    if association_scores and association_scores[0] < 30:
        print("✅ CHECK 2: Industry association scored < 30")
        checks_passed += 1
    else:
        print(f"❌ CHECK 2: Industry association scored {association_scores[0] if association_scores else 'N/A'} (expected < 30)")
    
    supplier_scores = [r.capability_match_score for r in results if "Supply" in r.vendor.company_name or "Fleet" in r.vendor.company_name]
    if supplier_scores and all(s >= 70 for s in supplier_scores):
        print("✅ CHECK 3: Actual suppliers scored ≥ 70")
        checks_passed += 1
    else:
        print(f"❌ CHECK 3: Suppliers scored {supplier_scores} (expected all ≥ 70)")
    
    top_vendor = results_sorted[0].vendor.company_name
    if "Supply" in top_vendor or "Fleet" in top_vendor:
        print("✅ CHECK 4: Top vendor is an actual supplier (not lobbying/association)")
        checks_passed += 1
    else:
        print(f"❌ CHECK 4: Top vendor is '{top_vendor}' (expected supplier)")
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {checks_passed}/{checks_total} checks passed")
    print("=" * 80)
    
    if checks_passed == checks_total:
        print("\n✅ ALL VALIDATION CHECKS PASSED - LLM prompt is working correctly!")
        return 0
    else:
        print(f"\n⚠️  {checks_total - checks_passed} checks failed - LLM prompt may need adjustment")
        return 1

if __name__ == "__main__":
    exit(main())
