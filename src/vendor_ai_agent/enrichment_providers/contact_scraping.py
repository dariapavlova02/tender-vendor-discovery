"""Contact scraping enrichment provider that extracts emails/phones from vendor websites."""
from __future__ import annotations

import logging
from typing import Optional

from ..models import VendorRecord
from ..modules.contact_extractor import ContactExtractor
from ..modules.tender_profiler import LLMProvider
from ..modules.website_scraper import WebsiteScraper
from .base import BaseEnrichmentProvider
from .serper_client import SerperClient


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
        self.scraper = WebsiteScraper(timeout_seconds=scraper_timeout)
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
        
        contacts = self.scraper.scrape_contacts(
            vendor.website, 
            self.extractor
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
    
    def _apply_backup_contacts(self, vendor: VendorRecord) -> None:
        backup_emails = vendor.filtering_metadata.get('serper_backup_emails')
        if backup_emails:
            vendor.email = backup_emails[0]
            vendor.filtering_metadata["email_source"] = "serper_backup"
            vendor.filtering_metadata["email_confidence"] = 0.7
            vendor.filtering_metadata["all_emails"] = backup_emails
            self.logger.info(f"  ✓ Level 2: Using {len(backup_emails)} backup emails from Serper snippets")
    
    def _targeted_serper_search(self, vendor: VendorRecord) -> None:
        try:
            self.logger.info(f"  → Level 3: Targeted Serper search for contacts")
            query = f"{vendor.company_name} email contact"
            if vendor.city:
                query += f" {vendor.city}"
            
            result = self.serper_client.search_company(
                company_name=query,
                include_contacts=True
            )
            
            if result.contacts and result.contacts.emails:
                vendor.email = result.contacts.emails[0]
                vendor.filtering_metadata["email_source"] = "serper_targeted"
                vendor.filtering_metadata["email_confidence"] = 0.6
                vendor.filtering_metadata["all_emails"] = result.contacts.emails
                self.logger.info(f"  ✓ Level 3: Found {len(result.contacts.emails)} emails via targeted Serper")
            
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
