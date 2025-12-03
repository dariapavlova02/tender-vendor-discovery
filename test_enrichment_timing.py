"""Test enrichment timing with parallel Phase 2."""
import asyncio
import logging
import time
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.models import VendorRecord
from src.vendor_ai_agent.modules.enrichment import VendorEnricher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

async def test_async_enrichment():
    """Test async enrichment with Phase 2 parallelization."""
    
    config = RuntimeConfig()
    config.enrichment.enable_website_search = True
    config.enrichment.enable_ddg_search = True
    
    enricher = VendorEnricher(config)
    
    test_vendors = [
        VendorRecord(company_name=f"Test Vendor {i}", location="Test Location")
        for i in range(18)
    ]
    
    print(f"\n{'='*80}")
    print(f"Testing async enrichment with {len(test_vendors)} vendors")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    try:
        enriched = await enricher._enrich_all_parallel_async(test_vendors)
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*80}")
        print(f"✅ Enrichment completed in {elapsed:.1f}s")
        print(f"   Input vendors: {len(test_vendors)}")
        print(f"   Enriched vendors: {len(enriched)}")
        print(f"{'='*80}\n")
        
        for i, vendor in enumerate(enriched[:3], 1):
            print(f"{i}. {vendor.company_name}")
            print(f"   Website: {vendor.website_url or 'N/A'}")
            print(f"   Contact email: {vendor.contact_email or 'N/A'}")
            print()
        
    except Exception as e:
        print(f"\n❌ Enrichment failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_async_enrichment())
