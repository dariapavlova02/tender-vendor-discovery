"""Rule-based extraction of structured fields from sections."""
from __future__ import annotations

import re
from typing import Iterable, List

from ...models import (
    Address,
    DocExtracted,
    DocSections,
    PackagingLeadTimes,
    PackagingLogistics,
    RequiredExperience,
    StructuredDocData,
    VendorConstraints,
    VolumeItem,
)
from .keywords import (
    CERTIFICATION_PATTERNS,
    EXPERIENCE_REGEXES,
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

    def extract(self, sections: DocSections) -> StructuredDocData:
        structured = StructuredDocData()
        structured.project_type = self._infer_project_type(sections.scope_of_work)
        structured.sector = self._infer_sector(sections.scope_of_work)
        structured.location = self._infer_location(sections.location_details)
        structured.volumes = self._extract_volumes(sections.scope_of_work)
        structured.required_experience = self._extract_experience(sections.vendor_qualifications)
        structured.required_licenses = self._find_keywords(sections.mandatory_requirements, LICENSE_PATTERNS)
        structured.required_certifications = self._find_keywords(
            sections.mandatory_requirements, CERTIFICATION_PATTERNS
        )
        structured.vendor_constraints = self._extract_constraints(sections.mandatory_requirements)
        structured.packaging_logistics = self._extract_packaging(sections.technical_requirements)
        structured.technical_keywords = self._collect_keywords(sections.scope_of_work, sections.technical_requirements)
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

    def _infer_sector(self, text: str) -> str:
        if not text:
            return "general"
        lowered = text.lower()
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return sector
        return "general"

    def _infer_location(self, text: str) -> Address:
        if not text:
            return Address()
        city_match = re.search(r"(?:in|at)\s+([A-Za-z\s]+),\s*([A-Za-z\s]+)", text)
        if city_match:
            return Address(city=city_match.group(1).strip(), state_province=city_match.group(2).strip())
        return Address()

    def _extract_volumes(self, text: str) -> List[VolumeItem]:
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
        return volumes

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

    def _collect_keywords(self, scope_text: str, technical_text: str | None) -> List[str]:
        keywords: List[str] = []
        for group in TECHNICAL_KEYWORDS.values():
            for candidate in group:
                if scope_text and candidate in scope_text.lower():
                    keywords.append(candidate)
                elif technical_text and candidate in technical_text.lower():
                    keywords.append(candidate)
        return keywords
