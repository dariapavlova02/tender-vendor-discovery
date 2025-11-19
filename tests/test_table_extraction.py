#!/usr/bin/env python3
"""Test table extraction from DocSections."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"),
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

profile = artifacts.tender_profile
sections = profile.doc_extracted.sections
structured = profile.doc_extracted.structured

print(f"\n=== TABLES IN DocSections ===")
print(f"Total tables: {len(sections.tables)}")
print(f"Table summaries length: {len(sections.table_summaries)} chars")

if sections.table_summaries:
    print(f"\n=== TABLE SUMMARIES ===")
    print(sections.table_summaries)

print(f"\n=== FIRST 3 TABLES (if any) ===")
for i, table in enumerate(sections.tables[:3], 1):
    print(f"\n--- Table {i} ---")
    print(f"Title: {table.title[:80]}")
    print(f"Source: {Path(table.source_path).name if table.source_path else 'N/A'}")
    print(f"Content preview:")
    lines = table.content.split('\n')[:10]
    for line in lines:
        print(f"  {line}")

print(f"\n=== VOLUMES EXTRACTED ===")
print(f"Total volumes: {len(structured.volumes)}")
for i, vol in enumerate(structured.volumes[:10], 1):
    print(f"  {i}. Item: {vol.item[:80]}, Qty: {vol.quantity}, Unit: {vol.unit}")

print(f"\n=== TECHNICAL KEYWORDS ===")
print(f"Total keywords: {len(structured.technical_keywords)}")
print(f"Sample: {structured.technical_keywords[:10]}")
