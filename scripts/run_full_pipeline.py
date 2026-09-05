#!/usr/bin/env python3
"""Run the Tender Vendor Discovery pipeline with optional API ingestion."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from vendor_ai_agent.ingestion.models import DateRange, TenderIngestionRequest
from vendor_ai_agent.pipeline import TenderVendorPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="End-to-end pipeline runner")
    parser.add_argument(
        "files",
        nargs="+",
        help="Paths to tender documents or directories",
    )
    parser.add_argument("--country", choices=("USA", "CAN"), help="Country for ingestion request")
    parser.add_argument(
        "--source-system",
        dest="source_system",
        choices=("SAM", "CANADABUYS", "MANUAL"),
        help="Source system identifier",
    )
    parser.add_argument("--solnum", help="Solicitation number (SAM)")
    parser.add_argument("--reference", help="Reference number (CanadaBuys)")
    parser.add_argument("--posted-from", dest="posted_from", help="SAM postedFrom MM/DD/YYYY")
    parser.add_argument("--posted-to", dest="posted_to", help="SAM postedTo MM/DD/YYYY")
    return parser


def build_ingestion_request(args: argparse.Namespace) -> Optional[TenderIngestionRequest]:
    if not args.source_system or args.source_system == "MANUAL":
        return None
    if args.source_system == "SAM":
        if not args.solnum or not args.posted_from or not args.posted_to:
            raise SystemExit("SAM ingestion requires --solnum, --posted-from, --posted-to")
        return TenderIngestionRequest(
            country=args.country or "USA",
            source_system="SAM",
            solicitation_number=args.solnum,
            date_range=DateRange(start=args.posted_from, end=args.posted_to),
        )
    if args.source_system == "CANADABUYS":
        if not args.reference:
            raise SystemExit("CanadaBuys ingestion requires --reference")
        return TenderIngestionRequest(
            country=args.country or "CAN",
            source_system="CANADABUYS",
            reference_number=args.reference,
        )
    return None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ingestion_request = build_ingestion_request(args)
    disable_auto_ingestion = args.source_system == "MANUAL"
    pipeline = TenderVendorPipeline()
    artifacts = pipeline.run(
        [Path(p) for p in args.files],
        ingestion_request=ingestion_request,
        disable_auto_ingestion=disable_auto_ingestion,
    )

    profile = artifacts.tender_profile
    print("=== API Metadata ===")
    print("External ID:", profile.api_metadata.external_id)
    print("Title:", profile.api_metadata.title)
    print("Buyer:", profile.api_metadata.buyer.name)
    print("Attachments fetched:", len(profile.api_metadata.attachments))
    print("=== Document Extraction ===")
    print("Project type:", profile.doc_extracted.structured.project_type)
    print("Sector:", profile.doc_extracted.structured.sector)
    print("Solicitation #:", profile.doc_extracted.structured.solicitation_number)
    print("Reference #:", profile.doc_extracted.structured.reference_number)
    print("Scope snippet:", profile.doc_extracted.sections.scope_of_work[:300])


if __name__ == "__main__":
    main()
