"""Test adaptive scoring on Canada tender (Ontario Parks Ammunition)."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig, CapabilityMatchingConfig
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from src.vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider
from src.vendor_ai_agent.models import VendorRecord

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_canada_tender_scoring():
    """Test adaptive scoring on Canada tender (Ontario Parks - Ammunition)."""
    
    logger.info("=" * 80)
    logger.info("CANADA TENDER - Adaptive Scoring Test")
    logger.info("=" * 80)
    
    # Parse Ontario Parks Ammunition tender
    tender_dir = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition")
    pdf_files = list(tender_dir.rglob("*.pdf"))
    
    if not pdf_files:
        logger.error(f"No PDF files found in {tender_dir}")
        return False
    
    logger.info(f"\n1. Parsing Canada tender: {pdf_files[0].name}")
    logger.info(f"   Total files: {len(pdf_files)}")
    
    parser = DocumentParser()
    sections = parser.parse([pdf_files[0]])  # Parse first PDF
    
    logger.info("2. Extracting requirements with adaptive logic...")
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    req_extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = req_extractor.extract(sections)
    
    logger.info(f"\nTender Profile (Canada-specific):")
    logger.info(f"  - Country: {profile.dynamic_context.country}")
    logger.info(f"  - Province: {profile.dynamic_context.province}")
    logger.info(f"  - GSIN codes: {profile.dynamic_context.gsin_codes}")
    logger.info(f"  - Total keywords: {len(profile.dynamic_context.technical_keywords)}")
    logger.info(f"  - Sections: scope={len(profile.doc_extracted.sections.scope_of_work)} chars, tech={len(profile.doc_extracted.sections.technical_requirements)} chars")
    
    # Create capability matcher
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        max_llm_evaluations=10,
        llm_model="gpt-4o-mini"
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    # Show adaptive summary with GSIN codes
    logger.info("\n3. Building adaptive tender summary (should include GSIN)...")
    summary = matcher._build_tender_requirements_summary(profile)
    logger.info(f"Summary length: {len(summary)} chars")
    
    # Check for GSIN codes
    has_gsin = any(gsin in summary for gsin in profile.dynamic_context.gsin_codes or [])
    logger.info(f"Contains GSIN codes: {has_gsin}")
    
    logger.info("\nFull summary:")
    logger.info("─" * 80)
    logger.info(summary)
    logger.info("─" * 80)
    
    # Create test vendors for ammunition tender
    test_vendors = [
        VendorRecord(
            company_name="Federal Premium Ammunition Canada",
            website="https://www.federalpremium.com",
            location="Ontario, Canada",
            country="Canada",
            is_past_winner=True,
            total_contract_value=10000000,
            contract_count=15,
            enrichment_flags=["high_value_supplier"],
            filtering_metadata={
                "website_content": "Federal Premium Ammunition is a leading manufacturer of high-quality ammunition for law enforcement, military, and sporting applications. We produce frangible training ammunition including 9mm and 5.56mm rounds specifically designed for law enforcement training. Our frangible bullets disintegrate on impact with hard surfaces, reducing ricochet hazards. We supply ammunition to Ontario law enforcement agencies including OPP, Toronto Police, and Parks enforcement. Our facility maintains strict quality control with lot testing and we have extensive experience with government contracts across Canada.",
                "content_source": "https://www.federalpremium.com",
                "scrape_status": "success"
            }
        ),
        VendorRecord(
            company_name="SinterFire Canada Inc",
            website="https://www.sinterfire.com",
            location="British Columbia, Canada",
            country="Canada",
            is_past_winner=False,
            total_contract_value=2000000,
            contract_count=5,
            enrichment_flags=[],
            filtering_metadata={
                "website_content": "SinterFire specializes in manufacturing frangible ammunition for law enforcement training. Our patented compressed copper/tin powder bullets completely disintegrate upon impact with hardened steel, eliminating ricochet and splashback. We produce 9mm, .40 S&W, 5.56mm, and .223 frangible rounds. Our ammunition is used by police training facilities across Canada. We maintain ISO 9001 certification and provide lot certification with each shipment.",
                "content_source": "https://www.sinterfire.com",
                "scrape_status": "success"
            }
        ),
        VendorRecord(
            company_name="Ontario Office Supplies Ltd",
            website="https://ontariooffice.com",
            location="Toronto, Ontario, Canada",
            country="Canada",
            is_past_winner=False,
            total_contract_value=0,
            contract_count=0,
            enrichment_flags=[],
            filtering_metadata={
                "website_content": "We provide office supplies, furniture, and stationery products to government agencies and businesses across Ontario. Our product range includes paper, pens, desks, chairs, filing cabinets, and office equipment. We handle procurement contracts for various government departments.",
                "content_source": "https://ontariooffice.com",
                "scrape_status": "success"
            }
        )
    ]
    
    logger.info("\n4. Scoring Canadian vendors with LLM...")
    logger.info("=" * 80)
    
    results = []
    for vendor in test_vendors:
        logger.info(f"\n--- {vendor.company_name} ---")
        logger.info(f"Location: {vendor.location}")
        logger.info(f"Website content: {len(vendor.filtering_metadata.get('website_content', ''))} chars")
        logger.info(f"Past winner: {vendor.is_past_winner}")
        
        # Score vendor
        match_result = matcher._llm_assess_capability(profile, vendor)
        
        logger.info(f"Score: {match_result.capability_match_score:.1f}/100")
        logger.info(f"Rationale: {match_result.rationale}")
        
        results.append({
            'vendor': vendor.company_name,
            'score': match_result.capability_match_score,
            'expected_high': 'Ammunition' in vendor.company_name or 'SinterFire' in vendor.company_name
        })
    
    # Validate results
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION RESULTS - Canada Tender")
    logger.info("=" * 80)
    
    all_passed = True
    for result in results:
        if result['expected_high']:
            if result['score'] >= 80:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (expected 80+)")
            else:
                logger.error(f"❌ FAIL - {result['vendor']}: {result['score']:.1f} (expected 80+)")
                all_passed = False
        else:
            if result['score'] < 60:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (correctly low)")
            else:
                logger.warning(f"⚠️  WARNING - {result['vendor']}: {result['score']:.1f} (expected <60)")
    
    logger.info("\n" + "=" * 80)
    if all_passed and has_gsin:
        logger.info("✅ ALL TESTS PASSED - Canada tender scoring works!")
        logger.info("✅ GSIN codes included in adaptive summary")
        logger.info("✅ Ammunition vendors scored correctly")
    elif not has_gsin:
        logger.warning("⚠️  WARNING - GSIN codes not found in summary")
        all_passed = False
    else:
        logger.error("❌ SOME TESTS FAILED")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = test_canada_tender_scoring()
    sys.exit(0 if success else 1)
