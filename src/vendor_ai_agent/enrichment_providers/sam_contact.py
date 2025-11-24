"""SAM.gov Points of Contact enrichment provider."""
from __future__ import annotations

import logging
from typing import Optional

from ..database import Vendor, VendorContact, get_session
from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class SamContactProvider(BaseEnrichmentProvider):
    def __init__(self) -> None:
        super().__init__(name="sam_gov_poc")
        self.logger = logging.getLogger(__name__)

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if self._has_real_contacts(vendor):
            self.logger.debug(f"Vendor {vendor.company_name} already has real contacts, skipping SAM POC lookup")
            return vendor
        
        self.logger.info(f"Searching SAM.gov POC for {vendor.company_name}")
        
        with get_session() as db_session:
            db_vendor = self._find_vendor(db_session, vendor)
            
            if not db_vendor:
                self.logger.debug(f"  ✗ No SAM.gov vendor found for {vendor.company_name}")
                return vendor
            
            contacts = db_session.query(VendorContact).filter(
                VendorContact.vendor_id == db_vendor.id,
                VendorContact.source == "sam_gov_poc"
            ).all()
            
            if not contacts:
                self.logger.debug(f"  ✗ No SAM POC contacts found for {vendor.company_name}")
                return vendor
            
            contact = contacts[0]
            
            if contact.email:
                vendor.email = contact.email
                vendor.filtering_metadata["email_source"] = "sam_gov_poc"
                vendor.filtering_metadata["email_confidence"] = 0.85
                self.logger.info(f"  ✓ Found SAM POC email: {contact.email}")
            
            if contact.phone:
                vendor.phone = contact.phone
                vendor.filtering_metadata["phone_source"] = "sam_gov_poc"
                vendor.filtering_metadata["phone_confidence"] = 0.85
                self.logger.info(f"  ✓ Found SAM POC phone: {contact.phone}")
            
            if contact.first_name or contact.last_name:
                full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                vendor.filtering_metadata["contact_names"] = [full_name]
                self.logger.info(f"  ✓ Found SAM POC name: {full_name}")
            
            if contact.email or contact.phone:
                vendor.enrichment_flags.append(self.name)
        
        return vendor
    
    def _find_vendor(self, db_session, vendor: VendorRecord) -> Optional[Vendor]:
        if vendor.uei:
            db_vendor = db_session.query(Vendor).filter(
                Vendor.source == "sam_entity",
                Vendor.uei == vendor.uei
            ).first()
            if db_vendor:
                return db_vendor
        
        if vendor.cage_code:
            db_vendor = db_session.query(Vendor).filter(
                Vendor.source == "sam_entity",
                Vendor.cage_code == vendor.cage_code
            ).first()
            if db_vendor:
                return db_vendor
        
        db_vendor = db_session.query(Vendor).filter(
            Vendor.source == "sam_entity",
            Vendor.legal_name == vendor.company_name
        ).first()
        return db_vendor
    
    def _has_real_contacts(self, vendor: VendorRecord) -> bool:
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
