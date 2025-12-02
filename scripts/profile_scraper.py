#!/usr/bin/env python
"""Profile how long the async website scraper takes for a batch."""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from vendor_ai_agent.modules.async_website_scraper import AsyncWebsiteScraper


async def main() -> None:
    parser = argparse.ArgumentParser(description="Profile website scraper")
    parser.add_argument("urls", type=Path, help="Path to JSON/CSV/text list of URLs")
    args = parser.parse_args()

    raw = args.urls.read_text().strip()
    if raw.startswith("["):
        urls = json.loads(raw)
    else:
        urls = [line.strip() for line in raw.splitlines() if line.strip()]

    scraper = AsyncWebsiteScraper(enable_playwright_fallback=True)
    start = time.time()
    results = await scraper.scrape_contacts_batch(urls)
    duration = time.time() - start

    success = sum(1 for r in results.values() if r.status == "success")
    print(f"Scraped {len(results)} urls in {duration:.2f}s; success={success}")


if __name__ == "__main__":
    asyncio.run(main())
