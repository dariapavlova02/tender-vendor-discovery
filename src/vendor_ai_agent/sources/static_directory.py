"""Static vendor source placeholder for MVP wiring."""
from __future__ import annotations

from typing import List

from ..models import TenderProfile, VendorRecord
from .base import BaseVendorSource


class StaticDirectorySource(BaseVendorSource):
    """Generates deterministic vendor entries to validate orchestration."""

    def __init__(self) -> None:
        super().__init__(name="static_directory")

    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        project_type = profile.doc_extracted.structured.project_type if profile.doc_extracted else None
        keyword = (project_type or "General Contractor").lower().replace(" ", "-")
        return [
            VendorRecord(
                company_name=f"{keyword.title()} Vendor {i}",
                website=None,
                source=self.name,
            )
            for i in range(1, 6)
        ]
