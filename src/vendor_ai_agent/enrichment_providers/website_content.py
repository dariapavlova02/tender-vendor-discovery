"""Website content enrichment provider."""
from __future__ import annotations

import logging
from typing import Optional

from urllib.parse import urlparse

from ..models import VendorRecord
from ..modules.website_scraper import WebsiteScraper
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
}


class WebsiteContentProvider(BaseEnrichmentProvider):
    
    def __init__(
        self,
        scraper: Optional[WebsiteScraper] = None,
        enable_logging: bool = True,
    ):
        super().__init__(name="website_content")
        self.scraper = scraper or WebsiteScraper(enable_logging=enable_logging)
        self.logger = logging.getLogger(__name__) if enable_logging else None
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if not vendor.website:
            if self.logger:
                self.logger.debug(f"Vendor {vendor.company_name} has no website, skipping scraping")
            return vendor
        
        if "website_content" in vendor.filtering_metadata:
            if self.logger:
                self.logger.debug(f"Vendor {vendor.company_name} already has scraped content")
            return vendor
        
        domain = self._extract_domain(vendor.website)
        if domain and self._is_social_domain(domain):
            vendor.filtering_metadata["scrape_status"] = "ignored_social"
            vendor.filtering_metadata["scrape_error"] = "Social profile link"
            vendor.filtering_metadata["social_profile_url"] = vendor.website
            if self.logger:
                self.logger.info(
                    "Skipping website scrape for %s: social profile (%s)",
                    vendor.company_name,
                    domain,
                )
            return vendor

        try:
            result = self.scraper.scrape(vendor.website)
            
            vendor.filtering_metadata["scrape_status"] = result.status
            vendor.filtering_metadata["scrape_timestamp"] = result.timestamp
            vendor.filtering_metadata["content_source"] = result.source_url
            
            if result.status == "success" and result.content:
                vendor.filtering_metadata["website_content"] = result.content
                
                if self.logger:
                    self.logger.info(
                        f"Scraped {len(result.content)} chars from {vendor.company_name}"
                    )
            else:
                vendor.filtering_metadata["scrape_error"] = result.error_message
                
                if self.logger:
                    self.logger.warning(
                        f"Scraping failed for {vendor.company_name}: {result.error_message}"
                    )
        
        except Exception as exc:
            vendor.filtering_metadata["scrape_status"] = "error"
            vendor.filtering_metadata["scrape_error"] = str(exc)
            
            if self.logger:
                self.logger.error(
                    f"Scraping exception for {vendor.company_name}: {exc}"
                )
        
        return vendor

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
