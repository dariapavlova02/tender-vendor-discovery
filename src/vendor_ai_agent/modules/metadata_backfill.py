"""Backfill empty API metadata fields from document extraction."""
from __future__ import annotations

import re
from typing import Optional

from ..models import BuyerInfo, DateMetadata, TenderProfile


class MetadataBackfill:
    """Fills missing API metadata fields from document-extracted data."""

    def backfill(self, profile: TenderProfile) -> TenderProfile:
        """Fill empty api_metadata fields from doc_extracted when available."""
        api_meta = profile.api_metadata
        doc_data = profile.doc_extracted.structured
        doc_sections = profile.doc_extracted.sections

        if not api_meta.external_id:
            api_meta.external_id = (
                doc_data.solicitation_number or doc_data.reference_number
            )

        if not api_meta.title:
            api_meta.title = self._extract_title_from_scope(doc_sections.scope_of_work)

        if not api_meta.buyer.name:
            buyer_name = self._extract_buyer_from_text(
                doc_sections.scope_of_work
                + "\n"
                + doc_sections.mandatory_requirements
            )
            if buyer_name:
                api_meta.buyer = BuyerInfo(name=buyer_name)

        if not api_meta.place_of_performance.city and doc_data.location.city:
            api_meta.place_of_performance.city = doc_data.location.city
            api_meta.place_of_performance.state_province = doc_data.location.state_province
            api_meta.place_of_performance.country = doc_data.location.country

        if not api_meta.dates.response_deadline:
            deadline = self._extract_deadline(doc_sections.scope_of_work)
            if deadline:
                api_meta.dates = DateMetadata(response_deadline=deadline)

        if not api_meta.codes.naics and doc_data.technical_keywords:
            api_meta.codes.naics = doc_data.technical_keywords[:3]

        return profile

    def _extract_title_from_scope(self, scope_text: str) -> Optional[str]:
        """Extract title from first meaningful line of scope."""
        if not scope_text:
            return None
        lines = [line.strip() for line in scope_text.splitlines() if line.strip()]
        if not lines:
            return None
        first_line = lines[0]
        if len(first_line) > 200:
            first_line = first_line[:197] + "..."
        return first_line

    def _extract_buyer_from_text(self, text: str) -> Optional[str]:
        """Extract buyer organization using regex patterns."""
        if not text:
            return None
        patterns = [
            r"(?:Issued by|Buyer|Purchaser|Client|Contracting Authority):\s*([^\n]+)",
            r"(?:Ontario Provincial Police|OPP|Government of [A-Z][a-z]+)",
            r"([A-Z][A-Za-z\s&]+(?:Police|Department|Ministry|Agency|Government))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:2000], re.IGNORECASE | re.MULTILINE)
            if match:
                buyer = match.group(1).strip() if match.lastindex else match.group(0).strip()
                buyer = re.sub(r"\s+", " ", buyer)
                if 3 < len(buyer) < 100:
                    return buyer
        return None

    def _extract_deadline(self, text: str) -> Optional[str]:
        """Extract response deadline date."""
        if not text:
            return None
        patterns = [
            r"(?:Closing Date|Deadline|Due Date|Bid Due):\s*([A-Za-z]+\s+\d{1,2}[a-z]{0,2},?\s+\d{4})",
            r"(?:December|November|October|January|February)\s+\d{1,2}[a-z]{0,2},?\s+\d{4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:1000], re.IGNORECASE)
            if match:
                date_str = match.group(1) if match.lastindex else match.group(0)
                return self._normalize_date(date_str.strip())
        return None

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to YYYY-MM-DD format if possible."""
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12"
        }
        pattern = r"([A-Za-z]+)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})"
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            month_name, day, year = match.groups()
            month_num = months.get(month_name.lower())
            if month_num:
                return f"{year}-{month_num}-{day.zfill(2)}"
        return date_str
