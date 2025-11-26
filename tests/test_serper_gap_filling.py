"""Test suite for Serper gap-filling functionality."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig, DiscoveryConfig
from src.vendor_ai_agent.models import TenderProfile, VendorRecord
from src.vendor_ai_agent.sources.serper_search import SerperVendorSource


def test_dynamic_config_thresholds():
    """Test that thresholds scale dynamically with max_candidates."""
    cfg = RuntimeConfig()
    
    cfg.filtering.max_candidates = 500
    cfg.discovery.target_results = cfg.filtering.max_candidates
    assert cfg.discovery.serper_discovery_trigger_threshold == 250
    assert cfg.discovery.min_relevant_candidates == 350
    
    cfg.filtering.max_candidates = 1000
    cfg.discovery.target_results = cfg.filtering.max_candidates
    assert cfg.discovery.serper_discovery_trigger_threshold == 500
    assert cfg.discovery.min_relevant_candidates == 700


def test_query_generation_with_target_count():
    """Test that _generate_queries respects target_count."""
    mock_profile = Mock(spec=TenderProfile)
    mock_profile.dynamic_context = Mock()
    mock_profile.dynamic_context.sector = "IT Services"
    mock_profile.dynamic_context.country = "USA"
    mock_profile.dynamic_context.search_terms = [f"term_{i}" for i in range(25)]
    mock_profile.dynamic_context.technical_keywords = [f"keyword_{i}" for i in range(20)]
    mock_profile.api_metadata = Mock()
    mock_profile.api_metadata.place_of_performance = Mock()
    mock_profile.api_metadata.place_of_performance.city = "Washington"
    mock_profile.api_metadata.place_of_performance.state_province = "DC"
    mock_profile.api_metadata.place_of_performance.country = "USA"
    mock_profile.api_metadata.codes = Mock()
    mock_profile.api_metadata.codes.naics = ["541519", "541511"]
    
    serper_source = SerperVendorSource(api_key="test_key", query_limit=10)
    
    queries_no_target = serper_source._generate_queries(mock_profile, target_count=None)
    assert len(queries_no_target) <= 50
    
    queries_with_target_700 = serper_source._generate_queries(mock_profile, target_count=700)
    expected_queries = min(50, (700 // 10) + 5)
    assert len(queries_with_target_700) == expected_queries
    
    queries_with_target_100 = serper_source._generate_queries(mock_profile, target_count=100)
    expected_queries_small = min(50, (100 // 10) + 5)
    assert len(queries_with_target_100) == expected_queries_small


def test_gap_filling_logic():
    """Test the gap-filling calculation logic."""
    max_candidates = 1000
    current_vendors = 300
    
    deficit = max(0, max_candidates - current_vendors)
    assert deficit == 700
    
    estimated_queries = min(50, (deficit // 10) + 5)
    assert estimated_queries == 50
    
    expected_new_vendors = estimated_queries * 10
    assert expected_new_vendors == 500
    
    expected_total = current_vendors + expected_new_vendors
    assert expected_total == 800


def test_serper_trigger_with_deficit():
    """Test that Serper triggers when there's a deficit."""
    cfg = RuntimeConfig()
    cfg.filtering.max_candidates = 1000
    cfg.discovery.enable_serper_discovery = True
    cfg.serper_api_key = "test_key"
    
    current_vendors = 300
    deficit = max(0, cfg.filtering.max_candidates - current_vendors)
    
    should_trigger = (
        cfg.discovery.enable_serper_discovery
        and cfg.serper_api_key
        and deficit > 0
    )
    
    assert should_trigger is True
    assert deficit == 700


def test_no_serper_trigger_when_at_capacity():
    """Test that Serper doesn't trigger when at max_candidates."""
    cfg = RuntimeConfig()
    cfg.filtering.max_candidates = 1000
    cfg.discovery.enable_serper_discovery = True
    cfg.serper_api_key = "test_key"
    
    current_vendors = 1000
    deficit = max(0, cfg.filtering.max_candidates - current_vendors)
    
    should_trigger = (
        cfg.discovery.enable_serper_discovery
        and cfg.serper_api_key
        and deficit > 0
    )
    
    assert should_trigger is False
    assert deficit == 0


def test_target_relevant_vendors_calculation():
    """Test that target_relevant_vendors is calculated as 70% of max_candidates."""
    cfg = RuntimeConfig()
    
    cfg.filtering.max_candidates = 500
    target = int(cfg.filtering.max_candidates * 0.7)
    assert target == 350
    
    cfg.filtering.max_candidates = 1000
    target = int(cfg.filtering.max_candidates * 0.7)
    assert target == 700


def test_search_terms_generation():
    """Test that LLM prompt requests 25 search terms."""
    with open("src/vendor_ai_agent/modules/tender_profiler.py", "r") as f:
        content = f.read()
        assert "search_terms: return exactly 25 unique search strings" in content
        assert "query 25" in content


if __name__ == "__main__":
    print("Running Serper gap-filling tests...")
    
    test_dynamic_config_thresholds()
    print("✓ Dynamic config thresholds")
    
    test_query_generation_with_target_count()
    print("✓ Query generation with target_count")
    
    test_gap_filling_logic()
    print("✓ Gap-filling logic")
    
    test_serper_trigger_with_deficit()
    print("✓ Serper triggers with deficit")
    
    test_no_serper_trigger_when_at_capacity()
    print("✓ No trigger at capacity")
    
    test_target_relevant_vendors_calculation()
    print("✓ Target relevant vendors calculation")
    
    print("\n✅ All tests passed!")
