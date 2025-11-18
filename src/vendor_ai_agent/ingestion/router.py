"""Routes ingestion requests to country-specific ingestors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import RuntimeConfig
from .canada import CanadaBuysIngestor, CanadaCkanClient
from .models import (
    CanadaIngestionRequest,
    DateRange,
    SamIngestionRequest,
    TenderIngestionRequest,
    TenderIngestionResult,
)
from .sam import SamClient, UsSamIngestor


@dataclass
class TenderIngestionRouter:
    sam_ingestor: UsSamIngestor
    canada_ingestor: CanadaBuysIngestor

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "TenderIngestionRouter":
        sam_client = SamClient(config.sam_api.base_url)
        sam_ingestor = UsSamIngestor(sam_client, config.sam_api)
        canada_client = CanadaCkanClient(config.canada_open_data.base_url)
        canada_ingestor = CanadaBuysIngestor(canada_client, config.canada_open_data)
        return cls(sam_ingestor=sam_ingestor, canada_ingestor=canada_ingestor)

    def ingest(self, request: TenderIngestionRequest) -> TenderIngestionResult:
        source = (request.source_system or "").upper()
        country = (request.country or "").upper()
        if source == "SAM" or country == "USA":
            sam_request = self._build_sam_request(request)
            return self.sam_ingestor.ingest(sam_request)
        if source == "CANADABUYS" or country == "CAN":
            canada_request = self._build_canada_request(request)
            return self.canada_ingestor.ingest(canada_request)
        raise ValueError(f"Unsupported ingestion source: {request.source_system}")

    def _build_sam_request(self, request: TenderIngestionRequest) -> SamIngestionRequest:
        if not request.solicitation_number:
            raise ValueError("SAM ingestion requires solicitation_number")
        if not request.date_range:
            raise ValueError("SAM ingestion requires a date_range")
        return SamIngestionRequest(
            solicitation_number=request.solicitation_number,
            date_range=request.date_range,
        )

    def _build_canada_request(self, request: TenderIngestionRequest) -> CanadaIngestionRequest:
        if not request.reference_number:
            raise ValueError("CanadaBuys ingestion requires reference_number")
        return CanadaIngestionRequest(reference_number=request.reference_number)
