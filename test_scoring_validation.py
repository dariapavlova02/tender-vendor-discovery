"""Quick real-world test for TRU-SPEC and TOMAHAWK scoring with adaptive context."""
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


def test_perfect_match_scoring():
    """Test that TRU-SPEC and TOMAHAWK score 85+ with adaptive context."""
    
    logger.info("=" * 80)
    logger.info("ADAPTIVE SCORING VALIDATION - Perfect Match Vendors")
    logger.info("=" * 80)
    
    # Parse DHS Uniforms tender
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    logger.info("\n1. Parsing tender document...")
    parser = DocumentParser()
    sections = parser.parse([pdf_path])
    
    logger.info("2. Extracting requirements with adaptive logic...")
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    req_extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = req_extractor.extract(sections)
    
    logger.info(f"\nTender Profile:")
    logger.info(f"  - Total keywords: {len(profile.dynamic_context.technical_keywords)}")
    logger.info(f"  - Sections extracted: scope={len(profile.doc_extracted.sections.scope_of_work)} chars, tech={len(profile.doc_extracted.sections.technical_requirements)} chars")
    
    # Create capability matcher
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        max_llm_evaluations=10,
        llm_model="gpt-4o-mini"
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    # Show adaptive summary
    logger.info("\n3. Building adaptive tender summary...")
    summary = matcher._build_tender_requirements_summary(profile)
    logger.info(f"Summary length: {len(summary)} chars")
    logger.info("Summary preview:")
    logger.info("─" * 80)
    logger.info(summary[:400] + "...")
    logger.info("─" * 80)
    
    # Create perfect match vendors
    test_vendors = [
        VendorRecord(
            company_name="TRU-SPEC GLOBAL LLC",
            website="https://www.truspec.com",
            location="Georgia, USA",
            is_past_winner=True,
            total_contract_value=50000000,
            contract_count=25,
            enrichment_flags=["high_value_supplier"],
            filtering_metadata={
                "website_content": "TRU-SPEC is a leading manufacturer of military, law enforcement, and tactical uniforms. We produce high-quality uniforms including BDUs, ACUs, flight suits, and tactical gear. Our products meet military specifications (MIL-SPEC) and are trusted by federal agencies including DHS, DOD, CBP, ICE, TSA, and law enforcement nationwide. We have over 20 years of experience in government contracting with extensive manufacturing capabilities and strict quality control. Our facility is Berry Amendment compliant and we maintain security clearances for handling sensitive government requirements.",
                "content_source": "https://www.truspec.com",
                "scrape_status": "success"
            }
        ),
        VendorRecord(
            company_name="TOMAHAWK PERFORMANCE INC",
            website="https://tomahawkperformance.com",
            location="California, USA",
            is_past_winner=True,
            total_contract_value=30000000,
            contract_count=18,
            enrichment_flags=["high_value_supplier"],
            filtering_metadata={
                "website_content": "Tomahawk Performance specializes in manufacturing tactical uniforms and performance apparel for law enforcement and federal agencies. We produce duty uniforms, tactical pants, shirts, jackets, and outerwear meeting federal specifications. Our products serve DHS, CBP, ICE, TSA, and other federal agencies. We have 15+ years of experience with government contracts and maintain Berry Amendment compliance. Our manufacturing facility includes quality control processes and we handle sensitive government-branded uniform items with proper security protocols.",
                "content_source": "https://tomahawkperformance.com",
                "scrape_status": "success"
            }
        ),
        VendorRecord(
            company_name="Random Cleaning Services LLC",
            website="https://randomcleaning.com",
            location="Georgia, USA",
            is_past_winner=False,
            total_contract_value=0,
            contract_count=0,
            enrichment_flags=[],
            filtering_metadata={
                "website_content": "We provide professional cleaning services for commercial buildings, offices, and facilities. Our team handles janitorial work, floor maintenance, window cleaning, and facility cleaning contracts. We serve local businesses and some government facilities.",
                "content_source": "https://randomcleaning.com",
                "scrape_status": "success"
            }
        )
    ]
    
    logger.info("\n4. Scoring vendors with LLM...")
    logger.info("=" * 80)
    
    results = []
    for vendor in test_vendors:
        logger.info(f"\n--- {vendor.company_name} ---")
        logger.info(f"Website content: {len(vendor.filtering_metadata.get('website_content', ''))} chars")
        logger.info(f"Past winner: {vendor.is_past_winner}")
        logger.info(f"Contract value: ${vendor.total_contract_value:,.0f}")
        
        # Score vendor
        match_result = matcher._llm_assess_capability(profile, vendor)
        
        logger.info(f"Score: {match_result.capability_match_score:.1f}/100")
        logger.info(f"Rationale: {match_result.rationale}")
        
        results.append({
            'vendor': vendor.company_name,
            'score': match_result.capability_match_score,
            'perfect_match': 'TRU-SPEC' in vendor.company_name or 'TOMAHAWK' in vendor.company_name
        })
    
    # Validate results
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION RESULTS")
    logger.info("=" * 80)
    
    all_passed = True
    for result in results:
        if result['perfect_match']:
            if result['score'] >= 85:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (expected 85+)")
            else:
                logger.error(f"❌ FAIL - {result['vendor']}: {result['score']:.1f} (expected 85+, BEFORE FIX WAS ~65)")
                all_passed = False
        else:
            if result['score'] < 60:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (correctly low)")
            else:
                logger.warning(f"⚠️  {result['vendor']}: {result['score']:.1f} (expected <60)")
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED - Adaptive context fixed the scoring!")
        logger.info("Perfect match vendors (TRU-SPEC, TOMAHAWK) now score 85+ instead of 65")
    else:
        logger.error("❌ TESTS FAILED - Adaptive context did not improve scores as expected")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = test_perfect_match_scoring()
    sys.exit(0 if success else 1)
