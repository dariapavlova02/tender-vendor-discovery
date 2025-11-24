#!/usr/bin/env python3
"""Test ammunition tender through full pipeline with 3-level contact enrichment."""

import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig, EnrichmentConfig
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    cfg = RuntimeConfig()
    
    cfg.enrichment = EnrichmentConfig(
        enable_contact_scraping=True,
        enable_llm_fallback=True,
        enable_website_search=True,
        enable_ddg_search=True,
        enable_serper_fallback=True,
        enable_targeted_serper_fallback=True,
        scraper_timeout_seconds=10,
        max_enrichment_workers=10,
        batch_size=50,
        min_batch_success_rate=0.15,
        max_enrichment_batches=5,
        target_relevant_vendors=200,
        enable_batch_quality_gates=True,
        enable_sampling_fallback=True,
        sample_positions=[150, 300],
        relevance_score_threshold=70.0,
        website_search_min_confidence=0.5
    )
    
    logger.info("Initializing pipeline with website search and contact scraping enabled")
    pipeline = TenderVendorPipeline(config=cfg)
    
    tender_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/")
    logger.info(f"Running pipeline on: {tender_path}")
    
    artifacts = pipeline.run([tender_path], disable_auto_ingestion=True)
    
    profile = artifacts.tender_profile
    logger.info("\n" + "="*80)
    logger.info("TENDER PROFILE")
    logger.info("="*80)
    logger.info(f"Project type: {profile.doc_extracted.structured.project_type}")
    logger.info(f"Sector: {profile.doc_extracted.structured.sector}")
    logger.info(f"Solicitation #: {profile.doc_extracted.structured.solicitation_number}")
    logger.info(f"Reference #: {profile.doc_extracted.structured.reference_number}")
    
    logger.info(f"\nDiscovered vendors: {len(artifacts.raw_vendors)}")
    logger.info(f"Filtered vendors: {len(artifacts.filtered_vendors)}")
    logger.info(f"Enriched vendors: {len(artifacts.enriched_vendors)}")
    logger.info(f"Final matches: {len(artifacts.final_matches)}")
    
    logger.info("\n" + "="*80)
    logger.info("CONTACT ENRICHMENT ANALYSIS")
    logger.info("="*80)
    
    enriched = artifacts.enriched_vendors
    
    with_websites = sum(1 for v in enriched if v.website)
    with_emails = sum(1 for v in enriched if v.email)
    with_phones = sum(1 for v in enriched if v.phone)
    
    logger.info(f"Websites: {with_websites}/{len(enriched)} ({with_websites/len(enriched)*100:.1f}%)")
    logger.info(f"Emails: {with_emails}/{len(enriched)} ({with_emails/len(enriched)*100:.1f}%)")
    logger.info(f"Phones: {with_phones}/{len(enriched)} ({with_phones/len(enriched)*100:.1f}%)")
    
    contact_sources = {}
    for vendor in enriched:
        if vendor.email:
            source = vendor.filtering_metadata.get("email_source", "unknown")
            contact_sources[source] = contact_sources.get(source, 0) + 1
    
    logger.info("\nContact sources:")
    for source, count in sorted(contact_sources.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {source}: {count}")
    
    logger.info("\n" + "="*80)
    logger.info("TOP 10 MATCHES")
    logger.info("="*80)
    
    for i, match in enumerate(artifacts.final_matches[:10], 1):
        logger.info(f"\n{i}. {match.vendor.company_name}")
        logger.info(f"   Score: {match.capability_match_score:.1f}")
        logger.info(f"   Location: {match.vendor.city}, {match.vendor.state}")
        logger.info(f"   Website: {match.vendor.website or 'N/A'}")
        logger.info(f"   Email: {match.vendor.email or 'N/A'}")
        logger.info(f"   Phone: {match.vendor.phone or 'N/A'}")
        if match.vendor.email:
            email_source = match.vendor.filtering_metadata.get("email_source", "unknown")
            logger.info(f"   Email source: {email_source}")
    
    logger.info("\n" + "="*80)
    logger.info("Saving outputs...")
    pipeline.save_outputs(artifacts.final_matches, base_name="ammunition_tender")
    logger.info("✓ Outputs saved to outputs/ammunition_tender.*")


if __name__ == "__main__":
    main()
