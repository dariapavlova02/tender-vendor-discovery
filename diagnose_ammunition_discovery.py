#!/usr/bin/env python3
"""Diagnose vendor discovery issue for ammunition tender."""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider
from src.vendor_ai_agent.database.connection import get_session
from src.vendor_ai_agent.sources.canada_contracts import CanadaContractsSource

cfg = RuntimeConfig()
llm = OpenAIProvider(default_model=cfg.llm.cheap_model, use_flex_tier=cfg.llm.use_flex_tier)
parser = DocumentParser()
extractor = RequirementExtractor(llm_provider=llm)

tender_path = Path('data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/')

logger.info("="*80)
logger.info("STEP 1: Parse tender documents")
logger.info("="*80)
sections = parser.parse([tender_path])
logger.info(f"Parsed {len(sections)} sections")

logger.info("\n" + "="*80)
logger.info("STEP 2: Extract tender profile")
logger.info("="*80)
profile = extractor.extract(sections)

logger.info(f"Project type: {profile.doc_extracted.structured.project_type}")
logger.info(f"Sector: {profile.doc_extracted.structured.sector}")
logger.info(f"Reference: {profile.doc_extracted.structured.reference_number}")

logger.info("\n" + "="*80)
logger.info("STEP 3: Check dynamic context")
logger.info("="*80)
dc = profile.dynamic_context
logger.info(f"Sector: {dc.sector}")
logger.info(f"Country: {dc.country}")
logger.info(f"Province: {dc.province}")
logger.info(f"GSIN codes: {dc.gsin_codes}")
logger.info(f"UNSPSC codes: {dc.unspsc_codes}")
logger.info(f"Technical keywords ({len(dc.technical_keywords)}): {dc.technical_keywords[:10]}")
logger.info(f"Search terms ({len(dc.search_terms)}): {dc.search_terms}")

logger.info("\n" + "="*80)
logger.info("STEP 4: Test vendor discovery with different filters")
logger.info("="*80)

with get_session() as session:
    source = CanadaContractsSource(session)
    
    # Test 1: With all filters
    logger.info("\nTest 1: Full filters (GSIN + UNSPSC + keywords + province)")
    vendors1 = source.search_vendors(
        gsin_codes=dc.gsin_codes if dc.gsin_codes else None,
        unspsc_codes=dc.unspsc_codes if dc.unspsc_codes else None,
        keywords=dc.technical_keywords[:5] if dc.technical_keywords else None,
        province=dc.province,
        limit=50
    )
    logger.info(f"  Found: {len(vendors1)} vendors")
    
    # Test 2: Keywords only
    logger.info("\nTest 2: Keywords only (top 5)")
    vendors2 = source.search_vendors(
        keywords=dc.technical_keywords[:5] if dc.technical_keywords else None,
        limit=50
    )
    logger.info(f"  Found: {len(vendors2)} vendors")
    if dc.technical_keywords:
        logger.info(f"  Keywords used: {dc.technical_keywords[:5]}")
    
    # Test 3: Keywords only (top 10)
    logger.info("\nTest 3: Keywords only (top 10)")
    vendors3 = source.search_vendors(
        keywords=dc.technical_keywords[:10] if dc.technical_keywords else None,
        limit=50
    )
    logger.info(f"  Found: {len(vendors3)} vendors")
    
    # Test 4: Province only
    if dc.province:
        logger.info(f"\nTest 4: Province only ({dc.province})")
        vendors4 = source.search_vendors(
            province=dc.province,
            limit=100
        )
        logger.info(f"  Found: {len(vendors4)} vendors")
    
    # Test 5: Ammunition-specific keywords
    logger.info("\nTest 5: Manual ammunition keywords")
    ammo_keywords = ["ammunition", "ammo", "munitions", "bullets", "cartridges"]
    vendors5 = source.search_vendors(
        keywords=ammo_keywords,
        province="Ontario",
        limit=100
    )
    logger.info(f"  Found: {len(vendors5)} vendors")
    logger.info(f"  Keywords: {ammo_keywords}")
    
    if vendors5:
        logger.info("\n  Sample vendors:")
        for v in vendors5[:5]:
            logger.info(f"    - {v.legal_name} ({v.city}, {v.state})")
            if v.total_contract_value:
                logger.info(f"      Contract value: ${v.total_contract_value:,.0f}")

logger.info("\n" + "="*80)
logger.info("DIAGNOSIS SUMMARY")
logger.info("="*80)
logger.info("Problem: Vendor discovery returns too few vendors (15 instead of hundreds)")
logger.info("Root causes:")
logger.info("1. GSIN/UNSPSC codes may not be in document → filters too restrictive")
logger.info("2. Keywords may be too specific → no matches")
logger.info("3. Limit hardcoded to 50 in source (line 316)")
logger.info("\nRecommended fixes:")
logger.info("1. Increase limit from 50 to 500+ in CanadaContractsSource")
logger.info("2. Make GSIN/UNSPSC optional, fall back to keywords")
logger.info("3. Broaden keyword matching (partial matches, synonyms)")
logger.info("4. Add sector-based fallback (if keywords fail, use sector)")
