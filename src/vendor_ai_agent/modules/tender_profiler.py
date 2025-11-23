from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    def generate(self, prompt: str, response_format: Optional[str] = None) -> str:
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
        
        prompt = f"""Analyze the following tender scope and extract:

1. The specific industry sector (e.g., "Ammunition Supply", "Construction", "IT Services", "Medical Equipment", "Vehicle Supply", "Food Services")
2. A brief industry description (1-2 sentences)
3. A list of 15-20 technical keywords critical for finding qualified vendors
4. A list of 5-10 search terms optimized for finding vendors (e.g., "ammunition suppliers ontario", "frangible bullet manufacturers")
5. Canadian GSIN codes (2, 4, or 6 digit goods/services identification numbers) if mentioned
6. UNSPSC codes (8-digit universal product/service codes) if mentioned
7. Canadian province/territory if this is a Canadian procurement (ON, QC, BC, AB, MB, SK, NS, NB, NL, PE, NT, YT, NU)
8. Country of origin for this tender (USA, Canada, or null if unclear). Indicators:
   - USA: mentions of federal agencies (DHS, DOD, GSA), US states, NAICS codes, SAM.gov, FAR regulations
   - Canada: mentions of Canadian agencies (PSPC, PWGSC), provinces, GSIN codes, buyandsell.gc.ca, SACC manual

Scope:
{smart_context[:max_tokens * 4]}

Return valid JSON with this structure:
{{
  "sector": "...",
  "industry_description": "...",
  "technical_keywords": ["keyword1", "keyword2", ...],
  "search_terms": ["search term 1", "search term 2", ...],
  "gsin_codes": ["12", "1234", ...],
  "unspsc_codes": ["12345678", ...],
  "province": "ON" or null,
  "country": "USA" or "Canada" or null
}}"""

        content = None
        try:
            content = self.llm_provider.generate(prompt, response_format="json")
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
