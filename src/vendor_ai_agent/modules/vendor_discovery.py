"""Vendor discovery across registries and directories."""
from __future__ import annotations

from typing import Iterable, List, Sequence

from ..contracts import VendorDiscoveryContract, VendorSource
from ..models import TenderProfile, VendorRecord
from ..sources import StaticDirectorySource


class VendorDiscovery(VendorDiscoveryContract):
    """Aggregates vendor candidates from configured sources."""

    def __init__(self, sources: Sequence[VendorSource] | None = None) -> None:
        self.sources: List[VendorSource] = list(sources or [StaticDirectorySource()])

    def discover(self, profile: TenderProfile) -> List[VendorRecord]:
        vendors: List[VendorRecord] = []
        for source in self.sources:
            vendors.extend(source.search(profile))
        return vendors

    def register_source(self, source: VendorSource) -> None:
        self.sources.append(source)
