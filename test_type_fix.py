#!/usr/bin/env python3
"""
Simple test of the async_website_scraper type error fix
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.async_website_scraper import AsyncWebsiteScraper


async def test_fetch_with_status():
    """Test that _fetch_page with include_status=True returns a tuple"""
    scraper = AsyncWebsiteScraper(enable_cache=False, enable_playwright_fallback=False)
    
    import httpx
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        result = await scraper._fetch_page(
            client,
            "https://bennettgroup.ca/contact.php",
            timeout=10.0,
            include_status=True,
            domain="bennettgroup.ca"
        )
        
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
        
        if result is not None and isinstance(result, tuple):
            content, status = result
            print(f"✅ Type error fixed! Returns tuple: (content={len(content) if content else 0} chars, status={status})")
        else:
            print(f"❌ Still broken: result is not a tuple")


if __name__ == "__main__":
    print("Testing async_website_scraper type error fix...")
    print("-" * 80)
    asyncio.run(test_fetch_with_status())
