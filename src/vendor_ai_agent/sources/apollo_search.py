"""Apollo.io discovery source using mixed_companies/search."""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import requests

from ..models import TenderProfile, VendorRecord
from .base import BaseVendorSource

logger = logging.getLogger(__name__)


class ApolloSearchSource(BaseVendorSource):
    ENDPOINT = "https://api.apollo.io/v1/mixed_companies/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        per_page: int = 100,
        max_pages: int = 1,
    ) -> None:
        super().__init__(name="apollo_search")
        self.api_key = api_key or os.getenv("APOLLO_API_KEY")
        self.per_page = max(1, min(per_page, 100))
        self.max_pages = max(1, max_pages)

    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        if not self.api_key:
            logger.warning("Apollo API key not configured; skipping Apollo search")
            return []

        payload_base = {
            "per_page": self.per_page,
            "sort_by": "relevance",
            "filters": self._build_filters(profile),
            "q": self._build_query(profile),
        }
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        vendors: List[VendorRecord] = []
        for page in range(1, self.max_pages + 1):
            payload = dict(payload_base)
            payload["page"] = page
            try:
                response = requests.post(
                    self.ENDPOINT, headers=headers, json=payload, timeout=30
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("Apollo search failed on page %s: %s", page, exc)
                break

            data = response.json()
            orgs = data.get("organizations", []) or []
            vendors.extend(self._map_organizations(orgs))

            pagination = data.get("pagination") or {}
            total_pages = pagination.get("total_pages") or page
            if page >= total_pages:
                break

        logger.info("Apollo search returned %s vendors", len(vendors))
        return vendors

    def _build_filters(self, profile: TenderProfile) -> dict:
        filters: dict = {}
        location = self._resolve_location(profile)
        if location:
            filters["organization_locations"] = location

        headcount_filters = self._resolve_headcount(profile)
        if headcount_filters:
            filters["employee_headcount"] = headcount_filters

        industry = self._resolve_industry(profile)
        if industry:
            filters["industry"] = industry

        return filters

    def _resolve_location(self, profile: TenderProfile) -> List[str]:
        locations: List[str] = []
        structured_loc = profile.doc_extracted.structured.location if profile.doc_extracted else None
        if structured_loc and structured_loc.country:
            locations.append(structured_loc.country)
        elif profile.dynamic_context and profile.dynamic_context.country:
            locations.append(profile.dynamic_context.country)
        elif profile.country:
            locations.append(profile.country)
        return locations

    def _resolve_industry(self, profile: TenderProfile) -> List[str]:
        industry: List[str] = []
        structured = profile.doc_extracted.structured if profile.doc_extracted else None
        if structured and structured.sector:
            industry.append(structured.sector)
        elif profile.dynamic_context and profile.dynamic_context.sector:
            industry.append(profile.dynamic_context.sector)
        return industry

    def _resolve_headcount(self, profile: TenderProfile) -> List[str]:
        constraints = (
            profile.doc_extracted.structured.vendor_constraints
            if profile.doc_extracted
            else None
        )
        headcounts = []
        size = constraints.business_size if constraints else None
        if size == "SMALL_ONLY":
            headcounts = ["1-10", "11-50", "51-200"]
        elif size:
            headcounts = ["51-200", "201-500"]
        else:
            headcounts = ["11-50", "51-200", "201-500", "501-1000"]
        return headcounts

    def _build_query(self, profile: TenderProfile) -> str:
        structured = profile.doc_extracted.structured if profile.doc_extracted else None
        parts: List[str] = []
        if structured and structured.project_type:
            parts.append(structured.project_type)
        if profile.dynamic_context and profile.dynamic_context.technical_keywords:
            keywords = " OR ".join(profile.dynamic_context.technical_keywords[:5])
            parts.append(keywords)
        return " OR ".join(parts) if parts else "technology"

    def _map_organizations(self, organizations: List[dict]) -> List[VendorRecord]:
        mapped: List[VendorRecord] = []
        for org in organizations:
            name = org.get("name")
            if not name:
                continue
            website = org.get("website_url") or org.get("primary_domain")
            location_parts = [
                org.get("city"),
                org.get("state"),
                org.get("country"),
            ]
            location = ", ".join(filter(None, location_parts)) or None
            vendor = VendorRecord(
                company_name=name,
                website=website,
                source=self.name,
                location=location,
                city=org.get("city"),
                state=org.get("state"),
                country=org.get("country"),
                business_types=[],
                filtering_metadata={
                    "apollo_id": org.get("id"),
                    "apollo_employee_count": org.get("estimated_num_employees"),
                    "apollo_last_activity": org.get("last_activity_date"),
                },
            )
            mapped.append(vendor)
        return mapped
