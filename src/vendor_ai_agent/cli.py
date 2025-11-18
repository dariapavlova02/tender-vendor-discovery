"""Command-line entrypoint for the Tender Vendor AI Agent MVP."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .pipeline import TenderVendorPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Tender Vendor AI Agent pipeline.")
    parser.add_argument("tender_files", nargs="+", type=Path, help="Tender document paths")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated result files (defaults to ./outputs)",
    )
    parser.add_argument(
        "--base-name",
        default="tender_vendors",
        help="Base filename for exported artifacts",
    )
    return parser


def main(argv: List[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    pipeline = TenderVendorPipeline()
    artifacts = pipeline.run(args.tender_files)
    base_name = args.base_name or pipeline.context.config.output.base_filename
    pipeline.save_outputs(artifacts.final_matches, base_name=base_name, directory=args.output_dir)
    print(
        f"Processed {len(artifacts.tender_sections)} sections and "
        f"generated {len(artifacts.final_matches)} vendor matches."
    )


if __name__ == "__main__":
    main()
