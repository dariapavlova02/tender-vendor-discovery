"""Multi-stage filtering and ranking logic for vendor candidates."""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Tuple

from ..config import FilteringConfig
from ..contracts import VendorFilterContract
from ..models import FilteringMetrics, TenderProfile, VendorRecord
from .filtering.duplicate_detector import DuplicateDetector
from .filtering.eligibility_checker import EligibilityChecker
from .filtering.geographic_matcher import GeographicMatcher

logger = logging.getLogger(__name__)


class VendorFilter(VendorFilterContract):
    """Multi-stage geographic and rule-based filtering with observability."""

    def __init__(self, config: Optional[FilteringConfig] = None):
        self.config = config or FilteringConfig()
        self.geographic_matcher = GeographicMatcher(
            local_boost=self.config.local_preference_boost,
            regional_boost=self.config.regional_preference_boost,
            enable_local_first=self.config.enable_local_first,
        )
        self.duplicate_detector = DuplicateDetector(merge_duplicates=True)
        self.eligibility_checker = EligibilityChecker(
            enable_set_aside=self.config.enable_set_aside_filtering,
            enable_size_heuristics=self.config.enable_size_heuristics,
            minimum_contract_value_ratio=self.config.minimum_contract_value_ratio,
        )
        self.metrics = FilteringMetrics()

    def filter(
        self, profile: TenderProfile, vendors: Iterable[VendorRecord]
    ) -> List[VendorRecord]:
        vendor_list = list(vendors)
        self.metrics = FilteringMetrics(total_input=len(vendor_list))

        logger.info(f"Starting multi-stage filtering with {len(vendor_list)} vendors")

        if self.config.enable_duplicate_removal:
            vendor_list, duplicates = self._stage_duplicate_removal(vendor_list)
            self.metrics.duplicates_removed = duplicates
        else:
            logger.info("Duplicate removal disabled")

        if self.config.enable_geographic:
            vendor_list, local_count, national_count = self._stage_geographic_filtering(
                profile, vendor_list
            )
            self.metrics.local_vendors = local_count
            self.metrics.national_vendors = national_count
            self.metrics.geo_filtered = national_count
        else:
            logger.info("Geographic filtering disabled")

        if self.config.enable_eligibility_checks:
            vendor_list, filter_reasons = self._stage_eligibility_filtering(
                profile, vendor_list
            )
            self.metrics.filter_reasons = filter_reasons
            self.metrics.eligibility_filtered = sum(filter_reasons.values())
        else:
            logger.info("Eligibility filtering disabled")

        vendor_list = self._stage_preliminary_ranking(profile, vendor_list)

        if self.config.max_candidates and len(vendor_list) > self.config.max_candidates:
            logger.info(
                f"Limiting to top {self.config.max_candidates} candidates (from {len(vendor_list)})"
            )
            vendor_list = vendor_list[: self.config.max_candidates]

        self.metrics.final_count = len(vendor_list)

        self._log_metrics()

        return vendor_list

    def _stage_duplicate_removal(
        self, vendors: List[VendorRecord]
    ) -> Tuple[List[VendorRecord], int]:
        logger.info(f"Stage 1: Duplicate Removal ({len(vendors)} vendors)")
        deduplicated, count = self.duplicate_detector.deduplicate(vendors)
        logger.info(f"  → {len(deduplicated)} unique vendors ({count} duplicates removed)")
        return deduplicated, count

    def _stage_geographic_filtering(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> Tuple[List[VendorRecord], int, int]:
        logger.info(f"Stage 2: Geographic Filtering ({len(vendors)} vendors)")

        expansion_mode = len(vendors) < self.config.national_expansion_threshold

        if expansion_mode:
            logger.info(
                f"  → National expansion triggered (vendor count {len(vendors)} < {self.config.national_expansion_threshold})"
            )

        filtered, local_count, national_count = (
            self.geographic_matcher.filter_by_geography(
                profile, vendors, expansion_mode=expansion_mode
            )
        )

        logger.info(
            f"  → {len(filtered)} vendors after geo filtering "
            f"({local_count} local, {national_count} national excluded unless expansion)"
        )

        return filtered, local_count, national_count

    def _stage_eligibility_filtering(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> Tuple[List[VendorRecord], dict]:
        logger.info(f"Stage 3: Eligibility Filtering ({len(vendors)} vendors)")
        eligible, reasons = self.eligibility_checker.filter_eligible(profile, vendors)
        logger.info(f"  → {len(eligible)} eligible vendors")
        return eligible, reasons

    def _stage_preliminary_ranking(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> List[VendorRecord]:
        logger.info(f"Stage 4: Preliminary Ranking ({len(vendors)} vendors)")

        for vendor in vendors:
            self.eligibility_checker.calculate_preliminary_score(profile, vendor)

        ranked = sorted(
            vendors,
            key=lambda v: (v.preliminary_score + v.geo_score, v.company_name),
            reverse=True,
        )

        if ranked:
            logger.info(
                f"  → Top vendor: {ranked[0].company_name} "
                f"(score: {ranked[0].preliminary_score:.1f}, geo: {ranked[0].geo_score:.1f})"
            )

        return ranked

    def _log_metrics(self) -> None:
        if not self.config.log_filtering_decisions:
            return

        logger.info("=" * 60)
        logger.info("FILTERING METRICS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total input vendors:       {self.metrics.total_input}")
        logger.info(f"Duplicates removed:        {self.metrics.duplicates_removed}")
        logger.info(f"Geographic filtered:       {self.metrics.geo_filtered}")
        logger.info(f"  - Local vendors:         {self.metrics.local_vendors}")
        logger.info(f"  - National vendors:      {self.metrics.national_vendors}")
        logger.info(f"Eligibility filtered:      {self.metrics.eligibility_filtered}")
        if self.metrics.filter_reasons:
            for reason, count in sorted(
                self.metrics.filter_reasons.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"  - {reason}: {count}")
        logger.info(f"Final vendor count:        {self.metrics.final_count}")
        logger.info(
            f"Total filtered:            {self.metrics.total_input - self.metrics.final_count}"
        )
        logger.info("=" * 60)

    def get_metrics(self) -> FilteringMetrics:
        return self.metrics
