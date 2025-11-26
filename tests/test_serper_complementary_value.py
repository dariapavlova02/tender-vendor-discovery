#!/usr/bin/env python3
"""
Test: Serper Complementary Value Analysis for DHS Uniforms Tender

Hypothesis: Serper discovery can add unique, relevant vendors that 
complement database sources (SAM Entity, Canada Contracts).

Test Case: DHS Uniforms III Contract
- Sector: Apparel/Uniforms (NAICS 315210)
- Location: Glynco, GA (USA)
- SAM baseline: 2000 vendors → 500 filtered → 18 scored ≥60

Questions:
1. How many Serper vendors pass filtering? (vs SAM 25% pass rate)
2. What's the overlap with SAM vendors?
3. Do Serper vendors score competitively?
4. What's the incremental value (unique high-scoring vendors)?

Expected cost: 10 queries × $0.005 = $0.05
Expected time: ~5-10 minutes
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.enrichment_providers.serper_client import SerperClient
from vendor_ai_agent.models import (
    TenderProfile, 
    VendorRecord, 
    Address,
    DocExtracted,
    StructuredDocData,
    DynamicTenderContext
)
from vendor_ai_agent.pipeline import TenderVendorPipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


IGNORE_DOMAINS = {
    'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'youtube.com', 'indeed.com', 'glassdoor.com', 'monster.com',
    'wikipedia.org', 'merx.com', 'buyandsell.gc.ca', 'sam.gov',
    'amazon.com', 'ebay.com', 'alibaba.com', 'thomasnet.com',
    'reddit.com', 'quora.com', 'pinterest.com'
}


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""


def should_filter_domain(domain: str) -> bool:
    return any(ignored in domain for ignored in IGNORE_DOMAINS)


def extract_company_name(title: str) -> str:
    common_suffixes = [
        ' - Home', ' | Home', ' - Official Site', ' | Official Site',
        ' - Wikipedia', ' | About Us', ' - Company Profile',
        ' - Contact', ' | Contact', ' - Products', ' | Products'
    ]
    
    cleaned = title
    for suffix in common_suffixes:
        if suffix.lower() in cleaned.lower():
            cleaned = cleaned[:cleaned.lower().index(suffix.lower())]
    
    return cleaned.strip() or title


def normalize_domain(website: Optional[str]) -> str:
    if not website:
        return ""
    domain = extract_domain(website)
    return domain.lower().replace("www.", "")


def phase1_serper_discovery() -> List[VendorRecord]:
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: SERPER DISCOVERY")
    logger.info("=" * 80)
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.error("SERPER_API_KEY not found in environment")
        return []
    
    queries = [
        "law enforcement uniforms manufacturer Georgia USA",
        "tactical apparel supplier manufacturer USA",
        "government uniforms contractor Georgia",
        "police uniforms manufacturer United States",
        "DHS uniforms supplier Georgia",
        "federal uniforms contractor USA",
        "tactical clothing manufacturer Georgia",
        "uniform cut and sew manufacturer USA",
        "law enforcement apparel supplier Georgia",
        "government tactical gear manufacturer USA"
    ]
    
    serper_client = SerperClient(api_key=api_key)
    
    all_vendors = []
    seen_domains = set()
    
    for idx, query in enumerate(queries, 1):
        logger.info(f"\n[Query {idx}/{len(queries)}] {query}")
        
        try:
            response = serper_client.discovery_search(query, num_results=10)
            results = response.get("organic", [])
            
            logger.info(f"  Received {len(results)} results")
            
            query_vendors = 0
            for result in results:
                link = result.get("link", "")
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                
                if not link or not title:
                    continue
                
                domain = extract_domain(link)
                
                if should_filter_domain(domain):
                    logger.debug(f"  Filtered: {domain} (ignored domain)")
                    continue
                
                if domain in seen_domains:
                    logger.debug(f"  Filtered: {domain} (duplicate)")
                    continue
                
                seen_domains.add(domain)
                
                company_name = extract_company_name(title)
                
                vendor = VendorRecord(
                    company_name=company_name,
                    website=link,
                    source="serper_discovery"
                )
                
                # Store Serper metadata in filtering_metadata for caching
                vendor.filtering_metadata["serper_snippet"] = snippet
                vendor.filtering_metadata["serper_position"] = result.get("position", 0)
                vendor.filtering_metadata["serper_query"] = query
                
                all_vendors.append(vendor)
                query_vendors += 1
                logger.debug(f"  Added: {company_name} ({domain})")
            
            logger.info(f"  Added {query_vendors} unique vendors")
            
            if idx < len(queries):
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"  Query failed: {e}")
            continue
    
    output_dir = Path("output_test/serper_value")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "serper_raw_vendors.json", "w") as f:
        json.dump([{
            "company_name": v.company_name,
            "website": v.website,
            "source": v.source,
            "filtering_metadata": v.filtering_metadata
        } for v in all_vendors], f, indent=2)
    
    logger.info(f"\n✓ Collected {len(all_vendors)} unique vendors from Serper")
    logger.info(f"✓ Saved to output_test/serper_value/serper_raw_vendors.json")
    
    return all_vendors


def load_dhs_tender_profile() -> TenderProfile:
    return TenderProfile(
        tender_id="DHS_UNIFORMS_III",
        country="USA",
        doc_extracted=DocExtracted(
            structured=StructuredDocData(
                naics_codes=["315210"],
                location=Address(
                    city="Glynco",
                    state_province="GA",
                    country="USA"
                )
            )
        ),
        dynamic_context=DynamicTenderContext(
            sector="Apparel Manufacturing",
            search_terms=[
                "law enforcement uniforms manufacturer USA",
                "tactical apparel supplier Georgia",
                "government uniforms contractor"
            ],
            technical_keywords=[
                "cut and sew",
                "uniform manufacturing",
                "tactical gear"
            ]
        )
    )


def phase2_pipeline_processing(serper_vendors: List[VendorRecord]) -> Dict:
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: PIPELINE PROCESSING")
    logger.info("=" * 80)
    
    config = RuntimeConfig()
    pipeline = TenderVendorPipeline(config)
    
    profile = load_dhs_tender_profile()
    
    logger.info(f"\n[Stage 1: Filtering]")
    logger.info(f"  Input vendors: {len(serper_vendors)}")
    
    filtered_vendors = pipeline.context.vendor_filter.filter(
        profile, 
        serper_vendors
    )
    
    filtering_metrics = pipeline.context.vendor_filter.get_metrics()
    
    logger.info(f"  Duplicates removed: {filtering_metrics.duplicates_removed}")
    logger.info(f"  Geo filtered: {filtering_metrics.geo_filtered}")
    logger.info(f"  Eligibility filtered: {filtering_metrics.eligibility_filtered}")
    logger.info(f"  Final count: {len(filtered_vendors)}")
    logger.info(f"  Pass rate: {len(filtered_vendors)/len(serper_vendors)*100:.1f}%")
    
    logger.info(f"\n[Stage 2: Enrichment]")
    logger.info(f"  Starting enrichment for {len(filtered_vendors)} vendors...")
    
    enriched_vendors = pipeline.context.vendor_enricher.enrich(filtered_vendors)
    
    scrape_success = sum(
        1 for v in enriched_vendors 
        if "website_content" in v.filtering_metadata
    )
    
    logger.info(f"  Vendors enriched: {len(enriched_vendors)}")
    logger.info(f"  Website scraping success: {scrape_success}/{len(enriched_vendors)}")
    if enriched_vendors:
        logger.info(f"  Scrape rate: {scrape_success/len(enriched_vendors)*100:.1f}%")
    
    logger.info(f"\n[Stage 3: Scoring]")
    logger.info(f"  Starting capability matching for {len(enriched_vendors)} vendors...")
    
    matches = pipeline.context.capability_matcher.score(
        profile,
        enriched_vendors
    )
    
    high_scoring = [m for m in matches if m.capability_match_score >= 60]
    medium_scoring = [m for m in matches if 40 <= m.capability_match_score < 60]
    
    logger.info(f"  Total scored: {len(matches)}")
    logger.info(f"  High scoring (≥60): {len(high_scoring)}")
    logger.info(f"  Medium scoring (40-59): {len(medium_scoring)}")
    if matches:
        logger.info(f"  Quality rate: {len(high_scoring)/len(matches)*100:.1f}%")
    
    if high_scoring:
        logger.info(f"\n[Top 5 High-Scoring Vendors]")
        for i, match in enumerate(sorted(high_scoring, key=lambda m: m.capability_match_score, reverse=True)[:5], 1):
            logger.info(f"  {i}. {match.vendor.company_name}")
            logger.info(f"     Score: {match.capability_match_score:.1f}")
            logger.info(f"     Website: {match.vendor.website}")
            logger.info(f"     Rationale: {match.rationale[:150]}...")
    
    output_dir = Path("output_test/serper_value")
    
    with open(output_dir / "serper_filtered_vendors.json", "w") as f:
        json.dump([{
            "company_name": v.company_name,
            "website": v.website,
            "location": v.location,
            "source": v.source
        } for v in filtered_vendors], f, indent=2)
    
    with open(output_dir / "serper_scored_matches.json", "w") as f:
        json.dump([{
            "company_name": m.vendor.company_name,
            "website": m.vendor.website,
            "location": m.vendor.location,
            "score": m.capability_match_score,
            "rationale": m.rationale
        } for m in matches], f, indent=2)
    
    logger.info(f"\n✓ Saved filtered vendors to output_test/serper_value/serper_filtered_vendors.json")
    logger.info(f"✓ Saved scored matches to output_test/serper_value/serper_scored_matches.json")
    
    return {
        "raw_count": len(serper_vendors),
        "filtered_count": len(filtered_vendors),
        "enriched_count": len(enriched_vendors),
        "scored_count": len(matches),
        "high_scoring_count": len(high_scoring),
        "medium_scoring_count": len(medium_scoring),
        "pass_rate": len(filtered_vendors)/len(serper_vendors) if serper_vendors else 0,
        "quality_rate": len(high_scoring)/len(matches) if matches else 0,
        "filtering_metrics": {
            "total_input": filtering_metrics.total_input,
            "duplicates_removed": filtering_metrics.duplicates_removed,
            "geo_filtered": filtering_metrics.geo_filtered,
            "eligibility_filtered": filtering_metrics.eligibility_filtered,
            "final_count": filtering_metrics.final_count
        },
        "matches": matches,
        "high_scoring_matches": high_scoring
    }


def phase3_comparison_analysis(serper_results: Dict) -> Dict:
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: COMPARISON ANALYSIS")
    logger.info("=" * 80)
    
    sam_baseline_path = Path("output_test/phase1_e2e/dhs_uniforms_stage5.json")
    
    if not sam_baseline_path.exists():
        logger.warning(f"SAM baseline not found at {sam_baseline_path}")
        logger.warning("Skipping overlap analysis")
        return {}
    
    with open(sam_baseline_path) as f:
        sam_matches = json.load(f)
    
    sam_websites = {
        normalize_domain(m.get("website")) 
        for m in sam_matches 
        if m.get("website")
    }
    
    serper_matches = serper_results["matches"]
    serper_websites = {
        normalize_domain(m.vendor.website)
        for m in serper_matches
        if m.vendor.website
    }
    
    overlap = sam_websites & serper_websites
    serper_unique = serper_websites - sam_websites
    
    sam_high_scoring = [m for m in sam_matches if m.get("capability_match_score", 0) >= 60]
    serper_high_scoring = serper_results["high_scoring_matches"]
    
    serper_unique_high_scoring = [
        m for m in serper_high_scoring
        if normalize_domain(m.vendor.website) in serper_unique
    ]
    
    analysis = {
        "sam_baseline": {
            "total_discovered": 2000,
            "filtered": 500,
            "high_scoring": len(sam_high_scoring),
            "pass_rate": 0.25,
            "quality_rate": len(sam_high_scoring) / 500 if sam_high_scoring else 0
        },
        "serper_discovery": {
            "total_discovered": serper_results["raw_count"],
            "filtered": serper_results["filtered_count"],
            "high_scoring": serper_results["high_scoring_count"],
            "pass_rate": serper_results["pass_rate"],
            "quality_rate": serper_results["quality_rate"]
        },
        "overlap_analysis": {
            "total_overlap": len(overlap),
            "overlap_rate": len(overlap) / len(serper_websites) if serper_websites else 0,
            "serper_unique_vendors": len(serper_unique),
            "serper_unique_high_scoring": len(serper_unique_high_scoring)
        },
        "incremental_value": {
            "description": "Unique high-quality vendors from Serper not in SAM",
            "count": len(serper_unique_high_scoring),
            "percentage_of_sam_high_scoring": (
                len(serper_unique_high_scoring) / len(sam_high_scoring) * 100
                if sam_high_scoring else 0
            ),
            "vendors": [
                {
                    "company_name": m.vendor.company_name,
                    "website": m.vendor.website,
                    "score": m.capability_match_score,
                    "rationale": m.rationale[:200]
                }
                for m in serper_unique_high_scoring
            ]
        }
    }
    
    logger.info("\n[Source Comparison]")
    logger.info(f"  SAM Entity:")
    logger.info(f"    Discovered: 2000 → Filtered: 500 (25% pass) → High scoring: {len(sam_high_scoring)}")
    logger.info(f"  Serper Discovery:")
    logger.info(f"    Discovered: {serper_results['raw_count']} → Filtered: {serper_results['filtered_count']} ({serper_results['pass_rate']*100:.1f}% pass) → High scoring: {serper_results['high_scoring_count']}")
    
    logger.info(f"\n[Overlap Analysis]")
    logger.info(f"  Total Serper websites: {len(serper_websites)}")
    logger.info(f"  Overlap with SAM: {len(overlap)} vendors ({len(overlap)/len(serper_websites)*100 if serper_websites else 0:.1f}%)")
    logger.info(f"  Serper unique: {len(serper_unique)} vendors")
    logger.info(f"  Serper unique high-scoring: {len(serper_unique_high_scoring)} vendors")
    
    logger.info(f"\n[Incremental Value]")
    logger.info(f"  SAM high-scoring vendors: {len(sam_high_scoring)}")
    logger.info(f"  Serper adds unique high-scoring: {len(serper_unique_high_scoring)}")
    if sam_high_scoring:
        logger.info(f"  Incremental contribution: {len(serper_unique_high_scoring)/len(sam_high_scoring)*100:.1f}%")
    
    if serper_unique_high_scoring:
        logger.info(f"\n[Unique High-Scoring Vendors from Serper]")
        for i, vendor_data in enumerate(analysis["incremental_value"]["vendors"], 1):
            logger.info(f"  {i}. {vendor_data['company_name']}")
            logger.info(f"     Score: {vendor_data['score']:.1f}")
            logger.info(f"     Website: {vendor_data['website']}")
            logger.info(f"     Rationale: {vendor_data['rationale']}...")
    
    cost = 10 * 0.005
    logger.info(f"\n[Cost-Benefit Analysis]")
    logger.info(f"  Serper API cost: ${cost:.2f} (10 queries)")
    if serper_unique_high_scoring:
        logger.info(f"  Cost per unique high-quality vendor: ${cost/len(serper_unique_high_scoring):.3f}")
    
    if len(serper_unique_high_scoring) >= 3:
        logger.info(f"\n✅ RECOMMENDATION: Enable Serper complement")
        logger.info(f"   Serper adds {len(serper_unique_high_scoring)} unique high-quality vendors (+{len(serper_unique_high_scoring)/len(sam_high_scoring)*100:.1f}%)")
        logger.info(f"   Cost-effective at ${cost/len(serper_unique_high_scoring):.3f} per vendor")
    else:
        logger.info(f"\n❌ RECOMMENDATION: Skip Serper for US tenders")
        logger.info(f"   Serper only adds {len(serper_unique_high_scoring)} unique vendors (minimal value)")
        logger.info(f"   SAM Entity provides sufficient coverage")
    
    with open("output_test/serper_value/comparison_analysis.json", "w") as f:
        json.dump({
            k: v for k, v in analysis.items() 
            if k != "incremental_value" or not isinstance(v, dict) or "vendors" not in v
        } | {
            "incremental_value": {
                k: v for k, v in analysis["incremental_value"].items() 
                if k != "vendors"
            } | {
                "vendors": [
                    {
                        "company_name": v["company_name"],
                        "website": v["website"],
                        "score": v["score"]
                    }
                    for v in analysis["incremental_value"]["vendors"]
                ]
            }
        }, f, indent=2)
    
    logger.info(f"\n✓ Saved analysis to output_test/serper_value/comparison_analysis.json")
    
    return analysis


def run_full_test():
    logger.info("=" * 80)
    logger.info("SERPER COMPLEMENTARY VALUE TEST - DHS UNIFORMS TENDER")
    logger.info("=" * 80)
    logger.info("\nGoal: Measure incremental value of Serper discovery vs SAM Entity")
    logger.info("Expected cost: $0.05 (10 queries)")
    logger.info("Expected time: 5-10 minutes")
    
    start_time = time.time()
    
    serper_vendors = phase1_serper_discovery()
    
    if not serper_vendors:
        logger.error("No vendors collected from Serper, aborting test")
        return
    
    serper_results = phase2_pipeline_processing(serper_vendors)
    
    analysis = phase3_comparison_analysis(serper_results)
    
    total_time = time.time() - start_time
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    logger.info(f"Results saved to: output_test/serper_value/")
    logger.info("  - serper_raw_vendors.json")
    logger.info("  - serper_filtered_vendors.json")
    logger.info("  - serper_scored_matches.json")
    logger.info("  - comparison_analysis.json")


if __name__ == "__main__":
    run_full_test()
