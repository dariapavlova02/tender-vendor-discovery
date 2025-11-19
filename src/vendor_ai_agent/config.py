"""Global configuration primitives for the Tender Vendor AI Agent."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Paths:
    """Commonly used filesystem locations."""

    root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = root / "data"
    output_dir: Path = root / "outputs"


@dataclass
class LLMConfig:
    model: str = "gpt-4"
    fallback_model: str = "gpt-3.5-turbo"
    max_tokens: int = 6000
    temperature: float = 0.0


@dataclass
class DiscoveryConfig:
    target_results: int = 1000
    preferred_sources: List[str] = field(default_factory=lambda: ["static_directory"])


@dataclass
class EnrichmentConfig:
    max_vendors: int = 300
    providers: List[str] = field(default_factory=lambda: ["static_contacts"])


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
class RuntimeConfig:
    """Runtime toggles and API keys (to be loaded from env/secret store)."""

    openai_api_key: Optional[str] = None
    apollo_api_key: Optional[str] = None
    hunter_api_key: Optional[str] = None
    enable_auto_ingestion: bool = True
    llm: LLMConfig = field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    sam_api: SamApiConfig = field(default_factory=SamApiConfig)
    canada_open_data: CanadaOpenDataConfig = field(default_factory=CanadaOpenDataConfig)


paths = Paths()
DEFAULT_CONFIG = RuntimeConfig()
