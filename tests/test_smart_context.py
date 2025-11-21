"""Test Smart Context Assembler for boilerplate filtering."""
import os
from pathlib import Path
from dataclasses import dataclass

from vendor_ai_agent.modules.tender_profiler import TenderProfiler
from vendor_ai_agent.modules.llm_providers import OpenAIProvider


@dataclass
class MockSection:
    title: str
    content: str
    content_type: str = "text"


def test_section_classification():
    """Test that sections are classified correctly."""
    profiler = TenderProfiler(llm_provider=None)
    
    gold_section = MockSection(
        title="Technical Specifications",
        content="The ammunition must meet SAAMI standards with non-corrosive primers"
    )
    
    junk_section = MockSection(
        title="Instructions to Bidders",
        content="Please submit your bid through the eTendering portal"
    )
    
    neutral_section = MockSection(
        title="Background Information",
        content="The Ontario Provincial Police requires ammunition for training"
    )
    
    assert profiler._classify_section(gold_section) == "gold"
    assert profiler._classify_section(junk_section) == "junk"
    assert profiler._classify_section(neutral_section) == "neutral"
    
    print("✓ Section classification works correctly")


def test_context_assembly_with_boilerplate():
    """Test that boilerplate is filtered out."""
    profiler = TenderProfiler(llm_provider=None)
    
    sections = [
        MockSection(
            title="Instructions to Bidders",
            content="Please submit your bid through the eTendering portal. " * 50
        ),
        MockSection(
            title="Legal Terms and Conditions",
            content="The contractor shall maintain insurance coverage. " * 50
        ),
        MockSection(
            title="Technical Specifications",
            content="9mm Luger ammunition, SAAMI compliant, brass cases, non-corrosive primers, FMJ for training"
        ),
        MockSection(
            title="Line Item Pricing",
            content="Line 1: 9mm 115gr FMJ - 500,000 rounds\nLine 2: .223 Rem 55gr FMJ - 250,000 rounds"
        ),
    ]
    
    context_text = profiler._assemble_smart_context(sections, max_chars=4000)
    
    # Verify gold sections are included
    assert "9mm Luger" in context_text
    assert "SAAMI" in context_text
    assert "Line Item" in context_text
    
    # Verify junk sections are excluded (or minimal)
    junk_ratio = context_text.count("eTendering") / max(1, context_text.count("9mm"))
    assert junk_ratio < 0.1  # Less than 10% junk content
    
    print(f"✓ Context assembly filtered boilerplate (junk ratio: {junk_ratio:.2%})")


def test_ammunition_tender():
    """Test with real ammunition tender structure."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ Skipping (OPENAI_API_KEY not set)")
        return
    
    provider = OpenAIProvider(default_model="gpt-5-mini")
    profiler = TenderProfiler(llm_provider=provider)
    
    sections = [
        MockSection("eTendering Portal Instructions", "Submit bids online via portal" * 20),
        MockSection("Legal Compliance", "Insurance and bonding requirements" * 20),
        MockSection("Scope of Work", "Supply and delivery of ammunition for Ontario Provincial Police"),
        MockSection("Technical Specifications", """
            9mm Luger: 115gr FMJ, SAAMI compliant, brass cases, non-corrosive primers
            .223 Remington: 55gr FMJ, frangible ammunition for training
            12 Gauge: 00 Buck, 1 oz slug, duty use
            Velocity tolerances per SAAMI specifications
        """),
        MockSection("Pricing Form - Line Items", """
            Line 1: 9mm Luger 115gr FMJ - 500,000 rounds
            Line 2: .223 Rem 55gr FMJ - 250,000 rounds  
            Line 3: 12ga 00 Buck - 100,000 rounds
        """),
    ]
    
    context = profiler.generate_context(sections)
    
    print(f"\n✓ Sector: {context.sector}")
    print(f"✓ Description: {context.industry_description}")
    print(f"✓ Keywords ({len(context.technical_keywords)}): {context.technical_keywords[:5]}...")
    print(f"✓ Search terms ({len(context.search_terms)}): {context.search_terms[:3]}...")
    
    # Verify it's correctly classified
    assert "ammunition" in context.sector.lower() or "supply" in context.sector.lower()
    assert len(context.technical_keywords) >= 10
    
    # Verify keywords are relevant (not generic portal/legal terms)
    keywords_str = " ".join(context.technical_keywords).lower()
    relevant_count = sum(1 for term in ["9mm", "223", "saami", "ammunition", "fmj", "caliber"] 
                         if term in keywords_str)
    assert relevant_count >= 2, "Keywords should be domain-specific, not generic"


def test_vehicle_tender():
    """Test with vehicle tender structure."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ Skipping (OPENAI_API_KEY not set)")
        return
    
    provider = OpenAIProvider(default_model="gpt-5-mini")
    profiler = TenderProfiler(llm_provider=provider)
    
    sections = [
        MockSection("Submission Instructions", "Submit via portal by deadline" * 30),
        MockSection("Legal Terms", "Insurance, bonding, and warranty requirements" * 30),
        MockSection("Technical Specifications - Utility Vehicles", """
            5 Utility Vehicles required for Ontario Parks
            4x4 drivetrain, diesel engine, minimum 1000kg payload
            ROPS/FOPS certified, enclosed cab with HVAC
            Ground clearance minimum 250mm, cargo bed with tie-downs
        """),
        MockSection("Delivery Requirements", """
            All vehicles to be delivered to designated Ontario Parks locations
            Full factory warranty, service manual, and training included
        """),
    ]
    
    context = profiler.generate_context(sections)
    
    print(f"\n✓ Sector: {context.sector}")
    print(f"✓ Description: {context.industry_description}")
    print(f"✓ Keywords ({len(context.technical_keywords)}): {context.technical_keywords[:5]}...")
    
    # Verify it's correctly classified
    assert "vehicle" in context.sector.lower() or "automotive" in context.sector.lower()
    
    # Verify keywords are vehicle-specific
    keywords_str = " ".join(context.technical_keywords).lower()
    relevant_count = sum(1 for term in ["vehicle", "4x4", "diesel", "rops", "payload"] 
                         if term in keywords_str)
    assert relevant_count >= 2, "Keywords should be vehicle-specific"


if __name__ == "__main__":
    print("Testing Smart Context Assembler\n")
    
    print("1. Section classification:")
    test_section_classification()
    
    print("\n2. Context assembly (boilerplate filtering):")
    test_context_assembly_with_boilerplate()
    
    if os.getenv("OPENAI_API_KEY"):
        print("\n3. Ammunition tender classification:")
        test_ammunition_tender()
        
        print("\n4. Vehicle tender classification:")
        test_vehicle_tender()
    else:
        print("\n⚠ Skipping LLM tests (OPENAI_API_KEY not set)")
    
    print("\n✅ All tests passed!")
