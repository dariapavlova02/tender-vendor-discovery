"""LLM-backed capability scoring of vendors."""
from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional

from ..config import CapabilityMatchingConfig
from ..contracts import CapabilityMatcherContract
from ..models import TenderProfile, VendorMatchResult, VendorRecord
from .tender_profiler import LLMProvider


class CapabilityMatcher(CapabilityMatcherContract):
    """Assigns scores and rationales to vendors based on contract history and capabilities."""

    def __init__(
        self, 
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[CapabilityMatchingConfig] = None,
    ):
        self.llm_provider = llm_provider
        self.config = config or CapabilityMatchingConfig()
        self.logger = logging.getLogger(__name__)

    def score(self, profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorMatchResult]:
        """Score vendors based on contract history, enrichment flags, and LLM assessment."""

        results: List[VendorMatchResult] = []
        vendor_list = list(vendors)
        
        llm_eligible_vendors = [
            v for v in vendor_list 
            if "website_content" in v.filtering_metadata
        ]
        
        llm_eligible_set = set(id(v) for v in llm_eligible_vendors)
        
        if self.config.enable_llm_assessment and llm_eligible_vendors and self.llm_provider:
            self.logger.info(
                f"LLM assessment: {len(llm_eligible_vendors)} vendors with website content available for evaluation"
            )
        
        for vendor in vendor_list:
            if (
                self.config.enable_llm_assessment 
                and id(vendor) in llm_eligible_set 
                and self.llm_provider
            ):
                try:
                    llm_result = self._llm_assess_capability(profile, vendor)
                    results.append(llm_result)
                except Exception as exc:
                    self.logger.warning(
                        f"LLM assessment failed for {vendor.company_name}: {exc}, "
                        f"falling back to rule-based"
                    )
                    if self.config.fallback_to_rule_based:
                        results.append(self._rule_based_score(profile, vendor))
            else:
                results.append(self._rule_based_score(profile, vendor))
        
        results.sort(key=lambda x: x.capability_match_score, reverse=True)
        return results
    
    def _rule_based_score(self, profile: TenderProfile, vendor: VendorRecord) -> VendorMatchResult:
        project_type = profile.doc_extracted.structured.project_type if profile.doc_extracted else None
        
        score = self._calculate_score(vendor)
        
        naics_similarity = self._calculate_naics_similarity(profile, vendor)
        naics_boost = naics_similarity * 20.0
        score += naics_boost
        
        score = min(score, 100.0)
        
        rationale = self._generate_rationale(vendor, project_type, naics_similarity)
        
        return VendorMatchResult(
            vendor=vendor,
            capability_match_score=score,
            rationale=rationale,
            references=[vendor.website or ""],
        )
    
    def _llm_assess_capability(self, profile: TenderProfile, vendor: VendorRecord) -> VendorMatchResult:
        website_content = vendor.filtering_metadata.get("website_content", "")
        content_source = vendor.filtering_metadata.get("content_source", vendor.website or "")
        
        tender_requirements = self._build_tender_requirements_summary(profile)
        
        prompt = f"""You are evaluating whether a vendor is qualified for a government contract.

TENDER REQUIREMENTS:
{tender_requirements}

VENDOR INFORMATION:
Company: {vendor.company_name}
Website: {content_source}
Location: {vendor.location or "Unknown"}

VENDOR CAPABILITIES (from website):
{website_content[:2500]}

CONTRACT HISTORY:
- Past winner: {vendor.is_past_winner}
- Total contract value: ${vendor.total_contract_value or 0:,.0f}
- Contract count: {vendor.contract_count or 0}
- Enrichment flags: {", ".join(vendor.enrichment_flags) if vendor.enrichment_flags else "None"}

TASK:
1. Assess this vendor's capability match for the tender requirements (0-100 score)
2. Provide a one-sentence rationale with specific evidence from the vendor's capabilities
3. Ground your assessment in the provided vendor information - do not hallucinate

Return valid JSON:
{{
  "score": 85,
  "rationale": "Specializes in tactical uniforms with 20+ years DHS experience and in-house manufacturing"
}}"""
        
        try:
            response = self.llm_provider.generate(
                prompt, 
                response_format="json",
                model=self.config.llm_model
            )
            
            data = json.loads(response)
            score = float(data.get("score", 50))
            rationale = data.get("rationale", f"{vendor.company_name} - LLM assessment")
            
            score = max(0.0, min(100.0, score))
            
            self.logger.debug(f"LLM scored {vendor.company_name}: {score}/100")
            
            return VendorMatchResult(
                vendor=vendor,
                capability_match_score=score,
                rationale=rationale,
                references=[content_source],
            )
        
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            self.logger.error(f"Failed to parse LLM response for {vendor.company_name}: {exc}")
            raise
    
    def _build_tender_requirements_summary(self, profile: TenderProfile) -> str:
        """
        Build tender requirements with intelligent adaptive fallback.
        
        Strategy:
        1. Calculate information density of structured sections
        2. Adaptively supplement with dynamic_context based on density
        3. Auto-scale keyword count based on available data richness
        4. Universal for US/Canada tenders - no hardcoded assumptions
        """
        parts = []
        structured_sections = []
        
        if profile.doc_extracted:
            structured = profile.doc_extracted.structured
            
            if structured.project_type:
                parts.append(f"Project Type: {structured.project_type}")
            
            if structured.sector:
                parts.append(f"Sector: {structured.sector}")
            
            sections = profile.doc_extracted.sections
            
            if sections.scope_of_work:
                structured_sections.append(("Scope", sections.scope_of_work))
            
            if sections.technical_requirements:
                structured_sections.append(("Technical", sections.technical_requirements))
            
            if sections.mandatory_requirements:
                structured_sections.append(("Mandatory", sections.mandatory_requirements))
        
        total_section_content = sum(len(content) for _, content in structured_sections)
        has_dynamic_context = (
            profile.dynamic_context and 
            profile.dynamic_context.technical_keywords and 
            len(profile.dynamic_context.technical_keywords) > 0
        )
        
        if total_section_content > 1500:
            section_budget = 600
        elif total_section_content > 0:
            section_budget = 500
        else:
            section_budget = 0
        
        for label, content in structured_sections:
            parts.append(f"{label}: {content[:section_budget]}")
        
        if has_dynamic_context:
            dctx = profile.dynamic_context
            
            info_gap_ratio = 1.0 - min(total_section_content / 1500.0, 1.0)
            
            if info_gap_ratio > 0.3 and dctx.industry_description:
                parts.append(f"Industry Context: {dctx.industry_description}")
            
            if dctx.sector:
                has_sector_info = any(
                    "Sector:" in p or "Industry:" in p 
                    for p in parts
                )
                if not has_sector_info or info_gap_ratio > 0.5:
                    parts.append(f"Domain: {dctx.sector}")
            
            keyword_count = 0
            if dctx.technical_keywords:
                base_keywords = 10
                bonus_keywords = int(info_gap_ratio * 15)
                keyword_count = min(base_keywords + bonus_keywords, len(dctx.technical_keywords))
                
                keywords = ", ".join(dctx.technical_keywords[:keyword_count])
                
                if info_gap_ratio > 0.5:
                    keyword_label = "Required Capabilities"
                else:
                    keyword_label = "Keywords"
                
                parts.append(f"{keyword_label}: {keywords}")
            
            if info_gap_ratio > 0.5 and dctx.search_terms:
                search_count = min(5, len(dctx.search_terms))
                search_terms = ", ".join(dctx.search_terms[:search_count])
                parts.append(f"Vendor Search Terms: {search_terms}")
            
            if dctx.gsin_codes:
                gsin = ", ".join(dctx.gsin_codes[:3])
                parts.append(f"GSIN Codes: {gsin}")
            
            if dctx.unspsc_codes:
                unspsc = ", ".join(dctx.unspsc_codes[:3])
                parts.append(f"UNSPSC: {unspsc}")
            
            if info_gap_ratio > 0.7:
                self.logger.info(
                    f"High information gap ({info_gap_ratio:.1%}) - enriching with "
                    f"{keyword_count} keywords + search terms"
                )
            elif info_gap_ratio > 0.3:
                self.logger.debug(
                    f"Medium information gap ({info_gap_ratio:.1%}) - moderate enrichment"
                )
        
        if not parts:
            parts.append("General government procurement")
        
        if len(parts) > 6:
            char_limit = 2500
        elif len(parts) > 3:
            char_limit = 2000
        else:
            char_limit = 1500
        
        result = "\n\n".join(parts)[:char_limit]
        
        self.logger.debug(
            f"Built tender summary: {len(result)} chars, "
            f"{len(parts)} sections, "
            f"structured_content={total_section_content} chars"
        )
        
        return result
    
    def _calculate_naics_similarity(self, profile: TenderProfile, vendor: VendorRecord) -> float:
        if not profile.doc_extracted or not profile.doc_extracted.structured.naics_codes:
            return 0.0
        
        vendor_naics_list = vendor.filtering_metadata.get("naics_codes", [])
        if not vendor_naics_list:
            return 0.0
        
        tender_naics = set(profile.doc_extracted.structured.naics_codes)
        vendor_naics = set(vendor_naics_list)
        
        if tender_naics & vendor_naics:
            return 1.0
        
        tender_prefixes = {code[:4] for code in tender_naics if len(code) >= 4}
        vendor_prefixes = {code[:4] for code in vendor_naics if len(code) >= 4}
        
        if tender_prefixes & vendor_prefixes:
            return 0.7
        
        tender_sectors = {code[:2] for code in tender_naics if len(code) >= 2}
        vendor_sectors = {code[:2] for code in vendor_naics if len(code) >= 2}
        
        if tender_sectors & vendor_sectors:
            return 0.4
        
        return 0.0
    
    def _calculate_score(self, vendor: VendorRecord) -> float:
        if vendor.website and vendor.filtering_metadata.get("website_content"):
            base_score = 45.0
        elif vendor.website:
            base_score = 35.0
        else:
            base_score = 25.0
        
        if "high_value_supplier" in vendor.enrichment_flags:
            base_score += 20.0
        
        if "frequent_supplier" in vendor.enrichment_flags:
            base_score += 15.0
        
        if vendor.is_past_winner:
            base_score += 10.0
        
        if vendor.source == "canada_contracts":
            base_score += 5.0
        
        if not vendor.email and not vendor.phone and not vendor.primary_contact:
            base_score -= 10.0
        
        return min(base_score, 100.0)
    
    def _generate_rationale(self, vendor: VendorRecord, project_type: str | None, naics_similarity: float) -> str:
        parts = [f"{vendor.company_name}"]
        
        if naics_similarity >= 0.7:
            parts.append("industry match (NAICS aligned)")
        
        if "high_value_supplier" in vendor.enrichment_flags:
            parts.append("extensive contract history (>$100M CAD)")
        
        if "frequent_supplier" in vendor.enrichment_flags:
            parts.append("frequent government supplier (>50 contracts)")
        
        if vendor.is_past_winner:
            parts.append("proven government contractor")
        
        if vendor.location:
            parts.append(f"located in {vendor.location}")
        
        if project_type:
            parts.append(f"for {project_type} requirements")
        
        return " - ".join(parts) + "."
