"""Static enrichment provider that injects placeholder contacts."""
from __future__ import annotations

from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class StaticContactsProvider(BaseEnrichmentProvider):
    def __init__(self) -> None:
        super().__init__(name="static_contacts")

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        normalized = vendor.company_name.lower().replace(" ", "")
        
        if not vendor.website:
            vendor.website = f"https://{normalized}.com"
        
        if not vendor.email:
            vendor.email = f"info@{normalized}.com"
            vendor.filtering_metadata["email_source"] = "fallback_static"
            vendor.filtering_metadata["email_confidence"] = 0.1
        
        if not vendor.phone or vendor.phone == "N/A":
            vendor.phone = "N/A"
            vendor.filtering_metadata["phone_source"] = "fallback_na"
            vendor.filtering_metadata["phone_confidence"] = 0.0
        
        vendor.enrichment_flags.append(self.name)
        return vendor
