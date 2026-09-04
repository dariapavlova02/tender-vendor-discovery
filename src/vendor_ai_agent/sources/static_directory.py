"""Explicitly fictional vendor source for local adapter experiments."""
from __future__ import annotations

from typing import List

from ..models import TenderProfile, VendorRecord
from .base import BaseVendorSource


class StaticDirectorySource(BaseVendorSource):
    """Generates deterministic vendor entries to validate orchestration."""

    def __init__(self) -> None:
        super().__init__(name="static_directory")

    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        # Try to use dynamic context search terms first
        if profile.dynamic_context and profile.dynamic_context.search_terms:
            # Use the first search term as the keyword
            keyword = profile.dynamic_context.search_terms[0].lower().replace(" ", "-")
        else:
            # Fall back to project type from structured data
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
