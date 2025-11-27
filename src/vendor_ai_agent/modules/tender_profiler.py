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
    
    contract_type: Optional[str] = None
    contract_type_confidence: float = 0.0
    fulfillment_model: Optional[str] = None
    primary_deliverables: List[str] = field(default_factory=list)
    vendor_inputs: List[str] = field(default_factory=list)
    location: Optional[Dict[str, Any]] = None


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

    def _calculate_semantic_overlap(self, q1: str, q2: str) -> float:
        """Calculate Jaccard similarity between two queries."""
        def tokenize(query: str) -> set:
            stopwords = {'a', 'an', 'and', 'or', 'the', 'for', 'of', 'in', 'to', 'with', 'by', 'from'}
            import re
            words = re.findall(r'\b[a-z]+\b', query.lower())
            return {w for w in words if w not in stopwords and len(w) > 2}
        
        words1 = tokenize(q1)
        words2 = tokenize(q2)
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _calculate_specificity_score(self, query: str) -> float:
        """Score query by specificity level (higher = more specific)."""
        import re
        words = re.findall(r'\b[a-z]+\b', query.lower())
        stopwords = {'a', 'an', 'and', 'or', 'the', 'for', 'of', 'in', 'to', 'with', 'by', 'from'}
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 2]
        
        score = len(meaningful_words)
        
        specific_indicators = ['oem', 'manufacturer', 'producer', 'maker', 'fabricator']
        if any(ind in query.lower() for ind in specific_indicators):
            score += 2
        
        business_type_indicators = ['distributor', 'wholesaler', 'installer', 'integrator', 
                                     'consultant', 'service', 'maintenance']
        if any(ind in query.lower() for ind in business_type_indicators):
            score += 1
        
        return score

    def _optimize_search_terms(self, queries: List[str], target_count: int = 20) -> List[str]:
        if not queries:
            self.logger.warning("No queries provided for optimization")
            return []
        
        self.logger.info(f"Optimizing {len(queries)} queries → target {target_count}")
        
        if len(queries) <= target_count:
            self.logger.info(f"No optimization needed: {len(queries)} queries ≤ target {target_count}")
            return queries
        
        n = len(queries)
        clusters = []
        assigned = set()
        
        for i in range(n):
            if i in assigned:
                continue
            
            cluster = [i]
            assigned.add(i)
            
            for j in range(i + 1, n):
                if j in assigned:
                    continue
                
                overlap = self._calculate_semantic_overlap(queries[i], queries[j])
                if overlap >= 0.4:
                    cluster.append(j)
                    assigned.add(j)
            
            clusters.append(cluster)
        
        self.logger.info(f"Clustered {len(queries)} queries into {len(clusters)} semantic groups")
        
        selected_queries = []
        for cluster in clusters:
            if len(cluster) == 1:
                selected_queries.append(queries[cluster[0]])
            else:
                scored = [(idx, self._calculate_specificity_score(queries[idx])) 
                          for idx in cluster]
                scored.sort(key=lambda x: x[1], reverse=True)
                best_idx = scored[0][0]
                selected_queries.append(queries[best_idx])
                
                overlap_str = f"{self._calculate_semantic_overlap(queries[cluster[0]], queries[cluster[1]]):.2f}"
                self.logger.debug(
                    f"Cluster of {len(cluster)}: kept '{queries[best_idx][:50]}...' "
                    f"(score={scored[0][1]:.1f}, dropped {len(cluster)-1} similar queries)"
                )
        
        if len(selected_queries) > target_count:
            scored_all = [(q, self._calculate_specificity_score(q)) 
                          for q in selected_queries]
            scored_all.sort(key=lambda x: x[1], reverse=True)
            
            specific_count = target_count // 3
            medium_count = target_count // 3
            broad_count = target_count - specific_count - medium_count
            
            result = []
            result.extend([q for q, s in scored_all[:specific_count]])
            result.extend([q for q, s in scored_all[-broad_count:]])
            
            remaining = [q for q, s in scored_all[specific_count:-broad_count] 
                        if q not in result]
            result.extend(remaining[:medium_count])
            
            self.logger.info(
                f"Balanced specificity: {specific_count} specific + "
                f"{medium_count} medium + {broad_count} broad = {len(result)} queries"
            )
            return result[:target_count]
        
        self.logger.info(f"Optimized: {len(queries)} → {len(selected_queries)} unique queries")
        
        if len(selected_queries) < target_count:
            shortfall = target_count - len(selected_queries)
            self.logger.warning(
                f"Only {len(selected_queries)}/{target_count} queries generated. "
                f"Consider reviewing LLM prompt effectiveness."
            )
        
        return selected_queries

    def _validate_and_filter_search_terms(
        self,
        raw_search_terms: List[str],
        contract_type: Optional[str],
        contract_type_confidence: float,
        vendor_inputs: List[str]
    ) -> List[str]:
        """
        Safety rails to filter inappropriate search queries based on contract type.
        
        Only applies filters if contract_type_confidence >= 0.75 to avoid false positives.
        
        Args:
            raw_search_terms: Search queries from LLM
            contract_type: Classified contract type
            contract_type_confidence: Confidence score (0-1)
            vendor_inputs: Items the vendor uses (NOT what buyer purchases)
            
        Returns:
            Filtered list of search terms
        """
        if not raw_search_terms:
            return []
        
        if contract_type_confidence < 0.75:
            self.logger.info(
                f"Skipping search term filtering: confidence {contract_type_confidence:.2f} < 0.75"
            )
            return raw_search_terms
        
        filtered_terms = []
        rejected_terms = []
        
        inappropriate_patterns = {
            "service": [
                r'\b(manufacturer|producer|maker|fabricator|oem)\b',
                r'\b(salt|sand|gravel|material)\s+(supplier|distributor|wholesaler)\b',
            ],
            "product": [
                r'\b(service provider|contractor|maintenance contractor)\b',
            ],
            "consulting": [
                r'\b(manufacturer|producer|supplier|distributor)\b',
            ]
        }
        
        vendor_input_patterns = []
        for vendor_input in vendor_inputs:
            if vendor_input and len(vendor_input.strip()) >= 3:
                escaped = vendor_input.strip().lower().replace(' ', r'\s+')
                vendor_input_patterns.append(
                    rf'\b{escaped}\s+(supplier|distributor|wholesaler|manufacturer)\b'
                )
        
        patterns_to_check = inappropriate_patterns.get(contract_type or "", [])
        patterns_to_check.extend(vendor_input_patterns)
        
        import re
        for term in raw_search_terms:
            term_lower = term.lower()
            is_inappropriate = False
            
            for pattern in patterns_to_check:
                if re.search(pattern, term_lower, re.IGNORECASE):
                    is_inappropriate = True
                    rejected_terms.append((term, pattern))
                    break
            
            if not is_inappropriate:
                filtered_terms.append(term)
        
        if rejected_terms:
            self.logger.warning(
                f"Safety rails filtered {len(rejected_terms)}/{len(raw_search_terms)} "
                f"inappropriate queries for contract_type={contract_type}"
            )
            for term, pattern in rejected_terms[:3]:
                self.logger.debug(f"  Rejected: '{term}' (matched pattern: {pattern})")
        
        return filtered_terms

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

        prompt = f"""Act as a procurement market analyst. Use only the provided scope excerpt.

STEP 1: CLASSIFY CONTRACT TYPE
Analyze the tender to determine what the buyer is purchasing:

- SERVICE: Vendor performs work (maintenance, cleaning, security, landscaping, IT services)
  Signal words: "contractor shall", "provide services", "perform", "maintain", "operate"
  
- PRODUCT: Vendor delivers items (equipment, materials, goods)
  Signal words: "supply", "deliver", "furnish", "provide equipment/materials"
  
- HYBRID: Vendor supplies AND installs/maintains (equipment with installation, turnkey solutions)
  Signal words: "supply and install", "turnkey", "including maintenance", "full-service"
  
- CONSULTING: Advisory, design, engineering, training services
  Signal words: "consulting", "advisory", "design services", "training", "assessment"

STEP 2: DISTINGUISH PROCUREMENT TARGET vs VENDOR INPUTS
Critical distinction for accurate vendor search:

PROCUREMENT TARGET = What the buyer purchases → SEARCH FOR THESE VENDORS
- Service contract: "grounds maintenance services" → search for grounds maintenance contractors
- Product contract: "hospital beds" → search for hospital bed manufacturers/distributors

VENDOR INPUTS = What the winning vendor must provide/use → DO NOT SEARCH FOR THESE
- Service contract: "salt for snow removal" → salt is an INPUT the contractor uses
- Service contract: "equipment for maintenance" → equipment is an INPUT the contractor owns
- Service contract: "training for staff" → training is a DELIVERABLE the contractor provides to buyer

Examples:
✓ "Contractor shall provide grounds maintenance using salt, equipment, and trained staff"
  - Procurement target: grounds maintenance services
  - Vendor inputs: salt, equipment, staff training
  - Search for: grounds maintenance contractors (NOT salt suppliers)

✓ "Supply 100 adjustable hospital beds with installation"
  - Procurement target: hospital beds, installation services
  - Vendor inputs: delivery trucks, installation tools
  - Search for: hospital furniture suppliers with installation

STEP 3: GENERATE CONTRACT-TYPE-AWARE SEARCH TERMS
Generate 25-30 search queries following these distribution rules:

FOR SERVICE CONTRACTS:
- 85% contractor/service provider queries: "[service type] contractors", "[service type] service providers"
- 10% integrator/consultant queries: "[service type] consultants", "[domain] integrators"
- 5% supplier queries ONLY if service requires specialized equipment: "[specialized equipment] suppliers for [service]"
- 0% manufacturer/producer queries (services aren't manufactured)

Example (Grounds Maintenance):
✓ "commercial grounds maintenance contractors Ontario"
✓ "landscape maintenance service providers Canada"
✓ "snow removal and lawn care services"
✓ "property maintenance contractors municipal contracts"
✗ "salt manufacturers" (salt is vendor INPUT, not procurement target)
✗ "lawn mower suppliers" (equipment is vendor INPUT)

FOR PRODUCT CONTRACTS:
- 40% manufacturer/OEM queries: "[product] manufacturers", "[product] OEM producers"
- 30% distributor/wholesaler queries: "[product category] distributors", "[product] wholesalers"
- 20% supplier queries: "[product] suppliers", "[industry] supply companies"
- 10% specialty queries: "[product] fabricators", "custom [product] makers"

Example (Hospital Beds):
✓ "adjustable hospital bed manufacturers"
✓ "medical furniture OEM producers"
✓ "healthcare equipment distributors"
✓ "hospital bed suppliers certified"

FOR HYBRID CONTRACTS:
- 50% full-service provider queries: "[product] with installation", "[product] turnkey solutions"
- 25% manufacturer queries: "[product] manufacturers with installation services"
- 25% integrator queries: "[product] system integrators", "[product] installation contractors"

FOR CONSULTING CONTRACTS:
- 70% consultant/advisory queries: "[domain] consultants", "[specialization] advisory firms"
- 20% engineering/design queries: "[domain] engineering services", "[specialization] design consultants"
- 10% training provider queries: "[domain] training providers", "[certification] trainers"

DIVERSITY REQUIREMENTS (applies to ALL contract types):
- SPECIFIC (30%): Exact products/services with business role
- MEDIUM (40%): Product/service categories with business role
- BROAD (30%): Industry sectors with business role

OUTPUT REQUIREMENTS:
Return strict JSON with the following structure:

{{
  "contract_type": "service" | "product" | "hybrid" | "consulting",
  "contract_type_confidence": 0.0-1.0,
  "fulfillment_model": "contractor" | "manufacturer" | "distributor" | "integrator" | "consultant",
  "primary_deliverables": ["what buyer purchases - list 3-5 items"],
  "vendor_inputs": ["what winning vendor must provide/use - list 3-5 items"],
  
  "sector": "concise label describing the procurement vertical",
  "industry_description": "exactly 2 sentences (≤60 words) summarizing buyer needs",
  "technical_keywords": ["exactly 15 unique keywords ordered from most specific to general"],
  "search_terms": ["25-30 DIVERSE search strings following contract-type distribution rules above"],
  
  "location": {{
    "country": "USA" | "Canada" | null,
    "province": "two-letter code if stated" | null,
    "region": "regional descriptor if mentioned" | null,
    "cities": ["list of cities if mentioned"],
    "service_area": "description of place of performance" | null
  }},
  
  "gsin_codes": ["only codes explicitly in text"],
  "unspsc_codes": ["only codes explicitly in text"],
  "confidence": 0.0-1.0
}}

CRITICAL RULES:
1. Contract classification MUST happen BEFORE generating search terms
2. Search terms MUST match the contract type distribution rules
3. NEVER search for vendor inputs (materials/tools/equipment the contractor uses)
4. ALWAYS search for procurement targets (what the buyer is purchasing)
5. Geographic qualifiers in location object ONLY, NOT in search terms

Scope Excerpt ({len(scope_excerpt)} characters):
{scope_excerpt}
"""

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
            raw_search_terms = data.get("search_terms", [])
            
            self.logger.info(f"LLM generated {len(raw_search_terms)} raw search terms")
            self.logger.debug(f"Sample raw terms: {raw_search_terms[:5]}")
            
            search_terms = self._optimize_search_terms(raw_search_terms, target_count=20)
            self.logger.info(f"Optimized to {len(search_terms)} diverse search terms")
            self.logger.debug(f"Sample optimized terms: {search_terms[:5]}")
            
            if sector == "Unknown" or not keywords:
                self.logger.warning(
                    f"LLM returned incomplete data: sector={sector}, "
                    f"keywords={len(keywords)}, raw_search_terms={len(raw_search_terms)}"
                )
                self.logger.debug(f"LLM raw response: {content[:500]}")
            
            location_data = data.get("location", {})
            
            return TenderContext(
                sector=sector,
                industry_description=data.get("industry_description", ""),
                technical_keywords=keywords,
                search_terms=search_terms,
                gsin_codes=data.get("gsin_codes", []),
                unspsc_codes=data.get("unspsc_codes", []),
                province=location_data.get("province") if isinstance(location_data, dict) else data.get("province"),
                country=location_data.get("country") if isinstance(location_data, dict) else data.get("country"),
                contract_type=data.get("contract_type"),
                contract_type_confidence=data.get("contract_type_confidence"),
                fulfillment_model=data.get("fulfillment_model"),
                primary_deliverables=data.get("primary_deliverables", []),
                vendor_inputs=data.get("vendor_inputs", []),
                location=location_data if isinstance(location_data, dict) and location_data else None,
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
