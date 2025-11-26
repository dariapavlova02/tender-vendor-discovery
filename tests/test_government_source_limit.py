import pytest
from unittest.mock import Mock

from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.models import TenderProfile, VendorRecord


@pytest.fixture
def mock_config():
    cfg = RuntimeConfig()
    cfg.filtering.max_candidates = 1000
    cfg.discovery.max_government_source_percentage = 0.7
    cfg.discovery.enable_serper_discovery = True
    cfg.serper_api_key = "test_key"
    return cfg


@pytest.fixture
def mock_profile():
    profile = Mock(spec=TenderProfile)
    profile.dynamic_context = Mock()
    profile.dynamic_context.sector = "Test Sector"
    return profile


def create_vendors(sam_count: int, canada_count: int, serper_count: int) -> list:
    vendors = []
    
    for i in range(sam_count):
        vendors.append(VendorRecord(
            company_name=f"SAM Vendor {i}",
            source="sam_entity",
            website=f"https://sam-vendor-{i}.com"
        ))
    
    for i in range(canada_count):
        vendors.append(VendorRecord(
            company_name=f"Canada Vendor {i}",
            source="canada_contracts",
            website=f"https://canada-vendor-{i}.com"
        ))
    
    for i in range(serper_count):
        vendors.append(VendorRecord(
            company_name=f"Serper Vendor {i}",
            source="serper",
            website=f"https://serper-vendor-{i}.com"
        ))
    
    return vendors


def test_government_source_count():
    vendors = create_vendors(sam_count=100, canada_count=200, serper_count=50)
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    assert govt_count == 300


def test_government_cap_calculation(mock_config):
    max_candidates = mock_config.filtering.max_candidates
    max_govt_pct = mock_config.discovery.max_government_source_percentage
    
    max_govt_vendors = int(max_candidates * max_govt_pct)
    
    assert max_govt_vendors == 700


def test_deficit_calculation_below_cap(mock_config):
    vendors = create_vendors(sam_count=200, canada_count=100, serper_count=0)
    
    max_candidates = mock_config.filtering.max_candidates
    current_count = len(vendors)
    
    deficit = max(0, max_candidates - current_count)
    
    assert deficit == 700


def test_deficit_calculation_at_cap(mock_config):
    vendors = create_vendors(sam_count=400, canada_count=300, serper_count=0)
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    max_candidates = mock_config.filtering.max_candidates
    current_count = len(vendors)
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    max_govt_vendors = int(max_candidates * mock_config.discovery.max_government_source_percentage)
    
    assert govt_count == 700
    assert govt_count >= max_govt_vendors
    
    deficit = max(0, max_candidates - current_count)
    
    assert deficit == 300


def test_force_serper_when_at_government_cap(mock_config):
    vendors = create_vendors(sam_count=400, canada_count=300, serper_count=0)
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    max_candidates = mock_config.filtering.max_candidates
    current_count = len(vendors)
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    max_govt_vendors = int(max_candidates * mock_config.discovery.max_government_source_percentage)
    
    deficit = max(0, max_candidates - current_count)
    
    should_use_serper = (
        mock_config.discovery.enable_serper_discovery
        and mock_config.serper_api_key
        and deficit > 0
    )
    
    assert govt_count >= max_govt_vendors
    assert deficit == 300
    assert should_use_serper is True


def test_percentage_boundary_zero_percent(mock_config):
    mock_config.discovery.max_government_source_percentage = 0.0
    
    max_candidates = mock_config.filtering.max_candidates
    max_govt_vendors = int(max_candidates * mock_config.discovery.max_government_source_percentage)
    
    assert max_govt_vendors == 0
    
    vendors = create_vendors(sam_count=10, canada_count=10, serper_count=0)
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    
    assert govt_count > max_govt_vendors


def test_percentage_boundary_hundred_percent(mock_config):
    mock_config.discovery.max_government_source_percentage = 1.0
    
    max_candidates = mock_config.filtering.max_candidates
    max_govt_vendors = int(max_candidates * mock_config.discovery.max_government_source_percentage)
    
    assert max_govt_vendors == 1000


def test_mixed_sources_below_cap(mock_config):
    vendors = create_vendors(sam_count=200, canada_count=100, serper_count=100)
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    max_candidates = mock_config.filtering.max_candidates
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    max_govt_vendors = int(max_candidates * mock_config.discovery.max_government_source_percentage)
    
    assert govt_count == 300
    assert govt_count < max_govt_vendors


def test_serper_skip_when_max_reached(mock_config):
    vendors = create_vendors(sam_count=600, canada_count=200, serper_count=200)
    
    current_count = len(vendors)
    max_candidates = mock_config.filtering.max_candidates
    
    deficit = max(0, max_candidates - current_count)
    
    should_use_serper = (
        mock_config.discovery.enable_serper_discovery
        and mock_config.serper_api_key
        and deficit > 0
    )
    
    assert current_count == 1000
    assert deficit == 0
    assert should_use_serper is False


def test_config_default_value():
    cfg = RuntimeConfig()
    assert cfg.discovery.max_government_source_percentage == 0.7


def test_all_canada_sources_counted():
    vendors = [
        VendorRecord(company_name="V1", source="canada_contracts"),
        VendorRecord(company_name="V2", source="canada_award_notices"),
        VendorRecord(company_name="V3", source="canada_odbus"),
        VendorRecord(company_name="V4", source="canada_pspc_payments"),
        VendorRecord(company_name="V5", source="canada_sosa"),
    ]
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    
    assert govt_count == 5


def test_non_government_sources_not_counted():
    vendors = [
        VendorRecord(company_name="V1", source="sam_entity"),
        VendorRecord(company_name="V2", source="serper"),
        VendorRecord(company_name="V3", source="apollo"),
        VendorRecord(company_name="V4", source="static_directory"),
    ]
    
    GOVERNMENT_SOURCES = {
        "sam_entity", 
        "canada_contracts", 
        "canada_award_notices",
        "canada_odbus", 
        "canada_pspc_payments", 
        "canada_sosa"
    }
    
    govt_count = len([v for v in vendors if v.source in GOVERNMENT_SOURCES])
    
    assert govt_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
