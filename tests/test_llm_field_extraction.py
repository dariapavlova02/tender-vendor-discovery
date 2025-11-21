"""Test LLM-powered field extraction with real tender data."""
import os
from pathlib import Path

from dotenv import load_dotenv

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
from vendor_ai_agent.modules.llm_providers import OpenAIProvider

load_dotenv()


def test_ammunition_table_extraction():
    """Test LLM extraction of ammunition line items from tables."""
    data_dir = Path(__file__).parent.parent / "data"
    ammo_pdf = data_dir / "Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition" / "RFB Addenda" / "Addendum #7" / "Amendment No.12 13 Preferred Sealed PR-8310-OPP-2TF 223 Frangible_2025.pdf"
    
    if not ammo_pdf.exists():
        print(f"❌ Test PDF not found: {ammo_pdf}")
        return
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set, skipping LLM test")
        return
    
    llm_provider = OpenAIProvider(api_key=api_key, default_model="gpt-5-mini")
    
    print("📄 Parsing PDF...")
    parser = DocumentParser()
    sections = parser.parse([ammo_pdf])
    
    print(f"✓ Extracted {len(sections)} sections")
    
    print("\n🤖 Running LLM-powered extraction...")
    extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = extractor.extract(sections)
    
    print("\n📊 Extracted Volumes:")
    if profile.doc_extracted.structured.volumes:
        for vol in profile.doc_extracted.structured.volumes[:5]:
            print(f"  • {vol.item}: {vol.quantity} {vol.unit or ''}")
        print(f"  ... ({len(profile.doc_extracted.structured.volumes)} total items)")
    else:
        print("  ❌ No volumes extracted")
    
    print("\n🎯 Required Experience:")
    exp = profile.doc_extracted.structured.required_experience
    if exp and exp.min_years:
        print(f"  • Minimum years: {exp.min_years}")
    if exp and exp.required_project_types:
        print(f"  • Project types: {', '.join(exp.required_project_types[:3])}")
    
    print("\n📜 Required Licenses:")
    if profile.doc_extracted.structured.required_licenses:
        for lic in profile.doc_extracted.structured.required_licenses[:3]:
            print(f"  • {lic}")
    
    print("\n🏆 Required Certifications:")
    if profile.doc_extracted.structured.required_certifications:
        for cert in profile.doc_extracted.structured.required_certifications[:3]:
            print(f"  • {cert}")
    
    print("\n🌍 Vendor Constraints:")
    constraints = profile.doc_extracted.structured.vendor_constraints
    if constraints and constraints.allowed_jurisdictions:
        print(f"  • Jurisdictions: {', '.join(constraints.allowed_jurisdictions)}")
    if constraints and constraints.business_size:
        print(f"  • Business size: {constraints.business_size}")
    
    assert len(profile.doc_extracted.structured.volumes) > 0, "Should extract at least one volume item"
    print("\n✅ Test passed!")


def test_vehicle_tender_extraction():
    """Test LLM extraction from vehicle supply tender."""
    data_dir = Path(__file__).parent.parent / "data"
    vehicle_pdf = data_dir / "Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks" / "RFB Attachments" / "tender_20488 - Attachment 1 - Parts 1-4.pdf"
    
    if not vehicle_pdf.exists():
        print(f"❌ Test PDF not found: {vehicle_pdf}")
        return
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set, skipping LLM test")
        return
    
    llm_provider = OpenAIProvider(api_key=api_key, default_model="gpt-5-mini")
    
    print("📄 Parsing vehicle tender PDF...")
    parser = DocumentParser()
    sections = parser.parse([vehicle_pdf])
    
    print(f"✓ Extracted {len(sections)} sections")
    
    print("\n🤖 Running LLM-powered extraction...")
    extractor = RequirementExtractor(llm_provider=llm_provider)
    profile = extractor.extract(sections)
    
    print("\n🚗 Extracted Volumes:")
    if profile.doc_extracted.structured.volumes:
        for vol in profile.doc_extracted.structured.volumes:
            print(f"  • {vol.item}: {vol.quantity} {vol.unit or ''}")
    else:
        print("  ℹ️  No volumes extracted (expected for this tender)")
    
    print(f"\n🏢 Detected Sector: {profile.doc_extracted.structured.sector}")
    print(f"📋 Project Type: {profile.doc_extracted.structured.project_type}")
    
    print("\n✅ Test passed!")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing LLM-Powered Field Extraction (Stage 2)")
    print("=" * 70)
    
    print("\n[Test 1] Ammunition Tender - Table Extraction")
    print("-" * 70)
    test_ammunition_table_extraction()
    
    print("\n\n[Test 2] Vehicle Tender - General Extraction")
    print("-" * 70)
    test_vehicle_tender_extraction()
    
    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)
