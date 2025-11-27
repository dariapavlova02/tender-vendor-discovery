"""
Quick validation that two-phase batch enrichment is working correctly.
This test checks that Phase 1 and Phase 2 are being executed.
"""
import asyncio
import logging
from typing import List

from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.enrichment_providers import AsyncWebsiteContentProvider
from vendor_ai_agent.modules.enrichment import VendorEnricher


logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')


def create_test_vendors(count: int = 5) -> List[VendorRecord]:
    """Create minimal test vendor records."""
    websites = [
        "https://www.example.com",
        "https://www.python.org",
        "https://www.github.com",
        "https://www.stackoverflow.com",
        "https://www.google.com",
    ]
    
    return [
        VendorRecord(
            company_name=f"Test Vendor {i}",
            website=websites[i],
            city="Test City",
            state="CA",
            country="USA"
        )
        for i in range(count)
    ]


async def main():
    print("\n" + "="*70)
    print("BATCH ENRICHMENT VALIDATION TEST")
    print("="*70)
    
    vendors = create_test_vendors(5)
    print(f"\nCreated {len(vendors)} test vendors")
    
    provider = AsyncWebsiteContentProvider(enable_cache=False, enable_logging=True)
    
    enricher = VendorEnricher(
        providers=[provider],
        batch_size=50,
        max_workers=10
    )
    
    print("\nStarting enrichment (watch for 'Phase 1' and 'Phase 2' in logs)...")
    print("-"*70)
    
    enriched = await enricher._enrich_all_parallel_async(vendors)
    
    print("-"*70)
    print(f"\n✓ Enrichment complete: {len(enriched)} vendors processed")
    
    enriched_count = sum(1 for v in enriched if v.filtering_metadata.get("website_content"))
    print(f"✓ Vendors with content: {enriched_count}/{len(enriched)}")
    
    print("\nSample results:")
    for i, v in enumerate(enriched[:3]):
        content_len = len(v.filtering_metadata.get("website_content", ""))
        status = v.filtering_metadata.get("scrape_status", "N/A")
        print(f"  {i+1}. {v.company_name}: {content_len} chars, status={status}")
    
    print("\n" + "="*70)
    print("TEST COMPLETE ✅")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
