"""Test script for new batch enrichment with quality gates."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_batch_enrichment():
    """Test batch enrichment with DHS Uniforms tender."""
    
    config = RuntimeConfig()
    config.enrichment.batch_size = 30
    config.enrichment.min_batch_success_rate = 0.15
    config.enrichment.max_enrichment_batches = 3
    config.enrichment.target_relevant_vendors = 100
    config.enrichment.enable_batch_quality_gates = True
    config.enrichment.enable_sampling_fallback = True
    config.enrichment.relevance_score_threshold = 60.0
    
    config.capability_matching.enable_llm_assessment = True
    config.capability_matching.max_llm_evaluations = 200
    
    config.filtering.max_candidates = 500
    
    logger.info("=" * 80)
    logger.info("BATCH ENRICHMENT TEST - DHS Uniforms")
    logger.info("=" * 80)
    logger.info(f"Config:")
    logger.info(f"  - Batch size: {config.enrichment.batch_size}")
    logger.info(f"  - Min success rate: {config.enrichment.min_batch_success_rate:.1%}")
    logger.info(f"  - Max batches: {config.enrichment.max_enrichment_batches}")
    logger.info(f"  - Target relevant: {config.enrichment.target_relevant_vendors}")
    logger.info(f"  - Relevance threshold: {config.enrichment.relevance_score_threshold}")
    logger.info("=" * 80)
    
    tender_dir = Path("data/DHS-wide+Uniforms+III+Contract")
    tender_files = [
        tender_dir / "RFP 70B01C26R00000004 Uniforms III.pdf",
    ]
    
    for f in tender_files:
        if not f.exists():
            logger.error(f"File not found: {f}")
            return
    
    pipeline = TenderVendorPipeline(config=config)
    
    logger.info("\nStarting pipeline...")
    result = pipeline.run(tender_files)
    
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Discovered vendors: {len(result.raw_vendors)}")
    logger.info(f"Filtered vendors: {len(result.filtered_vendors)}")
    logger.info(f"Enriched vendors: {len(result.enriched_vendors)}")
    logger.info(f"Final matches: {len(result.final_matches)}")
    
    if result.final_matches:
        logger.info("\nTop 10 matches:")
        for i, match in enumerate(result.final_matches[:10], 1):
            logger.info(
                f"{i}. {match.vendor.company_name} - "
                f"Score: {match.capability_match_score:.1f}/100"
            )
            logger.info(f"   Location: {match.vendor.location}")
            logger.info(f"   Rationale: {match.rationale[:100]}...")
    
    logger.info("\n" + "=" * 80)
    if result.filtering_metrics:
        logger.info("Filtering metrics:")
        logger.info(f"  {result.filtering_metrics}")
    
    logger.info("=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_batch_enrichment()
