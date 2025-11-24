"""Test hybrid enrichment with realistic vendor data (no database required)."""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockVendor:
    """Mock vendor object matching VendorRecord schema."""
    def __init__(self, company_name, city, state, country, uei=None):
        self.company_name = company_name
        self.city = city
        self.state = state
        self.country = country
        self.uei = uei
        self.website = None
        self.email = None
        self.phone = None
        self.enrichment_flags = []
        self.filtering_metadata = {}


async def test_realistic_vendors():
    """Test 3-level contact fallback with realistic vendor data."""
    from src.vendor_ai_agent.config import RuntimeConfig
    from src.vendor_ai_agent.enrichment_providers import HybridWebsiteEnricher, ContactScrapingProvider
    from src.vendor_ai_agent.enrichment_providers.serper_client import SerperClient
    from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider
    
    cfg = RuntimeConfig()
    
    if not cfg.serper_api_key:
        logger.error("❌ SERPER_API_KEY not set")
        return
    
    llm_provider = OpenAIProvider(
        default_model=cfg.llm.cheap_model,
        use_flex_tier=cfg.llm.use_flex_tier
    )
    
    # Real Canadian companies that likely don't have websites in mock database
    vendors = [
        MockVendor("Canadian Tire Corporation", "Toronto", "Ontario", "CA", "CAN123456"),
        MockVendor("Loblaw Companies Limited", "Brampton", "Ontario", "CA", "CAN789012"),
        MockVendor("Metro Inc", "Montreal", "Quebec", "CA", "CAN345678"),
        MockVendor("Sobeys Inc", "Stellarton", "Nova Scotia", "CA", "CAN901234"),
        MockVendor("Empire Company Limited", "Stellarton", "Nova Scotia", "CA", "CAN567890"),
        MockVendor("Tim Hortons", "Toronto", "Ontario", "CA", "CAN234567"),
        MockVendor("Hudson's Bay Company", "Toronto", "Ontario", "CA", "CAN890123"),
        MockVendor("Bombardier Inc", "Montreal", "Quebec", "CA", "CAN456789"),
        MockVendor("Magna International", "Aurora", "Ontario", "CA", "CAN012345"),
        MockVendor("CGI Group Inc", "Montreal", "Quebec", "CA", "CAN678901"),
    ]
    
    logger.info(f"Testing {len(vendors)} realistic Canadian vendors")
    
    website_enricher = HybridWebsiteEnricher(
        serper_api_key=cfg.serper_api_key,
        enable_ddg=cfg.enrichment.enable_ddg_search,
        enable_serper_fallback=cfg.enrichment.enable_serper_fallback,
        min_confidence=cfg.enrichment.website_search_min_confidence
    )
    
    serper_client = SerperClient(api_key=cfg.serper_api_key, timeout=10)
    
    contact_scraper = ContactScrapingProvider(
        llm_provider=llm_provider,
        scraper_timeout=cfg.enrichment.scraper_timeout_seconds,
        enable_llm_fallback=cfg.enrichment.enable_llm_fallback,
        serper_client=serper_client,
        enable_targeted_serper=cfg.enrichment.enable_targeted_serper_fallback
    )
    
    logger.info(f"\n{'='*80}")
    logger.info("TESTING 3-LEVEL CONTACT FALLBACK WITH REALISTIC DATA")
    logger.info(f"{'='*80}\n")
    
    results = []
    for i, vendor in enumerate(vendors, 1):
        logger.info(f"\n[{i}/{len(vendors)}] Testing: {vendor.company_name}")
        logger.info(f"  UEI: {vendor.uei}")
        logger.info(f"  Location: {vendor.city}, {vendor.state}, {vendor.country}")
        logger.info(f"  Initial website: {vendor.website or '(none)'}")
        
        try:
            enriched = website_enricher.enrich(vendor)
            
            if enriched.website:
                logger.info(f"\n  ✅ Website found: {enriched.website}")
                enriched = contact_scraper.enrich(enriched)
            
            logger.info(f"\n  ✅ Enrichment complete:")
            logger.info(f"    Website: {enriched.website or '(none)'}")
            logger.info(f"    Email: {enriched.email or '(none)'} (source: {enriched.filtering_metadata.get('email_source', 'none')})")
            logger.info(f"    Phone: {enriched.phone or '(none)'} (source: {enriched.filtering_metadata.get('phone_source', 'none')})")
            
            results.append({
                'uei': vendor.uei,
                'name': vendor.company_name,
                'website_found': bool(enriched.website),
                'email_found': bool(enriched.email),
                'phone_found': bool(enriched.phone),
                'website': enriched.website,
                'email': enriched.email,
                'phone': enriched.phone,
                'email_source': enriched.filtering_metadata.get('email_source', 'none'),
                'phone_source': enriched.filtering_metadata.get('phone_source', 'none'),
            })
            
        except Exception as exc:
            logger.error(f"  ❌ Error enriching {vendor.company_name}: {exc}")
            results.append({
                'uei': vendor.uei,
                'name': vendor.company_name,
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
    
    level1_emails = sum(1 for r in results if r.get('email_source', '').startswith('contact_page'))
    level2_emails = sum(1 for r in results if r.get('email_source') == 'serper_backup')
    level3_emails = sum(1 for r in results if r.get('email_source') == 'serper_targeted')
    
    logger.info(f"\nContact source breakdown:")
    logger.info(f"  Level 1 (scraped): {level1_emails}/{emails_found} ({level1_emails/max(emails_found,1)*100:.1f}%)")
    logger.info(f"  Level 2 (backup): {level2_emails}/{emails_found} ({level2_emails/max(emails_found,1)*100:.1f}%)")
    logger.info(f"  Level 3 (targeted): {level3_emails}/{emails_found} ({level3_emails/max(emails_found,1)*100:.1f}%)")
    
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
                    logger.info(f"   Email: {r['email']} [{r['email_source']}]")
                if r['phone_found']:
                    logger.info(f"   Phone: {r['phone']} [{r['phone_source']}]")
    
    logger.info(f"\n{'='*80}")
    logger.info("COST ESTIMATE")
    logger.info(f"{'='*80}\n")
    
    base_serper_calls = total - errors
    targeted_serper_calls = level3_emails
    total_serper_calls = base_serper_calls + targeted_serper_calls
    cost_per_call = 0.01
    total_cost = total_serper_calls * cost_per_call
    
    logger.info(f"Base Serper calls (website discovery): {base_serper_calls}")
    logger.info(f"Targeted Serper calls (Level 3 fallback): {targeted_serper_calls}")
    logger.info(f"Total Serper calls: {total_serper_calls}")
    logger.info(f"Cost per call: ${cost_per_call:.3f}")
    logger.info(f"Total cost: ${total_cost:.3f}")
    logger.info(f"Average cost per vendor: ${total_cost/total:.4f}")
    
    logger.info(f"\n{'='*80}\n")
    
    if websites_found / total >= 0.5:
        logger.info("✅ Test PASSED - >50% success rate, ready for production!")
    else:
        logger.warning("⚠️  Test WARNING - <50% success rate, review results")


if __name__ == "__main__":
    asyncio.run(test_realistic_vendors())
