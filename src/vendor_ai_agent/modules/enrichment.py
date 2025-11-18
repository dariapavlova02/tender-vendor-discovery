"""Vendor data enrichment via websites and APIs."""
from __future__ import annotations

from typing import Iterable, List, Sequence

from ..contracts import EnrichmentProvider, VendorEnricherContract
from ..enrichment_providers import StaticContactsProvider
from ..models import VendorRecord


class VendorEnricher(VendorEnricherContract):
    """Adds contact and metadata fields to vendor records."""

    def __init__(self, providers: Sequence[EnrichmentProvider] | None = None) -> None:
        self.providers: List[EnrichmentProvider] = list(providers or [StaticContactsProvider()])

    def enrich(self, vendors: Iterable[VendorRecord]) -> List[VendorRecord]:
        enriched: List[VendorRecord] = []
        for vendor in vendors:
            for provider in self.providers:
                vendor = provider.enrich(vendor)
            enriched.append(vendor)
        return enriched

    def register_provider(self, provider: EnrichmentProvider) -> None:
        self.providers.append(provider)
