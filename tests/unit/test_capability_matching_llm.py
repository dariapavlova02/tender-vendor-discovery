"""Integration tests for LLM-based capability matching."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from vendor_ai_agent.config import CapabilityMatchingConfig
from vendor_ai_agent.models import (
    ContactInfo,
    TenderProfile,
    VendorRecord,
)
from vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from vendor_ai_agent.modules.tender_profiler import LLMProvider


class MockLLMProvider(LLMProvider):
    def __init__(self, mock_responses=None):
        self.mock_responses = mock_responses or {}
        self.call_count = 0
    
    def generate(self, prompt: str, response_format=None, model=None) -> str:
        self.call_count += 1
        
        if "VENDOR:" in prompt and "Tactical Uniforms Inc" in prompt:
            return '{"score": 95, "rationale": "Band: Perfect Match — Evidence: \'tactical uniforms for DHS\' directly matches requirements", "confidence": "high"}'
        
        if "VENDOR:" in prompt and "Generic Supplier" in prompt:
            return '{"score": 65, "rationale": "Band: Moderate Match — Evidence: \'various products and services\' shows capability but no specific alignment", "confidence": "medium"}'
        
        if "VENDOR:" in prompt and "ammunition" in prompt.lower():
            return '{"score": 92, "rationale": "Band: Perfect Match — Evidence: \'ammunition manufacturer with frangible bullet expertise\' directly matches tender", "confidence": "high"}'
        
        if "lobbying" in prompt.lower() or "Canadian Natural Gas Vehicle Alliance" in prompt:
            return '{"score": 5, "rationale": "Band: No Match — Evidence: \'lobbying office\' is not a product supplier", "confidence": "high"}'
        
        return '{"score": 65, "rationale": "Band: Moderate Match — General capabilities detected", "confidence": "medium"}'


def create_test_vendor(
    name: str, 
    website: str, 
    website_content: str = "",
    is_past_winner: bool = False,
    total_contract_value: float = 0,
    contract_count: int = 0,
) -> VendorRecord:
    vendor = VendorRecord(
        company_name=name,
        website=website,
        location="Washington, DC",
        is_past_winner=is_past_winner,
        total_contract_value=total_contract_value,
        contract_count=contract_count,
        enrichment_flags=["high_value_supplier"] if total_contract_value > 100000000 else [],
    )
    
    if website_content:
        vendor.filtering_metadata["website_content"] = website_content
        vendor.filtering_metadata["content_source"] = website
        vendor.filtering_metadata["scrape_status"] = "success"
        vendor.filtering_metadata["scrape_timestamp"] = "2024-01-15T10:00:00Z"
    
    return vendor


def create_test_profile() -> TenderProfile:
    return TenderProfile(
        tender_id="TEST-001",
        country="USA",
        source_system="test",
    )


def test_llm_capability_matching_basic():
    llm_provider = MockLLMProvider()
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        llm_model="gpt-5-mini",
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    profile = create_test_profile()
    
    vendors = [
        create_test_vendor(
            "Tactical Uniforms Inc",
            "https://tacticaluniforms.com",
            website_content="Tactical Uniforms Inc specializes in tactical uniforms for DHS with 20+ years experience",
            is_past_winner=True,
            total_contract_value=150000000,
            contract_count=75,
        ),
        create_test_vendor(
            "Generic Supplier",
            "https://generic.com",
            website_content="We sell various products and services",
            is_past_winner=False,
            total_contract_value=500000,
            contract_count=5,
        ),
    ]
    
    results = matcher.score(profile, vendors)
    
    assert len(results) == 2
    assert results[0].capability_match_score == 95
    assert "tactical uniforms" in results[0].rationale.lower()
    assert results[0].vendor.company_name == "Tactical Uniforms Inc"
    
    assert results[1].capability_match_score == 65
    assert results[1].vendor.company_name == "Generic Supplier"
    
    assert llm_provider.call_count == 2


def test_fallback_to_rule_based():
    config = CapabilityMatchingConfig(
        enable_llm_assessment=False,
        fallback_to_rule_based=True,
    )
    matcher = CapabilityMatcher(llm_provider=None, config=config)
    
    profile = create_test_profile()
    
    vendors = [
        create_test_vendor(
            "High Value Vendor",
            "https://highvalue.com",
            website_content="High value manufacturing partner",
            is_past_winner=True,
            total_contract_value=200000000,
            contract_count=100,
        ),
    ]
    
    vendors[0].enrichment_flags = ["high_value_supplier", "frequent_supplier"]
    
    results = matcher.score(profile, vendors)
    
    assert len(results) == 1
    assert results[0].capability_match_score >= 80.0
    assert "high_value_supplier" in results[0].rationale.lower() or "extensive" in results[0].rationale.lower()


def test_llm_with_fallback_on_no_content():
    llm_provider = MockLLMProvider()
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        fallback_to_rule_based=True,
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    profile = create_test_profile()
    
    vendors = [
        create_test_vendor(
            "No Website Vendor",
            "https://nowebsite.com",
            website_content="",
            is_past_winner=True,
        ),
    ]
    
    results = matcher.score(profile, vendors)
    
    assert len(results) == 0
    assert llm_provider.call_count == 0
    assert vendors[0].filtering_metadata.get("match_status") == "needs_data"


def test_llm_runs_for_all_vendors_without_limit():
    llm_provider = MockLLMProvider()
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    profile = create_test_profile()
    
    vendors = [
        create_test_vendor(f"Vendor {i}", f"https://vendor{i}.com", website_content=f"Content {i}")
        for i in range(3)
    ]
    
    results = matcher.score(profile, vendors)
    
    assert len(results) == 3
    assert llm_provider.call_count == 3


def test_llm_error_fallback():
    class FailingLLMProvider(LLMProvider):
        def generate(self, prompt: str, response_format=None, model=None) -> str:
            raise Exception("LLM API error")
    
    llm_provider = FailingLLMProvider()
    config = CapabilityMatchingConfig(
        enable_llm_assessment=True,
        fallback_to_rule_based=True,
    )
    matcher = CapabilityMatcher(llm_provider=llm_provider, config=config)
    
    profile = create_test_profile()
    
    vendors = [
        create_test_vendor(
            "Test Vendor",
            "https://test.com",
            website_content="Test content",
            is_past_winner=True,
        ),
    ]
    
    results = matcher.score(profile, vendors)
    
    assert len(results) == 1
    assert results[0].capability_match_score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
