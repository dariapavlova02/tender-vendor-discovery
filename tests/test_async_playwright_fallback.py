import httpx
import pytest

from vendor_ai_agent.enrichment_providers.async_website_content import (
    AsyncWebsiteContentProvider,
)
from vendor_ai_agent.modules.async_website_scraper import AsyncWebsiteScraper


class _ForbiddenClient:
    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)


@pytest.mark.asyncio
async def test_fetch_page_uses_playwright_fallback(monkeypatch):
    scraper = AsyncWebsiteScraper(enable_cache=False, enable_playwright_fallback=True)

    async def fake_fetch_with_playwright(**kwargs):
        return "rendered via playwright"

    monkeypatch.setattr(scraper, "_fetch_with_playwright", fake_fetch_with_playwright)

    content, status = await scraper._fetch_page(
        _ForbiddenClient(),
        "https://blocked.example",
        timeout=1.0,
        include_status=True,
    )

    assert content == "rendered via playwright"
    assert status == 200


def test_async_provider_propagates_playwright_settings():
    provider = AsyncWebsiteContentProvider(
        enable_cache=False,
        enable_playwright_fallback=True,
        playwright_max_contexts=5,
        playwright_wait_ms=1500,
    )

    assert provider.scraper.enable_playwright_fallback is True
    assert provider.scraper.playwright_max_contexts == 5
    assert provider.scraper.playwright_wait_ms == 1500
