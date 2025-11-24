from __future__ import annotations

import logging
from typing import List, Optional

from ..models import VendorRecord
from ..enrichment_providers import GoogleMapsContactProvider

logger = logging.getLogger(__name__)


class ManualEnrichmentService:
    
    def __init__(
        self,
        google_maps_api_key: Optional[str] = None,
        apollo_api_key: Optional[str] = None
    ):
        self.google_maps_provider = None
        self.apollo_provider = None
        
        if google_maps_api_key:
            try:
                self.google_maps_provider = GoogleMapsContactProvider(api_key=google_maps_api_key)
                logger.info("GoogleMapsContactProvider initialized for manual enrichment")
            except Exception as exc:
                logger.warning(f"Failed to initialize Google Maps: {exc}")
        
        if apollo_api_key:
            logger.warning("Apollo provider not yet implemented - skipping initialization")
    
    def enrich_single_vendor_google_maps(self, vendor: VendorRecord) -> VendorRecord:
        if not self.google_maps_provider:
            logger.warning("Google Maps provider not available")
            return vendor
        
        if not vendor.company_name:
            logger.warning("Cannot enrich vendor without company name")
            return vendor
        
        try:
            enriched = self.google_maps_provider.enrich(vendor)
            logger.info(
                f"Google Maps enrichment for {vendor.company_name}: "
                f"email={'✓' if enriched.email else '✗'}, "
                f"phone={'✓' if enriched.phone else '✗'}"
            )
            return enriched
        except Exception as exc:
            logger.error(f"Google Maps enrichment failed for {vendor.company_name}: {exc}")
            return vendor
    
    def enrich_single_vendor_apollo(self, vendor: VendorRecord) -> VendorRecord:
        if not self.apollo_provider:
            logger.warning("Apollo provider not available")
            return vendor
        
        if not vendor.company_name:
            logger.warning("Cannot enrich vendor without company name")
            return vendor
        
        try:
            enriched = self.apollo_provider.enrich(vendor)
            logger.info(
                f"Apollo enrichment for {vendor.company_name}: "
                f"email={'✓' if enriched.email else '✗'}, "
                f"phone={'✓' if enriched.phone else '✗'}"
            )
            return enriched
        except Exception as exc:
            logger.error(f"Apollo enrichment failed for {vendor.company_name}: {exc}")
            return vendor
    
    def batch_enrich_google_maps(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        if not self.google_maps_provider:
            logger.warning("Google Maps provider not available")
            return vendors
        
        enriched_vendors = []
        success_count = 0
        
        for vendor in vendors:
            enriched = self.enrich_single_vendor_google_maps(vendor)
            if enriched.email or enriched.phone:
                success_count += 1
            enriched_vendors.append(enriched)
        
        logger.info(
            f"Batch Google Maps enrichment completed: "
            f"{success_count}/{len(vendors)} vendors enriched"
        )
        
        return enriched_vendors
    
    def batch_enrich_apollo(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        if not self.apollo_provider:
            logger.warning("Apollo provider not available")
            return vendors
        
        enriched_vendors = []
        success_count = 0
        
        for vendor in vendors:
            enriched = self.enrich_single_vendor_apollo(vendor)
            if enriched.email or enriched.phone:
                success_count += 1
            enriched_vendors.append(enriched)
        
        logger.info(
            f"Batch Apollo enrichment completed: "
            f"{success_count}/{len(vendors)} vendors enriched"
        )
        
        return enriched_vendors
    
    def get_vendors_missing_contacts(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        return [v for v in vendors if not v.email and not v.phone]
    
    def get_contact_status(self, vendor: VendorRecord) -> str:
        has_email = bool(vendor.email)
        has_phone = bool(vendor.phone)
        
        if has_email and has_phone:
            return "complete"
        elif has_email or has_phone:
            return "partial"
        else:
            return "missing"
