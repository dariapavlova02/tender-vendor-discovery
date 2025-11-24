"""Debug script to check if sections are being extracted from DHS PDF."""
import logging
from pathlib import Path

from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from src.vendor_ai_agent.modules.tender_profiler import TenderProfiler
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Check section extraction and profile building for DHS Uniforms."""
    
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        return
    
    # Step 1: Parse PDF into sections
    logger.info("=" * 80)
    logger.info("STEP 1: DocumentParser.parse()")
    logger.info("=" * 80)
    
    parser = DocumentParser()
    sections = parser.parse([pdf_path])
    
    logger.info(f"Total sections parsed: {len(sections)}")
    logger.info(f"\nFirst 5 sections:")
    for i, section in enumerate(sections[:5]):
        logger.info(f"{i+1}. Title: {section.title[:80]}")
        logger.info(f"   Type: {section.section_type}")
        logger.info(f"   Content: {len(section.content)} chars")
        logger.info(f"   Preview: {section.content[:150]}...")
        logger.info("")
    
    # Step 2: Extract sections with SectionExtractor
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: SectionExtractor.extract()")
    logger.info("=" * 80)
    
    from src.vendor_ai_agent.modules.document_processing import SectionExtractor
    extractor = SectionExtractor()
    doc_sections = extractor.extract(sections)
    
    logger.info(f"DocSections extracted:")
    logger.info(f"  - scope_of_work: {len(doc_sections.scope_of_work)} chars")
    logger.info(f"  - technical_requirements: {len(doc_sections.technical_requirements)} chars")
    logger.info(f"  - mandatory_requirements: {len(doc_sections.mandatory_requirements)} chars")
    logger.info(f"  - vendor_qualifications: {len(doc_sections.vendor_qualifications)} chars")
    logger.info(f"  - evaluation_criteria: {len(doc_sections.evaluation_criteria)} chars")
    logger.info(f"  - tables: {len(doc_sections.tables)} tables")
    logger.info(f"  - table_summaries: {len(doc_sections.table_summaries)} chars")
    
    if doc_sections.scope_of_work:
        logger.info(f"\nScope preview:\n{doc_sections.scope_of_work[:300]}...")
    else:
        logger.warning("\n⚠️  scope_of_work is EMPTY!")
    
    if doc_sections.technical_requirements:
        logger.info(f"\nTechnical preview:\n{doc_sections.technical_requirements[:300]}...")
    else:
        logger.warning("\n⚠️  technical_requirements is EMPTY!")
    
    # Step 3: Create TenderProfile with RequirementExtractor
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: RequirementExtractor.extract()")
    logger.info("=" * 80)
    
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini", use_flex_tier=True)
    req_extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = req_extractor.extract(sections)
    
    logger.info(f"\nTenderProfile created:")
    logger.info(f"  - project_type: {profile.doc_extracted.structured.project_type}")
    logger.info(f"  - sector: {profile.doc_extracted.structured.sector}")
    logger.info(f"  - scope_of_work: {len(profile.doc_extracted.sections.scope_of_work)} chars")
    logger.info(f"  - technical_requirements: {len(profile.doc_extracted.sections.technical_requirements)} chars")
    logger.info(f"  - dynamic_context.sector: {profile.dynamic_context.sector}")
    logger.info(f"  - dynamic_context.technical_keywords: {len(profile.dynamic_context.technical_keywords)} keywords")
    
    if profile.dynamic_context.technical_keywords:
        logger.info(f"\nKeywords: {', '.join(profile.dynamic_context.technical_keywords[:10])}")
    else:
        logger.warning("\n⚠️  No technical keywords generated!")
    
    # Step 4: Build tender requirements summary (what LLM sees)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: What LLM Scoring Sees (tender requirements)")
    logger.info("=" * 80)
    
    from src.vendor_ai_agent.modules.capability_matching import CapabilityMatcher
    from src.vendor_ai_agent.config import RuntimeConfig
    
    config = RuntimeConfig()
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config.capability_matching)
    
    # This is what gets sent to LLM
    tender_summary = matcher._build_tender_requirements_summary(profile)
    
    logger.info(f"\nTender requirements summary ({len(tender_summary)} chars):")
    logger.info("─" * 80)
    logger.info(tender_summary)
    logger.info("─" * 80)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSIS")
    logger.info("=" * 80)
    
    issues = []
    if not doc_sections.scope_of_work:
        issues.append("❌ scope_of_work is EMPTY")
    if not doc_sections.technical_requirements:
        issues.append("❌ technical_requirements is EMPTY")
    if not profile.dynamic_context.technical_keywords:
        issues.append("❌ No technical keywords generated")
    if len(tender_summary) < 200:
        issues.append(f"❌ Tender summary is too short ({len(tender_summary)} chars)")
    
    if issues:
        logger.error("\nISSUES FOUND:")
        for issue in issues:
            logger.error(f"  {issue}")
        logger.error("\nThis explains low vendor scores - LLM has insufficient context!")
    else:
        logger.info("\n✅ All sections extracted successfully")

if __name__ == "__main__":
    main()
