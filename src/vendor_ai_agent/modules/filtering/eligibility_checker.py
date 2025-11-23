"""Eligibility and mandatory criteria filtering."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ...models import TenderProfile, VendorRecord

logger = logging.getLogger(__name__)


class EligibilityChecker:
    def __init__(
        self,
        enable_set_aside: bool = True,
        enable_size_heuristics: bool = True,
        minimum_contract_value_ratio: float = 0.1,
    ):
        self.enable_set_aside = enable_set_aside
        self.enable_size_heuristics = enable_size_heuristics
        self.minimum_contract_value_ratio = minimum_contract_value_ratio

    def filter_eligible(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> tuple[List[VendorRecord], Dict[str, int]]:
        eligible = []
        filter_reasons: Dict[str, int] = {}

        for vendor in vendors:
            reason = self._check_eligibility(profile, vendor)
            if reason:
                filter_reasons[reason] = filter_reasons.get(reason, 0) + 1
                vendor.filtering_metadata["exclusion_reason"] = reason
                logger.debug(f"Filtered {vendor.company_name}: {reason}")
            else:
                eligible.append(vendor)

        logger.info(
            f"Eligibility filtering: {len(vendors)} -> {len(eligible)} "
            f"({len(vendors) - len(eligible)} filtered)"
        )
        if filter_reasons:
            logger.info(f"Filter reasons: {filter_reasons}")

        return eligible, filter_reasons

    def _check_eligibility(
        self, profile: TenderProfile, vendor: VendorRecord
    ) -> Optional[str]:
        if self.enable_set_aside:
            reason = self._check_set_aside(profile, vendor)
            if reason:
                return reason

        if self.enable_size_heuristics:
            reason = self._check_size_capacity(profile, vendor)
            if reason:
                return reason

        reason = self._check_naics_mismatch(profile, vendor)
        if reason:
            return reason

        return None

    def _check_set_aside(
        self, profile: TenderProfile, vendor: VendorRecord
    ) -> Optional[str]:
        if not profile.api_metadata or not profile.api_metadata.set_aside:
            return None

        set_aside_code = profile.api_metadata.set_aside.code
        if not set_aside_code or set_aside_code == "NONE":
            return None

        required_types = self._map_set_aside_to_business_types(set_aside_code)
        if not required_types:
            return None

        if not vendor.business_types:
            return f"set_aside_missing_{set_aside_code}"

        vendor_types_lower = [bt.lower() for bt in vendor.business_types]
        for req_type in required_types:
            if req_type.lower() in vendor_types_lower:
                return None

        return f"set_aside_mismatch_{set_aside_code}"

    def _map_set_aside_to_business_types(self, set_aside_code: str) -> List[str]:
        mapping = {
            "SBA": ["8(a)", "Small Business"],
            "8A": ["8(a)"],
            "8AN": ["8(a) Native"],
            "WOSB": ["Women Owned Small Business", "WOSB"],
            "EDWOSB": ["Economically Disadvantaged WOSB", "EDWOSB"],
            "HZC": ["HUBZone"],
            "HUBZONE": ["HUBZone"],
            "SDVOSB": ["Service-Disabled Veteran-Owned", "SDVOSB"],
            "SDVOSBC": ["Service-Disabled Veteran-Owned", "SDVOSB"],
        }
        return mapping.get(set_aside_code, [])

    def _check_size_capacity(
        self, profile: TenderProfile, vendor: VendorRecord
    ) -> Optional[str]:
        if not profile.api_metadata or not profile.api_metadata.estimated_value:
            return None

        tender_value = profile.api_metadata.estimated_value.amount
        if not tender_value or tender_value <= 0:
            return None

        if not vendor.total_contract_value or vendor.total_contract_value <= 0:
            return None

        threshold = tender_value * self.minimum_contract_value_ratio

        if vendor.total_contract_value < threshold:
            logger.debug(
                f"{vendor.company_name}: contract history ${vendor.total_contract_value:,.0f} "
                f"below threshold ${threshold:,.0f} (tender: ${tender_value:,.0f})"
            )
            return "insufficient_contract_history"

        return None

    def _check_naics_mismatch(
        self, profile: TenderProfile, vendor: VendorRecord
    ) -> Optional[str]:
        return None

    def calculate_preliminary_score(
        self, profile: TenderProfile, vendor: VendorRecord
    ) -> float:
        score = 50.0

        if vendor.is_past_winner:
            score += 15.0

        if "high_value_supplier" in vendor.enrichment_flags:
            score += 10.0
        if "frequent_supplier" in vendor.enrichment_flags:
            score += 10.0

        if vendor.source in ["canada_contracts", "sam_entity"]:
            score += 5.0

        if profile.api_metadata and profile.api_metadata.estimated_value:
            tender_value = profile.api_metadata.estimated_value.amount
            if (
                tender_value
                and vendor.total_contract_value
                and vendor.total_contract_value >= tender_value
            ):
                score += 10.0

        vendor.preliminary_score = score
        return score
