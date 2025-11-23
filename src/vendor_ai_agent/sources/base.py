"""Base abstractions for vendor discovery sources."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..models import TenderProfile, VendorRecord


@dataclass
class BaseVendorSource:
    """Simple base class to unify configuration for discovery sources."""

    name: str

    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        raise NotImplementedError
    
    def is_compatible(self, profile: TenderProfile) -> bool:
        return True
