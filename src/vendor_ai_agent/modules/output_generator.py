"""Result serialization utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from ..contracts import OutputGeneratorContract
from ..models import VendorMatchResult


class OutputGenerator(OutputGeneratorContract):
    """Writes pipeline results to disk in multiple formats."""

    def to_excel(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        df = self._to_dataframe(matches)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(path, index=False)
        return path

    def to_csv(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        df = self._to_dataframe(matches)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return path

    def to_json(self, matches: Iterable[VendorMatchResult], path: Path) -> Path:
        data = [self._to_dict(match) for match in matches]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        return path

    def _to_dataframe(self, matches: Iterable[VendorMatchResult]) -> pd.DataFrame:
        records = [self._to_dict(match) for match in matches]
        return pd.DataFrame(records)

    @staticmethod
    def _to_dict(match: VendorMatchResult) -> dict:
        return {
            "company_name": match.vendor.company_name,
            "website": match.vendor.website,
            "email": match.vendor.email,
            "phone": match.vendor.phone,
            "location": match.vendor.location,
            "industry": match.vendor.industry,
            "source": match.vendor.source,
            "match_status": match.vendor.filtering_metadata.get("match_status"),
            "scoring_method": match.vendor.filtering_metadata.get("scoring_method"),
            "email_source": match.vendor.filtering_metadata.get("email_source"),
            "email_confidence": match.vendor.filtering_metadata.get("email_confidence"),
            "email_validation": match.vendor.filtering_metadata.get("email_validation"),
            "capability_match_score": match.capability_match_score,
            "rationale": match.rationale,
            "references": match.references,
            "enrichment_flags": match.vendor.enrichment_flags,
        }
