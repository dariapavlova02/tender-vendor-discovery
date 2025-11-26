"""Contact scraping enrichment provider that extracts emails/phones from vendor websites."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional
from urllib.parse import urlparse

from ..models import VendorRecord
from ..modules.contact_extractor import ContactExtractor
from ..modules.tender_profiler import LLMProvider
from ..modules.async_website_scraper import AsyncWebsiteScraper
from .base import BaseEnrichmentProvider
from .serper_client import SerperClient
from .utils import filter_emails_for_vendor


class ContactScrapingProvider(BaseEnrichmentProvider):
    def __init__(
        self, 
        llm_provider: LLMProvider,
        scraper_timeout: int = 10,
        enable_llm_fallback: bool = True,
        serper_client: Optional[SerperClient] = None,
        enable_targeted_serper: bool = True
    ) -> None:
        super().__init__(name="contact_scraping")
        self.scraper = AsyncWebsiteScraper(
            timeout_seconds=scraper_timeout,
            max_concurrent_global=50,
            max_concurrent_per_domain=2,
            enable_cache=True
        )
        self.extractor = ContactExtractor(llm_provider=llm_provider)
        self.enable_llm_fallback = enable_llm_fallback
        self.serper_client = serper_client
        self.enable_targeted_serper = enable_targeted_serper
        self.logger = logging.getLogger(__name__)

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if self._has_real_contacts(vendor):
            self.logger.debug(f"Vendor {vendor.company_name} already has real contacts, skipping")
            return vendor
        
        if not vendor.website:
            self.logger.debug(f"Vendor {vendor.company_name} has no website, skipping contact scraping")
            return vendor
        
        self.logger.info(f"Scraping contacts for {vendor.company_name} ({vendor.website})")
        
        scrape_results = self.scraper.scrape_contacts_batch_sync([vendor.website])
        
        if vendor.website not in scrape_results:
            self.logger.warning(f"No scrape result for {vendor.website}")
            contacts = self.extractor.extract("", use_llm_fallback=False)
        else:
            scrape_result = scrape_results[vendor.website]
            if scrape_result.status != "success" or not scrape_result.contact_text:
                self.logger.warning(f"Contact scrape failed: {scrape_result.status}")
                contacts = self.extractor.extract("", use_llm_fallback=False)
            else:
                contacts = self.extractor.extract(
                    scrape_result.contact_text, 
                    use_llm_fallback=self.enable_llm_fallback
                )
        
        if contacts.emails:
            vendor.email = contacts.emails[0]
            vendor.filtering_metadata["email_source"] = contacts.email_sources[0]
            vendor.filtering_metadata["email_confidence"] = contacts.confidence
            vendor.filtering_metadata["all_emails"] = contacts.emails
            self.logger.info(f"  ✓ Level 1: Found {len(contacts.emails)} emails via {contacts.extraction_method}")
        else:
            if not vendor.email:
                self._apply_backup_contacts(vendor)
            
            if not vendor.email and self.enable_targeted_serper and self.serper_client:
                self._targeted_serper_search(vendor)
        
        if contacts.phones:
            vendor.phone = contacts.phones[0]
            vendor.filtering_metadata["phone_source"] = contacts.phone_sources[0]
            vendor.filtering_metadata["phone_confidence"] = contacts.confidence
            vendor.filtering_metadata["all_phones"] = contacts.phones
            self.logger.info(f"  ✓ Found {len(contacts.phones)} phones via {contacts.extraction_method}")
        else:
            if not vendor.phone and 'serper_backup_phones' in vendor.filtering_metadata:
                phones = vendor.filtering_metadata['serper_backup_phones']
                vendor.phone = phones[0]
                vendor.filtering_metadata["phone_source"] = "serper_backup"
                vendor.filtering_metadata["phone_confidence"] = 0.7
                vendor.filtering_metadata["all_phones"] = phones
                self.logger.info(f"  ✓ Level 2: Using {len(phones)} backup phones from Serper snippets")
        
        if contacts.contact_names:
            vendor.filtering_metadata["contact_names"] = contacts.contact_names
            self.logger.info(f"  ✓ Found {len(contacts.contact_names)} contact names")
        
        if vendor.email or vendor.phone:
            vendor.enrichment_flags.append(self.name)
        
        return vendor
    
    async def enrich_async(self, vendor: VendorRecord) -> VendorRecord:
        if self._has_real_contacts(vendor):
            self.logger.debug(f"Vendor {vendor.company_name} already has real contacts, skipping")
            return vendor
        
        if not vendor.website:
            self.logger.debug(f"Vendor {vendor.company_name} has no website, skipping contact scraping")
            return vendor
        
        self.logger.info(f"Scraping contacts for {vendor.company_name} ({vendor.website})")
        
        scrape_results = await self.scraper.scrape_contacts_batch([vendor.website])
        
        if vendor.website not in scrape_results:
            self.logger.warning(f"No scrape result for {vendor.website}")
            contacts = self.extractor.extract("", use_llm_fallback=False)
        else:
            scrape_result = scrape_results[vendor.website]
            if scrape_result.status != "success" or not scrape_result.contact_text:
                self.logger.warning(f"Contact scrape failed: {scrape_result.status}")
                contacts = self.extractor.extract("", use_llm_fallback=False)
            else:
                contacts = self.extractor.extract(
                    scrape_result.contact_text, 
                    use_llm_fallback=self.enable_llm_fallback
                )
        
        if contacts.emails:
            vendor.email = contacts.emails[0]
            vendor.filtering_metadata["email_source"] = contacts.email_sources[0]
            vendor.filtering_metadata["email_confidence"] = contacts.confidence
            vendor.filtering_metadata["all_emails"] = contacts.emails
            self.logger.info(f"  ✓ Level 1: Found {len(contacts.emails)} emails via {contacts.extraction_method}")
        else:
            if not vendor.email:
                self._apply_backup_contacts(vendor)
            
            if not vendor.email and self.enable_targeted_serper and self.serper_client:
                await self._targeted_serper_search_async(vendor)
        
        if contacts.phones:
            vendor.phone = contacts.phones[0]
            vendor.filtering_metadata["phone_source"] = contacts.phone_sources[0]
            vendor.filtering_metadata["phone_confidence"] = contacts.confidence
            vendor.filtering_metadata["all_phones"] = contacts.phones
            self.logger.info(f"  ✓ Found {len(contacts.phones)} phones via {contacts.extraction_method}")
        else:
            if not vendor.phone and 'serper_backup_phones' in vendor.filtering_metadata:
                phones = vendor.filtering_metadata['serper_backup_phones']
                vendor.phone = phones[0]
                vendor.filtering_metadata["phone_source"] = "serper_backup"
                vendor.filtering_metadata["phone_confidence"] = 0.7
                vendor.filtering_metadata["all_phones"] = phones
                self.logger.info(f"  ✓ Level 2: Using {len(phones)} backup phones from Serper snippets")
        
        if contacts.contact_names:
            vendor.filtering_metadata["contact_names"] = contacts.contact_names
            self.logger.info(f"  ✓ Found {len(contacts.contact_names)} contact names")
        
        if vendor.email or vendor.phone:
            vendor.enrichment_flags.append(self.name)
        
        return vendor
    
    def _apply_backup_contacts(self, vendor: VendorRecord) -> None:
        backup_emails = vendor.filtering_metadata.get('serper_backup_emails')
        if backup_emails:
            filtered = filter_emails_for_vendor(vendor, backup_emails)
            if not filtered:
                return
            vendor.email = filtered[0]
            vendor.filtering_metadata["email_source"] = "serper_backup"
            vendor.filtering_metadata["email_confidence"] = 0.7
            vendor.filtering_metadata["all_emails"] = filtered
            self.logger.info(f"  ✓ Level 2: Using {len(filtered)} filtered backup emails from Serper snippets")
    
    def _targeted_serper_search(self, vendor: VendorRecord) -> None:
        if not self.serper_client:
            return
        
        serper = self.serper_client
        filtered: List[str] = []
        try:
            self.logger.info(f"  → Level 3: Targeted Serper search for contacts")
            query = self._build_serper_query(vendor)
            
            result = serper.search_company(
                company_name=vendor.company_name,
                include_contacts=True,
                query=query,
            )
            
            if result.contacts and result.contacts.emails:
                filtered = filter_emails_for_vendor(vendor, result.contacts.emails)
                if filtered:
                    vendor.email = filtered[0]
                    vendor.filtering_metadata["email_source"] = "serper_targeted"
                    vendor.filtering_metadata["email_confidence"] = 0.6
                    vendor.filtering_metadata["all_emails"] = filtered
                    self.logger.info(
                        f"  ✓ Level 3: Found {len(filtered)} filtered emails via targeted Serper"
                    )

            if result.contacts and result.contacts.emails and not filtered:
                self.logger.info("  ↩️ Serper returned only generic emails, skipped")
            
            if result.contacts and result.contacts.phones and not vendor.phone:
                vendor.phone = result.contacts.phones[0]
                vendor.filtering_metadata["phone_source"] = "serper_targeted"
                vendor.filtering_metadata["phone_confidence"] = 0.6
                vendor.filtering_metadata["all_phones"] = result.contacts.phones
                self.logger.info(f"  ✓ Level 3: Found {len(result.contacts.phones)} phones via targeted Serper")
                
        except Exception as exc:
            self.logger.debug(f"  ✗ Level 3 targeted Serper failed: {exc}")
    
    async def _targeted_serper_search_async(self, vendor: VendorRecord) -> None:
        if not self.serper_client:
            return
        
        serper = self.serper_client
        filtered: List[str] = []
        try:
            self.logger.info(f"  → Level 3: Targeted Serper search for contacts")
            query = self._build_serper_query(vendor)
            
            result = await serper.search_company_async(
                company_name=vendor.company_name,
                include_contacts=True,
                query=query,
            )
            
            if result.contacts and result.contacts.emails:
                filtered = filter_emails_for_vendor(vendor, result.contacts.emails)
                if filtered:
                    vendor.email = filtered[0]
                    vendor.filtering_metadata["email_source"] = "serper_targeted"
                    vendor.filtering_metadata["email_confidence"] = 0.6
                    vendor.filtering_metadata["all_emails"] = filtered
                    self.logger.info(
                        f"  ✓ Level 3: Found {len(filtered)} filtered emails via targeted Serper"
                    )

            if result.contacts and result.contacts.emails and not filtered:
                self.logger.info("  ↩️ Serper returned only generic emails, skipped")
            
            if result.contacts and result.contacts.phones and not vendor.phone:
                vendor.phone = result.contacts.phones[0]
                vendor.filtering_metadata["phone_source"] = "serper_targeted"
                vendor.filtering_metadata["phone_confidence"] = 0.6
                vendor.filtering_metadata["all_phones"] = result.contacts.phones
                self.logger.info(f"  ✓ Level 3: Found {len(result.contacts.phones)} phones via targeted Serper")
                
        except Exception as exc:
            self.logger.debug(f"  ✗ Level 3 targeted Serper failed: {exc}")
    
    def _has_real_contacts(self, vendor: VendorRecord) -> bool:
        """Check if vendor already has real (not fallback) contacts."""
        metadata = vendor.filtering_metadata
        
        has_real_email = bool(
            vendor.email and 
            metadata.get("email_source") not in [None, "fallback_static", "fallback_na"]
        )
        
        has_real_phone = bool(
            vendor.phone and 
            vendor.phone != "N/A" and
            metadata.get("phone_source") not in [None, "fallback_static", "fallback_na"]
        )
        
        return has_real_email or has_real_phone

    def _build_serper_query(self, vendor: VendorRecord) -> str:
        domain = self._extract_domain(vendor.website)
        base = f'"{vendor.company_name}"'
        if domain:
            query = f"site:{domain} (\"contact\" OR \"email\" OR \"support\") {base}"
        else:
            query = f"{base} email contact"
        if vendor.city:
            query += f' "{vendor.city}"'
        if vendor.state:
            query += f' "{vendor.state}"'
        return query

    @staticmethod
    def _extract_domain(url: Optional[str]) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""
