#!/usr/bin/env python3
"""Test script to check vendor discovery."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

print("\n=== RAW VENDORS ===")
print(f"Total: {len(artifacts.raw_vendors)}")
for i, vendor in enumerate(artifacts.raw_vendors, 1):
    print(f"\n[{i}] {vendor.company_name}")
    print(f"    Industry: {vendor.industry or 'N/A'}")
    print(f"    Location: {vendor.location or 'N/A'}")
    print(f"    Email: {vendor.email or 'No email'}")
    print(f"    Source: {vendor.source}")

print("\n\n=== ENRICHED VENDORS ===")
print(f"Total: {len(artifacts.enriched_vendors)}")
for i, vendor in enumerate(artifacts.enriched_vendors, 1):
    print(f"\n[{i}] {vendor.company_name}")
    print(f"    Email: {vendor.email}")
    print(f"    Phone: {vendor.phone or 'N/A'}")
    print(f"    Enrichment: {', '.join(vendor.enrichment_flags) if vendor.enrichment_flags else 'None'}")

print("\n\n=== FINAL MATCHES ===")
print(f"Total: {len(artifacts.final_matches)}")
for i, match in enumerate(artifacts.final_matches, 1):
    print(f"\n[{i}] {match.vendor.company_name}")
    print(f"    Score: {match.capability_match_score:.2f}")
    print(f"    Rationale: {match.rationale[:200]}")
