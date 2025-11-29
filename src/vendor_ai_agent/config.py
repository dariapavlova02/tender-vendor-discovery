"""Global configuration primitives for the Tender Vendor AI Agent."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Paths:
    """Commonly used filesystem locations."""

    root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = root / "data"
    output_dir: Path = root / "outputs"


@dataclass
class LLMConfig:
    smart_model: str = field(default_factory=lambda: os.getenv("SMART_LLM_MODEL", "gpt-5.1"))
    cheap_model: str = field(default_factory=lambda: os.getenv("CHEAP_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "gpt-5-mini")))
    vision_model: str = field(default_factory=lambda: os.getenv("VISION_LLM_MODEL", "gpt-5-mini"))
    use_flex_tier: bool = field(default_factory=lambda: os.getenv("USE_FLEX_TIER", "true").lower() == "true")
    max_tokens: int = 6000
    temperature: float = 0.0


@dataclass
class DiscoveryConfig:
    target_results: int = 1000
    preferred_sources: List[str] = field(default_factory=lambda: ["static_directory"])
    enable_apollo_discovery: bool = False
    enable_apollo_booster: bool = False
    apollo_min_candidates: int = 200
    apollo_max_pages: int = 1
    enable_serper_discovery: bool = True
    serper_discovery_query_limit: int = 10
    serper_max_queries: int = 50
    serper_discovery_always_canada: bool = True
    serper_use_places_api: bool = True
    serper_contract_aware_queries: bool = True
    serper_geo_query_expansion: bool = True
    enable_batch_cache: bool = True
    batch_size: int = 500
    processing_batch: int = 1
    max_government_source_percentage: float = 0.7

    @property
    def serper_discovery_trigger_threshold(self) -> int:
        return int(self.target_results * 0.5)

    @property
    def min_relevant_candidates(self) -> int:
        return int(self.target_results * 0.7)


@dataclass
class EnrichmentConfig:
    providers: List[str] = field(default_factory=lambda: ["static_contacts"])
    enable_contact_scraping: bool = True
    enable_llm_fallback: bool = False
    scraper_timeout_seconds: int = 5
    enable_google_maps: bool = True
    google_maps_min_confidence: float = 0.7
    google_maps_cache_ttl_days: int = 90
    enable_apollo_enrichment: bool = True
    enable_manual_enrichment: bool = True
    auto_enrich_on_missing: bool = False
    max_enrichment_workers: int = 10
    batch_size: int = 50
    min_batch_success_rate: float = 0.15
    max_enrichment_batches: int = 5
    target_relevant_vendors: int = 200
    enable_batch_quality_gates: bool = True
    enable_sampling_fallback: bool = True
    sample_positions: List[int] = field(default_factory=lambda: [150, 300])
    relevance_score_threshold: float = 40.0
    enable_website_search: bool = False
    enable_ddg_search: bool = True
    enable_serper_fallback: bool = True
    enable_targeted_serper_fallback: bool = True
    website_search_min_confidence: float = 0.5
    enable_playwright_fallback: bool = True
    playwright_max_contexts: int = 2
    playwright_wait_ms: int = 800
    enable_smart_email_generation: bool = True
    smart_email_enable_mx_check: bool = True
    smart_email_serper_validation: bool = True
    smart_email_prefixes: List[str] = field(default_factory=lambda: ['sales', 'contact', 'info', 'hello', 'inquiry', 'business'])
    smart_email_max_candidates: int = 3
    smart_email_require_company_context: bool = True
    smart_email_min_confidence: float = 0.6


@dataclass
class FilteringConfig:
    enable_geographic: bool = True
    enable_local_first: bool = True
    enable_geographic_sorting: bool = True
    local_preference_boost: float = 20.0
    regional_preference_boost: float = 10.0
    national_expansion_threshold: int = 50
    enable_duplicate_removal: bool = True
    enable_eligibility_checks: bool = True
    max_candidates: int = 500
    enable_size_heuristics: bool = True
    minimum_contract_value_ratio: float = 0.1
    enable_set_aside_filtering: bool = True
    log_filtering_decisions: bool = True
    geographic_search_radius_km: int = 200
    geographic_mode: str = "local_plus_regional"


@dataclass
class CapabilityMatchingConfig:
    enable_llm_assessment: bool = True
    llm_model: str = "gpt-5.1"
    enable_website_scraping: bool = True
    scrape_timeout_seconds: int = 5
    max_content_chars: int = 3000
    fallback_to_rule_based: bool = True
    llm_parallelism: int = 5
    llm_batch_size: int = 5


@dataclass
class OutputConfig:
    base_filename: str = "tender_vendors"
    include_json: bool = True
    include_csv: bool = True
    include_xlsx: bool = True


@dataclass
class SamApiConfig:
    base_url: str = "https://api.sam.gov/opportunities/v2/search"
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("SAM_API_KEY"))


@dataclass
class CanadaOpenDataConfig:
    base_url: str = "https://open.canada.ca/data/en/api/3/action"
    tender_dataset_id: str = "6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
    tender_resource_id: Optional[str] = None
    contracts_dataset_id: str = "4fe645a1-ffcd-40c1-9385-2c771be956a4"
    contracts_resource_id: Optional[str] = None


@dataclass
class DatabaseConfig:
    url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/vendor_ai"
    ))
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = field(default_factory=lambda: os.getenv("SQL_ECHO", "false").lower() == "true")


@dataclass
class RuntimeConfig:
    """Runtime toggles and API keys (to be loaded from env/secret store)."""

    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    apollo_api_key: Optional[str] = field(default_factory=lambda: os.getenv("APOLLO_API_KEY"))
    hunter_api_key: Optional[str] = field(default_factory=lambda: os.getenv("HUNTER_API_KEY"))
    google_maps_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY"))
    serper_api_key: Optional[str] = field(default_factory=lambda: os.getenv("SERPER_API_KEY"))
    enable_auto_ingestion: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTO_INGESTION", "true").lower() == "true")
    enable_manual_review: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)
    filtering: FilteringConfig = field(default_factory=FilteringConfig)
    capability_matching: CapabilityMatchingConfig = field(default_factory=CapabilityMatchingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    sam_api: SamApiConfig = field(default_factory=SamApiConfig)
    canada_open_data: CanadaOpenDataConfig = field(default_factory=CanadaOpenDataConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    def __post_init__(self):
        self.discovery.target_results = self.filtering.max_candidates


paths = Paths()
DEFAULT_CONFIG = RuntimeConfig()
