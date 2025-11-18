"""Typed objects used across ingestion modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..models import APIMetadata, AttachmentMetadata


@dataclass
class DateRange:
    start: str
    end: str


@dataclass
class SamIngestionRequest:
    solicitation_number: str
    date_range: DateRange


@dataclass
class CanadaIngestionRequest:
    reference_number: str


@dataclass
class TenderIngestionResult:
    api_metadata: APIMetadata
    attachments: List[AttachmentMetadata] = field(default_factory=list)


@dataclass
class TenderIngestionRequest:
    country: str
    source_system: str
    solicitation_number: Optional[str] = None
    reference_number: Optional[str] = None
    date_range: Optional[DateRange] = None
