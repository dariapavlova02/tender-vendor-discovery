"""LLM-powered tender requirement extraction."""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from ..contracts import RequirementExtractorContract
from ..models import (
    APIMetadata,
    DocExtracted,
    DocSections,
    DynamicTenderContext,
    KeyRequirement,
    PlaceOfPerformance,
    StructuredDocData,
    TargetIndustryCodes,
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
            gsin_codes=tender_context_data.gsin_codes,
            unspsc_codes=tender_context_data.unspsc_codes,
            province=tender_context_data.province,
            country=tender_context_data.country,
            contract_type=tender_context_data.contract_type,
            contract_type_confidence=tender_context_data.contract_type_confidence,
            fulfillment_model=tender_context_data.fulfillment_model,
            primary_deliverables=tender_context_data.primary_deliverables,
            vendor_inputs=tender_context_data.vendor_inputs,
            location=tender_context_data.location,
        )
        
        # Pass dynamic keywords and LLM provider to field extractor
        structured = FieldExtractor(
            dynamic_keywords=tender_context_data.technical_keywords,
            llm_provider=self.llm_provider
        ).extract(doc_sections, sections)
        doc_extracted = DocExtracted(sections=doc_sections, structured=structured)
        vendor_profile = self._build_vendor_capability_profile(
            doc_sections=doc_sections,
            structured=structured,
            tender_context=tender_context_data,
        )
        
        profile = base_profile or TenderProfile(
            tender_id=None,
            country=None,
            source_system="MANUAL",
            api_metadata=APIMetadata(),
        )
        profile.doc_extracted = doc_extracted
        profile.vendor_capability_profile = vendor_profile
        profile.dynamic_context = dynamic_context
        
        if structured.naics_codes:
            profile.api_metadata.codes.naics = structured.naics_codes
        
        if structured.location and structured.location.state_province:
            profile.api_metadata.place_of_performance = PlaceOfPerformance(
                city=structured.location.city,
                state_province=structured.location.state_province,
                country=structured.location.country or "United States"
            )
        
        return profile

    # ------------------------------------------------------------------
    def _build_vendor_capability_profile(
        self,
        *,
        doc_sections: DocSections,
        structured: StructuredDocData,
        tender_context,
    ) -> VendorCapabilityProfile:
        """Generate vendor capability profile using LLM with fallbacks."""

        fallback_profile = self._build_fallback_vendor_profile(doc_sections, structured)

        if not self.llm_provider:
            return fallback_profile

        try:
            payload = self._extract_capabilities_with_llm(
                doc_sections=doc_sections,
                tender_context=tender_context,
                structured=structured,
            )
        except Exception as exc:  # noqa: BLE001 - downstream logging already includes context
            logging.warning("LLM capability extraction failed: %s", exc)
            return fallback_profile

        if not payload:
            return fallback_profile

        summary = payload.get("summary") or fallback_profile.summary
        key_requirements = self._parse_key_requirements(payload.get("key_requirements", []))
        if not key_requirements:
            key_requirements = fallback_profile.key_requirements

        target_codes_payload = payload.get("target_codes", {}) or {}
        target_codes = self._merge_target_codes(
            structured_codes=structured.naics_codes,
            context_codes=tender_context,
            llm_codes=target_codes_payload,
        )

        return VendorCapabilityProfile(
            summary=summary,
            key_requirements=key_requirements,
            target_industry_codes=target_codes,
        )

    def _build_fallback_vendor_profile(
        self, doc_sections: DocSections, structured: StructuredDocData
    ) -> VendorCapabilityProfile:
        summary_source = (
            doc_sections.scope_of_work
            or doc_sections.technical_requirements
            or doc_sections.mandatory_requirements
        )
        summary = (summary_source or "General government procurement").strip()
        summary = summary[:600]

        key_requirements: List[KeyRequirement] = []
        counter = 1

        if structured.required_experience and structured.required_experience.min_years:
            key_requirements.append(
                KeyRequirement(
                    requirement_id=f"REQ-{counter:03d}",
                    type="experience",
                    description=(
                        f"Minimum {structured.required_experience.min_years} years of relevant project experience"
                    ),
                    must_have=True,
                )
            )
            counter += 1

        if structured.required_licenses:
            key_requirements.append(
                KeyRequirement(
                    requirement_id=f"REQ-{counter:03d}",
                    type="license",
                    description=f"Licenses: {', '.join(structured.required_licenses[:5])}",
                    must_have=True,
                )
            )
            counter += 1

        if structured.required_certifications:
            key_requirements.append(
                KeyRequirement(
                    requirement_id=f"REQ-{counter:03d}",
                    type="certification",
                    description=f"Certifications: {', '.join(structured.required_certifications[:5])}",
                    must_have=True,
                )
            )
            counter += 1

        if not key_requirements and structured.technical_keywords:
            key_requirements.append(
                KeyRequirement(
                    requirement_id=f"REQ-{counter:03d}",
                    type="capability",
                    description=f"Capabilities: {', '.join(structured.technical_keywords[:6])}",
                    must_have=False,
                )
            )

        target_codes = TargetIndustryCodes(
            naics=list(structured.naics_codes or []),
            gsin=[],
            unspsc=[],
        )

        return VendorCapabilityProfile(
            summary=summary,
            key_requirements=key_requirements,
            target_industry_codes=target_codes,
        )

    def _extract_capabilities_with_llm(
        self,
        *,
        doc_sections: DocSections,
        tender_context,
        structured: StructuredDocData,
    ) -> dict:
        if not self.llm_provider:
            return {}

        sections_payload = self._build_section_context(doc_sections)
        context_summary = self._build_context_summary(tender_context)

        prompt = f"""SYSTEM ROLE:
Act as a procurement requirements auditor. Use only the provided context summary and tender sections. Never reuse the sample JSON values or infer data that is absent.

CONTEXT SUMMARY:
{context_summary}

EXISTING NAICS CODES (for reference only, add new ones only if they appear verbatim in the sections): {structured.naics_codes or []}

TENDER SECTIONS:
{sections_payload}

INSTRUCTIONS:
- Summarize what the buyer needs in <=2 sentences (<=50 words).
- Extract at most 8 unique key requirements. Merge duplicates and normalize types to one of: capability | experience | license | certification | logistics | compliance.
- Each key requirement must include: id (REQ-###), description, must_have (true/false), source_section (MANDATORY | TECHNICAL | SCOPE | QUALIFICATIONS | OTHER), and an evidence snippet (<=20 words quoting/paraphrasing the source text).
- Treat words like "must/shall" as must_have=true; conditional or optional language becomes must_have=false.
- Only add NAICS/GSIN/UNSPSC codes that appear verbatim in the sections. Return them as arrays of strings. If none exist, return empty arrays.
- Anything not present in the text must be null or an empty array. Do NOT copy placeholder values from the example.

Return strict JSON ONLY:
{{
  "summary": "...",
  "key_requirements": [
    {{
      "id": "REQ-001",
      "type": "capability",
      "description": "...",
      "must_have": true,
      "source_section": "MANDATORY",
      "evidence": "\"Contractor shall provide ...\""
    }}
  ],
  "target_codes": {{
    "naics": ["codes that appear in text"],
    "gsin": [],
    "unspsc": []
  }}
}}"""

        response = self.llm_provider.generate(prompt, response_format="json")
        data = json.loads(response)
        if not isinstance(data, dict):
            raise ValueError("LLM capability payload is not a JSON object")
        return data

    def _build_section_context(self, doc_sections: DocSections) -> str:
        def trim(text: str, limit: int = 1000) -> str:
            if not text:
                return ""
            text = text.strip()
            return text[:limit]

        parts = []
        if doc_sections.scope_of_work:
            parts.append("SCOPE:\n" + trim(doc_sections.scope_of_work))
        if doc_sections.technical_requirements:
            parts.append("TECHNICAL:\n" + trim(doc_sections.technical_requirements))
        if doc_sections.mandatory_requirements:
            parts.append("MANDATORY:\n" + trim(doc_sections.mandatory_requirements))
        if doc_sections.vendor_qualifications:
            parts.append("VENDOR QUALIFICATIONS:\n" + trim(doc_sections.vendor_qualifications))

        return "\n\n".join(parts)[:3500]

    def _build_context_summary(self, tender_context) -> str:
        keywords = ", ".join(tender_context.technical_keywords[:10]) if tender_context else ""
        gsin = ", ".join(tender_context.gsin_codes[:5]) if tender_context else ""
        unspsc = ", ".join(tender_context.unspsc_codes[:5]) if tender_context else ""
        sector = tender_context.sector if tender_context else "Unknown"
        industry = tender_context.industry_description if tender_context else ""
        return (
            f"Sector: {sector}\n"
            f"Industry: {industry}\n"
            f"Keywords: {keywords}\n"
            f"GSIN: {gsin}\n"
            f"UNSPSC: {unspsc}"
        )

    def _parse_key_requirements(self, raw_requirements: List[dict]) -> List[KeyRequirement]:
        parsed: List[KeyRequirement] = []
        for idx, requirement in enumerate(raw_requirements or [], start=1):
            description = requirement.get("description")
            if not description:
                continue
            req_type = requirement.get("type", "capability")
            rid = requirement.get("id") or f"REQ-{idx:03d}"
            parsed.append(
                KeyRequirement(
                    requirement_id=rid,
                    type=req_type,
                    description=description.strip(),
                    must_have=bool(requirement.get("must_have", True)),
                )
            )
        return parsed

    def _merge_target_codes(
        self,
        *,
        structured_codes: List[str],
        context_codes,
        llm_codes: dict,
    ) -> TargetIndustryCodes:
        def unique(sequence: List[str]) -> List[str]:
            seen = set()
            result = []
            for item in sequence:
                if not item:
                    continue
                norm = item.strip()
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                result.append(norm)
            return result

        naics = unique((llm_codes.get("naics") or []) + (structured_codes or []))
        gsin = unique((llm_codes.get("gsin") or []) + (getattr(context_codes, "gsin_codes", []) or []))
        unspsc = unique((llm_codes.get("unspsc") or []) + (getattr(context_codes, "unspsc_codes", []) or []))

        return TargetIndustryCodes(naics=naics, gsin=gsin, unspsc=unspsc)
