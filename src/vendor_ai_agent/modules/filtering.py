"""Filtering and ranking logic for vendor candidates."""
from __future__ import annotations

from typing import Iterable, List

from ..contracts import VendorFilterContract
from ..models import TenderProfile, VendorRecord


class VendorFilter(VendorFilterContract):
    """Applies geographic and rule-based filters to vendors."""

    def filter(self, profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorRecord]:
        """Simple pass-through with deterministic ordering placeholder."""

        sorted_vendors = sorted(vendors, key=lambda vendor: vendor.company_name)
        return list(sorted_vendors)
