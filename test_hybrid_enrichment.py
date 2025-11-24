"""Test hybrid website enrichment (DDG + Serper fallback).

This test validates:
1. HybridWebsiteEnricher integration
2. DDG search for vendors without websites
3. Serper fallback when DDG fails
4. Contact pre-filling from Serper snippets
5. Pipeline integration readiness
"""

import asyncio
import logging
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestVendor:
    """Minimal vendor for testing."""
    uei: str
    company_name: str
    city: str
    state_province: str
    country: str
    website: str = ""
    primary_email: str = ""
    primary_phone: str = ""
    
    @property
    def state(self):
        return self.state_province
    
    @property
    def email(self):
        return self.primary_email
    
    @email.setter
    def email(self, value):
        self.primary_email = value
    
    @property
    def phone(self):
        return self.primary_phone
    
    @phone.setter
    def phone(self, value):
        self.primary_phone = value
    
    def __post_init__(self):
        if not hasattr(self, 'enrichment_flags'):
            self.enrichment_flags = []
        if not hasattr(self, 'filtering_metadata'):
            self.filtering_metadata = {}


async def test_hybrid_enrichment():
    """Test hybrid website enrichment on vendors without websites."""
    from src.vendor_ai_agent.enrichment_providers import HybridWebsiteEnricher
    from src.vendor_ai_agent.config import RuntimeConfig
    
    cfg = RuntimeConfig()
    
    if not cfg.serper_api_key:
        logger.error("❌ SERPER_API_KEY not set in .env")
        return
    
    logger.info("✅ Serper API key found")
    
    enricher = HybridWebsiteEnricher(
        serper_api_key=cfg.serper_api_key,
        enable_ddg=cfg.enrichment.enable_ddg_search,
        enable_serper_fallback=cfg.enrichment.enable_serper_fallback,
        min_confidence=cfg.enrichment.website_search_min_confidence
    )
    
    test_vendors = [
        TestVendor(
            uei="TEST001",
            company_name="General Dynamics Information Technology",
            city="Falls Church",
            state_province="VA",
            country="United States"
        ),
        TestVendor(
            uei="TEST002",
            company_name="Lockheed Martin Corporation",
            city="Bethesda",
            state_province="MD",
            country="United States"
        ),
        TestVendor(
            uei="TEST003",
            company_name="Booz Allen Hamilton",
            city="McLean",
            state_province="VA",
            country="United States"
        ),
        TestVendor(
            uei="TEST004",
            company_name="CACI International Inc",
            city="Reston",
            state_province="VA",
            country="United States"
        ),
        TestVendor(
            uei="TEST005",
            company_name="Leidos Holdings Inc",
            city="Reston",
            state_province="VA",
            country="United States"
        ),
    ]
    
    logger.info(f"\n{'='*80}")
    logger.info("TESTING HYBRID WEBSITE ENRICHMENT")
    logger.info(f"{'='*80}\n")
    
    results = []
    for vendor in test_vendors:
        logger.info(f"\n--- Testing: {vendor.company_name} ---")
        logger.info(f"Location: {vendor.city}, {vendor.state_province}")
        logger.info(f"Initial website: {vendor.website or '(none)'}")
        
        enriched = enricher.enrich(vendor)
        
        logger.info(f"\n✅ Enrichment complete:")
        logger.info(f"  Website found: {enriched.website or '(none)'}")
        logger.info(f"  Email: {enriched.primary_email or '(none)'}")
        logger.info(f"  Phone: {enriched.primary_phone or '(none)'}")
        
        results.append({
            'name': vendor.company_name,
            'website_found': bool(enriched.website),
            'email_found': bool(enriched.primary_email),
            'phone_found': bool(enriched.primary_phone),
            'website': enriched.website,
        })
    
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}\n")
    
    total = len(results)
    websites_found = sum(1 for r in results if r['website_found'])
    emails_found = sum(1 for r in results if r['email_found'])
    phones_found = sum(1 for r in results if r['phone_found'])
    
    logger.info(f"Total vendors tested: {total}")
    logger.info(f"Websites found: {websites_found}/{total} ({websites_found/total*100:.1f}%)")
    logger.info(f"Emails found: {emails_found}/{total} ({emails_found/total*100:.1f}%)")
    logger.info(f"Phones found: {phones_found}/{total} ({phones_found/total*100:.1f}%)")
    
    logger.info("\nDetailed results:")
    for r in results:
        status = "✅" if r['website_found'] else "❌"
        logger.info(f"{status} {r['name']}: {r['website']}")
    
    logger.info(f"\n{'='*80}")
    logger.info("COST ESTIMATE")
    logger.info(f"{'='*80}\n")
    
    serper_calls = total
    cost_per_call = 0.01
    total_cost = serper_calls * cost_per_call
    
    logger.info(f"Serper API calls: {serper_calls}")
    logger.info(f"Cost per call: ${cost_per_call:.2f}")
    logger.info(f"Total cost: ${total_cost:.2f}")
    
    logger.info(f"\n{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(test_hybrid_enrichment())
