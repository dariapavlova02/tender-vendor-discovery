#!/usr/bin/env python3
"""Show complete data that will be passed to LLM."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

data_folder = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition")
pdf_files = list(data_folder.rglob("*.pdf"))

print(f"=== INPUT FILES ===")
print(f"Total PDF files found: {len(pdf_files)}")
for f in pdf_files[:10]:
    print(f"  - {f.name}")
if len(pdf_files) > 10:
    print(f"  ... and {len(pdf_files) - 10} more files")

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(pdf_files, disable_auto_ingestion=True)

profile = artifacts.tender_profile
sections = profile.doc_extracted.sections
structured = profile.doc_extracted.structured

print(f"\n" + "="*80)
print("=== DATA THAT WILL BE PASSED TO LLM ===")
print("="*80)

print(f"\n### 1. TEXT SECTIONS ###")
print(f"Scope of work: {len(sections.scope_of_work)} chars")
if sections.scope_of_work:
    print(f"  Preview: {sections.scope_of_work[:300]}...")

print(f"\nTechnical requirements: {len(sections.technical_requirements or '')} chars")
if sections.technical_requirements:
    print(f"  Preview: {sections.technical_requirements[:200]}...")

print(f"\nMandatory requirements: {len(sections.mandatory_requirements or '')} chars")
if sections.mandatory_requirements:
    print(f"  Preview: {sections.mandatory_requirements[:200]}...")

print(f"\nVendor qualifications: {len(sections.vendor_qualifications or '')} chars")
print(f"Evaluation criteria: {len(sections.evaluation_criteria or '')} chars")
print(f"Location details: {len(sections.location_details or '')} chars")
print(f"Timeline details: {len(sections.timeline_details or '')} chars")

print(f"\n### 2. TABLE SUMMARIES (for LLM preview) ###")
print(f"Total length: {len(sections.table_summaries)} chars")
print(f"Number of tables: {len(sections.tables)}")
if sections.table_summaries:
    print(f"\n{sections.table_summaries}\n")

print(f"\n### 3. FULL TABLES (Markdown format) ###")
print(f"Total tables available: {len(sections.tables)}")
total_table_chars = sum(len(t.content) for t in sections.tables)
print(f"Total table content: {total_table_chars:,} chars")

print(f"\nFirst 3 tables content:")
for i, table in enumerate(sections.tables[:3], 1):
    print(f"\n--- Table {i}: {table.title[:60]} ---")
    print(f"Source: {Path(table.source_path).name if table.source_path else 'N/A'}")
    print(f"Length: {len(table.content)} chars")
    lines = table.content.split('\n')
    print(f"Preview (first 15 lines):")
    for line in lines[:15]:
        print(f"  {line}")
    if len(lines) > 15:
        print(f"  ... ({len(lines) - 15} more lines)")

print(f"\n### 4. STRUCTURED DATA (extracted by regex) ###")
print(f"Project Type: {structured.project_type}")
print(f"Sector: {structured.sector}")
print(f"Solicitation: {structured.solicitation_number}")
print(f"Reference: {structured.reference_number}")
print(f"Location: {structured.location.city}, {structured.location.state_province}")

print(f"\nVolumes: {len(structured.volumes)} items")
for i, vol in enumerate(structured.volumes[:10], 1):
    print(f"  {i}. {vol.item[:60]} | Qty: {vol.quantity} | Unit: {vol.unit}")
if len(structured.volumes) > 10:
    print(f"  ... and {len(structured.volumes) - 10} more items")

print(f"\nTechnical Keywords: {len(structured.technical_keywords)}")
print(f"  {structured.technical_keywords[:10]}")

print(f"\nRequired Certifications: {structured.required_certifications}")
print(f"Required Licenses: {structured.required_licenses}")

print(f"\n" + "="*80)
print("=== TOTAL DATA SIZE FOR LLM ===")
print("="*80)

text_sections_size = (
    len(sections.scope_of_work) +
    len(sections.technical_requirements or '') +
    len(sections.mandatory_requirements or '') +
    len(sections.vendor_qualifications or '') +
    len(sections.evaluation_criteria or '') +
    len(sections.location_details or '') +
    len(sections.timeline_details or '')
)

print(f"Text sections: {text_sections_size:,} chars")
print(f"Table summaries: {len(sections.table_summaries):,} chars")
print(f"Full tables (Markdown): {total_table_chars:,} chars")
print(f"TOTAL: {text_sections_size + len(sections.table_summaries) + total_table_chars:,} chars")
print(f"Estimated tokens (chars/4): ~{(text_sections_size + len(sections.table_summaries) + total_table_chars) // 4:,} tokens")

print(f"\n### COMPARISON ###")
total_raw_sections = sum(len(s.content) for s in artifacts.tender_sections)
print(f"Raw sections (before filtering): {total_raw_sections:,} chars")
filtered_size = text_sections_size + len(sections.table_summaries) + total_table_chars
print(f"Filtered data (for LLM): {filtered_size:,} chars")
reduction = 100 * (1 - filtered_size / total_raw_sections) if total_raw_sections > 0 else 0
print(f"Data reduction: {reduction:.1f}%")
