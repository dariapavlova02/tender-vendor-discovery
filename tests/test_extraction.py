#!/usr/bin/env python3
"""Test structured data extraction quality."""
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf"),
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf"),
]

pipeline = TenderVendorPipeline()
artifacts = pipeline.run(files, disable_auto_ingestion=True)

profile = artifacts.tender_profile
structured = profile.doc_extracted.structured

print("=== STRUCTURED DATA EXTRACTION ===\n")
print(f"Project Type: {structured.project_type}")
print(f"Sector: {structured.sector}")
print(f"Solicitation: {structured.solicitation_number}")
print(f"Reference: {structured.reference_number}")
print(f"\nLocation: {structured.location.city}, {structured.location.state_province}" if structured.location.city else "Location: Not extracted")
print(f"\nVolumes: {len(structured.volumes)} items")
for vol in structured.volumes[:3]:
    print(f"  - {vol.item}: {vol.quantity} {vol.unit}")

print(f"\nRequired Experience:")
print(f"  Min years: {structured.required_experience.min_years}")
print(f"  Project types: {structured.required_experience.required_project_types[:3] if structured.required_experience.required_project_types else 'None'}")

print(f"\nRequired Licenses: {structured.required_licenses[:3] if structured.required_licenses else 'None'}")
print(f"Required Certifications: {structured.required_certifications[:3] if structured.required_certifications else 'None'}")

print(f"\nTechnical Keywords: {len(structured.technical_keywords)} found")
print(f"  Sample: {structured.technical_keywords[:5]}")

print(f"\nVendor Constraints:")
print(f"  Jurisdictions: {structured.vendor_constraints.allowed_jurisdictions}")
print(f"  Business size: {structured.vendor_constraints.business_size}")
print(f"  Special status: {structured.vendor_constraints.special_status}")

print(f"\nPackaging/Logistics:")
print(f"  Special requirements: {structured.packaging_logistics.special_requirements}")
print(f"  Lead times: {structured.packaging_logistics.lead_times_days}")

print("\n=== EXTRACTION QUALITY CHECK ===")
issues = []
if not structured.solicitation_number:
    issues.append("❌ Solicitation number not extracted")
else:
    print("✅ Solicitation number extracted")
    
if not structured.reference_number:
    issues.append("❌ Reference number not extracted")
else:
    print("✅ Reference number extracted")

if not structured.volumes:
    issues.append("⚠️  No volumes extracted from tables")
else:
    print(f"✅ {len(structured.volumes)} volume items extracted")

if not structured.technical_keywords:
    issues.append("⚠️  No technical keywords extracted")
else:
    print(f"✅ {len(structured.technical_keywords)} technical keywords extracted")

if issues:
    print("\n" + "\n".join(issues))
