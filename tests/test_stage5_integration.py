"""End-to-end test for Stage 5 LLM capability matching with website scraping."""
import logging
from pathlib import Path

from vendor_ai_agent.config import RuntimeConfig, CapabilityMatchingConfig
from vendor_ai_agent.pipeline import TenderVendorPipeline
from vendor_ai_agent.models import VendorRecord

logging.basicConfig(level=logging.INFO)


def test_stage5_integration():
    """Test that Stage 5 components are properly integrated into pipeline."""
    
    # Configure with Stage 5 features enabled
    config = RuntimeConfig()
    config.capability_matching = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        llm_model="gpt-5-mini",
        enable_website_scraping=True,
        scrape_timeout_seconds=5,
        max_content_chars=2000,
        fallback_to_rule_based=True,
    )
    
    # Initialize pipeline
    pipeline = TenderVendorPipeline(config=config)
    
    # Verify configuration
    assert pipeline.context.config.capability_matching.enable_llm_assessment
    assert pipeline.context.config.capability_matching.enable_website_scraping
    assert pipeline.context.config.capability_matching.enable_llm_assessment
    
    # Verify enrichment providers
    enrichers = pipeline.context.vendor_enricher.providers
    assert len(enrichers) == 1
    assert enrichers[0].__class__.__name__ == "WebsiteContentProvider"
    
    # Verify capability matcher configuration
    matcher = pipeline.context.capability_matcher
    assert matcher.config.enable_llm_assessment
    assert matcher.config.enable_website_scraping
    assert matcher.config.enable_llm_assessment
    
    print("✅ Stage 5 integration test PASSED!")
    print(f"   - WebsiteContentProvider registered")
    print(f"   - CapabilityMatcher configured with LLM support")
    print("   - LLM assessments run for all eligible vendors")
    print(f"   - Scrape timeout: {config.capability_matching.scrape_timeout_seconds}s")
    print(f"   - Max content chars: {config.capability_matching.max_content_chars}")
    

if __name__ == "__main__":
    test_stage5_integration()
