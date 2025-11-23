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
        ][:self.config.max_llm_evaluations]
        
        llm_eligible_set = set(id(v) for v in llm_eligible_vendors)
        
        if self.config.enable_llm_assessment and llm_eligible_vendors and self.llm_provider:
            self.logger.info(
                f"LLM assessment: {len(llm_eligible_vendors)} vendors with website content "
                f"(limited to {self.config.max_llm_evaluations})"
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
        rationale = self._generate_rationale(vendor, project_type)
        
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
        parts = []
        
        if profile.doc_extracted:
            structured = profile.doc_extracted.structured
            
            if structured.project_type:
                parts.append(f"Project Type: {structured.project_type}")
            
            if structured.sector:
                parts.append(f"Sector: {structured.sector}")
            
            sections = profile.doc_extracted.sections
            
            if sections.scope_of_work:
                parts.append(f"Scope: {sections.scope_of_work[:500]}")
            
            if sections.technical_requirements:
                parts.append(f"Technical: {sections.technical_requirements[:500]}")
            
            if sections.mandatory_requirements:
                parts.append(f"Mandatory: {sections.mandatory_requirements[:500]}")
        
        if profile.dynamic_context:
            if profile.dynamic_context.sector:
                parts.append(f"Industry: {profile.dynamic_context.sector}")
            
            if profile.dynamic_context.technical_keywords:
                keywords = ", ".join(profile.dynamic_context.technical_keywords[:10])
                parts.append(f"Keywords: {keywords}")
        
        if not parts:
            parts.append("General government procurement")
        
        return "\n\n".join(parts)[:2000]
    
    def _calculate_score(self, vendor: VendorRecord) -> float:
        base_score = 50.0
        
        if "high_value_supplier" in vendor.enrichment_flags:
            base_score += 20.0
        
        if "frequent_supplier" in vendor.enrichment_flags:
            base_score += 15.0
        
        if vendor.is_past_winner:
            base_score += 10.0
        
        if vendor.source == "canada_contracts":
            base_score += 5.0
        
        return min(base_score, 100.0)
    
    def _generate_rationale(self, vendor: VendorRecord, project_type: str | None) -> str:
        parts = [f"{vendor.company_name}"]
        
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
