"""Quick test to validate adaptive tender summary logic."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from src.vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider
from src.vendor_ai_agent.models import TenderProfile, DynamicTenderContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_rich_sections():
    """Test adaptive logic with RICH sections (DHS tender)."""
    logger.info("=" * 80)
    logger.info("TEST 1: Rich Sections (DHS Uniforms)")
    logger.info("=" * 80)
    
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    parser = DocumentParser()
    sections = parser.parse([pdf_path])
    
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    req_extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = req_extractor.extract(sections)
    
    config = RuntimeConfig()
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config.capability_matching)
    
    summary = matcher._build_tender_requirements_summary(profile)
    
    logger.info(f"\nProfile Info:")
    logger.info(f"  - scope_of_work: {len(profile.doc_extracted.sections.scope_of_work)} chars")
    logger.info(f"  - technical_requirements: {len(profile.doc_extracted.sections.technical_requirements)} chars")
    logger.info(f"  - mandatory_requirements: {len(profile.doc_extracted.sections.mandatory_requirements)} chars")
    logger.info(f"  - total structured: {len(profile.doc_extracted.sections.scope_of_work) + len(profile.doc_extracted.sections.technical_requirements) + len(profile.doc_extracted.sections.mandatory_requirements)} chars")
    logger.info(f"  - keywords available: {len(profile.dynamic_context.technical_keywords)}")
    
    logger.info(f"\nAdaptive Summary:")
    logger.info(f"  - Length: {len(summary)} chars")
    logger.info(f"  - Sections: {len(summary.split(chr(10) + chr(10)))}")
    
    logger.info(f"\nFull Summary:")
    logger.info("─" * 80)
    logger.info(summary)
    logger.info("─" * 80)
    
    expected_info_gap = 1.0 - min((1236 + 65759 + 35034) / 1500.0, 1.0)
    logger.info(f"\nExpected info_gap_ratio: {expected_info_gap:.2%}")
    logger.info(f"Expected keyword count: ~{10 + int(expected_info_gap * 15)}")
    logger.info(f"Expected behavior: Use section_budget=600, limit keywords to 10")


def test_sparse_sections():
    """Test adaptive logic with SPARSE sections (simulated empty)."""
    logger.info("\n\n" + "=" * 80)
    logger.info("TEST 2: Sparse Sections (Simulated Empty)")
    logger.info("=" * 80)
    
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    config = RuntimeConfig()
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config.capability_matching)
    
    profile = TenderProfile()
    profile.doc_extracted.structured.project_type = "Government uniform supply"
    profile.doc_extracted.structured.sector = "Apparel Manufacturing"
    
    profile.dynamic_context = DynamicTenderContext(
        sector="Law Enforcement Uniforms",
        industry_description="Supply of tactical uniforms and gear to federal law enforcement agencies including DHS components.",
        technical_keywords=[
            "tactical", "law enforcement", "uniforms", "DHS", "federal", "police", 
            "security", "apparel", "specifications", "contract", "protective gear",
            "badges", "insignia", "outerwear", "pants", "shirts", "boots", "ballistic",
            "duty belt", "accessories", "patches"
        ],
        search_terms=[
            "law enforcement uniform suppliers",
            "tactical gear manufacturers",
            "DHS uniform contractors",
            "police apparel vendors",
            "federal uniform supply"
        ],
        country="USA"
    )
    
    summary = matcher._build_tender_requirements_summary(profile)
    
    logger.info(f"\nProfile Info:")
    logger.info(f"  - scope_of_work: 0 chars (EMPTY)")
    logger.info(f"  - technical_requirements: 0 chars (EMPTY)")
    logger.info(f"  - mandatory_requirements: 0 chars (EMPTY)")
    logger.info(f"  - keywords available: {len(profile.dynamic_context.technical_keywords)}")
    
    logger.info(f"\nAdaptive Summary:")
    logger.info(f"  - Length: {len(summary)} chars")
    logger.info(f"  - Sections: {len(summary.split(chr(10) + chr(10)))}")
    
    logger.info(f"\nFull Summary:")
    logger.info("─" * 80)
    logger.info(summary)
    logger.info("─" * 80)
    
    logger.info(f"\nExpected info_gap_ratio: 100% (empty sections)")
    logger.info(f"Expected keyword count: ~25 (10 base + 15 bonus)")
    logger.info(f"Expected behavior: Add industry_description + 20+ keywords + search terms")


def test_canada_tender():
    """Test adaptive logic with Canada-specific fields."""
    logger.info("\n\n" + "=" * 80)
    logger.info("TEST 3: Canada Tender with GSIN Codes")
    logger.info("=" * 80)
    
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    config = RuntimeConfig()
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config.capability_matching)
    
    profile = TenderProfile()
    profile.doc_extracted.structured.project_type = "Supply and delivery of ammunition"
    profile.doc_extracted.structured.sector = "Ammunition"
    
    profile.dynamic_context = DynamicTenderContext(
        sector="Ammunition Supply",
        industry_description="Supply of frangible training ammunition to Ontario Parks rangers.",
        technical_keywords=[
            "ammunition", "frangible", "training", "9mm", "5.56mm", "bullets",
            "ontario", "parks", "rangers", "law enforcement", "supply"
        ],
        search_terms=[
            "frangible ammunition suppliers ontario",
            "training ammunition manufacturers canada",
            "law enforcement ammo suppliers"
        ],
        gsin_codes=["12", "1210", "121015"],
        province="ON",
        country="Canada"
    )
    
    summary = matcher._build_tender_requirements_summary(profile)
    
    logger.info(f"\nProfile Info (Canada-specific):")
    logger.info(f"  - GSIN codes: {profile.dynamic_context.gsin_codes}")
    logger.info(f"  - Province: {profile.dynamic_context.province}")
    logger.info(f"  - Country: {profile.dynamic_context.country}")
    
    logger.info(f"\nAdaptive Summary:")
    logger.info(f"  - Length: {len(summary)} chars")
    logger.info(f"  - Contains GSIN: {'GSIN Codes' in summary}")
    
    logger.info(f"\nFull Summary:")
    logger.info("─" * 80)
    logger.info(summary)
    logger.info("─" * 80)
    
    logger.info(f"\nExpected behavior: Include GSIN codes (Canada-specific)")


if __name__ == "__main__":
    test_rich_sections()
    test_sparse_sections()
    test_canada_tender()
    
    logger.info("\n\n" + "=" * 80)
    logger.info("ADAPTIVE SUMMARY VALIDATION COMPLETE")
    logger.info("=" * 80)
