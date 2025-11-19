#!/usr/bin/env python3
"""Debug table classification."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"),
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

profile = artifacts.tender_profile
sections = profile.doc_extracted.sections

classifier = TableClassifier()

print(f"=== TABLE CLASSIFICATION ({len(sections.tables)} total tables) ===\n")

classified = {}
for i, table in enumerate(sections.tables[:15], 1):
    table_type = classifier.classify(table)
    if table_type not in classified:
        classified[table_type] = 0
    classified[table_type] += 1
    
    lines = table.content.split('\n')[:3]
    preview = '\n'.join(lines)
    
    print(f"Table {i}: {table_type.upper()}")
    print(f"Source: {table.title[:80]}")
    print(f"Preview:\n{preview}\n")

print("\n=== SUMMARY ===")
for table_type, count in sorted(classified.items()):
    print(f"{table_type}: {count} tables")
