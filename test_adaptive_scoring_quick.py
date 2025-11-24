"""Quick test to verify adaptive scoring for TRU-SPEC and TOMAHAWK."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.ingestion.parser import TenderDocumentParser
from src.vendor_ai_agent.modules.extraction import TenderInformationExtractor
from src.vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from src.vendor_ai_agent.models import Vendor

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_truspec_tomahawk_scoring():
    """Test scoring for TRU-SPEC and TOMAHAWK with adaptive context."""
    
    config = RuntimeConfig()
    config.capability_matching.enable_llm_assessment = True
    
    # Parse tender
    tender_file = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    logger.info("Parsing tender document...")
    parser = TenderDocumentParser()
    parsed_doc = parser.parse(str(tender_file))
    
    logger.info("Extracting tender information...")
    extractor = TenderInformationExtractor(config=config)
    tender_info = extractor.extract(parsed_doc)
    
    logger.info(f"Tender: {tender_info.tender_metadata.title}")
    logger.info(f"Project type: {tender_info.project_type}")
    logger.info(f"Keywords: {len(tender_info.keywords)} extracted")
    
    # Create test vendors
    vendors = [
        Vendor(
            company_name="TRU-SPEC GLOBAL LLC",
            location="Georgia, USA",
            naics_codes=["315220"],  # Men's and Boys' Cut and Sew Apparel Manufacturing
            website_content="TRU-SPEC is a leading manufacturer of military, law enforcement, and tactical uniforms. We produce high-quality uniforms including BDUs, ACUs, flight suits, and tactical gear. Our products meet military specifications and are trusted by federal agencies including DHS, DOD, and law enforcement nationwide."
        ),
        Vendor(
            company_name="TOMAHAWK PERFORMANCE INC",
            location="California, USA", 
            naics_codes=["315220"],
            website_content="Tomahawk Performance specializes in manufacturing tactical uniforms and performance apparel for law enforcement and federal agencies. We produce duty uniforms, tactical pants, shirts, and outerwear meeting federal specifications. Our products serve DHS, CBP, ICE, and other federal agencies."
        ),
        Vendor(
            company_name="Random Cleaning Services LLC",
            location="Georgia, USA",
            naics_codes=["561720"],  # Janitorial Services
            website_content="We provide cleaning services for commercial buildings, offices, and facilities. Our team handles janitorial work, floor maintenance, and facility cleaning contracts."
        )
    ]
    
    logger.info("\n" + "=" * 80)
    logger.info("SCORING VENDORS WITH ADAPTIVE CONTEXT")
    logger.info("=" * 80)
    
    matcher = CapabilityMatcher(config=config)
    
    for vendor in vendors:
        logger.info(f"\n--- Vendor: {vendor.company_name} ---")
        
        # Score vendor
        result = matcher.assess_capability_match(vendor, tender_info)
        
        logger.info(f"Score: {result.capability_match_score:.1f}/100")
        logger.info(f"Rationale: {result.rationale[:200]}...")
        
        # Expected results
        if "TRU-SPEC" in vendor.company_name or "TOMAHAWK" in vendor.company_name:
            if result.capability_match_score >= 85:
                logger.info("✅ PASS - Perfect match vendor scored high!")
            else:
                logger.error(f"❌ FAIL - Expected 85+, got {result.capability_match_score:.1f}")
        else:
            if result.capability_match_score < 60:
                logger.info("✅ PASS - Irrelevant vendor scored low")
            else:
                logger.warning(f"⚠️  Irrelevant vendor scored unexpectedly high: {result.capability_match_score:.1f}")
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_truspec_tomahawk_scoring()
