"""Test dynamic tender profiling with LLM integration."""
import os
from pathlib import Path

import pytest

from vendor_ai_agent.modules.tender_profiler import TenderProfiler
from vendor_ai_agent.modules.llm_providers import OpenAIProvider


def test_profiler_without_llm_provider():
    """Test that profiler works without LLM provider (fallback mode)."""
    profiler = TenderProfiler(llm_provider=None)
    
    context = profiler.generate_context_from_sections(
        scope_of_work="Supply and delivery of ammunition for training purposes",
        technical_requirements="SAAMI compliant, non-corrosive primers required"
    )
    
    assert context.sector == "Unknown"
    assert context.industry_description == "LLM provider not configured"
    assert context.technical_keywords == []
    assert context.search_terms == []


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
def test_profiler_with_openai_provider():
    """Test that profiler generates dynamic context with OpenAI."""
    provider = OpenAIProvider()
    profiler = TenderProfiler(llm_provider=provider)
    
    scope = """
    The Ontario Provincial Police (OPP) requires ammunition for training and operational use.
    This includes 9mm ball ammunition, .223 Remington, 12 gauge shotgun ammunition, and .308 rifle ammunition.
    All ammunition must comply with SAAMI standards and feature non-corrosive primers.
    """
    
    tech_requirements = """
    Technical Requirements:
    - SAAMI compliant
    - Non-corrosive primers
    - Brass cases (reloadable)
    - Full metal jacket (FMJ) for training
    - Jacketed hollow point (JHP) for duty use
    - Velocity specifications per caliber
    """
    
    context = profiler.generate_context_from_sections(scope, tech_requirements)
    
    # Verify structure
    assert context.sector != "Unknown"
    assert len(context.industry_description) > 10
    assert len(context.technical_keywords) >= 10
    assert len(context.search_terms) >= 3
    
    # Verify content relevance (fuzzy check)
    keywords_str = " ".join(context.technical_keywords).lower()
    assert any(term in keywords_str for term in ["ammunition", "ammo", "saami", "caliber"])
    
    search_terms_str = " ".join(context.search_terms).lower()
    assert any(term in search_terms_str for term in ["ammunition", "supplier", "manufacturer"])
    
    print(f"\n✓ Sector: {context.sector}")
    print(f"✓ Description: {context.industry_description}")
    print(f"✓ Keywords ({len(context.technical_keywords)}): {context.technical_keywords[:5]}...")
    print(f"✓ Search terms ({len(context.search_terms)}): {context.search_terms[:3]}...")


if __name__ == "__main__":
    # Run manual test
    print("Testing dynamic tender profiler...")
    print("\n1. Testing without LLM provider (fallback mode):")
    test_profiler_without_llm_provider()
    print("✓ Fallback mode works\n")
    
    if os.getenv("OPENAI_API_KEY"):
        print("2. Testing with OpenAI provider:")
        test_profiler_with_openai_provider()
    else:
        print("2. Skipping OpenAI test (OPENAI_API_KEY not set)")
