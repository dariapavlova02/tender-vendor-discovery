#!/usr/bin/env python3
"""
Test email extraction fixes on the three problem cases:
- bennettgroup.ca
- alpineservices.ca
- madergroup.ca
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.database.models import Vendor
from vendor_ai_agent.enrichment_providers.contact_scraping import ContactScrapingProvider
from vendor_ai_agent.enrichment_providers.serper_email_finder import SerperEmailFinder
from vendor_ai_agent.enrichment_providers.smart_email_generator import SmartEmailGeneratorEnricher
from vendor_ai_agent.modules.async_website_scraper import AsyncWebsiteScraper


async def test_vendor(website: str, company_name: str):
    print(f"\n{'='*80}")
    print(f"Testing: {company_name} ({website})")
    print(f"{'='*80}\n")
    
    config = RuntimeConfig()
    
    vendor = Vendor(
        company_name=company_name,
        website=website,
        domain=website.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/"),
    )
    
    scraper = AsyncWebsiteScraper(
        enable_cache=False,
        enable_playwright_fallback=True,
    )
    
    print("📝 LEVEL 1: Contact Scraping")
    print("-" * 80)
    contact_scraper = ContactScrapingProvider(scraper=scraper)
    result1 = await contact_scraper.enrich(vendor, config)
    if result1 and result1.email:
        print(f"✅ Found: {result1.email}")
        print(f"   Source: {result1.source}")
        return
    else:
        print(f"❌ No email found")
    
    print("\n📝 LEVEL 2: Apollo (Skipped - requires API)")
    print("-" * 80)
    print("⏭️  Skipping Apollo (would need real API key)")
    
    print("\n📝 LEVEL 3: Serper Email Finder")
    print("-" * 80)
    if config.serper_api_key:
        serper = SerperEmailFinder(api_key=config.serper_api_key)
        result3 = await serper.enrich(vendor, config)
        if result3 and result3.email:
            print(f"✅ Found: {result3.email}")
            print(f"   Source: {result3.source}")
            return
        else:
            print(f"❌ No email found")
    else:
        print("⏭️  No SERPER_API_KEY configured")
    
    print("\n📝 LEVEL 4: Smart Email Generator")
    print("-" * 80)
    if config.serper_api_key:
        smart_gen = SmartEmailGeneratorEnricher(
            api_key=config.serper_api_key,
            website_scraper=scraper,
        )
        result4 = await smart_gen.enrich(vendor, config)
        if result4 and result4.email:
            print(f"✅ Found: {result4.email}")
            print(f"   Source: {result4.source}")
            if result4.metadata:
                print(f"   Confidence: {result4.metadata.get('confidence', 'N/A')}")
        else:
            print(f"❌ No email found")
            if result4 and result4.metadata:
                print(f"   Reason: {result4.metadata.get('reason', 'Unknown')}")
    else:
        print("⏭️  No SERPER_API_KEY configured")


async def main():
    test_cases = [
        ("bennettgroup.ca", "Bennett Group"),
        ("alpineservices.ca", "Alpine Building Maintenance"),
        ("madergroup.ca", "Mader Group (CANADA)"),
    ]
    
    for website, company_name in test_cases:
        await test_vendor(website, company_name)
    
    print(f"\n{'='*80}")
    print("Test completed!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
