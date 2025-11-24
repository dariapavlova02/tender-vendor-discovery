"""Quick test to verify TRU-SPEC and TOMAHAWK adaptive scoring."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from src.vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider
from src.vendor_ai_agent.models import Vendor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_perfect_match_vendors():
    """Test scoring for TRU-SPEC and TOMAHAWK with adaptive context."""
    
    logger.info("=" * 80)
    logger.info("ADAPTIVE SCORING TEST - Perfect Match Vendors")
    logger.info("=" * 80)
    
    # Parse tender
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    logger.info("\nParsing tender document...")
    parser = DocumentParser()
    sections = parser.parse([pdf_path])
    
    logger.info("Extracting requirements...")
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    req_extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = req_extractor.extract(sections)
    
    logger.info(f"\nTender: {profile.meta.title}")
    logger.info(f"Project type: {profile.dynamic_context.project_type}")
    logger.info(f"Keywords: {len(profile.dynamic_context.technical_keywords)}")
    
    # Create test vendors
    test_vendors = [
        Vendor(
            company_name="TRU-SPEC GLOBAL LLC",
            location_str="Georgia, USA",
            naics_codes=["315220"],
            website_content="TRU-SPEC is a leading manufacturer of military, law enforcement, and tactical uniforms. We produce high-quality uniforms including BDUs, ACUs, flight suits, and tactical gear. Our products meet military specifications and are trusted by federal agencies including DHS, DOD, and law enforcement nationwide. We have manufacturing facilities capable of large-scale production and maintain strict quality control standards."
        ),
        Vendor(
            company_name="TOMAHAWK PERFORMANCE INC",
            location_str="California, USA",
            naics_codes=["315220"],
            website_content="Tomahawk Performance specializes in manufacturing tactical uniforms and performance apparel for law enforcement and federal agencies. We produce duty uniforms, tactical pants, shirts, and outerwear meeting federal specifications. Our products serve DHS, CBP, ICE, TSA, and other federal agencies. We have extensive experience with government contracts and maintain Berry Amendment compliance."
        ),
        Vendor(
            company_name="Random Cleaning Services LLC",
            location_str="Georgia, USA",
            naics_codes=["561720"],
            website_content="We provide cleaning services for commercial buildings, offices, and facilities. Our team handles janitorial work, floor maintenance, and facility cleaning contracts."
        )
    ]
    
    config = RuntimeConfig()
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config.capability_matching)
    
    # Test summary generation
    logger.info("\n" + "─" * 80)
    logger.info("ADAPTIVE TENDER SUMMARY")
    logger.info("─" * 80)
    summary = matcher._build_tender_requirements_summary(profile)
    logger.info(f"Summary length: {len(summary)} chars")
    logger.info(summary[:500] + "...")
    
    logger.info("\n" + "=" * 80)
    logger.info("SCORING RESULTS")
    logger.info("=" * 80)
    
    results = []
    for vendor in test_vendors:
        logger.info(f"\n--- {vendor.company_name} ---")
        
        # Score vendor
        match_result = matcher.match_vendor_to_tender(vendor, profile)
        
        logger.info(f"Score: {match_result.score:.1f}/100")
        logger.info(f"Rationale: {match_result.rationale[:150]}...")
        
        results.append({
            'vendor': vendor.company_name,
            'score': match_result.score,
            'expected_high': 'TRU-SPEC' in vendor.company_name or 'TOMAHAWK' in vendor.company_name
        })
    
    # Validate results
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION")
    logger.info("=" * 80)
    
    all_passed = True
    for result in results:
        if result['expected_high']:
            if result['score'] >= 85:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (expected 85+)")
            else:
                logger.error(f"❌ FAIL - {result['vendor']}: {result['score']:.1f} (expected 85+)")
                all_passed = False
        else:
            if result['score'] < 60:
                logger.info(f"✅ PASS - {result['vendor']}: {result['score']:.1f} (expected <60)")
            else:
                logger.warning(f"⚠️  WARNING - {result['vendor']}: {result['score']:.1f} (expected <60)")
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED - Adaptive scoring working correctly!")
    else:
        logger.error("❌ SOME TESTS FAILED - Check scoring logic")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_perfect_match_vendors()
