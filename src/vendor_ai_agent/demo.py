"""An authored export example; not a discovery or model-quality evaluation."""
from pathlib import Path

from .models import VendorMatchResult, VendorRecord
from .modules.output_generator import OutputGenerator


def example_matches() -> list[VendorMatchResult]:
    return [VendorMatchResult(
        vendor=VendorRecord(
            company_name="Example Grounds Services",
            website="https://grounds.example",
            email="contact@grounds.example",
            location="Ontario, Canada",
            industry="Grounds maintenance",
            source="illustrative_fixture",
            filtering_metadata={
                "match_status": "needs_review",
                "scoring_method": "authored_example",
                "email_source": "authored_example",
                "email_confidence": None,
                "email_validation": "not_validated",
            },
        ),
        capability_match_score=75.0,
        rationale="Illustrative score only. Example services include mowing and seasonal cleanup; insurance and service area need review.",
        references=["https://grounds.example/services"],
    )]


def export_demo(output_dir: Path) -> None:
    matches = example_matches()
    generator = OutputGenerator()
    generator.to_json(matches, output_dir / "vendor_matches.json")
    generator.to_csv(matches, output_dir / "vendor_matches.csv")
    generator.to_excel(matches, output_dir / "vendor_matches.xlsx")
