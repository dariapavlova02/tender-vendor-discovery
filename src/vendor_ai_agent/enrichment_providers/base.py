"""Base enrichment provider definition."""
from __future__ import annotations

from dataclasses import dataclass

from ..models import VendorRecord


@dataclass
class BaseEnrichmentProvider:
    name: str

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        raise NotImplementedError
