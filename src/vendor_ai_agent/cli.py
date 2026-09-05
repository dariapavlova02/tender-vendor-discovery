"""Command-line interface for Tender Vendor Discovery."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

COMMANDS = {"run", "ingest-sam-csv", "ingest-cid-csv", "ingest-ccc-data", "ingest-canada-contracts"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tender document processing and vendor discovery.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Process tender documents using configured providers")
    run.add_argument("tender_files", nargs="+", type=Path)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--base-name", default="tender_vendors")
    run.add_argument("--no-auto-ingestion", action="store_true")
    for name in sorted(COMMANDS - {"run"}):
        command = commands.add_parser(name, help="Import a locally supplied source export")
        command.add_argument("file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Retain the historical `tender-vendor-agent document.pdf` invocation.
    if arguments and arguments[0] not in COMMANDS and not arguments[0].startswith("-"):
        arguments.insert(0, "run")
    args = build_parser().parse_args(arguments)
    if args.command == "run":
        from .pipeline import TenderVendorPipeline
        pipeline = TenderVendorPipeline()
        artifacts = pipeline.run(args.tender_files, disable_auto_ingestion=args.no_auto_ingestion)
        pipeline.save_outputs(artifacts.final_matches, base_name=args.base_name, directory=args.output_dir)
        print(f"Processed {len(artifacts.tender_sections)} sections; {len(artifacts.final_matches)} shortlisted vendors.")
        return
    from .database.connection import get_session
    if args.command == "ingest-canada-contracts":
        from .ingestion.canada_contracts import load_canada_contracts
        with get_session() as session:
            print(load_canada_contracts(session, str(args.file)))
        return
    if args.command == "ingest-sam-csv":
        from .ingestion.sam_csv import ingest_sam_csv
        loader = ingest_sam_csv
    elif args.command == "ingest-cid-csv":
        from .ingestion.cid_csv import ingest_cid_csv
        loader = ingest_cid_csv
    else:
        from .ingestion.ccc_loader import ingest_ccc_data
        loader = ingest_ccc_data
    print(f"Imported {loader(args.file)} records.")


if __name__ == "__main__":
    main()
