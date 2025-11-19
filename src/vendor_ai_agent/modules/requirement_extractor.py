"""LLM-powered tender requirement extraction."""
from __future__ import annotations

from typing import List, Optional

from ..contracts import RequirementExtractorContract
from ..models import (
    APIMetadata,
    DocExtracted,
    DocSections,
    StructuredDocData,
    TenderProfile,
    TenderSection,
    VendorCapabilityProfile,
)
from .document_processing import FieldExtractor, SectionExtractor


class RequirementExtractor(RequirementExtractorContract):
    """Transforms parsed sections into a structured tender profile."""

    def extract(
        self, sections: List[TenderSection], base_profile: Optional[TenderProfile] = None
    ) -> TenderProfile:
        """Return a skeletal TenderProfile from provided sections.

        Real implementation will call GPT models with carefully engineered
        prompts and post-process outputs.
        """

        combined_scope = "\n\n".join(section.content for section in sections)
        doc_sections = SectionExtractor().extract(sections)
        structured = FieldExtractor().extract(doc_sections, sections)
        doc_extracted = DocExtracted(sections=doc_sections, structured=structured)
        vendor_profile = VendorCapabilityProfile(summary="Placeholder vendor profile")
        profile = base_profile or TenderProfile(
            tender_id=None,
            country=None,
            source_system="MANUAL",
            api_metadata=APIMetadata(),
        )
        profile.doc_extracted = doc_extracted
        profile.vendor_capability_profile = vendor_profile
        return profile
