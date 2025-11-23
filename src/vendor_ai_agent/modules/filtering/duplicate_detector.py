"""Duplicate detection and vendor deduplication."""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from ...models import VendorRecord

logger = logging.getLogger(__name__)


class DuplicateDetector:
    def __init__(self, merge_duplicates: bool = True):
        self.merge_duplicates = merge_duplicates

    def deduplicate(
        self, vendors: List[VendorRecord]
    ) -> tuple[List[VendorRecord], int]:
        if not vendors:
            return [], 0

        seen_companies: Dict[str, VendorRecord] = {}
        seen_websites: Dict[str, VendorRecord] = {}
        seen_identifiers: Dict[str, VendorRecord] = {}
        duplicates_removed = 0

        deduplicated = []

        for vendor in vendors:
            normalized_name = self._normalize_company_name(vendor.company_name)
            normalized_website = self._normalize_website(vendor.website)
            identifier_key = self._get_identifier_key(vendor)

            existing_vendor = None

            if identifier_key and identifier_key in seen_identifiers:
                existing_vendor = seen_identifiers[identifier_key]
                logger.debug(
                    f"Duplicate by identifier: {vendor.company_name} matches {existing_vendor.company_name}"
                )
            elif normalized_website and normalized_website in seen_websites:
                existing_vendor = seen_websites[normalized_website]
                logger.debug(
                    f"Duplicate by website: {vendor.company_name} matches {existing_vendor.company_name}"
                )
            elif normalized_name in seen_companies:
                existing_vendor = seen_companies[normalized_name]
                logger.debug(
                    f"Duplicate by name: {vendor.company_name} matches {existing_vendor.company_name}"
                )

            if existing_vendor:
                duplicates_removed += 1
                if self.merge_duplicates:
                    self._merge_vendor_data(existing_vendor, vendor)
            else:
                deduplicated.append(vendor)
                seen_companies[normalized_name] = vendor
                if normalized_website:
                    seen_websites[normalized_website] = vendor
                if identifier_key:
                    seen_identifiers[identifier_key] = vendor

        logger.info(
            f"Deduplication: {len(vendors)} -> {len(deduplicated)} ({duplicates_removed} duplicates removed)"
        )
        return deduplicated, duplicates_removed

    def _normalize_company_name(self, name: str) -> str:
        if not name:
            return ""

        normalized = name.strip().lower()

        suffixes = [
            r"\s+inc\.?$",
            r"\s+llc\.?$",
            r"\s+ltd\.?$",
            r"\s+corporation$",
            r"\s+corp\.?$",
            r"\s+limited$",
            r"\s+company$",
            r"\s+co\.?$",
            r"\s+incorporated$",
            r"\s+s\.?a\.?$",
            r"\s+gmbh$",
            r"\s+pty\.?\s+ltd\.?$",
            r"\s+l\.?l\.?c\.?$",
        ]

        for suffix in suffixes:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _normalize_website(self, website: Optional[str]) -> Optional[str]:
        if not website:
            return None

        try:
            website = website.strip().lower()
            if not website.startswith(("http://", "https://")):
                website = f"https://{website}"

            parsed = urlparse(website)
            domain = parsed.netloc

            domain = domain.replace("www.", "")

            return domain
        except Exception as e:
            logger.debug(f"Failed to normalize website '{website}': {e}")
            return None

    def _get_identifier_key(self, vendor: VendorRecord) -> Optional[str]:
        if vendor.uei:
            return f"uei:{vendor.uei.strip().upper()}"
        if vendor.duns:
            return f"duns:{vendor.duns.strip()}"
        if vendor.cage_code:
            return f"cage:{vendor.cage_code.strip().upper()}"
        return None

    def _merge_vendor_data(
        self, existing: VendorRecord, duplicate: VendorRecord
    ) -> None:
        if not existing.website and duplicate.website:
            existing.website = duplicate.website
        if not existing.email and duplicate.email:
            existing.email = duplicate.email
        if not existing.phone and duplicate.phone:
            existing.phone = duplicate.phone
        if not existing.location and duplicate.location:
            existing.location = duplicate.location
        if not existing.city and duplicate.city:
            existing.city = duplicate.city
        if not existing.state and duplicate.state:
            existing.state = duplicate.state
        if not existing.country and duplicate.country:
            existing.country = duplicate.country

        if not existing.uei and duplicate.uei:
            existing.uei = duplicate.uei
        if not existing.duns and duplicate.duns:
            existing.duns = duplicate.duns
        if not existing.cage_code and duplicate.cage_code:
            existing.cage_code = duplicate.cage_code

        if duplicate.is_past_winner and not existing.is_past_winner:
            existing.is_past_winner = True

        for flag in duplicate.enrichment_flags:
            if flag not in existing.enrichment_flags:
                existing.enrichment_flags.append(flag)

        for btype in duplicate.business_types:
            if btype not in existing.business_types:
                existing.business_types.append(btype)

        if duplicate.total_contract_value:
            existing.total_contract_value = max(
                existing.total_contract_value or 0, duplicate.total_contract_value
            )
        if duplicate.contract_count:
            existing.contract_count = max(
                existing.contract_count or 0, duplicate.contract_count
            )

        sources = existing.filtering_metadata.get("merged_sources", [])
        if duplicate.source and duplicate.source not in sources:
            sources.append(duplicate.source)
        existing.filtering_metadata["merged_sources"] = sources

        logger.debug(
            f"Merged {duplicate.company_name} ({duplicate.source}) into {existing.company_name} ({existing.source})"
        )
