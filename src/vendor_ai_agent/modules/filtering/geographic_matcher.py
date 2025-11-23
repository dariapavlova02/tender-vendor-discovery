"""Geographic matching and scoring for vendor filtering."""
from __future__ import annotations

import logging
from typing import Dict, Optional

from ...models import Address, TenderProfile, VendorRecord

logger = logging.getLogger(__name__)


US_STATE_NEIGHBORS: Dict[str, list[str]] = {
    "AL": ["FL", "GA", "MS", "TN"],
    "AK": [],
    "AZ": ["CA", "NV", "NM", "UT"],
    "AR": ["LA", "MO", "MS", "OK", "TN", "TX"],
    "CA": ["AZ", "NV", "OR"],
    "CO": ["KS", "NE", "NM", "OK", "UT", "WY"],
    "CT": ["MA", "NY", "RI"],
    "DE": ["MD", "NJ", "PA"],
    "FL": ["AL", "GA"],
    "GA": ["AL", "FL", "NC", "SC", "TN"],
    "HI": [],
    "ID": ["MT", "NV", "OR", "UT", "WA", "WY"],
    "IL": ["IN", "IA", "KY", "MO", "WI"],
    "IN": ["IL", "KY", "MI", "OH"],
    "IA": ["IL", "MN", "MO", "NE", "SD", "WI"],
    "KS": ["CO", "MO", "NE", "OK"],
    "KY": ["IL", "IN", "MO", "OH", "TN", "VA", "WV"],
    "LA": ["AR", "MS", "TX"],
    "ME": ["NH"],
    "MD": ["DE", "PA", "VA", "WV"],
    "MA": ["CT", "NH", "NY", "RI", "VT"],
    "MI": ["IN", "OH", "WI"],
    "MN": ["IA", "ND", "SD", "WI"],
    "MS": ["AL", "AR", "LA", "TN"],
    "MO": ["AR", "IL", "IA", "KS", "KY", "NE", "OK", "TN"],
    "MT": ["ID", "ND", "SD", "WY"],
    "NE": ["CO", "IA", "KS", "MO", "SD", "WY"],
    "NV": ["AZ", "CA", "ID", "OR", "UT"],
    "NH": ["ME", "MA", "VT"],
    "NJ": ["DE", "NY", "PA"],
    "NM": ["AZ", "CO", "OK", "TX"],
    "NY": ["CT", "MA", "NJ", "PA", "VT"],
    "NC": ["GA", "SC", "TN", "VA"],
    "ND": ["MN", "MT", "SD"],
    "OH": ["IN", "KY", "MI", "PA", "WV"],
    "OK": ["AR", "CO", "KS", "MO", "NM", "TX"],
    "OR": ["CA", "ID", "NV", "WA"],
    "PA": ["DE", "MD", "NJ", "NY", "OH", "WV"],
    "RI": ["CT", "MA"],
    "SC": ["GA", "NC"],
    "SD": ["IA", "MN", "MT", "NE", "ND", "WY"],
    "TN": ["AL", "AR", "GA", "KY", "MS", "MO", "NC", "VA"],
    "TX": ["AR", "LA", "NM", "OK"],
    "UT": ["AZ", "CO", "ID", "NV", "WY"],
    "VT": ["MA", "NH", "NY"],
    "VA": ["KY", "MD", "NC", "TN", "WV"],
    "WA": ["ID", "OR"],
    "WV": ["KY", "MD", "OH", "PA", "VA"],
    "WI": ["IL", "IA", "MI", "MN"],
    "WY": ["CO", "ID", "MT", "NE", "SD", "UT"],
}

CANADA_PROVINCE_NEIGHBORS: Dict[str, list[str]] = {
    "AB": ["BC", "SK", "NT"],
    "BC": ["AB", "YT", "NT"],
    "MB": ["SK", "ON", "NU"],
    "NB": ["QC", "NS", "PE"],
    "NL": ["QC"],
    "NT": ["YT", "NU", "BC", "AB", "SK"],
    "NS": ["NB", "PE"],
    "NU": ["NT", "MB"],
    "ON": ["MB", "QC"],
    "PE": ["NB", "NS"],
    "QC": ["ON", "NB", "NL"],
    "SK": ["AB", "MB", "NT"],
    "YT": ["BC", "NT"],
}


class GeographicMatcher:
    def __init__(
        self,
        local_boost: float = 20.0,
        regional_boost: float = 10.0,
        enable_local_first: bool = True,
    ):
        self.local_boost = local_boost
        self.regional_boost = regional_boost
        self.enable_local_first = enable_local_first

    def calculate_geo_score(
        self, tender_location: Address, vendor: VendorRecord
    ) -> float:
        if not tender_location or not tender_location.city:
            return 0.0

        vendor_state = self._normalize_state(vendor.state)
        vendor_city = self._normalize_city(vendor.city)
        tender_state = self._normalize_state(tender_location.state_province)
        tender_city = self._normalize_city(tender_location.city)
        tender_country = tender_location.country or "United States"

        if tender_city in ["Nationwide", "Multiple locations", "International"]:
            return 0.0

        if not vendor_state:
            return 0.0

        if tender_city and vendor_city:
            if tender_city == vendor_city and tender_state == vendor_state:
                logger.debug(
                    f"Exact city match: {vendor.company_name} in {vendor_city}, {vendor_state}"
                )
                return self.local_boost

        if tender_state and vendor_state:
            if tender_state == vendor_state:
                logger.debug(
                    f"Same state match: {vendor.company_name} in {vendor_state}"
                )
                return self.local_boost

        if self._is_neighboring_region(tender_state, vendor_state, tender_country):
            logger.debug(
                f"Neighboring region: {vendor.company_name} in {vendor_state} (tender in {tender_state})"
            )
            return self.regional_boost

        return 0.0

    def is_local_vendor(self, tender_location: Address, vendor: VendorRecord) -> bool:
        if not tender_location or not tender_location.state_province:
            return False

        tender_state = self._normalize_state(tender_location.state_province)
        vendor_state = self._normalize_state(vendor.state)

        if not vendor_state:
            return False

        return tender_state == vendor_state

    def is_regional_vendor(
        self, tender_location: Address, vendor: VendorRecord
    ) -> bool:
        if not tender_location or not tender_location.state_province:
            return False

        tender_state = self._normalize_state(tender_location.state_province)
        vendor_state = self._normalize_state(vendor.state)
        tender_country = tender_location.country or "United States"

        if not vendor_state or tender_state == vendor_state:
            return False

        return self._is_neighboring_region(tender_state, vendor_state, tender_country)

    def _is_neighboring_region(
        self, state1: Optional[str], state2: Optional[str], country: str
    ) -> bool:
        if not state1 or not state2:
            return False

        if "Canada" in country:
            neighbors = CANADA_PROVINCE_NEIGHBORS.get(state1, [])
        else:
            neighbors = US_STATE_NEIGHBORS.get(state1, [])

        return state2 in neighbors

    def _normalize_state(self, state: Optional[str]) -> Optional[str]:
        if not state:
            return None
        state_upper = state.strip().upper()
        if len(state_upper) == 2:
            return state_upper
        return state_upper[:2] if len(state_upper) > 2 else state_upper

    def _normalize_city(self, city: Optional[str]) -> Optional[str]:
        if not city:
            return None
        return city.strip().lower()

    def filter_by_geography(
        self,
        profile: TenderProfile,
        vendors: list[VendorRecord],
        expansion_mode: bool = False,
    ) -> tuple[list[VendorRecord], int, int]:
        if not self.enable_local_first:
            for vendor in vendors:
                vendor.geo_score = self.calculate_geo_score(
                    profile.doc_extracted.structured.location, vendor
                )
            return vendors, 0, len(vendors)

        tender_location = profile.doc_extracted.structured.location
        if not tender_location or not tender_location.state_province:
            if profile.api_metadata and profile.api_metadata.place_of_performance:
                tender_location = profile.api_metadata.place_of_performance

        if not tender_location or not tender_location.state_province:
            logger.warning(
                "No tender location found, skipping geographic filtering"
            )
            return vendors, 0, len(vendors)

        local_vendors = []
        regional_vendors = []
        national_vendors = []

        for vendor in vendors:
            geo_score = self.calculate_geo_score(tender_location, vendor)
            vendor.geo_score = geo_score

            if self.is_local_vendor(tender_location, vendor):
                local_vendors.append(vendor)
                vendor.filtering_metadata["geo_tier"] = "local"
            elif self.is_regional_vendor(tender_location, vendor):
                regional_vendors.append(vendor)
                vendor.filtering_metadata["geo_tier"] = "regional"
            else:
                national_vendors.append(vendor)
                vendor.filtering_metadata["geo_tier"] = "national"

        if expansion_mode:
            filtered = local_vendors + regional_vendors + national_vendors
            logger.info(
                f"Geographic expansion mode: {len(local_vendors)} local, "
                f"{len(regional_vendors)} regional, {len(national_vendors)} national"
            )
        else:
            filtered = local_vendors + regional_vendors
            logger.info(
                f"Geographic local-first mode: {len(local_vendors)} local, "
                f"{len(regional_vendors)} regional, {len(national_vendors)} excluded"
            )

        return filtered, len(local_vendors), len(national_vendors)
