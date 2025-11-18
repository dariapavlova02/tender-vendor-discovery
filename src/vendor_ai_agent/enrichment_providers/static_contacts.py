"""Static enrichment provider that injects placeholder contacts."""
from __future__ import annotations

from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class StaticContactsProvider(BaseEnrichmentProvider):
    def __init__(self) -> None:
        super().__init__(name="static_contacts")

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        normalized = vendor.company_name.lower().replace(" ", "")
        vendor.website = vendor.website or f"https://{normalized}.com"
        vendor.email = vendor.email or f"info@{normalized}.com"
        vendor.phone = vendor.phone or "+1-000-000-0000"
        vendor.enrichment_flags.append(self.name)
        return vendor
