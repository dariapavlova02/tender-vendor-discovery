"""Reproducible local document-to-review workflow using fictional source snapshots."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import FilteringConfig
from .models import TenderProfile, VendorMatchResult, VendorRecord
from .modules.document_parser import DocumentParser
from .modules.document_processing import SectionExtractor
from .modules.output_generator import OutputGenerator
from .modules.vendor_filter import VendorFilter

DATA_DIR = Path(__file__).with_name("demo_data")


def _checklist(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"^\s*[-*+]\s+(.+?)\s*$", text, re.MULTILINE)))


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def build_demo(tender_file: Path | None = None, vendors_file: Path | None = None) -> tuple[dict, list[VendorMatchResult]]:
    """Parse requirement bullets and compare exact service labels in a saved snapshot.

    This local demonstrator uses the production parser, section classifier,
    candidate filter and exporters. Its explicit service-label comparison is
    separate from the live LLM matcher: coverage is not a relevance probability.
    """
    tender_file = tender_file or DATA_DIR / "tender.md"
    vendors_file = vendors_file or DATA_DIR / "vendors.json"
    sections = DocumentParser().parse([tender_file])
    document = SectionExtractor().extract(sections)
    requirements = _checklist(document.technical_requirements)
    follow_up = _checklist(document.mandatory_requirements)
    if not requirements:
        raise ValueError("Demo tender needs a Technical requirements section with a bullet checklist")
    snapshot = json.loads(vendors_file.read_text())
    vendors = []
    for entry in snapshot:
        vendors.append(VendorRecord(
            company_name=entry["company_name"], website=entry.get("website"),
            email=entry.get("email"), location=entry.get("location"),
            source="fictional_source_snapshot",
            filtering_metadata={
                "services": entry["services"], "source_reference": entry["source_reference"],
                "match_status": "needs_review", "scoring_method": "demo_service_coverage",
                "email_source": "fictional_source_snapshot" if entry.get("email") else None,
                "email_validation": "not_validated" if entry.get("email") else "missing",
            },
        ))
    vendor_filter = VendorFilter(FilteringConfig(enable_geographic=False, enable_eligibility_checks=False))
    candidates = vendor_filter.filter(TenderProfile(), vendors)
    matches, rows = [], []
    for vendor in candidates:
        metadata = vendor.filtering_metadata
        services = {_normalized(service): service for service in metadata["services"]}
        evidence = [{"requirement": requirement, "listed_service": services.get(_normalized(requirement))}
                    for requirement in requirements]
        covered = sum(item["listed_service"] is not None for item in evidence)
        missing = [item["requirement"] for item in evidence if item["listed_service"] is None]
        disposition = "Review first" if covered == len(requirements) else "Partial evidence" if covered else "No service overlap"
        rationale = f"{covered}/{len(requirements)} service labels found in the supplied snapshot."
        if missing:
            rationale += " Not listed: " + ", ".join(missing) + "."
        if follow_up:
            rationale += " Request: " + "; ".join(follow_up) + "."
        match = VendorMatchResult(vendor, 100 * covered / len(requirements), rationale,
                                  references=[metadata["source_reference"]])
        matches.append(match)
        rows.append({"company_name": vendor.company_name, "email": vendor.email,
                     "source_reference": metadata["source_reference"], "covered": covered,
                     "disposition": disposition, "evidence": evidence, "missing": missing,
                     "follow_up": follow_up, "match_status": "needs_review"})
    matches.sort(key=lambda match: (-match.capability_match_score, match.vendor.company_name))
    rows.sort(key=lambda row: (-row["covered"], row["company_name"]))
    report = {"title": sections[0].title, "scope": document.scope_of_work,
              "location": document.location_details, "requirements": requirements,
              "follow_up": follow_up, "input_count": len(snapshot),
              "duplicates_removed": vendor_filter.metrics.duplicates_removed,
              "candidates": rows}
    return report, matches


def export_demo(output_dir: Path, tender_file: Path | None = None, vendors_file: Path | None = None) -> None:
    from .demo_report import render_report

    report, matches = build_demo(tender_file, vendors_file)
    generator = OutputGenerator()
    generator.to_json(matches, output_dir / "vendor_matches.json")
    generator.to_csv(matches, output_dir / "vendor_matches.csv")
    generator.to_excel(matches, output_dir / "vendor_matches.xlsx")
    (output_dir / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    (output_dir / "review.html").write_text(render_report(report), encoding="utf-8")
    for source, name in [(tender_file or DATA_DIR / "tender.md", "tender.md"),
                         (vendors_file or DATA_DIR / "vendors.json", "vendors.json")]:
        if source.resolve() != (output_dir / name).resolve():
            shutil.copyfile(source, output_dir / name)
