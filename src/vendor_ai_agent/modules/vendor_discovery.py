"""Vendor discovery across registries and directories."""
from __future__ import annotations

from typing import Iterable, List, Sequence

from ..contracts import VendorDiscoveryContract, VendorSource
from ..models import TenderProfile, VendorRecord


class VendorDiscovery(VendorDiscoveryContract):
    """Aggregates vendor candidates from configured sources."""

    def __init__(self, sources: Sequence[VendorSource] | None = None) -> None:
        self.sources: List[VendorSource] = list(sources) if sources is not None else []

    def discover(self, profile: TenderProfile) -> List[VendorRecord]:
        import logging
        logger = logging.getLogger(__name__)
        
        vendors: List[VendorRecord] = []
        for source in self.sources:
            if hasattr(source, 'is_compatible') and not source.is_compatible(profile):
                logger.info(f"Skipping {source.name} - incompatible with tender")
                continue
            try:
                vendors.extend(source.search(profile))
            except Exception as e:
                logger.error(f"Source {source.name} failed: {e}")
                raise Exception(f"Vendor discovery failed - {source.name}: {e}")
        return vendors

    def register_source(self, source: VendorSource) -> None:
        self.sources.append(source)
