#!/usr/bin/env python3
"""Test script to verify section extraction."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"),
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

profile = artifacts.tender_profile
print(f"\n=== RAW SECTIONS ({len(artifacts.tender_sections)} total) ===")
for i, section in enumerate(artifacts.tender_sections[:15], 1):  # First 15
    print(f"\n[{i}] {section.title[:80]}")
    print(f"    Source: {Path(section.source_path).name if section.source_path else 'N/A'}")
    print(f"    Content: {section.content[:120]}...")

print(f"\n\n=== STRUCTURED SECTIONS ===")
sections = profile.doc_extracted.sections
print(f"Scope of work: {len(sections.scope_of_work)} chars")
print(f"Technical requirements: {len(sections.technical_requirements or '')} chars")
print(f"Mandatory requirements: {len(sections.mandatory_requirements or '')} chars")
print(f"Vendor qualifications: {len(sections.vendor_qualifications or '')} chars")

print(f"\n=== TABLE CHECK ===")
scope_has_tables = '|' in sections.scope_of_work
tech_has_tables = '|' in (sections.technical_requirements or '')
print(f"Scope has tables: {scope_has_tables}")
print(f"Technical requirements has tables: {tech_has_tables}")

if scope_has_tables or tech_has_tables:
    print("\n✅ SUCCESS: Tables are preserved in extraction!")
    text = sections.scope_of_work if scope_has_tables else sections.technical_requirements
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if '|' in line:
            # Print context around first table
            start = max(0, i-2)
            end = min(len(lines), i+8)
            print("\nTable context:")
            print('\n'.join(lines[start:end]))
            break
else:
    print("\n❌ WARNING: No tables found in structured sections!")
