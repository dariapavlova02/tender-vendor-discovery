from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import LLMConfig


@dataclass
class TenderContext:
    sector: str
    industry_description: str
    technical_keywords: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    gsin_codes: List[str] = field(default_factory=list)
    unspsc_codes: List[str] = field(default_factory=list)
    province: Optional[str] = None
    country: Optional[str] = None


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, response_format: Optional[str] = None, model: Optional[str] = None) -> str:
        pass


class TenderProfiler:
    HIGH_PRIORITY_KEYWORDS = [
        "scope of work", "specifications", "technical specifications",
        "requirements", "deliverables", "commodity", "line item",
        "pricing form", "statement of work", "technical requirements",
        "product specifications", "service specifications", "materials",
        "equipment", "supply", "delivery", "schedule of requirements"
    ]
    
    LOW_PRIORITY_KEYWORDS = [
        "instruction to bidders", "submission instructions", "definitions",
        "legal", "insurance", "etendering", "portal", "how to bid",
        "submission process", "terms and conditions", "general conditions",
        "payment terms", "invoicing", "contract award", "evaluation criteria"
    ]
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.llm_config = LLMConfig()  # Load LLM config for smart model selection

    def _classify_section(self, section: Any) -> str:
        title = getattr(section, "title", "").lower()
        content_preview = getattr(section, "content", "")[:200].lower()
        
        combined = f"{title} {content_preview}"
        
        for keyword in self.HIGH_PRIORITY_KEYWORDS:
            if keyword in combined:
                return "gold"
        
        for keyword in self.LOW_PRIORITY_KEYWORDS:
            if keyword in combined:
                return "junk"
        
        return "neutral"
    
    def _assemble_smart_context(self, sections: List[Any], max_chars: int = 8000) -> str:
        gold_sections = []
        neutral_sections = []
        
        for section in sections:
            classification = self._classify_section(section)
            
            if classification == "gold":
                gold_sections.append(section)
            elif classification == "neutral":
                neutral_sections.append(section)
        
        context_parts = []
        current_length = 0
        
        for section in gold_sections:
            content = getattr(section, "content", "")
            title = getattr(section, "title", "")
            
            section_text = f"\n\n## {title}\n{content}" if title else f"\n\n{content}"
            
            if current_length + len(section_text) > max_chars:
                break
            
            context_parts.append(section_text)
            current_length += len(section_text)
        
        if current_length < max_chars // 2 and neutral_sections:
            for section in neutral_sections:
                content = getattr(section, "content", "")
                title = getattr(section, "title", "")
                
                section_text = f"\n\n## {title}\n{content}" if title else f"\n\n{content}"
                
                if current_length + len(section_text) > max_chars:
                    break
                
                context_parts.append(section_text)
                current_length += len(section_text)
        
        if not context_parts and sections:
            fallback = ""
            for section in sections[:5]:
                content = getattr(section, "content", "")
                fallback += content + "\n\n"
                if len(fallback) >= 2000:
                    break
            return fallback[:2000]
        
        return "".join(context_parts)

    def generate_context(self, raw_sections: List[Any], max_tokens: int = 3000) -> TenderContext:
        if not self.llm_provider:
            self.logger.warning("No LLM provider configured, returning empty context")
            return TenderContext(
                sector="Unknown",
                industry_description="LLM provider not configured",
                technical_keywords=[],
                search_terms=[],
            )
        
        smart_context = self._assemble_smart_context(raw_sections, max_chars=max_tokens * 4)
        
        if not smart_context.strip():
            self.logger.warning("No relevant context assembled, returning empty context")
            return TenderContext(
                sector="Unknown",
                industry_description="No relevant sections found",
                technical_keywords=[],
                search_terms=[],
            )
        
        scope_excerpt = smart_context[:max_tokens * 4]

        prompt = f"""SYSTEM ROLE:
Act as a procurement market analyst. Use only the provided scope excerpt. Never invent agencies, geographies, or product lines not present in the text.

OUTPUT REQUIREMENTS:
1. sector: concise label describing the procurement vertical.
2. industry_description: exactly 2 sentences (<=60 words total) summarizing what the buyer needs.
3. technical_keywords: return exactly 15 unique keywords ordered from most specific to most general; prioritize terms buyers would use to screen vendors.
4. search_terms: return exactly 20 HIGHLY DIVERSE search strings WITHOUT geographic qualifiers. 
   
   ⚠️ CRITICAL CONSTRAINT: NO WORD (except industry names) may appear >3 times across all 20 queries. Count carefully!
   ⚠️ FORBIDDEN OVERUSED WORDS: "equipment" >3, "device" >3, "supplier" >3, "supply/supplies" >3, "vendor" >3 = OUTPUT FAILS.
   ⚠️ WORD ALTERNATIVES: Instead of repeating, use: machinery, apparatus, tools, systems, technology, instruments, gear, solutions, products, goods, materials, resources.
   
   MANDATORY DISTRIBUTION:
   - Specificity: 6 highly specific (30%) + 8 medium (40%) + 6 broad (30%)
     * Highly specific: Named products like "ICU ventilator", "surgical sutures", "MRI scanners"
     * Medium: Product categories like "respiratory care", "wound care", "diagnostic imaging"  
     * Broad: Sectors like "medical technology", "healthcare services", "clinical solutions"
   - Business types: 7 manufacturers/OEM (35%) + 3 distributors (15%) + 6 services (30%) + 2 consultants (10%) + 2 integrators/VAR (10%)
   
   Diversity dimensions to vary:
   - Product specificity: Narrow specialties ("ventilator manufacturers") → Medium categories ("respiratory care") → Broad sectors ("medical technology")
   - Business models: manufacturers, distributors, wholesalers, service providers, consultants, installers, integrators, resellers
   - Market segments: Commercial vendors, government contractors, institutional suppliers, retail distributors
   - Technical approaches: Traditional suppliers, innovative technology vendors, specialized niche providers, integrated solution providers
   - Supply chain roles: OEMs, authorized distributors, value-added resellers, maintenance providers, logistics specialists
   
   Examples: "ammunition manufacturer", "ballistic vest OEM", "tactical gear distributor", "law enforcement installer", "firearms training services"
5. gsin_codes / unspsc_codes: include only codes explicitly present in the text; otherwise return empty arrays.
6. province: two-letter Canadian province/territory if clearly stated, else null.
7. country: choose "USA" or "Canada" only if one set of indicators clearly dominates (see below). If signals conflict or are missing, return null. Use cues such as agencies (DHS vs PSPC), regulatory references (FAR vs SACC), and postal conventions.
8. confidence: float between 0 and 1 (two decimals) reflecting how certain you are about sector + geography (1.0 = explicit statements, 0.3 = inferred/weak).

ADDITIONAL RULES:
- Scope excerpt truncated to {len(scope_excerpt)} characters; if critical data is missing, state "unknown" or null accordingly.
- Sort keywords/search terms deterministically so downstream systems can rely on order.
- For search_terms, apply strict ANTI-DUPLICATION rules to prevent wasting API credits:
  1. WORD FREQUENCY CAP (CRITICAL): Before finalizing, COUNT how many times each word appears. If "equipment" appears 4+ times → FAIL. If "device" appears 4+ times → FAIL. Replace with alternatives: machinery, apparatus, tools, systems, technology, instruments, gear, solutions.
  2. NO SYNONYMS: Avoid "medical equipment" + "medical devices" + "healthcare supplies" → choose ONE most relevant term
  3. VARY BUSINESS TYPES: Must hit distribution: 7 manufacturers/OEM + 3 distributors + 6 services + 2 consultants + 2 integrators
  4. VARY SPECIFICITY: Must hit distribution: 6 highly specific + 8 medium + 6 broad
  5. MAP TO TENDER NEEDS: If tender requires equipment + maintenance + training, create SEPARATE queries for each (don't lump into generic "equipment supplier")
  6. OVERLAP TEST: Mentally check if 2 queries would return >70% same companies → if yes, MERGE into 1 more specific query or DROP the less relevant one
  7. USE SPECIFIC PRODUCT NAMES: Instead of "portable X-ray equipment", use "mobile radiography systems" or "digital X-ray solutions"
- If both USA and Canada cues exist with similar strength, set country=null and explain uncertainty in industry_description sentence 2.
- Return JSON only, matching this schema.

SEARCH_TERMS QUALITY EXAMPLES:

BAD - Word repetition (redundant, waste API credits):
❌ "medical equipment distributors"
❌ "portable X-ray equipment manufacturers"  
❌ "hospital equipment authorized distributors"
❌ "surgical equipment manufacturers"
❌ "biomedical equipment installation services"
→ Problem: "equipment" appears 5 times. Limit: 3 max. Use alternatives: systems, technology, instruments, apparatus, tools, machinery.

BAD - "device" overuse:
❌ "medical device suppliers"
❌ "diagnostic device manufacturers"  
❌ "monitoring device OEM"
❌ "emergency device distributors"
→ Problem: "device" appears 4 times. Use alternatives: systems, instruments, units, solutions.

GOOD - Diverse vocabulary (unique vendor segments):
✓ "ICU ventilator manufacturers"              (specific product name, no generic words)
✓ "hospital supply chain consultants"         (service, not product)
✓ "biomedical installation services"          (service, different terminology)
✓ "diagnostic imaging OEM"                    (category + role, no "equipment"/"device")
✓ "healthcare facilities maintenance"         (service, no product words)
✓ "patient monitoring systems integrator"     (uses "systems" not "equipment")
✓ "surgical instrument distributors"          (uses "instrument" not "equipment")
✓ "mobile radiography solutions manufacturers"(uses "solutions" not "equipment")
✓ "critical care technology VAR"              (uses "technology" not "equipment")

Scope Excerpt:
{scope_excerpt}

Return strict JSON:
{{
  "sector": "...",
  "industry_description": "Sentence 1. Sentence 2",
  "technical_keywords": ["keyword_1", "keyword_2", "keyword_3", "...15"],
  "search_terms": ["query 1", "query 2", "...", "query 20"],
  "gsin_codes": ["1234"],
  "unspsc_codes": ["12345678"],
  "province": "ON" or null,
  "country": "USA" or "Canada" or null,
  "confidence": 0.78
}}"""

        content = None
        try:
            # Use SMART model (gpt-5.1) for query generation - higher quality search terms
            # justify API cost by reducing Serper duplicate queries (saves $0.025+ per tender)
            self.logger.info(f"Using smart model ({self.llm_config.smart_model}) for search_terms generation")
            content = self.llm_provider.generate(prompt, response_format="json", model=self.llm_config.smart_model)
            self.logger.debug(f"LLM response length: {len(content)} chars")
            
            data = json.loads(content)
            
            sector = data.get("sector", "Unknown")
            keywords = data.get("technical_keywords", [])
            search_terms = data.get("search_terms", [])
            
            if sector == "Unknown" or not keywords:
                self.logger.warning(
                    f"LLM returned incomplete data: sector={sector}, "
                    f"keywords={len(keywords)}, search_terms={len(search_terms)}"
                )
                self.logger.debug(f"LLM raw response: {content[:500]}")
            
            return TenderContext(
                sector=sector,
                industry_description=data.get("industry_description", ""),
                technical_keywords=keywords,
                search_terms=search_terms,
                gsin_codes=data.get("gsin_codes", []),
                unspsc_codes=data.get("unspsc_codes", []),
                province=data.get("province"),
                country=data.get("country"),
            )
        
        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse LLM JSON response: {exc}")
            if content:
                self.logger.debug(f"Raw LLM output: {content[:1000]}")
            return TenderContext(
                sector="Unknown",
                industry_description="Failed to parse LLM response",
                technical_keywords=[],
                search_terms=[],
            )
        except Exception as exc:
            self.logger.error(f"Failed to generate tender context: {exc}")
            return TenderContext(
                sector="Unknown",
                industry_description="Failed to analyze tender scope",
                technical_keywords=[],
                search_terms=[],
            )

    def generate_context_from_text(self, scope_text: str, max_tokens: int = 3000) -> TenderContext:
        @dataclass
        class TextSection:
            content: str
            title: str = ""
        
        sections = [TextSection(content=scope_text)]
        return self.generate_context(sections, max_tokens)
    
    def generate_context_from_sections(
        self, 
        scope_of_work: str, 
        technical_requirements: str = "", 
        max_tokens: int = 3000
    ) -> TenderContext:
        combined_text = f"{scope_of_work}\n\n{technical_requirements}"
        return self.generate_context_from_text(combined_text, max_tokens)
