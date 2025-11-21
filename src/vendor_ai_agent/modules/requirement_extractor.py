"""LLM-powered tender requirement extraction."""
from __future__ import annotations

from typing import List, Optional

from ..contracts import RequirementExtractorContract
from ..models import (
    APIMetadata,
    DocExtracted,
    DocSections,
    DynamicTenderContext,
    StructuredDocData,
    TenderProfile,
    TenderSection,
    VendorCapabilityProfile,
)
from .document_processing import FieldExtractor, SectionExtractor
from .tender_profiler import LLMProvider, TenderProfiler


class RequirementExtractor(RequirementExtractorContract):
    """Transforms parsed sections into a structured tender profile."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.profiler = TenderProfiler(llm_provider)
        self.llm_provider = llm_provider

    def extract(
        self, sections: List[TenderSection], base_profile: Optional[TenderProfile] = None
    ) -> TenderProfile:
        """Return a skeletal TenderProfile from provided sections.

        Real implementation will call GPT models with carefully engineered
        prompts and post-process outputs.
        """

        combined_scope = "\n\n".join(section.content for section in sections)
        doc_sections = SectionExtractor().extract(sections)
        
        # Generate dynamic tender context from raw sections (smart filtering)
        tender_context_data = self.profiler.generate_context(sections)
        
        dynamic_context = DynamicTenderContext(
            sector=tender_context_data.sector,
            industry_description=tender_context_data.industry_description,
            technical_keywords=tender_context_data.technical_keywords,
            search_terms=tender_context_data.search_terms,
        )
        
        # Pass dynamic keywords and LLM provider to field extractor
        structured = FieldExtractor(
            dynamic_keywords=tender_context_data.technical_keywords,
            llm_provider=self.llm_provider
        ).extract(doc_sections, sections)
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
        profile.dynamic_context = dynamic_context
        return profile
