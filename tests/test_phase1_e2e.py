"""Phase 1: End-to-end test with real tender to validate Stage 5."""
import logging
import time
from pathlib import Path
import json

from vendor_ai_agent.config import RuntimeConfig, CapabilityMatchingConfig, EnrichmentConfig
from vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_dhs_uniforms_stage5():
    """Test Stage 5 with DHS Uniforms tender - with full enrichment chain."""
    
    logger.info("=" * 80)
    logger.info("PHASE 1: END-TO-END TEST WITH DHS UNIFORMS TENDER")
    logger.info("=" * 80)
    
    # Configure pipeline with FULL ENRICHMENT CHAIN
    config = RuntimeConfig()
    
    # Stage 5: Capability Matching - NO LIMITS, continue until target reached
    config.capability_matching = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        llm_model="gpt-5-mini",
        enable_website_scraping=True,
        scrape_timeout_seconds=10,
        max_content_chars=3000,
        fallback_to_rule_based=True,
    )
    
    # Enrichment: Enable multi-level fallback chain
    config.enrichment = EnrichmentConfig(
        # Website discovery for vendors without URLs
        enable_website_search=True,  # ← NEW: Search websites via DDG/Serper
        enable_ddg_search=True,
        enable_serper_fallback=True,
        website_search_min_confidence=0.5,
        
        # Contact extraction with 3-level fallback
        enable_contact_scraping=True,
        enable_llm_fallback=True,
        enable_targeted_serper_fallback=True,  # ← NEW: Serper for contacts
        scraper_timeout_seconds=5,
        
        # Scoring thresholds
        relevance_score_threshold=60.0,  # ← NEW: Lower threshold for SAM vendors (was 70)
        
        # Batch processing - NO BATCH LIMIT, continue until target reached
        max_enrichment_workers=10,
        batch_size=50,
        min_batch_success_rate=0.15,
        target_relevant_vendors=200,
        enable_batch_quality_gates=True,
        enable_sampling_fallback=True,
        sample_positions=[150, 300],
    )
    
    logger.info(f"Configuration:")
    logger.info(f"  - LLM Assessment: {config.capability_matching.enable_llm_assessment}")
    logger.info(f"  - Website Scraping: {config.capability_matching.enable_website_scraping}")
    logger.info(f"  - LLM Model: {config.capability_matching.llm_model}")
    logger.info(f"  - Target Relevant Vendors: {config.enrichment.target_relevant_vendors}")
    logger.info(f"\nEnrichment Chain:")
    logger.info(f"  - Website Search (DDG/Serper): {config.enrichment.enable_website_search}")
    logger.info(f"  - Contact Scraping (3-level): {config.enrichment.enable_contact_scraping}")
    logger.info(f"  - Targeted Serper Fallback: {config.enrichment.enable_targeted_serper_fallback}")
    logger.info(f"  - Relevance Threshold: {config.enrichment.relevance_score_threshold}")
    
    # Initialize pipeline
    start_time = time.time()
    logger.info("\n[1/7] Initializing pipeline...")
    pipeline = TenderVendorPipeline(config=config)
    init_time = time.time() - start_time
    logger.info(f"✓ Pipeline initialized in {init_time:.2f}s")
    
    # Tender files (use main RFP and PWS)
    tender_files = [
        Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf"),
        Path("data/DHS-wide+Uniforms+III+Contract/Attachment C - PWS UMC.pdf"),
    ]
    
    # Verify files exist
    for file in tender_files:
        if not file.exists():
            logger.error(f"File not found: {file}")
            return
        logger.info(f"  - {file.name} ({file.stat().st_size / 1024:.1f} KB)")
    
    # Run pipeline with timing for each stage
    logger.info("\n[2/7] Parsing documents...")
    stage_start = time.time()
    
    try:
        artifacts = pipeline.run(tender_files, disable_auto_ingestion=True)
        total_time = time.time() - start_time
        
        # Extract metrics
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE EXECUTION SUMMARY")
        logger.info("=" * 80)
        
        # Tender Profile
        logger.info(f"\n[Tender Profile]")
        profile = artifacts.tender_profile
        logger.info(f"  - Tender ID: {profile.tender_id}")
        logger.info(f"  - Country: {profile.country}")
        logger.info(f"  - Sections parsed: {len(artifacts.tender_sections)}")
        if profile.doc_extracted.structured.naics_codes:
            logger.info(f"  - NAICS codes: {profile.doc_extracted.structured.naics_codes}")
        if profile.doc_extracted.structured.location:
            loc = profile.doc_extracted.structured.location
            if loc.city or loc.state_province:
                logger.info(f"  - Location: {loc.city}, {loc.state_province}")
        
        # Vendor Discovery
        logger.info(f"\n[Vendor Discovery]")
        logger.info(f"  - Raw vendors discovered: {len(artifacts.raw_vendors)}")
        logger.info(f"  - Enriched vendors: {len(artifacts.enriched_vendors)}")
        logger.info(f"  - Filtered vendors: {len(artifacts.filtered_vendors)}")
        
        # Website Scraping Analysis
        logger.info(f"\n[Website Scraping Results]")
        scraped_count = 0
        success_count = 0
        failed_count = 0
        no_website_count = 0
        
        for vendor in artifacts.filtered_vendors:
            if "scrape_status" in vendor.filtering_metadata:
                scraped_count += 1
                if vendor.filtering_metadata["scrape_status"] == "success":
                    success_count += 1
                else:
                    failed_count += 1
            elif not vendor.website:
                no_website_count += 1
        
        logger.info(f"  - Vendors scraped: {scraped_count}/{len(artifacts.filtered_vendors)}")
        logger.info(f"  - Successful scrapes: {success_count}")
        logger.info(f"  - Failed scrapes: {failed_count}")
        logger.info(f"  - No website: {no_website_count}")
        
        if scraped_count > 0:
            logger.info(f"  - Success rate: {success_count/scraped_count*100:.1f}%")
        
        # Capability Matching
        logger.info(f"\n[Capability Matching - Stage 5]")
        logger.info(f"  - Total matches: {len(artifacts.final_matches)}")
        
        llm_assessed = 0
        rule_based = 0
        
        for match in artifacts.final_matches:
            if "website_content" in match.vendor.filtering_metadata:
                llm_assessed += 1
            else:
                rule_based += 1
        
        logger.info(f"  - LLM assessed: {llm_assessed}")
        logger.info(f"  - Rule-based: {rule_based}")
        
        # Top 5 vendors
        logger.info(f"\n[Top 5 Vendor Matches]")
        for i, match in enumerate(artifacts.final_matches[:5], 1):
            logger.info(f"\n  {i}. {match.vendor.company_name}")
            logger.info(f"     Score: {match.capability_match_score:.1f}")
            logger.info(f"     Location: {match.vendor.location}")
            logger.info(f"     Website: {match.vendor.website or 'N/A'}")
            logger.info(f"     Rationale: {match.rationale[:150]}...")
            if match.references:
                logger.info(f"     References: {', '.join(match.references[:2])}")
        
        # Performance Metrics
        logger.info(f"\n[Performance Metrics]")
        logger.info(f"  - Total execution time: {total_time:.2f}s")
        logger.info(f"  - Initialization: {init_time:.2f}s")
        logger.info(f"  - Pipeline execution: {total_time - init_time:.2f}s")
        
        # Filtering Metrics
        if artifacts.filtering_metrics:
            logger.info(f"\n[Filtering Metrics]")
            metrics = artifacts.filtering_metrics
            logger.info(f"  - total_input: {metrics.total_input}")
            logger.info(f"  - duplicates_removed: {metrics.duplicates_removed}")
            logger.info(f"  - geo_filtered: {metrics.geo_filtered}")
            logger.info(f"  - eligibility_filtered: {metrics.eligibility_filtered}")
            logger.info(f"  - final_count: {metrics.final_count}")
        
        # Save detailed results
        output_dir = Path("output_test/phase1_e2e")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save vendor matches
        pipeline.save_outputs(
            artifacts.final_matches,
            base_name="dhs_uniforms_stage5",
            directory=output_dir
        )
        
        # Save detailed analysis
        analysis = {
            "tender": {
                "id": profile.tender_id,
                "country": profile.country,
                "sections": len(artifacts.tender_sections),
                "naics": profile.doc_extracted.structured.naics_codes,
                "location": {
                    "city": profile.doc_extracted.structured.location.city,
                    "state": profile.doc_extracted.structured.location.state_province,
                } if profile.doc_extracted.structured.location else None,
            },
            "vendors": {
                "discovered": len(artifacts.raw_vendors),
                "enriched": len(artifacts.enriched_vendors),
                "filtered": len(artifacts.filtered_vendors),
                "final_matches": len(artifacts.final_matches),
            },
            "scraping": {
                "attempted": scraped_count,
                "successful": success_count,
                "failed": failed_count,
                "no_website": no_website_count,
                "success_rate": f"{success_count/scraped_count*100:.1f}%" if scraped_count > 0 else "N/A",
            },
            "capability_matching": {
                "llm_assessed": llm_assessed,
                "rule_based": rule_based,
            },
            "performance": {
                "total_time_seconds": round(total_time, 2),
                "init_time_seconds": round(init_time, 2),
                "pipeline_time_seconds": round(total_time - init_time, 2),
            },
            "filtering_metrics": {
                "total_input": artifacts.filtering_metrics.total_input,
                "duplicates_removed": artifacts.filtering_metrics.duplicates_removed,
                "geo_filtered": artifacts.filtering_metrics.geo_filtered,
                "eligibility_filtered": artifacts.filtering_metrics.eligibility_filtered,
                "final_count": artifacts.filtering_metrics.final_count,
            } if artifacts.filtering_metrics else None,
        }
        
        with open(output_dir / "analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"\n✓ Results saved to {output_dir}")
        logger.info(f"  - dhs_uniforms_stage5.csv")
        logger.info(f"  - dhs_uniforms_stage5.xlsx")
        logger.info(f"  - dhs_uniforms_stage5.json")
        logger.info(f"  - analysis.json")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n✗ Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    test_dhs_uniforms_stage5()
