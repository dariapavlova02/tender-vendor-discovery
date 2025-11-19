#!/usr/bin/env python3
"""Check actual table content in sections."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

print(f"Total sections: {len(artifacts.tender_sections)}\n")

# Find sections with tables
table_sections = [s for s in artifacts.tender_sections if '|' in s.content]
print(f"Sections with tables: {len(table_sections)}\n")

# Show first table section
if table_sections:
    section = table_sections[0]
    print(f"=== SAMPLE TABLE SECTION ===")
    print(f"Title: {section.title}")
    print(f"Content:\n{section.content[:1500]}\n")
