"""LLM-backed capability scoring of vendors."""
from __future__ import annotations

import asyncio
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
        
        llm_results, llm_failures = self._assess_llm_parallel(profile, llm_eligible_vendors)
        llm_eligible_set = set(id(v) for v in llm_eligible_vendors)

        for vendor in vendor_list:
            if "website_content" not in vendor.filtering_metadata:
                reason = vendor.filtering_metadata.get("scrape_error") or "No website content available"
                vendor.filtering_metadata.setdefault("match_status", "needs_data")
                vendor.filtering_metadata.setdefault("match_reason", reason)
                continue

            vendor_key = id(vendor)
            if vendor_key in llm_results:
                results.append(llm_results[vendor_key])
                continue
            if vendor_key in llm_failures:
                if self.config.fallback_to_rule_based:
                    results.append(self._rule_based_score(profile, vendor))
                continue
            if (
                self.config.enable_llm_assessment
                and vendor_key in llm_eligible_set
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
    
    async def score_async(
        self, 
        profile: TenderProfile, 
        vendors: Iterable[VendorRecord]
    ) -> List[VendorMatchResult]:
        """Async score vendors with parallel LLM calls."""
        results: List[VendorMatchResult] = []
        vendor_list = list(vendors)
        
        llm_eligible_vendors = [
            v for v in vendor_list 
            if "website_content" in v.filtering_metadata
        ]
        
        for vendor in vendor_list:
            if "website_content" not in vendor.filtering_metadata:
                reason = vendor.filtering_metadata.get("scrape_error") or "No website content available"
                vendor.filtering_metadata.setdefault("match_status", "needs_data")
                vendor.filtering_metadata.setdefault("match_reason", reason)
        
        if not llm_eligible_vendors:
            return results
        
        if not (self.config.enable_llm_assessment and self.llm_provider):
            for vendor in llm_eligible_vendors:
                results.append(self._rule_based_score(profile, vendor))
            results.sort(key=lambda x: x.capability_match_score, reverse=True)
            return results
        
        from .llm_providers import AsyncOpenAIProvider
        if not isinstance(self.llm_provider, AsyncOpenAIProvider):
            self.logger.warning(
                "LLM provider is not async, falling back to sync scoring"
            )
            return self.score(profile, vendors)
        
        tasks = [
            self._llm_assess_capability_async(profile, vendor)
            for vendor in llm_eligible_vendors
        ]
        
        scored_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for vendor, result in zip(llm_eligible_vendors, scored_results):
            if isinstance(result, Exception):
                self.logger.warning(
                    f"LLM async assessment failed for {vendor.company_name}: {result}"
                )
                if self.config.fallback_to_rule_based:
                    results.append(self._rule_based_score(profile, vendor))
            else:
                results.append(result)
        
        results.sort(key=lambda x: x.capability_match_score, reverse=True)
        return results
    
    async def _llm_assess_capability_async(
        self, 
        profile: TenderProfile, 
        vendor: VendorRecord
    ) -> VendorMatchResult:
        """Async version of _llm_assess_capability."""
        website_content = vendor.filtering_metadata.get("website_content", "")
        content_source = vendor.filtering_metadata.get("content_source", vendor.website or "")
        
        tender_requirements = self._build_tender_requirements_summary(profile)
        
        prompt = f"""You are a product/service matching AI. Determine if this vendor SELLS what the tender needs.

RULES:
1. Website content = PRIMARY (80%), metadata = SECONDARY (20%)
2. Focus: What do they offer TODAY? Ignore past contracts as proof of capability.
3. Lobbying offices, associations, advocacy groups = score < 10 regardless of metadata

SCORING:
100-90: PERFECT - Sells exactly what tender needs
89-70: STRONG - Relevant products in same vertical
69-50: MODERATE - Related industry, potential capability
49-30: WEAK - Tangential relevance, major gaps
29-0: NO MATCH - Unrelated, lobbying office, or association

METADATA (apply AFTER scoring):
- Score ≥70 + past_winner: +5 | Score ≥60 + high_value_supplier: +5
- Score <50: ignore all metadata

EXAMPLES:

Ex1: Perfect Match
Tender: "Hospital beds" | Website: "MedEquip - hospital bed manufacturer"
→ Score: 95 | Rationale: "Band: Perfect Match — Evidence: 'hospital beds' in catalog"

Ex2: NO MATCH - Lobbying (prevent false positive!)
Tender: "Utility vehicles" | Website: "Natural Gas Vehicle Alliance - lobbying office"
Metadata: past_winner, $5.5M contracts
→ Score: 5 | Rationale: "Band: No Match — Evidence: 'lobbying office', not supplier"

Ex3: NO MATCH - Association (ignore metadata!)
Tender: "Ammunition" | Website: "Defense Contractors Assoc - advocacy group"
Metadata: past_winner, $10M, 50 contracts
→ Score: 8 | Rationale: "Band: No Match — Evidence: 'association', not supplier"

---
TENDER: {tender_requirements}

VENDOR: {vendor.company_name}
Website: {content_source}
Location: {vendor.location or "Unknown"}

CAPABILITIES: {website_content[:2500]}

METADATA (tie-breaking only):
Past winner: {vendor.is_past_winner} | Value: ${vendor.total_contract_value or 0:,.0f} | Count: {vendor.contract_count or 0}
Flags: {", ".join(vendor.enrichment_flags) if vendor.enrichment_flags else "None"}

Return JSON:
{{
  "score": 0,
  "rationale": "Band: [band] — Evidence: \"[quote]\"",
  "confidence": "high|medium|low"
}}"""
        
        try:
            response = await self.llm_provider.generate_async(
                prompt, 
                response_format="json",
                model=self.config.llm_model
            )
            
            data = json.loads(response)
            score = float(data.get("score", 50))
            rationale = data.get("rationale", f"{vendor.company_name} - LLM assessment")
            
            score = max(0.0, min(100.0, score))
            
            self.logger.debug(f"LLM async scored {vendor.company_name}: {score}/100")
            
            return VendorMatchResult(
                vendor=vendor,
                capability_match_score=score,
                rationale=rationale,
                references=[content_source],
            )
        
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            self.logger.error(f"Failed to parse async LLM response for {vendor.company_name}: {exc}")
            raise
    
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
        
        prompt = f"""You are a product/service matching AI. Determine if this vendor SELLS what the tender needs.

RULES:
1. Website content = PRIMARY (80%), metadata = SECONDARY (20%)
2. Focus: What do they offer TODAY? Ignore past contracts as proof of capability.
3. Lobbying offices, associations, advocacy groups = score < 10 regardless of metadata

SCORING:
100-90: PERFECT - Sells exactly what tender needs
89-70: STRONG - Relevant products in same vertical
69-50: MODERATE - Related industry, potential capability
49-30: WEAK - Tangential relevance, major gaps
29-0: NO MATCH - Unrelated, lobbying office, or association

METADATA (apply AFTER scoring):
- Score ≥70 + past_winner: +5 | Score ≥60 + high_value_supplier: +5
- Score <50: ignore all metadata

EXAMPLES:

Ex1: Perfect Match
Tender: "Hospital beds" | Website: "MedEquip - hospital bed manufacturer"
→ Score: 95 | Rationale: "Band: Perfect Match — Evidence: 'hospital beds' in catalog"

Ex2: NO MATCH - Lobbying (prevent false positive!)
Tender: "Utility vehicles" | Website: "Natural Gas Vehicle Alliance - lobbying office"
Metadata: past_winner, $5.5M contracts
→ Score: 5 | Rationale: "Band: No Match — Evidence: 'lobbying office', not supplier"

Ex3: NO MATCH - Association (ignore metadata!)
Tender: "Ammunition" | Website: "Defense Contractors Assoc - advocacy group"
Metadata: past_winner, $10M, 50 contracts
→ Score: 8 | Rationale: "Band: No Match — Evidence: 'association', not supplier"

---
TENDER: {tender_requirements}

VENDOR: {vendor.company_name}
Website: {content_source}
Location: {vendor.location or "Unknown"}

CAPABILITIES: {website_content[:2500]}

METADATA (tie-breaking only):
Past winner: {vendor.is_past_winner} | Value: ${vendor.total_contract_value or 0:,.0f} | Count: {vendor.contract_count or 0}
Flags: {", ".join(vendor.enrichment_flags) if vendor.enrichment_flags else "None"}

Return JSON:
{{
  "score": 0,
  "rationale": "Band: [band] — Evidence: \"[quote]\"",
  "confidence": "high|medium|low"
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

    def _assess_llm_parallel(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> tuple[dict[int, VendorMatchResult], set[int]]:
        if not (
            self.config.enable_llm_assessment
            and vendors
            and self.llm_provider
        ):
            return {}, set()

        parallelism = max(1, getattr(self.config, "llm_parallelism", 5))

        async def runner() -> tuple[dict[int, VendorMatchResult], set[int]]:
            results: dict[int, VendorMatchResult] = {}
            failures: set[int] = set()
            semaphore = asyncio.Semaphore(parallelism)

            async def run_for_vendor(vendor: VendorRecord) -> None:
                async with semaphore:
                    try:
                        result = await asyncio.to_thread(
                            self._llm_assess_capability, profile, vendor
                        )
                        results[id(vendor)] = result
                    except Exception as exc:  # noqa: BLE001
                        failures.add(id(vendor))
                        self.logger.warning(
                            "LLM assessment failed for %s (async batch): %s",
                            vendor.company_name,
                            exc,
                        )

            await asyncio.gather(*(run_for_vendor(v) for v in vendors))
            return results, failures

        try:
            return asyncio.run(runner())
        except RuntimeError:
            # If already inside an event loop, create a new nested loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(runner())
            finally:
                loop.close()
    
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
            parts.append("frequent supplier (>50 contracts)")
        
        if vendor.is_past_winner:
            parts.append("past contract experience")
        
        if vendor.location:
            parts.append(f"located in {vendor.location}")
        
        if project_type:
            parts.append(f"for {project_type} requirements")
        
        return " - ".join(parts) + "."
