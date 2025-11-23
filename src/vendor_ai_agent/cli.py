"""Command-line entrypoint for the Tender Vendor AI Agent MVP."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from .pipeline import TenderVendorPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Tender Vendor AI Agent pipeline.")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("run", help="Run the full pipeline")
    pipeline_parser.add_argument("tender_files", nargs="+", type=Path, help="Tender document paths")
    pipeline_parser.add_argument("--output-dir", type=Path, default=None)
    pipeline_parser.add_argument("--base-name", default="tender_vendors")
    
    # Ingest CSV command
    ingest_parser = subparsers.add_parser("ingest-sam-csv", help="Ingest SAM.gov CSV export")
    ingest_parser.add_argument("csv_file", type=Path, help="Path to SAM.gov CSV export")
    
    # Ingest CID command
    cid_parser = subparsers.add_parser("ingest-cid-csv", help="Ingest Canadian Importers Database CSV")
    cid_parser.add_argument("csv_file", type=Path, help="Path to CID CSV export")
    
    # Ingest CCC command
    ccc_parser = subparsers.add_parser("ingest-ccc-data", help="Ingest CCC Data (CSV or JSON)")
    ccc_parser.add_argument("file", type=Path, help="Path to CCC export file")
    
    # Ingest Canada Contracts command
    canada_parser = subparsers.add_parser("ingest-canada-contracts", help="Ingest Canada contract history CSV")
    canada_parser.add_argument("csv_file", type=Path, help="Path to Canada contracts CSV")
    
    return parser


def main(argv: List[str] | None = None) -> None:
    load_dotenv()
    
    parser = build_parser()
    args = parser.parse_args(argv)
    
    if args.command == "ingest-sam-csv":
        from .ingestion.sam_csv import ingest_sam_csv
        try:
            count = ingest_sam_csv(args.csv_file)
            print(f"Successfully ingested {count} vendors from {args.csv_file}")
        except Exception as e:
            print(f"Error ingesting CSV: {e}")
            exit(1)
    elif args.command == "ingest-cid-csv":
        from .ingestion.cid_csv import ingest_cid_csv
        try:
            count = ingest_cid_csv(args.csv_file)
            print(f"Successfully ingested {count} vendors from {args.csv_file}")
        except Exception as e:
            print(f"Error ingesting CID CSV: {e}")
            exit(1)
    elif args.command == "ingest-ccc-data":
        from .ingestion.ccc_loader import ingest_ccc_data
        try:
            count = ingest_ccc_data(args.file)
            print(f"Successfully ingested {count} vendors from {args.file}")
        except Exception as e:
            print(f"Error ingesting CCC data: {e}")
            exit(1)
    elif args.command == "ingest-canada-contracts":
        from .ingestion.canada_contracts import load_canada_contracts
        from .database.connection import get_session
        try:
            with get_session() as session:
                stats = load_canada_contracts(session, str(args.csv_file))
                print(f"Successfully loaded Canada contracts from {args.csv_file}")
                print(f"  Vendors created: {stats['vendors_created']}")
                print(f"  Vendors updated: {stats['vendors_updated']}")
                print(f"  GSIN codes added: {stats['gsin_codes_added']}")
                print(f"  UNSPSC codes added: {stats['unspsc_codes_added']}")
                print(f"  Contacts added: {stats['contacts_added']}")
        except Exception as e:
            print(f"Error loading Canada contracts: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
    else:
        # Default to pipeline run if no command or 'run' command (for backward compatibility if we want, but let's be strict with subcommands or handle default)
        # To maintain backward compatibility with "tender-vendor-agent file1 file2", we need to check if args.command is None but tender_files is present in top level?
        # argparse logic above moved tender_files to 'run' subparser. 
        # To keep it simple and compatible, let's check if argv has a subcommand.
        # Actually, the previous CLI just took files. Let's support both.
        
        # Re-implementing to support legacy usage (just files) + new commands requires a bit of hack or a top-level optional arg.
        # Let's stick to the plan: add a command.
        # But wait, if I change `parser.add_argument("tender_files"...)` to a subparser, I break existing `tender-vendor-agent file1` usage.
        # I should keep the top level arguments for the default behavior, and add a --ingest-csv flag OR use a proper subparser structure and maybe break compat or detect.
        
        # Better approach for now: Add a separate argument group or check.
        # Or just add `ingest` as a subcommand and keep `tender_files` as positional at top level? No, that's ambiguous.
        
        # Let's try to detect if the first arg is a known command.
        pass

    # Re-doing the parser construction to be safe and compatible
    parser = argparse.ArgumentParser(description="Run the Tender Vendor AI Agent pipeline.")
    subparsers = parser.add_subparsers(dest="command")
    
    # Ingest command
    ingest = subparsers.add_parser("ingest-sam-csv")
    ingest.add_argument("csv_file", type=Path)
    
    # We also want to support "tender-vendor-agent file1 file2"
    # So we add the files argument to the main parser too, but make it optional?
    # Or we use parse_known_args.
    
    # Let's go with a cleaner approach:
    # If "ingest-sam-csv" is the first argument, use that mode.
    # Otherwise, assume pipeline mode.
    
    import sys
    if argv is None:
        argv = sys.argv[1:]
        
    if argv and argv[0] == "ingest-sam-csv":
        # Use the subparser logic just for this
        sub_parser = argparse.ArgumentParser()
        sub_parser.add_argument("command")
        sub_parser.add_argument("csv_file", type=Path)
        args = sub_parser.parse_args(argv)
        
        from .ingestion.sam_csv import ingest_sam_csv
        try:
            count = ingest_sam_csv(args.csv_file)
            print(f"Successfully ingested {count} vendors from {args.csv_file}")
        except Exception as e:
            print(f"Error ingesting CSV: {e}")
            exit(1)
        return

    # Legacy/Default Pipeline Mode
    parser = argparse.ArgumentParser()
    parser.add_argument("tender_files", nargs="+", type=Path, help="Tender document paths")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--base-name", default="tender_vendors")
    
    args = parser.parse_args(argv)
    pipeline = TenderVendorPipeline()
    artifacts = pipeline.run(args.tender_files)
    base_name = args.base_name or pipeline.context.config.output.base_filename
    pipeline.save_outputs(artifacts.final_matches, base_name=base_name, directory=args.output_dir)
    print(
        f"Processed {len(artifacts.tender_sections)} sections and "
        f"generated {len(artifacts.final_matches)} vendor matches."
    )
