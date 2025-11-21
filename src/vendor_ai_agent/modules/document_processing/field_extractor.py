"""Rule-based extraction of structured fields from sections."""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, Iterable, List, Optional

from ...models import (
    Address,
    Amendment,
    Clarification,
    ContactInfo,
    ContractTerms,
    DocExtracted,
    DocSections,
    EvaluationCriteria,
    EvaluationStage,
    MandatoryRequirements,
    PackagingLeadTimes,
    PackagingLogistics,
    RequiredExperience,
    SampleRequirements,
    StructuredDocData,
    TenderSection,
    VendorConstraints,
    VolumeItem,
)
from .table_classifier import TableClassifier
from .qa_handler import QAHandler
from .keywords import (
    CERTIFICATION_PATTERNS,
    EXPERIENCE_REGEXES,
    IDENTIFIER_REGEXES,
    LICENSE_PATTERNS,
    SECTOR_KEYWORDS,
    SPECIAL_STATUS_PATTERNS,
    TECHNICAL_KEYWORDS,
    TIMELINE_REGEXES,
    VOLUME_REGEXES,
)

EXPERIENCE_PATTERN = re.compile(r"(\d+)\s+(?:years|yrs)", re.IGNORECASE)
VOLUME_PATTERN = re.compile(r"([0-9,.]+)\s*(?:sq\.? ft|square feet|m2|meters)", re.IGNORECASE)
LEAD_TIME_PATTERN = re.compile(r"(\d{1,3})\s+(?:days|business days)", re.IGNORECASE)


class FieldExtractor:
    """Populate StructuredDocData from DocSections text."""
    
    def __init__(self, dynamic_keywords: Optional[List[str]] = None, llm_provider=None):
        self.classifier = TableClassifier()
        self.qa_handler = QAHandler()
        self.dynamic_keywords = dynamic_keywords or []
        self.llm_provider = llm_provider

    def extract(self, sections: DocSections, sections_list: Optional[List[TenderSection]] = None) -> StructuredDocData:
        structured = StructuredDocData()
        structured.project_type = self._infer_project_type(sections.scope_of_work)
        structured.sector = self._infer_sector(
            sections.scope_of_work, 
            sections.technical_requirements or None, 
            sections.mandatory_requirements or None
        )
        structured.location = self._infer_location(sections.location_details)
        structured.volumes = self._extract_volumes(sections.scope_of_work, sections_list)
        
        if sections.tables:
            classified_tables = self._classify_and_sort_tables(sections.tables)
            table_volumes = self._extract_volumes_from_tables(classified_tables)
            structured.volumes.extend(table_volumes)
            table_keywords = self._collect_keywords_from_tables(classified_tables, structured.sector)
            structured.technical_keywords.extend(table_keywords)
        
        llm_requirements = self._extract_requirements_with_llm(sections)
        
        if llm_requirements:
            structured.required_experience = RequiredExperience(
                min_years=llm_requirements.get("min_years"),
                required_project_types=llm_requirements.get("required_project_types", [])
            )
            structured.required_licenses = llm_requirements.get("licenses", [])
            structured.required_certifications = llm_requirements.get("certifications", [])
            structured.vendor_constraints = VendorConstraints(
                allowed_jurisdictions=llm_requirements.get("allowed_jurisdictions", []),
                business_size=llm_requirements.get("business_size"),
                special_status=llm_requirements.get("special_status", [])
            )
        else:
            structured.required_experience = self._extract_experience(sections.vendor_qualifications)
            structured.required_licenses = self._find_keywords(sections.mandatory_requirements, LICENSE_PATTERNS)
            structured.required_certifications = self._find_keywords(
                sections.mandatory_requirements, CERTIFICATION_PATTERNS
            )
            structured.vendor_constraints = self._extract_constraints(sections.mandatory_requirements)
        structured.packaging_logistics = self._extract_packaging(sections.technical_requirements)
        text_keywords = self._collect_keywords(sections.scope_of_work, sections.technical_requirements, structured.sector)
        structured.technical_keywords.extend(text_keywords)
        solicitation, reference = self._extract_identifiers(sections)
        structured.solicitation_number = solicitation
        structured.reference_number = reference
        
        structured.external_ids = self._extract_reference_numbers(sections)
        structured.contact_info = self._extract_contact_info(sections)
        structured.mandatory_requirements = self._extract_mandatory_requirements(sections)
        structured.evaluation_criteria = self._extract_evaluation_criteria(sections, sections_list)
        structured.contract_terms = self._extract_contract_terms(sections)
        
        if sections.tables:
            classified_tables = self._classify_and_sort_tables(sections.tables)
            structured.clarifications = self._extract_clarifications_from_tables(classified_tables)
        
        return structured

    # ------------------------------------------------------------------
    def _infer_project_type(self, text: str) -> str:
        if not text:
            return "Unknown Project"
        lowered = text.lower()
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return f"{sector.title()} project"
        return text.split(".")[0][:120]

    def _infer_sector(self, scope_text: str, tech_text: Optional[str] = None, mandatory_text: Optional[str] = None) -> str:
        combined_text = scope_text or ""
        if tech_text:
            combined_text += " " + tech_text
        if mandatory_text:
            combined_text += " " + mandatory_text
        
        if not combined_text.strip():
            return "general"
        
        lowered = combined_text.lower()
        sector_scores = {}
        for sector, keywords in SECTOR_KEYWORDS.items():
            count = sum(1 for keyword in keywords if keyword in lowered)
            if count > 0:
                sector_scores[sector] = count
        
        if not sector_scores:
            return "general"
        
        return max(sector_scores.items(), key=lambda x: x[1])[0]

    def _infer_location(self, text: str) -> Address:
        if not text:
            return Address()
        city_match = re.search(r"(?:in|at)\s+([A-Za-z\s]+),\s*([A-Za-z\s]+)", text)
        if city_match:
            return Address(city=city_match.group(1).strip(), state_province=city_match.group(2).strip())
        return Address()

    def _extract_volumes(self, text: str, sections_list: Optional[List[TenderSection]] = None) -> List[VolumeItem]:
        volumes: List[VolumeItem] = []
        if not text:
            return volumes
        for regex in VOLUME_REGEXES:
            for match in regex.finditer(text):
                amount = match.group(1)
                unit = match.group(2)
                try:
                    quantity = float(amount.replace(",", ""))
                except ValueError:
                    continue
                volumes.append(VolumeItem(item="Quantity", quantity=quantity, unit=unit))
        
        if not volumes and sections_list:
            for section in sections_list:
                search_text = f"{section.title} {section.content}"
                for regex in VOLUME_REGEXES:
                    for match in regex.finditer(search_text):
                        amount = match.group(1)
                        unit = match.group(2)
                        try:
                            quantity = float(amount.replace(",", ""))
                        except ValueError:
                            continue
                        volumes.append(VolumeItem(item="Quantity", quantity=quantity, unit=unit))
                if volumes:
                    break
        
        return volumes
    
    def _extract_requirements_with_llm(self, sections: DocSections) -> dict:
        """Extract vendor requirements using LLM with token limits."""
        if not self.llm_provider:
            return {}
        
        try:
            combined_text = "\n\n".join(filter(None, [
                sections.mandatory_requirements,
                sections.vendor_qualifications,
                sections.technical_requirements
            ]))[:3200]
            
            prompt = f"""Extract vendor requirements from this tender text:

{combined_text}

Extract:
- min_years: minimum years of experience (integer or null)
- required_project_types: list of project types/experience areas
- licenses: required licenses (list of strings)
- certifications: required certifications (list of strings)
- allowed_jurisdictions: geographic restrictions (list like ["Canada"])
- business_size: "SMALL_ONLY" if small business preference, else null
- special_status: special vendor statuses (list)

Return JSON:
{{
  "min_years": 5,
  "required_project_types": ["law enforcement ammunition supply"],
  "licenses": ["ATF license"],
  "certifications": ["ISO 9001"],
  "allowed_jurisdictions": ["Canada"],
  "business_size": null,
  "special_status": []
}}"""

            response = self.llm_provider.generate(prompt)
            if not response or not response.strip():
                return {}
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            data = json.loads(response)
            return data if isinstance(data, dict) else {}
            
        except Exception as e:
            logging.warning(f"LLM requirements extraction failed: {e}")
            return {}

    def _extract_experience(self, text: str) -> RequiredExperience:
        if not text:
            return RequiredExperience()
        min_years = None
        for regex in EXPERIENCE_REGEXES:
            match = regex.search(text)
            if match:
                try:
                    min_years = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        project_types = [phrase.strip() for phrase in re.findall(r"experience in ([^.;]+)", text, re.IGNORECASE)]
        return RequiredExperience(min_years=min_years, required_project_types=project_types)

    def _find_keywords(self, text: str, keywords: Iterable[str]) -> List[str]:
        if not text:
            return []
        lowered = text.lower()
        return [kw for kw in keywords if kw in lowered]

    def _extract_constraints(self, text: str) -> VendorConstraints:
        constraints = VendorConstraints()
        if not text:
            return constraints
        lowered = text.lower()
        if "canadian" in lowered:
            constraints.allowed_jurisdictions.append("Canada")
        if "trade agreement" in lowered:
            constraints.allowed_jurisdictions.append("trade-agreement partners")
        if "small business" in lowered:
            constraints.business_size = "SMALL_ONLY"
        if SPECIAL_STATUS_PATTERNS:
            for pattern in SPECIAL_STATUS_PATTERNS:
                if pattern in lowered:
                    constraints.special_status.append(pattern)
        return constraints

    def _extract_packaging(self, text: str) -> PackagingLogistics:
        packaging = PackagingLogistics()
        if not text:
            return packaging
        lowered = text.lower()
        requirements = []
        if "pallet" in lowered:
            requirements.append("special pallet requirements")
        if "styrofoam" in lowered or "biodegradable" in lowered:
            requirements.append("eco packaging")
        packaging.special_requirements = requirements
        lead_matches = TIMELINE_REGEXES[0].findall(text)
        if lead_matches:
            packaging.lead_times_days = PackagingLeadTimes(samples=int(lead_matches[0][0]))
        return packaging

    def _collect_keywords(self, scope_text: str, technical_text: str | None, sector: str) -> List[str]:
        keywords: List[str] = []
        # Use dynamic keywords if available, otherwise fall back to hardcoded sector keywords
        keyword_list = self.dynamic_keywords if self.dynamic_keywords else TECHNICAL_KEYWORDS.get(sector, [])
        for candidate in keyword_list:
            if scope_text and candidate in scope_text.lower():
                keywords.append(candidate)
            elif technical_text and candidate in technical_text.lower():
                keywords.append(candidate)
        return keywords
    
    def _extract_reference_numbers(self, sections: DocSections) -> Dict[str, str]:
        external_ids = {}
        text_sources = [
            sections.evaluation_criteria,
            sections.scope_of_work,
            sections.mandatory_requirements,
            sections.technical_requirements,
            sections.timeline_details,
        ]
        combined = "\n".join(filter(None, text_sources))
        if not combined:
            return external_ids
        
        rfb_match = re.search(r'RFB[:\s#\-\)]*[#\s]*(OPP-\d+)', combined, re.IGNORECASE)
        if rfb_match:
            external_ids['rfb'] = rfb_match.group(1).strip()
        else:
            rfb_match_generic = re.search(r'RFB[:\s#\-\)]*[#\s]*([A-Z0-9]+-\d+)', combined, re.IGNORECASE)
            if rfb_match_generic:
                external_ids['rfb'] = rfb_match_generic.group(1).strip()
        
        tender_match = re.search(r'[Tt]ender[:\s#]*(\d+)', combined)
        if tender_match:
            external_ids['tender'] = tender_match.group(1).strip()
        
        rfx_match = re.search(r'RFX[:\s#-]*(\d+)', combined, re.IGNORECASE)
        if rfx_match:
            external_ids['rfx'] = rfx_match.group(1).strip()
        
        return external_ids
    
    def _extract_contact_info(self, sections: DocSections) -> ContactInfo:
        contact = ContactInfo()
        text_sources = [
            sections.evaluation_criteria,
            sections.scope_of_work,
            sections.mandatory_requirements,
            sections.timeline_details,
        ]
        combined = "\n".join(filter(None, text_sources))
        if not combined:
            return contact
        
        email_match = re.search(r'([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})', combined, re.IGNORECASE)
        if email_match:
            contact.email = email_match.group(1)
        
        name_match = re.search(r'(?:[Cc]ontact|[Nn]ame)[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)', combined)
        if name_match:
            contact.name = name_match.group(1).strip()
        
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', combined)
        if phone_match:
            contact.phone = phone_match.group(0)
        
        return contact
    
    def _extract_mandatory_requirements(self, sections: DocSections) -> MandatoryRequirements:
        reqs = MandatoryRequirements()
        text_sources = [
            sections.mandatory_requirements,
            sections.evaluation_criteria,
            sections.scope_of_work,
            sections.technical_requirements,
        ]
        text = "\n".join(filter(None, text_sources))
        if not text:
            return reqs
        
        lowered = text.lower()
        reqs.form_of_offer = 'form of offer' in lowered or 'form 1' in lowered
        reqs.jurisdiction_attestation = 'jurisdiction' in lowered and 'attestation' in lowered
        reqs.manufacturer_letter = 'manufacturer letter' in lowered or 'letter from manufacturer' in lowered
        reqs.saami_compliance = 'saami' in lowered
        reqs.mds_required = 'mds' in lowered or 'material data sheet' in lowered or 'material safety data sheet' in lowered or 'msds' in lowered
        reqs.specs_upload = 'specification' in lowered and ('upload' in lowered or 'submit' in lowered)
        
        max_bids_matches = re.findall(r'(?:maximum|up\s+to)(?:\s+of)?\s+(?:\w+\s+)?\(?(\d+)\)?\s+bids?\s+per', lowered)
        if max_bids_matches:
            reqs.max_bids_per_item = max(int(n) for n in max_bids_matches)
        
        return reqs
    
    def _extract_evaluation_criteria(self, sections: DocSections, sections_list: Optional[List[TenderSection]] = None) -> EvaluationCriteria:
        criteria = EvaluationCriteria()
        text = sections.evaluation_criteria
        if not text:
            return criteria
        
        lowered = text.lower()
        
        stage_patterns = [
            (1, r'stage\s*1|mandatory\s+submission|qualification\s+envelope', 'Verification of mandatory forms and documentation', True),
            (2, r'stage\s*2|technical\s+(?:response\s+)?evaluation|technical\s+envelope', 'Assessment of technical specifications and SAAMI compliance', True),
            (3, r'stage\s*3|sample\s+evaluation|sample\s+testing', 'Physical testing of ammunition samples', False),
            (4, r'stage\s*4|price\s+evaluation|financial\s+evaluation', 'Evaluation of pricing for qualified bidders', False),
        ]
        
        for stage_num, pattern, desc, pass_fail in stage_patterns:
            match = re.search(pattern, lowered)
            if match:
                name_extract = self._find_stage_title(stage_num, sections_list)
                if not name_extract:
                    name_extract = match.group(0).replace('\n', ' ').strip().title()
                criteria.stages.append(EvaluationStage(
                    stage_number=stage_num,
                    name=name_extract,
                    description=desc,
                    pass_fail=pass_fail
                ))
        
        tech_weight_match = re.search(r'technical[:\s]*(\d+)\s*%', lowered)
        price_weight_match = re.search(r'price[:\s]*(\d+)\s*%', lowered)
        if tech_weight_match and price_weight_match:
            criteria.category_a_weights = {
                'technical': float(tech_weight_match.group(1)) / 100,
                'price': float(price_weight_match.group(1)) / 100,
            }
        
        sample_days_match = re.search(r'(?:thirty\s*\(\s*)?(\d+)\s*\)?\s*(?:calendar|business)\s*days.*?(?:submit|provide).*?sample', lowered)
        if not sample_days_match:
            sample_days_match = re.search(r'sample.*?(?:thirty\s*\(\s*)?(\d+)\s*\)?\s*(?:calendar|business)\s*days', lowered)
        if sample_days_match:
            if not criteria.sample_requirements:
                criteria.sample_requirements = SampleRequirements()
            criteria.sample_requirements.delivery_days = int(sample_days_match.group(1))
        
        return criteria
    
    def _find_stage_title(self, stage_num: int, sections_list: Optional[List[TenderSection]]) -> Optional[str]:
        if not sections_list:
            return None
        
        stage_title_patterns = [
            (1, r'stage\s*1[:\s\-–]+(.+?)(?:\n|$)', r'evaluation\s+of\s+(?:qualification|mandatory).*'),
            (2, r'stage\s*2[:\s\-–]+(.+?)(?:\n|$)', r'evaluation\s+of\s+mandatory.*'),
            (3, r'stage\s*3[:\s\-–]+(.+?)(?:\n|$)', r'technical\s+response\s+evaluation'),
            (4, r'stage\s*4[:\s\-–]+(.+?)(?:\n|$)', r'commercial\s+response\s+evaluation'),
        ]
        
        for section in sections_list:
            title_lower = section.title.lower()
            content_lower = section.content.lower()
            
            for snum, title_pattern, content_pattern in stage_title_patterns:
                if snum == stage_num:
                    match = re.search(title_pattern, title_lower, re.IGNORECASE)
                    if match:
                        return match.group(1).strip().title()
                    
                    content_match = re.search(content_pattern, content_lower, re.IGNORECASE)
                    if content_match:
                        full_match = content_match.group(0)
                        return full_match.replace('\n', ' ').strip().title()
        
        return None
    
    def _extract_contract_terms(self, sections: DocSections) -> ContractTerms:
        terms = ContractTerms()
        text_sources = [
            sections.timeline_details,
            sections.evaluation_criteria,
            sections.scope_of_work,
            sections.mandatory_requirements,
        ]
        text = "\n".join(filter(None, text_sources))
        if not text:
            return terms
        
        lowered = text.lower()
        
        start_date_match = re.search(r'(?:commence|start|effective)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE)
        if start_date_match:
            terms.start_date = start_date_match.group(1)
        
        term_match = re.search(r'\(?\s*(\d+)\s*\)?\s+year[s]?\s+with\s+(?:one\s+\(?\s*)?(\d+)\s*\)?\s+additional', lowered)
        if term_match:
            terms.term_years = int(term_match.group(1))
            terms.extension_years = int(term_match.group(2))
        else:
            term_match_simple = re.search(r'\(?\s*(\d+)\s*\)?\s+year[s]?\s+(?:contract\s+)?(?:term)?', lowered)
            if term_match_simple:
                terms.term_years = int(term_match_simple.group(1))
            else:
                term_match_alt = re.search(r'(?:term|duration)[:\s\-–]+\(?\s*(\d+)\s*\)?\s+year', lowered)
                if term_match_alt:
                    terms.term_years = int(term_match_alt.group(1))
        
        if not terms.extension_years:
            extension_match = re.search(r'(?:extension|additional\s+period)[:\s\-–]+(?:up\s+to\s+)?(?:one\s+)?\(?\s*(\d+)\s*\)?\s+year', lowered)
            if extension_match:
                terms.extension_years = int(extension_match.group(1))
        
        irrevocable_match = re.search(r'irrevocable.*?(\d+)\s+(?:calendar\s+)?days', lowered)
        if irrevocable_match:
            terms.bid_irrevocable_days = int(irrevocable_match.group(1))
        
        terms.insurance_required = 'insurance' in lowered
        terms.security_clearance_required = 'security clearance' in lowered or 'clearance' in lowered
        terms.wsia_required = 'wsia' in lowered or 'workplace safety' in lowered
        terms.tax_compliance_required = 'tax compliance' in lowered
        
        return terms

    def _extract_identifiers(self, sections: DocSections) -> tuple[Optional[str], Optional[str]]:
        text_sources = [
            sections.scope_of_work,
            sections.mandatory_requirements,
            sections.technical_requirements,
            sections.vendor_qualifications,
            sections.timeline_details,
        ]
        combined = "\n".join(filter(None, text_sources))
        solicitation = None
        reference = None
        if combined:
            for pattern in IDENTIFIER_REGEXES["solicitation"]:
                match = pattern.search(combined)
                if match:
                    candidate = (match.group(1) if match.lastindex else match.group(0)).strip()
                    if self._valid_identifier(candidate):
                        solicitation = candidate
                        break
            for pattern in IDENTIFIER_REGEXES["reference"]:
                match = pattern.search(combined)
                if match:
                    candidate = (match.group(1) if match.lastindex else match.group(0)).strip()
                    if self._valid_identifier(candidate):
                        reference = candidate
                        break
        return solicitation, reference

    def _valid_identifier(self, value: str) -> bool:
        return any(ch.isdigit() for ch in value)

    def _classify_and_sort_tables(self, tables: List[TenderSection]) -> List[tuple[TenderSection, str]]:
        classified = []
        for table in tables:
            table_type = self.classifier.classify(table)
            priority = TableClassifier.get_priority(table_type)
            classified.append((table, table_type, priority))
        
        classified.sort(key=lambda x: x[2])
        
        return [(table, table_type) for table, table_type, _ in classified]
    
    def _extract_items_with_llm(self, table_section: TenderSection) -> List[VolumeItem]:
        """Extract line items from table using LLM with token limits."""
        if not self.llm_provider:
            return []
        
        try:
            table_content = table_section.content[:2400]
            
            prompt = f"""Extract line items from this tender table. For each row, extract:
- item: item description (combine line number, caliber/type, and description)
- quantity: numeric quantity (just the number)
- unit: unit of measure

Skip header rows and rows without quantities.

Table:
{table_content}

Return JSON array:
[{{"item": "...", "quantity": 1000, "unit": "rounds"}}]"""

            response = self.llm_provider.generate(prompt)
            if not response or not response.strip():
                return []
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            data = json.loads(response)
            if not isinstance(data, list):
                return []
            
            volumes = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                item = entry.get("item", "").strip()
                quantity = entry.get("quantity")
                unit = entry.get("unit", "").strip() or None
                
                if item:
                    volumes.append(VolumeItem(
                        item=item[:100],
                        quantity=quantity,
                        unit=unit
                    ))
            
            return volumes
            
        except Exception as e:
            logging.warning(f"LLM table extraction failed: {e}")
            return []
    
    def _extract_volumes_from_tables(self, classified_tables: List[tuple[TenderSection, str]]) -> List[VolumeItem]:
        """Best-effort extraction of volumes from Markdown tables (LLM + regex fallback)."""
        volumes = []
        
        for table, table_type in classified_tables:
            if table_type in ('qa', 'pricing', 'unknown'):
                continue
            
            if table_type != 'line_items':
                continue
            
            llm_volumes = self._extract_items_with_llm(table)
            if llm_volumes:
                volumes.extend(llm_volumes)
                continue
            
            try:
                lines = [l.strip() for l in table.content.split('\n') if '|' in l]
                if len(lines) < 3:
                    continue
                
                headers = [h.strip().lower() for h in lines[0].split('|')[1:-1]]
                
                line_no_col = self._find_column(headers, ['line item no', 'line no', 'item no'])
                caliber_col = self._find_column(headers, ['caliber'])
                desc_col = self._find_column(headers, ['description', 'bullet descriptor', 'product'])
                qty_col = self._find_column(headers, ['quantity', 'qty', 'amount', 'volume'])
                unit_col = self._find_column(headers, ['unit', 'uom', 'measure', 'units'])
                
                start_row = 2
                if len(lines) > 2:
                    second_row_cells = [c.strip() for c in lines[2].split('|')[1:-1]]
                    if caliber_col is not None and caliber_col < len(second_row_cells):
                        if not second_row_cells[caliber_col] or second_row_cells[caliber_col] in ['Primary', 'Secondary', 'Construction']:
                            start_row = 3
                
                for line in lines[start_row:]:
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    if len(cells) != len(headers):
                        continue
                    
                    item_parts = []
                    if line_no_col is not None and line_no_col < len(cells) and cells[line_no_col]:
                        item_parts.append(f"#{cells[line_no_col]}")
                    if caliber_col is not None and caliber_col < len(cells) and cells[caliber_col]:
                        item_parts.append(cells[caliber_col])
                    if desc_col is not None and desc_col < len(cells) and cells[desc_col]:
                        item_parts.append(cells[desc_col])
                    
                    item = " - ".join(item_parts) if item_parts else ""
                    
                    quantity = None
                    if qty_col is not None and qty_col < len(cells):
                        quantity = self._parse_quantity(cells[qty_col])
                    unit = cells[unit_col] if unit_col is not None and unit_col < len(cells) else None
                    
                    if item and item.strip() and item.strip() != '-':
                        volumes.append(VolumeItem(item=item[:100], quantity=quantity, unit=unit))
            
            except Exception:
                continue
        
        return volumes

    def _find_column(self, headers: List[str], candidates: List[str]) -> Optional[int]:
        """Find column index by matching candidate names."""
        for i, header in enumerate(headers):
            for candidate in candidates:
                if candidate in header:
                    return i
        return None

    def _parse_quantity(self, text: str) -> Optional[float]:
        """Extract numeric quantity from cell text."""
        if not text:
            return None
        cleaned = text.replace(',', '').strip()
        match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _collect_keywords_from_tables(self, classified_tables: List[tuple[TenderSection, str]], sector: str) -> List[str]:
        """Extract technical keywords from table content."""
        keywords = []
        # Use dynamic keywords if available, otherwise fall back to hardcoded sector keywords
        keyword_list = self.dynamic_keywords if self.dynamic_keywords else TECHNICAL_KEYWORDS.get(sector, [])
        
        for table, table_type in classified_tables:
            if table_type in ('qa', 'pricing', 'unknown'):
                continue
            content_lower = table.content.lower()
            for candidate in keyword_list:
                if candidate in content_lower and candidate not in keywords:
                    keywords.append(candidate)
        
        return keywords
    
    def _extract_clarifications_from_tables(self, classified_tables: List[tuple[TenderSection, str]]) -> List[Clarification]:
        """Extract Q&A clarifications from qa-type tables using QAHandler."""
        all_qa_pairs = []
        
        for table, table_type in classified_tables:
            if table_type != 'qa':
                continue
            
            qa_pairs = self.qa_handler.extract_qa_pairs(table)
            all_qa_pairs.extend(qa_pairs)
        
        merged_pairs = self._merge_cross_table_qa_pairs(all_qa_pairs)
        
        clarifications = []
        for qa_pair in merged_pairs:
            if qa_pair.question and qa_pair.answer:
                clarifications.append(Clarification(
                    question=qa_pair.question[:500],
                    answer=qa_pair.answer[:1000],
                    question_number=qa_pair.question_id
                ))
        
        return clarifications
    
    def _merge_cross_table_qa_pairs(self, all_pairs: List) -> List:
        """Merge Q&A pairs that span across multiple tables."""
        pairs_by_id = {}
        
        for pair in all_pairs:
            if pair.question_id not in pairs_by_id:
                pairs_by_id[pair.question_id] = pair
            else:
                existing = pairs_by_id[pair.question_id]
                if pair.question and not existing.question:
                    existing.question = pair.question
                if pair.answer and not existing.answer:
                    existing.answer = pair.answer
        
        return list(pairs_by_id.values())
