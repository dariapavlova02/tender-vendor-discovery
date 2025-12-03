"""Subprocess worker that executes the discovery pipeline and writes artifacts to disk."""
from __future__ import annotations

import argparse
import gc
import logging
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import json

import pandas as pd

from vendor_ai_agent.models import PipelineArtifacts
from vendor_ai_agent.pipeline import TenderVendorPipeline

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[worker] %(levelname)s:%(message)s")


def _apply_extraction_overrides(profile, edited_data: Optional[Dict[str, Any]]) -> List[str]:
    if not edited_data:
        return []

    structured = profile.doc_extracted.structured
    changes: List[str] = []

    city = edited_data.get("city")
    if city is not None and city != structured.location.city:
        old_val = structured.location.city or "(empty)"
        structured.location.city = city
        changes.append(f"📍 City: {old_val} → {city}")

    state = edited_data.get("state")
    if state is not None and state != structured.location.state_province:
        old_val = structured.location.state_province or "(empty)"
        structured.location.state_province = state
        changes.append(f"📍 State: {old_val} → {state}")

    country = edited_data.get("country")
    if country is not None and country != structured.location.country:
        old_val = structured.location.country or "(empty)"
        structured.location.country = country
        changes.append(f"📍 Country: {old_val} → {country}")

    naics = edited_data.get("naics_codes")
    if naics is not None:
        old_codes = set(structured.naics_codes or [])
        new_codes = set(naics)
        if old_codes != new_codes:
            structured.naics_codes = naics
            changes.append(
                f"🏷️ NAICS: {', '.join(old_codes or ['(empty)'])} → {', '.join(new_codes)}"
            )

    return changes


def _vendor_to_row(vendor) -> Dict[str, Any]:
    primary_contact = vendor.primary_contact or None
    return {
        "company_name": vendor.company_name,
        "website": vendor.website,
        "email": vendor.email,
        "phone": vendor.phone,
        "location": vendor.location,
        "city": vendor.city,
        "state": vendor.state,
        "country": vendor.country,
        "industry": vendor.industry,
        "source": vendor.source,
        "is_past_winner": vendor.is_past_winner,
        "enrichment_flags": json.dumps(vendor.enrichment_flags or []),
        "uei": vendor.uei,
        "duns": vendor.duns,
        "cage_code": vendor.cage_code,
        "business_types": json.dumps(vendor.business_types or []),
        "primary_contact_name": getattr(primary_contact, "name", None),
        "primary_contact_email": getattr(primary_contact, "email", None),
        "primary_contact_phone": getattr(primary_contact, "phone", None),
        "geo_score": vendor.geo_score,
        "preliminary_score": vendor.preliminary_score,
        "filtering_metadata": json.dumps(vendor.filtering_metadata or {}),
        "total_contract_value": vendor.total_contract_value,
        "contract_count": vendor.contract_count,
    }


def _match_to_row(match) -> Dict[str, Any]:
    base = _vendor_to_row(match.vendor)
    base.update(
        {
            "capability_match_score": match.capability_match_score,
            "rationale": match.rationale,
            "references": json.dumps(match.references or []),
        }
    )
    return base


def _persist_tables(run_dir: Path, artifacts: PipelineArtifacts) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata_payload = {
        "tender_profile": artifacts.tender_profile,
        "tender_sections": artifacts.tender_sections,
        "filtering_metrics": artifacts.filtering_metrics,
        "batch_id": getattr(artifacts, "batch_id", 1),
        "processed_batches": getattr(artifacts, "processed_batches", []),
        "raw_vendor_count": len(artifacts.raw_vendors),
        "enriched_vendor_count": len(artifacts.enriched_vendors),
        "final_match_count": len(artifacts.final_matches),
        "all_match_count": len(artifacts.all_matches or artifacts.final_matches),
    }
    with (run_dir / "metadata.pkl").open("wb") as fh:
        pickle.dump(metadata_payload, fh)

    if artifacts.final_matches:
        df_final = pd.DataFrame([_match_to_row(m) for m in artifacts.final_matches])
        df_final.to_parquet(run_dir / "final_matches.parquet", index=False)

    matches = artifacts.all_matches or artifacts.final_matches
    if matches:
        df_all = pd.DataFrame([_match_to_row(m) for m in matches])
        df_all.to_parquet(run_dir / "all_matches.parquet", index=False)

    if artifacts.raw_vendors:
        df_raw = pd.DataFrame([_vendor_to_row(v) for v in artifacts.raw_vendors])
        df_raw.to_parquet(run_dir / "raw_vendors.parquet", index=False)

    if artifacts.enriched_vendors:
        df_enriched = pd.DataFrame([_vendor_to_row(v) for v in artifacts.enriched_vendors])
        df_enriched.to_parquet(run_dir / "enriched_vendors.parquet", index=False)


def run_pipeline_job(input_path: Path, output_dir: Path) -> None:
    with input_path.open("rb") as fh:
        payload = pickle.load(fh)

    config = payload["config"]
    file_paths = [Path(p) for p in payload["file_paths"]]
    edited_extraction = payload.get("edited_extraction")
    disable_auto_ingestion = payload.get("disable_auto_ingestion", False)

    logger.info("Starting worker run for %d documents", len(file_paths))
    config.output.base_filename = str(output_dir)
    pipeline = TenderVendorPipeline(config)
    artifacts = pipeline.run(file_paths, disable_auto_ingestion=disable_auto_ingestion)

    changes = _apply_extraction_overrides(artifacts.tender_profile, edited_extraction)
    if changes:
        logger.info("Manual overrides detected, rerunning discovery with updated profile")
        discovered_vendors = pipeline.context.vendor_discovery.discover(
            artifacts.tender_profile
        )
        filtered_vendors = pipeline.context.vendor_filter.filter(
            artifacts.tender_profile, discovered_vendors
        )
        filtering_metrics = pipeline.context.vendor_filter.get_metrics()
        enriched_vendors = pipeline.context.vendor_enricher.enrich(filtered_vendors)
        matches = pipeline.context.capability_matcher.score(
            artifacts.tender_profile, enriched_vendors
        )
        artifacts = PipelineArtifacts(
            tender_sections=artifacts.tender_sections,
            tender_profile=artifacts.tender_profile,
            raw_vendors=discovered_vendors,
            enriched_vendors=enriched_vendors,
            filtered_vendors=filtered_vendors,
            filtering_metrics=filtering_metrics,
            final_matches=matches,
        )

    _persist_tables(output_dir, artifacts)
    with (output_dir / "run_state.pkl").open("wb") as fh:
        pickle.dump({"changes": changes}, fh)
    logger.info("Worker completed successfully - artifacts saved to %s", output_dir)
    del artifacts
    gc.collect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pipeline worker")
    parser.add_argument("input", type=Path, help="Path to the pickled job payload")
    parser.add_argument("output", type=Path, help="Path where artifacts should be saved")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        run_pipeline_job(args.input, args.output)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Worker failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
