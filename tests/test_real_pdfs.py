"""Test Smart Context Assembler with real PDF documents."""
import os
from pathlib import Path

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
from vendor_ai_agent.modules.tender_profiler import TenderProfiler


def test_ammunition_pdf():
    """Test ammunition tender PDF classification."""
    ammo_pdf = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf")
    
    if not ammo_pdf.exists():
        print(f"⚠ PDF not found: {ammo_pdf}")
        return
    
    parser = DocumentParser()
    sections = parser.parse([ammo_pdf])
    
    print(f"\n📄 Ammunition Tender - Parsed {len(sections)} sections")
    print(f"   Tables: {len([s for s in sections if s.section_type == 'table'])}")
    print(f"   Text: {len([s for s in sections if s.section_type == 'text'])}")
    
    provider = OpenAIProvider(default_model="gpt-5-mini")
    profiler = TenderProfiler(llm_provider=provider)
    
    print("\n🔍 Running Smart Context Assembler...")
    context = profiler.generate_context(sections)
    
    print(f"\n✅ Sector: {context.sector}")
    print(f"📝 Description: {context.industry_description}")
    print(f"🔑 Keywords ({len(context.technical_keywords)}): {', '.join(context.technical_keywords[:5])}...")
    print(f"🔎 Search terms ({len(context.search_terms)}): {', '.join(context.search_terms[:3])}...")
    
    # Verify correct classification
    assert "ammunition" in context.sector.lower(), f"Expected 'ammunition' in sector, got: {context.sector}"
    
    # Check keyword quality
    keywords_str = " ".join(context.technical_keywords).lower()
    domain_specific = sum(1 for term in ["9mm", "223", "caliber", "saami", "fmj", "ammunition", "primer"]
                          if term in keywords_str)
    total_keywords = len(context.technical_keywords)
    quality = domain_specific / max(1, total_keywords)
    
    print(f"\n📊 Quality: {domain_specific}/{total_keywords} domain-specific keywords ({quality:.1%})")
    assert quality >= 0.25, "At least 25% of keywords should be domain-specific"


def test_vehicle_pdf():
    """Test vehicle tender PDF classification."""
    vehicle_pdf = Path("data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks/RFB Attachments/tender_20488 - Attachment 1 - Parts 1-4.pdf")
    
    if not vehicle_pdf.exists():
        print(f"⚠ PDF not found: {vehicle_pdf}")
        return
    
    parser = DocumentParser()
    sections = parser.parse([vehicle_pdf])
    
    print(f"\n📄 Vehicle Tender - Parsed {len(sections)} sections")
    print(f"   Tables: {len([s for s in sections if s.section_type == 'table'])}")
    print(f"   Text: {len([s for s in sections if s.section_type == 'text'])}")
    
    provider = OpenAIProvider(default_model="gpt-5-mini")
    profiler = TenderProfiler(llm_provider=provider)
    
    print("\n🔍 Running Smart Context Assembler...")
    context = profiler.generate_context(sections)
    
    print(f"\n✅ Sector: {context.sector}")
    print(f"📝 Description: {context.industry_description}")
    print(f"🔑 Keywords ({len(context.technical_keywords)}): {', '.join(context.technical_keywords[:5])}...")
    print(f"🔎 Search terms ({len(context.search_terms)}): {', '.join(context.search_terms[:3])}...")
    
    # Verify correct classification (should NOT be "IT Services" anymore!)
    assert "vehicle" in context.sector.lower() or "automotive" in context.sector.lower(), \
        f"Expected vehicle-related sector, got: {context.sector}"
    
    # Check keyword quality
    keywords_str = " ".join(context.technical_keywords).lower()
    domain_specific = sum(1 for term in ["vehicle", "4x4", "diesel", "rops", "utility", "payload"]
                          if term in keywords_str)
    total_keywords = len(context.technical_keywords)
    quality = domain_specific / max(1, total_keywords)
    
    print(f"\n📊 Quality: {domain_specific}/{total_keywords} domain-specific keywords ({quality:.1%})")


def compare_before_after():
    """Show the improvement from Smart Context Assembler."""
    vehicle_pdf = Path("data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks/RFB Attachments/tender_20488 - Attachment 1 - Parts 1-4.pdf")
    
    if not vehicle_pdf.exists():
        print(f"⚠ PDF not found: {vehicle_pdf}")
        return
    
    parser = DocumentParser()
    sections = parser.parse([vehicle_pdf])
    
    provider = OpenAIProvider(default_model="gpt-5-mini")
    profiler = TenderProfiler(llm_provider=provider)
    
    print("\n" + "="*60)
    print("COMPARISON: First 10 Sections vs Smart Assembly")
    print("="*60)
    
    # OLD METHOD: First 10 sections
    print("\n❌ OLD METHOD: First 10 sections (boilerplate trap)")
    old_text = "\n\n".join(s.content for s in sections[:10])[:2000]
    print(f"   Sample text: {old_text[:200]}...")
    
    context_old = profiler.generate_context_from_text(old_text)
    print(f"   Sector: {context_old.sector}")
    print(f"   Keywords: {', '.join(context_old.technical_keywords[:5])}...")
    
    # NEW METHOD: Smart assembly
    print("\n✅ NEW METHOD: Smart Context Assembly")
    context_new = profiler.generate_context(sections)
    print(f"   Sector: {context_new.sector}")
    print(f"   Keywords: {', '.join(context_new.technical_keywords[:5])}...")
    
    print("\n📊 Result:")
    if "vehicle" in context_new.sector.lower():
        print("   ✅ Correctly identified as Vehicle tender")
    else:
        print(f"   ❌ Misclassified as: {context_new.sector}")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY not set. Skipping tests.")
        exit(1)
    
    print("Testing Smart Context Assembler with Real PDFs")
    print("="*60)
    
    try:
        test_ammunition_pdf()
    except Exception as e:
        print(f"\n❌ Ammunition test failed: {e}")
    
    try:
        test_vehicle_pdf()
    except Exception as e:
        print(f"\n❌ Vehicle test failed: {e}")
    
    try:
        compare_before_after()
    except Exception as e:
        print(f"\n❌ Comparison failed: {e}")
    
    print("\n" + "="*60)
    print("✅ Testing complete!")
