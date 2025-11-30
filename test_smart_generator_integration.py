#!/usr/bin/env python3
"""
Integration test: Test email extraction on real vendor websites
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database.models import Vendor
from vendor_ai_agent.enrichment_providers.smart_email_generator import SmartEmailGeneratorProvider
from vendor_ai_agent.modules.async_website_scraper import AsyncWebsiteScraper
from vendor_ai_agent.config import RuntimeConfig

logging.basicConfig(level=logging.INFO)


async def test_smart_generator():
    config = RuntimeConfig()
    
    if not config.serper_api_key:
        print("❌ SERPER_API_KEY not configured - skipping test")
        return
    
    test_cases = [
        ("bennettgroup.ca", "Bennett Group"),
        ("alpineservices.ca", "Alpine Building Maintenance"),
        ("madergroup.ca", "Mader Group (CANADA)"),
    ]
    
    scraper = AsyncWebsiteScraper(enable_cache=False, enable_playwright_fallback=True)
    generator = SmartEmailGeneratorProvider(
        api_key=config.serper_api_key,
        website_scraper=scraper,
    )
    
    print("\n" + "="*80)
    print("SMART EMAIL GENERATOR TEST")
    print("="*80 + "\n")
    
    for website, company_name in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {company_name} ({website})")
        print(f"{'='*80}\n")
        
        vendor = Vendor(
            company_name=company_name,
            website=f"https://{website}",
            domain=website,
        )
        
        result = await generator.enrich(vendor, config)
        
        if result and result.email:
            print(f"✅ SUCCESS: {result.email}")
            print(f"   Source: {result.source}")
            if result.metadata:
                print(f"   Confidence: {result.metadata.get('confidence', 'N/A')}")
                if 'candidates' in result.metadata:
                    print(f"   Candidates tried: {result.metadata['candidates']}")
        else:
            print(f"❌ FAILED: No email found")
            if result and result.metadata:
                print(f"   Reason: {result.metadata.get('reason', 'Unknown')}")
                if 'candidates' in result.metadata:
                    print(f"   Candidates tried: {result.metadata['candidates']}")
    
    print(f"\n{'='*80}")
    print("Test completed!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(test_smart_generator())
