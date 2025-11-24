"""Protocol contracts that define module interfaces."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Protocol

from .models import FilteringMetrics, TenderProfile, TenderSection, VendorMatchResult, VendorRecord


class DocumentParserContract(Protocol):
    def parse(self, files: Iterable[Path]) -> List[TenderSection]:
        ...


class RequirementExtractorContract(Protocol):
    def extract(self, sections: List[TenderSection], base_profile: Optional[TenderProfile] = None) -> TenderProfile:
        ...


class VendorSource(Protocol):
    name: str

    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        ...


class VendorDiscoveryContract(Protocol):
    def discover(self, profile: TenderProfile) -> List[VendorRecord]:
        ...


class EnrichmentProvider(Protocol):
    name: str

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        ...


class VendorEnricherContract(Protocol):
    def enrich(self, vendors: Iterable[VendorRecord]) -> List[VendorRecord]:
        ...


class VendorFilterContract(Protocol):
    def filter(self, profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorRecord]:
        ...
    
    def get_metrics(self) -> FilteringMetrics:
        ...


class CapabilityMatcherContract(Protocol):
    def score(self, profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorMatchResult]:
        ...


class OutputGeneratorContract(Protocol):
    def to_excel(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        ...

    def to_csv(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        ...

    def to_json(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        ...
