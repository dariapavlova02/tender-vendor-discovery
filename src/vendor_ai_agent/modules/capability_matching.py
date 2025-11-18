"""LLM-backed capability scoring of vendors."""
from __future__ import annotations

from typing import Iterable, List

from ..contracts import CapabilityMatcherContract
from ..models import TenderProfile, VendorMatchResult, VendorRecord


class CapabilityMatcher(CapabilityMatcherContract):
    """Assigns placeholder scores and rationales to vendors."""

    def score(self, profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorMatchResult]:
        """Produce deterministic scores to wire up pipeline orchestration."""

        results: List[VendorMatchResult] = []
        project_type = profile.doc_extracted.structured.project_type if profile.doc_extracted else None
        for idx, vendor in enumerate(vendors, start=1):
            score = 100 - (idx - 1) * 5
            rationale = (
                f"Placeholder rationale: {vendor.company_name} is assumed to match "
                f"{project_type or 'the tender'} requirements."
            )
            results.append(
                VendorMatchResult(
                    vendor=vendor,
                    capability_match_score=max(score, 0),
                    rationale=rationale,
                    references=[vendor.website or ""],
                )
            )
        return results
