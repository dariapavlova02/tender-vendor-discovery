"""Async website content enrichment provider."""
from __future__ import annotations

import logging
from typing import Dict, List
from urllib.parse import urlparse

from ..models import VendorRecord
from ..modules.async_website_scraper import AsyncWebsiteScraper, ScrapedContent
from .base import BaseEnrichmentProvider

SOCIAL_DOMAINS = {
    "facebook.com",
    "m.facebook.com",
    "instagram.com",
    "twitter.com",
    "linkedin.com",
    "ca.linkedin.com",
    "zoominfo.com",
    "mapquest.com",
    "yelp.com",
    "squarespace.com",
    "finance.yahoo.com",
    "yahoo.com",
    "news.yahoo.com",
}


class AsyncWebsiteContentProvider(BaseEnrichmentProvider):
    
    def __init__(
        self,
        enable_cache: bool = True,
        enable_logging: bool = True,
        *,
        enable_playwright_fallback: bool = False,
        playwright_max_contexts: int = 2,
        playwright_wait_ms: int = 800,
    ):
        super().__init__(name="async_website_content")
        self.scraper = AsyncWebsiteScraper(
            enable_cache=enable_cache,
            enable_playwright_fallback=enable_playwright_fallback,
            playwright_max_contexts=playwright_max_contexts,
            playwright_wait_ms=playwright_wait_ms,
        )
        self.logger = logging.getLogger(__name__) if enable_logging else None
    
    def enrich_batch(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        """Enrich multiple vendors in a single sync batch."""
        if not vendors:
            return []
        
        urls_to_scrape = []
        vendor_by_url: Dict[str, List[VendorRecord]] = {}
        
        for vendor in vendors:
            if not vendor.website:
                continue
            
            if "website_content" in vendor.filtering_metadata:
                continue
            
            domain = self._extract_domain(vendor.website)
            if domain and self._is_social_domain(domain):
                vendor.filtering_metadata["scrape_status"] = "ignored_social"
                vendor.filtering_metadata["scrape_error"] = "Social profile link"
                vendor.filtering_metadata["social_profile_url"] = vendor.website
                if self.logger:
                    self.logger.info(f"Skipping {vendor.company_name}: social profile ({domain})")
                continue
            
            urls_to_scrape.append(vendor.website)
            if vendor.website not in vendor_by_url:
                vendor_by_url[vendor.website] = []
            vendor_by_url[vendor.website].append(vendor)
        
        if not urls_to_scrape:
            return vendors
        
        results = self.scraper.scrape_batch_sync(urls_to_scrape)
        
        for url, result in results.items():
            for vendor in vendor_by_url.get(url, []):
                self._apply_scrape_result(vendor, result)
        
        return vendors
    
    async def enrich_batch_async(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        """Enrich multiple vendors in a single async batch."""
        if not vendors:
            return []
        
        urls_to_scrape = []
        vendor_by_url: Dict[str, List[VendorRecord]] = {}
        
        for vendor in vendors:
            if not vendor.website:
                continue
            
            if "website_content" in vendor.filtering_metadata:
                continue
            
            domain = self._extract_domain(vendor.website)
            if domain and self._is_social_domain(domain):
                vendor.filtering_metadata["scrape_status"] = "ignored_social"
                vendor.filtering_metadata["scrape_error"] = "Social profile link"
                vendor.filtering_metadata["social_profile_url"] = vendor.website
                if self.logger:
                    self.logger.info(f"Skipping {vendor.company_name}: social profile ({domain})")
                continue
            
            urls_to_scrape.append(vendor.website)
            if vendor.website not in vendor_by_url:
                vendor_by_url[vendor.website] = []
            vendor_by_url[vendor.website].append(vendor)
        
        if not urls_to_scrape:
            return vendors
        
        if self.logger:
            self.logger.info(f"Starting async website content scrape batch: {len(urls_to_scrape)} URLs")
        results = await self.scraper.scrape_batch(urls_to_scrape)
        
        for url, result in results.items():
            for vendor in vendor_by_url.get(url, []):
                self._apply_scrape_result(vendor, result)
        
        return vendors
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        """Legacy single-vendor enrichment (fallback to batch of 1)."""
        enriched = self.enrich_batch([vendor])
        return enriched[0] if enriched else vendor
    
    def _apply_scrape_result(self, vendor: VendorRecord, result: ScrapedContent) -> None:
        """Apply scraping result to vendor record."""
        vendor.filtering_metadata["scrape_status"] = result.status
        vendor.filtering_metadata["scrape_timestamp"] = result.timestamp
        vendor.filtering_metadata["fetch_duration_ms"] = result.fetch_duration_ms
        vendor.filtering_metadata["from_cache"] = result.from_cache
        
        if result.source_urls:
            vendor.filtering_metadata["content_sources"] = result.source_urls
        
        if result.status == "success" and result.content:
            vendor.filtering_metadata["website_content"] = result.content
            
            if self.logger:
                cache_str = " (cached)" if result.from_cache else ""
                self.logger.info(
                    f"Scraped {len(result.content)} chars from {vendor.company_name} "
                    f"({result.fetch_duration_ms}ms{cache_str})"
                )
        else:
            vendor.filtering_metadata["scrape_error"] = result.error_message
            
            if self.logger and not result.from_cache:
                self.logger.warning(f"Scraping failed for {vendor.company_name}: {result.error_message}")
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""
    
    @staticmethod
    def _is_social_domain(host: str) -> bool:
        if host in SOCIAL_DOMAINS:
            return True
        return any(host.endswith(f".{base}") for base in SOCIAL_DOMAINS)
