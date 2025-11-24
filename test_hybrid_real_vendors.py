"""Test hybrid enrichment on real vendors from database."""

import asyncio
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_on_real_vendors():
    """Test hybrid enrichment on real vendors without websites."""
    from src.vendor_ai_agent.config import RuntimeConfig
    from src.vendor_ai_agent.database.models import Vendor
    from src.vendor_ai_agent.enrichment_providers import HybridWebsiteEnricher
    
    cfg = RuntimeConfig()
    
    if not cfg.serper_api_key:
        logger.error("❌ SERPER_API_KEY not set")
        return
    
    engine = create_engine(cfg.database.url)
    
    with Session(engine) as session:
        stmt = (
            select(Vendor)
            .where(Vendor.website == None)
            .where(Vendor.country == "Canada")
            .limit(10)
        )
        
        vendors = session.execute(stmt).scalars().all()
        
        if not vendors:
            logger.warning("No vendors without websites found!")
            return
        
        logger.info(f"Found {len(vendors)} vendors without websites")
        
        enricher = HybridWebsiteEnricher(
            serper_api_key=cfg.serper_api_key,
            enable_ddg=cfg.enrichment.enable_ddg_search,
            enable_serper_fallback=cfg.enrichment.enable_serper_fallback,
            min_confidence=cfg.enrichment.website_search_min_confidence
        )
        
        logger.info(f"\n{'='*80}")
        logger.info("TESTING ON REAL VENDORS FROM DATABASE")
        logger.info(f"{'='*80}\n")
        
        results = []
        for i, vendor in enumerate(vendors, 1):
            logger.info(f"\n[{i}/{len(vendors)}] Testing: {vendor.legal_name}")
            logger.info(f"  UEI: {vendor.uei}")
            logger.info(f"  Location: {vendor.city}, {vendor.state}, {vendor.country}")
            logger.info(f"  Initial website: {vendor.website or '(none)'}")
            
            try:
                enriched = enricher.enrich(vendor)
                
                logger.info(f"\n  ✅ Enrichment complete:")
                logger.info(f"    Website: {enriched.website or '(none)'}")
                logger.info(f"    Email: {enriched.primary_email or '(none)'}")
                logger.info(f"    Phone: {enriched.primary_phone or '(none)'}")
                
                results.append({
                    'uei': vendor.uei,
                    'name': vendor.legal_name,
                    'website_found': bool(enriched.website),
                    'email_found': bool(enriched.primary_email),
                    'phone_found': bool(enriched.primary_phone),
                    'website': enriched.website,
                    'email': enriched.primary_email,
                    'phone': enriched.primary_phone,
                })
                
            except Exception as exc:
                logger.error(f"  ❌ Error enriching {vendor.legal_name}: {exc}")
                results.append({
                    'uei': vendor.uei,
                    'name': vendor.legal_name,
                    'website_found': False,
                    'email_found': False,
                    'phone_found': False,
                    'error': str(exc)
                })
        
        logger.info(f"\n{'='*80}")
        logger.info("SUMMARY")
        logger.info(f"{'='*80}\n")
        
        total = len(results)
        websites_found = sum(1 for r in results if r.get('website_found', False))
        emails_found = sum(1 for r in results if r.get('email_found', False))
        phones_found = sum(1 for r in results if r.get('phone_found', False))
        errors = sum(1 for r in results if 'error' in r)
        
        logger.info(f"Total vendors: {total}")
        logger.info(f"Websites found: {websites_found}/{total} ({websites_found/total*100:.1f}%)")
        logger.info(f"Emails found: {emails_found}/{total} ({emails_found/total*100:.1f}%)")
        logger.info(f"Phones found: {phones_found}/{total} ({phones_found/total*100:.1f}%)")
        logger.info(f"Errors: {errors}/{total}")
        
        logger.info("\nDetailed results:")
        for r in results:
            if 'error' in r:
                logger.info(f"❌ {r['name']}: ERROR - {r['error']}")
            else:
                status = "✅" if r['website_found'] else "❌"
                logger.info(f"{status} {r['name']}")
                if r['website_found']:
                    logger.info(f"   Website: {r['website']}")
                    if r['email_found']:
                        logger.info(f"   Email: {r['email']}")
                    if r['phone_found']:
                        logger.info(f"   Phone: {r['phone']}")
        
        logger.info(f"\n{'='*80}")
        logger.info("COST ESTIMATE")
        logger.info(f"{'='*80}\n")
        
        serper_calls = total - errors
        cost_per_call = 0.01
        total_cost = serper_calls * cost_per_call
        
        logger.info(f"Serper API calls: {serper_calls}")
        logger.info(f"Cost per call: ${cost_per_call:.2f}")
        logger.info(f"Total cost: ${total_cost:.2f}")
        
        logger.info(f"\n{'='*80}\n")
        
        if websites_found / total >= 0.5:
            logger.info("✅ Test PASSED - >50% success rate, ready for production!")
        else:
            logger.warning("⚠️  Test WARNING - <50% success rate, review results")


if __name__ == "__main__":
    asyncio.run(test_on_real_vendors())
