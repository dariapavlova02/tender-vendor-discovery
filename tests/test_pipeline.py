from pathlib import Path

from vendor_ai_agent.pipeline import TenderVendorPipeline


def test_pipeline_runs_with_placeholder_sections(tmp_path: Path) -> None:
    dummy_file = tmp_path / "tender.txt"
    dummy_file.write_text("Sample tender content")

    pipeline = TenderVendorPipeline()
    artifacts = pipeline.run([dummy_file])

    assert artifacts.tender_sections, "Expected parsed sections"
    assert artifacts.final_matches, "Expected placeholder vendor matches"
