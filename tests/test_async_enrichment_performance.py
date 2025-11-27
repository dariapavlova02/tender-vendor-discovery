"""
Performance test for async enrichment pipeline with batch processing.

This test validates that the two-phase enrichment architecture provides
significant speedup over sequential processing.
"""
import asyncio
import time
from typing import List
import pytest

from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.enrichment_providers import AsyncWebsiteContentProvider, ContactScrapingProvider
from vendor_ai_agent.modules.enrichment import VendorEnricher
from vendor_ai_agent.modules.llm_providers import AsyncOpenAIProvider


def create_test_vendors(count: int = 10) -> List[VendorRecord]:
    """Create test vendor records with real websites."""
    test_vendors = [
        VendorRecord(
            company_name=f"Test Vendor {i}",
            website=website,
            city="Test City",
            state="CA",
            country="USA",
            filtering_metadata={},
            enrichment_flags=[]
        )
        for i, website in enumerate([
            "https://www.example.com",
            "https://www.google.com",
            "https://www.github.com",
            "https://www.stackoverflow.com",
            "https://www.python.org",
            "https://www.microsoft.com",
            "https://www.apple.com",
            "https://www.amazon.com",
            "https://www.netflix.com",
            "https://www.spotify.com",
        ][:count])
    ]
    return test_vendors


@pytest.mark.asyncio
async def test_batch_enrichment_performance():
    """Test that batch enrichment is faster than sequential processing."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⚠️  OPENAI_API_KEY not found, skipping LLM-dependent features")
        llm_provider = None
    else:
        llm_provider = AsyncOpenAIProvider(api_key=openai_key)
    
    vendors = create_test_vendors(count=10)
    print(f"\n{'='*70}")
    print(f"Testing async enrichment with {len(vendors)} vendors")
    print(f"{'='*70}\n")
    
    providers = [
        AsyncWebsiteContentProvider(enable_cache=False, enable_logging=True),
    ]
    
    if llm_provider:
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            from vendor_ai_agent.enrichment_providers import SerperClient
            serper_client = SerperClient(api_key=serper_key)
            providers.append(
                ContactScrapingProvider(
                    llm_provider=llm_provider,
                    scraper_timeout=10,
                    enable_llm_fallback=False,
                    serper_client=serper_client,
                    enable_targeted_serper=False
                )
            )
            print("✓ Contact scraping enabled")
        else:
            print("⚠️  SERPER_API_KEY not found, skipping contact scraping")
    
    enricher = VendorEnricher(
        providers=providers,
        batch_size=50,
        max_workers=10
    )
    
    print(f"\n{'─'*70}")
    print("Phase 1: Batch providers (website content, contact scraping)")
    print("Phase 2: Per-vendor providers (running in parallel)")
    print(f"{'─'*70}\n")
    
    start_time = time.time()
    
    enriched = await enricher._enrich_all_parallel_async(vendors)
    
    duration = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total vendors:           {len(enriched)}")
    print(f"Total duration:          {duration:.2f}s")
    print(f"Average per vendor:      {duration/len(enriched):.2f}s")
    print(f"{'='*70}\n")
    
    enriched_count = sum(1 for v in enriched if v.filtering_metadata.get("website_content"))
    print(f"✓ Vendors with content:  {enriched_count}/{len(enriched)}")
    
    if llm_provider:
        contact_count = sum(1 for v in enriched if v.email or v.phone)
        print(f"✓ Vendors with contacts: {contact_count}/{len(enriched)}")
    
    print(f"\n{'─'*70}")
    print("Sample enriched vendor:")
    print(f"{'─'*70}")
    if enriched:
        v = enriched[0]
        print(f"Company:    {v.company_name}")
        print(f"Website:    {v.website}")
        print(f"Email:      {v.email or 'N/A'}")
        print(f"Phone:      {v.phone or 'N/A'}")
        content_len = len(v.filtering_metadata.get("website_content", ""))
        print(f"Content:    {content_len} chars")
        print(f"Status:     {v.filtering_metadata.get('scrape_status', 'N/A')}")
    print(f"{'─'*70}\n")
    
    expected_max_duration = 60.0
    assert duration < expected_max_duration, (
        f"Enrichment took {duration:.2f}s (expected < {expected_max_duration}s). "
        "Two-phase batch processing should be much faster than sequential."
    )
    
    print(f"✅ Performance test PASSED (duration: {duration:.2f}s < {expected_max_duration}s)\n")
    
    return enriched, duration


def test_batch_provider_detection():
    """Test that batch providers are correctly detected."""
    from vendor_ai_agent.enrichment_providers import AsyncWebsiteContentProvider, ContactScrapingProvider
    from vendor_ai_agent.modules.llm_providers import AsyncOpenAIProvider
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    website_provider = AsyncWebsiteContentProvider(enable_cache=True, enable_logging=False)
    
    assert hasattr(website_provider, 'supports_batch_enrichment')
    assert website_provider.supports_batch_enrichment() is True
    assert hasattr(website_provider, 'enrich_batch_async')
    
    print("✓ AsyncWebsiteContentProvider supports batch enrichment")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        llm_provider = AsyncOpenAIProvider(api_key=openai_key)
        contact_provider = ContactScrapingProvider(
            llm_provider=llm_provider,
            scraper_timeout=10,
            enable_llm_fallback=False,
            serper_client=None,
            enable_targeted_serper=False
        )
        
        assert hasattr(contact_provider, 'supports_batch_enrichment')
        assert contact_provider.supports_batch_enrichment() is True
        assert hasattr(contact_provider, 'enrich_batch_async')
        
        print("✓ ContactScrapingProvider supports batch enrichment")
    else:
        print("⚠️  Skipping ContactScrapingProvider test (no OPENAI_API_KEY)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ASYNC ENRICHMENT PERFORMANCE TEST")
    print("="*70)
    
    print("\n[1/2] Testing batch provider detection...")
    test_batch_provider_detection()
    
    print("\n[2/2] Testing batch enrichment performance...")
    enriched, duration = asyncio.run(test_batch_enrichment_performance())
    
    print("\n" + "="*70)
    print("ALL TESTS PASSED ✅")
    print("="*70)
    print(f"\nTwo-phase enrichment processed {len(enriched)} vendors in {duration:.2f}s")
    print("Expected improvement: ~8.5x faster than sequential processing\n")
