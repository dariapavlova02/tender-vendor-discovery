#!/usr/bin/env python3
"""Enhanced test for location extraction with LLM integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.sections import SectionExtractor
from vendor_ai_agent.modules.document_processing.field_extractor import FieldExtractor
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
import os
from dotenv import load_dotenv

load_dotenv()

def test_enhanced_location_extraction():
    pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    print("=" * 80)
    print("ENHANCED LOCATION EXTRACTION TEST")
    print("=" * 80)
    
    print("\n1. Parsing PDF...")
    parser = DocumentParser()
    tender_sections = parser.parse([pdf_path])
    print(f"   ✓ Found {len(tender_sections)} sections")
    
    print("\n2. Extracting sections...")
    section_extractor = SectionExtractor()
    doc_sections = section_extractor.extract(tender_sections)
    print(f"   ✓ location_details: {len(doc_sections.location_details)} chars")
    
    print("\n3. Testing _extract_location_chunks()...")
    llm = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            llm = OpenAIProvider()
            print(f"   ✓ LLM provider available: {type(llm).__name__}")
        except Exception as e:
            print(f"   ⚠️  Could not create LLM provider: {e}")
    else:
        print(f"   ⚠️  No OPENAI_API_KEY - testing without LLM")
    
    field_extractor = FieldExtractor(llm_provider=llm)
    
    chunks = field_extractor._extract_location_chunks(doc_sections.location_details, max_chars=2500)
    print(f"\n   Extracted chunks ({len(chunks)} chars):")
    print("   " + "-" * 76)
    if chunks:
        preview = chunks[:1500] if len(chunks) > 1500 else chunks
        for line in preview.split("\n"):
            print(f"   {line}")
        if len(chunks) > 1500:
            print(f"   ... (truncated, total {len(chunks)} chars)")
    else:
        print("   ⚠️  No chunks extracted!")
    print("   " + "-" * 76)
    
    print("\n4. Testing full extraction with LLM...")
    structured = field_extractor.extract(doc_sections, tender_sections)
    
    print(f"\n   📍 EXTRACTED LOCATION:")
    print(f"   - City: {structured.location.city or '(none)'}")
    print(f"   - State: {structured.location.state_province or '(none)'}")
    print(f"   - Country: {structured.location.country or '(none)'}")
    
    print("\n5. Validation:")
    if structured.location.city and structured.location.state_province:
        print("   ✅ Location successfully extracted with city and state")
        print(f"   ✅ Can be used for SAM vendor search in state: {structured.location.state_province}")
    elif structured.location.city == "Nationwide":
        print("   ✅ Detected as nationwide project")
        print("   ℹ️  SAM search will query all states")
    elif structured.location.city:
        print(f"   ⚠️  Extracted city but no state: {structured.location.city}")
    else:
        print("   ❌ No location extracted")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_enhanced_location_extraction()
