#!/usr/bin/env python3
"""Integration test for multi-stage vendor filtering."""
import logging
import sys
from pathlib import Path

from vendor_ai_agent.config import FilteringConfig, RuntimeConfig
from vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    test_files = [
        "data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf",
    ]
    
    available_files = [f for f in test_files if Path(f).exists()]
    
    if not available_files:
        logger.error("No test files found. Looking for alternative files...")
        data_dir = Path("data")
        if data_dir.exists():
            pdf_files = list(data_dir.rglob("*.pdf"))
            if pdf_files:
                available_files = [str(pdf_files[0])]
                logger.info(f"Using alternative file: {available_files[0]}")
            else:
                logger.error("No PDF files found in data directory")
                return 1
        else:
            logger.error("Data directory not found")
            return 1
    
    logger.info("=" * 80)
    logger.info("TESTING MULTI-STAGE VENDOR FILTERING")
    logger.info("=" * 80)
    logger.info(f"Test files: {available_files}")
    
    config = RuntimeConfig()
    config.filtering = FilteringConfig(
        enable_duplicate_removal=True,
        enable_geographic=True,
        enable_local_first=True,
        enable_eligibility_checks=True,
        enable_set_aside_filtering=True,
        enable_size_heuristics=True,
        log_filtering_decisions=True,
        max_candidates=300,
        local_preference_boost=20.0,
        regional_preference_boost=10.0,
        national_expansion_threshold=50,
    )
    
    logger.info("\n" + "=" * 80)
    logger.info("FILTERING CONFIGURATION")
    logger.info("=" * 80)
    logger.info(f"Duplicate removal:      {config.filtering.enable_duplicate_removal}")
    logger.info(f"Geographic filtering:   {config.filtering.enable_geographic}")
    logger.info(f"Local-first strategy:   {config.filtering.enable_local_first}")
    logger.info(f"Eligibility checks:     {config.filtering.enable_eligibility_checks}")
    logger.info(f"Set-aside filtering:    {config.filtering.enable_set_aside_filtering}")
    logger.info(f"Size heuristics:        {config.filtering.enable_size_heuristics}")
    logger.info(f"Max candidates:         {config.filtering.max_candidates}")
    logger.info(f"Local boost:            {config.filtering.local_preference_boost}")
    logger.info(f"Regional boost:         {config.filtering.regional_preference_boost}")
    logger.info(f"Expansion threshold:    {config.filtering.national_expansion_threshold}")
    
    try:
        pipeline = TenderVendorPipeline(config=config)
        
        logger.info("\n" + "=" * 80)
        logger.info("RUNNING PIPELINE")
        logger.info("=" * 80)
        
        artifacts = pipeline.run(
            [Path(f) for f in available_files],
            disable_auto_ingestion=True,
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE RESULTS")
        logger.info("=" * 80)
        
        logger.info(f"\nTender Profile:")
        logger.info(f"  Country: {artifacts.tender_profile.country}")
        logger.info(f"  Tender ID: {artifacts.tender_profile.tender_id}")
        
        logger.info(f"\nVendor Counts:")
        logger.info(f"  Raw vendors (discovered):  {len(artifacts.raw_vendors)}")
        logger.info(f"  Enriched vendors:          {len(artifacts.enriched_vendors)}")
        logger.info(f"  Filtered vendors:          {len(artifacts.filtered_vendors)}")
        logger.info(f"  Final matches:             {len(artifacts.final_matches)}")
        
        if artifacts.filtering_metrics:
            metrics = artifacts.filtering_metrics
            logger.info("\n" + "=" * 80)
            logger.info("FILTERING METRICS DETAILED")
            logger.info("=" * 80)
            logger.info(f"Total input:               {metrics.total_input}")
            logger.info(f"Duplicates removed:        {metrics.duplicates_removed}")
            logger.info(f"Geographic filtered:       {metrics.geo_filtered}")
            logger.info(f"  - Local vendors:         {metrics.local_vendors}")
            logger.info(f"  - National vendors:      {metrics.national_vendors}")
            logger.info(f"Eligibility filtered:      {metrics.eligibility_filtered}")
            
            if metrics.filter_reasons:
                logger.info(f"\nFilter reasons breakdown:")
                for reason, count in sorted(metrics.filter_reasons.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"  - {reason}: {count}")
            
            logger.info(f"\nFinal count:               {metrics.final_count}")
            total_filtered = metrics.total_input - metrics.final_count
            logger.info(f"Total filtered out:        {total_filtered}")
            if metrics.total_input > 0:
                percentage = (total_filtered / metrics.total_input) * 100
                logger.info(f"Filtering rate:            {percentage:.1f}%")
        else:
            logger.warning("No filtering metrics available!")
        
        if artifacts.filtered_vendors:
            logger.info("\n" + "=" * 80)
            logger.info("TOP 10 FILTERED VENDORS")
            logger.info("=" * 80)
            for i, vendor in enumerate(artifacts.filtered_vendors[:10], 1):
                location = f"{vendor.city}, {vendor.state}" if vendor.city and vendor.state else vendor.state or vendor.country or "Unknown"
                logger.info(f"{i}. {vendor.company_name}")
                logger.info(f"   Location: {location}")
                logger.info(f"   Geo Score: {vendor.geo_score:.1f}")
                logger.info(f"   Preliminary Score: {vendor.preliminary_score:.1f}")
                logger.info(f"   Total Score: {vendor.geo_score + vendor.preliminary_score:.1f}")
                logger.info(f"   Source: {vendor.source}")
                if vendor.total_contract_value:
                    logger.info(f"   Contract Value: ${vendor.total_contract_value:,.0f}")
                if vendor.contract_count:
                    logger.info(f"   Contract Count: {vendor.contract_count}")
                logger.info("")
        
        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        return 0
        
    except Exception as e:
        logger.error(f"\n{'='*80}")
        logger.error("TEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
