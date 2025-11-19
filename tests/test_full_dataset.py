#!/usr/bin/env python3
"""Test on complete OPP-1984 dataset."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

data_dir = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/")

all_pdfs = sorted(data_dir.rglob("*.pdf"))
print(f"Found {len(all_pdfs)} PDF files")

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(all_pdfs, disable_auto_ingestion=True)

profile = artifacts.tender_profile
structured = profile.doc_extracted.structured

print("\n=== FULL DATASET EXTRACTION ===\n")
print(f"Project Type: {structured.project_type}")
print(f"Sector: {structured.sector}")
print(f"Solicitation: {structured.solicitation_number}")
print(f"Reference: {structured.reference_number}")

print(f"\n✅ VOLUMES: {len(structured.volumes)} line items extracted")
print("\nSample line items:")
for vol in structured.volumes[:15]:
    print(f"  - {vol.item}")

print(f"\n✅ TECHNICAL KEYWORDS: {len(structured.technical_keywords)} unique keywords")
print(f"Keywords: {sorted(set(structured.technical_keywords))}")

print("\n=== QUALITY METRICS ===")
print(f"✅ Solicitation: {structured.solicitation_number}")
print(f"✅ Reference: {structured.reference_number}")
print(f"✅ Sector: {structured.sector}")
print(f"✅ Line items: {len(structured.volumes)}")
print(f"✅ Keywords: {len(structured.technical_keywords)}")
