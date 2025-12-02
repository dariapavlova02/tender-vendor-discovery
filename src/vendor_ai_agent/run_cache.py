"""Utilities for loading persisted pipeline runs (metadata + parquet tables)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import json

import pandas as pd

from vendor_ai_agent.models import ContactInfo, PipelineArtifacts, VendorMatchResult, VendorRecord


@dataclass
class RunCacheLoader:
    run_dir: Path

    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir)
        self.metadata: Optional[PipelineArtifacts] = None

    def load_metadata(self) -> PipelineArtifacts:
        if self.metadata is None:
            metadata_path = self.run_dir / "metadata.pkl"
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata not found: {metadata_path}")
            from pickle import load

            with metadata_path.open("rb") as fh:
                payload: Dict[str, Any] = load(fh)
            self.metadata = PipelineArtifacts(
                tender_sections=payload["tender_sections"],
                tender_profile=payload["tender_profile"],
                raw_vendors=[],
                enriched_vendors=[],
                final_matches=[],
                filtering_metrics=payload.get("filtering_metrics"),
            )
            self.metadata.batch_id = payload.get("batch_id", 1)
            self.metadata.processed_batches = payload.get("processed_batches", [])
            setattr(self.metadata, "raw_vendor_count", payload.get("raw_vendor_count", 0))
            setattr(self.metadata, "enriched_vendor_count", payload.get("enriched_vendor_count", 0))
            setattr(self.metadata, "final_match_count", payload.get("final_match_count", 0))
            setattr(self.metadata, "all_match_count", payload.get("all_match_count", 0))
        return self.metadata

    def _load_table(self, name: str, columns: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> pd.DataFrame:
        path = self.run_dir / f"{name}.parquet"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path, columns=list(columns) if columns else None)
        if limit is not None:
            df = df.head(limit)
        return df

    def load_final_matches(self, *, columns: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> pd.DataFrame:
        return self._load_table("final_matches", columns=columns, limit=limit)

    def load_all_matches(self, *, columns: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> pd.DataFrame:
        return self._load_table("all_matches", columns=columns, limit=limit)

    def load_raw_vendors(self, *, columns: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> pd.DataFrame:
        return self._load_table("raw_vendors", columns=columns, limit=limit)

    def load_enriched_vendors(self, *, columns: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> pd.DataFrame:
        return self._load_table("enriched_vendors", columns=columns, limit=limit)

    @staticmethod
    def _parse_json(value: Any, default: Any) -> Any:
        if value in (None, "", "null"):
            return default
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _row_to_vendor(self, row: pd.Series) -> VendorRecord:
        return VendorRecord(
            company_name=row.get("company_name", ""),
            website=row.get("website"),
            email=row.get("email"),
            phone=row.get("phone"),
            location=row.get("location"),
            city=row.get("city"),
            state=row.get("state"),
            country=row.get("country"),
            industry=row.get("industry"),
            source=row.get("source"),
            is_past_winner=bool(row.get("is_past_winner")),
            enrichment_flags=self._parse_json(row.get("enrichment_flags"), []),
            uei=row.get("uei"),
            duns=row.get("duns"),
            cage_code=row.get("cage_code"),
            business_types=self._parse_json(row.get("business_types"), []),
            primary_contact=ContactInfo(
                name=row.get("primary_contact_name"),
                email=row.get("primary_contact_email"),
                phone=row.get("primary_contact_phone"),
            ),
            geo_score=row.get("geo_score", 0.0),
            preliminary_score=row.get("preliminary_score", 0.0),
            filtering_metadata=self._parse_json(row.get("filtering_metadata"), {}),
            total_contract_value=row.get("total_contract_value"),
            contract_count=row.get("contract_count"),
        )

    def _row_to_match(self, row: pd.Series) -> VendorMatchResult:
        return VendorMatchResult(
            vendor=self._row_to_vendor(row),
            capability_match_score=row.get("capability_match_score", 0.0),
            rationale=row.get("rationale", ""),
            references=self._parse_json(row.get("references"), []),
        )

    def load_final_matches_objects(self, limit: Optional[int] = None) -> list[VendorMatchResult]:
        df = self.load_final_matches(limit=limit)
        return [self._row_to_match(row) for _, row in df.iterrows()]

    def load_all_matches_objects(self, limit: Optional[int] = None) -> list[VendorMatchResult]:
        df = self.load_all_matches(limit=limit)
        return [self._row_to_match(row) for _, row in df.iterrows()]

    def update_final_match(self, index: int, updates: Dict[str, Any]) -> None:
        path = self.run_dir / "final_matches.parquet"
        if not path.exists():
            raise FileNotFoundError("final_matches.parquet not found")
        df = pd.read_parquet(path)
        for key, value in updates.items():
            df.at[index, key] = value
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(path)

    def update_all_match(self, index: int, updates: Dict[str, Any]) -> None:
        path = self.run_dir / "all_matches.parquet"
        if not path.exists():
            raise FileNotFoundError("all_matches.parquet not found")
        df = pd.read_parquet(path)
        for key, value in updates.items():
            df.at[index, key] = value
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(path)
