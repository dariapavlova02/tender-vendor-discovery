# Configuration Reference

Complete guide to configuring the Vendor AI Agent system.

## Table of Contents

- [Overview](#overview)
- [Environment Variables](#environment-variables)
- [Configuration Classes](#configuration-classes)
  - [RuntimeConfig](#runtimeconfig)
  - [LLMConfig](#llmconfig)
  - [DiscoveryConfig](#discoveryconfig)
  - [EnrichmentConfig](#enrichmentconfig)
  - [FilteringConfig](#filteringconfig)
  - [CapabilityMatchingConfig](#capabilitymatchingconfig)
  - [OutputConfig](#outputconfig)
  - [DatabaseConfig](#databaseconfig)
  - [SamApiConfig](#samapiconfig)
  - [CanadaOpenDataConfig](#canadaopendataconfig)
- [Configuration Patterns](#configuration-patterns)
- [Performance Tuning](#performance-tuning)
- [Security Best Practices](#security-best-practices)

---

## Overview

The system uses a hierarchical configuration structure with environment variables as the primary interface. All configuration is centralized in `src/vendor_ai_agent/config.py`.

**Key Principles:**
- Environment variables override default values
- All API keys and secrets come from environment variables
- Configuration is immutable at runtime (dataclass frozen where applicable)
- Sensible defaults for development; production requires explicit configuration

**Configuration Loading:**
```python
from vendor_ai_agent.config import DEFAULT_CONFIG

pipeline = VendorDiscoveryPipeline(config=DEFAULT_CONFIG)
```

---

## Environment Variables

### Required Variables

```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```
Required for all LLM-based features (requirement extraction, capability matching, profiling).

### Database Configuration

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/vendor_ai
```
- **Default:** `postgresql://postgres:postgres@localhost:5432/vendor_ai`
- **Format:** Standard database URL format
- **Supported:** PostgreSQL (recommended), SQLite (development only)

```bash
SQL_ECHO=false
```
- **Default:** `false`
- **Options:** `true` | `false`
- **Purpose:** Enable SQLAlchemy query logging for debugging

### LLM Model Selection

```bash
SMART_LLM_MODEL=gpt-5.1
```
- **Default:** `gpt-5.1`
- **Purpose:** Used for complex reasoning tasks (requirement extraction, tender profiling)
- **Considerations:** Higher cost, better accuracy

```bash
CHEAP_LLM_MODEL=gpt-5-mini
```
- **Default:** `gpt-5-mini` (falls back to `DEFAULT_LLM_MODEL`)
- **Purpose:** Used for high-volume tasks (capability matching, contact extraction)
- **Considerations:** Lower cost, faster processing

```bash
DEFAULT_LLM_MODEL=gpt-5-mini
```
- **Default:** `gpt-5-mini`
- **Purpose:** Fallback model when `CHEAP_LLM_MODEL` not set

```bash
VISION_LLM_MODEL=gpt-5-mini
```
- **Default:** `gpt-5-mini`
- **Purpose:** Used for document vision tasks (table extraction, image analysis)

```bash
USE_FLEX_TIER=true
```
- **Default:** `true`
- **Options:** `true` | `false`
- **Purpose:** Enable OpenAI flexible tier for cost optimization

### External API Keys (Optional)

```bash
SAM_API_KEY=your-sam-gov-api-key
```
- **Purpose:** Access SAM.gov Entity Management API for vendor discovery
- **Get Key:** https://sam.gov/profile/apikeys
- **Required For:** `sam_entity` source

```bash
APOLLO_API_KEY=your-apollo-api-key
```
- **Purpose:** Access Apollo.io API for contact enrichment and vendor discovery
- **Get Key:** https://apolloio.github.io/apollo-api-docs/
- **Required For:** `apollo_search` source, Apollo enrichment provider

```bash
HUNTER_API_KEY=your-hunter-api-key
```
- **Purpose:** Email verification and contact discovery
- **Get Key:** https://hunter.io/api
- **Required For:** Hunter enrichment provider

```bash
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```
- **Purpose:** Geocoding and address validation
- **Get Key:** https://developers.google.com/maps/documentation/geocoding/get-api-key
- **Required For:** Geographic matching and location normalization

```bash
SERPER_API_KEY=your-serper-api-key
```
- **Purpose:** Google Search API for web search and contact discovery
- **Get Key:** https://serper.dev
- **Required For:** `serper_search` source, Serper enrichment provider

### LangSmith Observability (Optional)

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=ls-your-langsmith-key-here
LANGCHAIN_PROJECT=vendor-agent
```
- **Purpose:** Enable LangSmith tracing for LLM call debugging
- **Get Key:** https://smith.langchain.com
- **See Also:** [OBSERVABILITY_QUICKSTART.md](OBSERVABILITY_QUICKSTART.md)

### Pipeline Behavior

```bash
ENABLE_AUTO_INGESTION=true
```
- **Default:** `true`
- **Options:** `true` | `false`
- **Purpose:** Automatically ingest SAM.gov and Canada Open Data sources on pipeline initialization

---

## Configuration Classes

### RuntimeConfig

Top-level configuration container holding all subsystem configurations.

```python
@dataclass
class RuntimeConfig:
    openai_api_key: Optional[str]
    apollo_api_key: Optional[str]
    hunter_api_key: Optional[str]
    google_maps_api_key: Optional[str]
    serper_api_key: Optional[str]
    enable_auto_ingestion: bool = True
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
```

**Key Fields:**

- **`enable_auto_ingestion`**: Automatically ingest vendor sources on initialization
- **`enable_manual_review`**: Pause pipeline for human review checkpoints (future feature)

**Usage:**
```python
from vendor_ai_agent.config import DEFAULT_CONFIG

config = DEFAULT_CONFIG
config.discovery.enable_apollo_discovery = True
config.filtering.enable_geographic = False

pipeline = VendorDiscoveryPipeline(config=config)
```

---

### LLMConfig

Controls LLM model selection and behavior.

```python
@dataclass
class LLMConfig:
    smart_model: str = "gpt-5.1"
    cheap_model: str = "gpt-5-mini"
    vision_model: str = "gpt-5-mini"
    use_flex_tier: bool = True
    max_tokens: int = 6000
    temperature: float = 0.0
```

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `smart_model` | `gpt-5.1` | Model for complex reasoning (requirement extraction, profiling) |
| `cheap_model` | `gpt-5-mini` | Model for high-volume tasks (matching, contact extraction) |
| `vision_model` | `gpt-5-mini` | Model for vision tasks (table extraction, image analysis) |
| `use_flex_tier` | `True` | Use OpenAI flexible tier for cost savings |
| `max_tokens` | `6000` | Maximum tokens per LLM response |
| `temperature` | `0.0` | Sampling temperature (0 = deterministic, 1 = creative) |

**Usage:**
```python
config = RuntimeConfig()
config.llm.smart_model = "gpt-4"
config.llm.temperature = 0.1
```

**Environment Variables:**
- `SMART_LLM_MODEL` → `smart_model`
- `CHEAP_LLM_MODEL` → `cheap_model` (fallback to `DEFAULT_LLM_MODEL`)
- `VISION_LLM_MODEL` → `vision_model`
- `USE_FLEX_TIER` → `use_flex_tier`

---

### DiscoveryConfig

Controls vendor discovery sources and behavior.

```python
@dataclass
class DiscoveryConfig:
    target_results: int = 1000
    preferred_sources: List[str] = ["static_directory"]
    enable_apollo_discovery: bool = False
    enable_apollo_booster: bool = False
    apollo_min_candidates: int = 200
    apollo_max_pages: int = 1
    enable_serper_discovery: bool = True
    serper_discovery_query_limit: int = 10
    serper_discovery_trigger_threshold: int = 100
    serper_discovery_always_canada: bool = True
    min_relevant_candidates: int = 200
    enable_batch_cache: bool = True
    batch_size: int = 500
    processing_batch: int = 1
```

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `target_results` | `1000` | Target number of vendors to discover |
| `preferred_sources` | `["static_directory"]` | Sources to use in order: `sam_entity`, `apollo_search`, `serper_search`, `static_directory`, `canada_contracts` |
| `enable_apollo_discovery` | `False` | Enable Apollo.io vendor search |
| `enable_apollo_booster` | `False` | Use Apollo to boost results when candidates < `apollo_min_candidates` |
| `apollo_min_candidates` | `200` | Minimum candidates before Apollo booster triggers |
| `apollo_max_pages` | `1` | Maximum pages to fetch from Apollo (100 results/page) |
| `enable_serper_discovery` | `True` | Enable Serper web search for vendor discovery |
| `serper_discovery_query_limit` | `10` | Maximum search queries to execute |
| `serper_discovery_trigger_threshold` | `100` | Trigger Serper when candidates < threshold |
| `serper_discovery_always_canada` | `True` | Always use Serper for Canada-based contracts |
| `min_relevant_candidates` | `200` | Minimum relevant candidates for high-quality results |
| `enable_batch_cache` | `True` | Cache vendor lookups in batches |
| `batch_size` | `500` | Number of vendors per batch |
| `processing_batch` | `1` | Current processing batch number |

**Discovery Source Priority:**

1. **SAM Entity** (`sam_entity`): U.S. government vendor registry (requires `SAM_API_KEY`)
2. **Apollo Search** (`apollo_search`): B2B database (requires `APOLLO_API_KEY`)
3. **Serper Search** (`serper_search`): Web search (requires `SERPER_API_KEY`)
4. **Static Directory** (`static_directory`): Database of ingested vendors (default, always available)
5. **Canada Contracts** (`canada_contracts`): Canadian government contracts (Canada tenders only)

**Usage Examples:**

**Scenario 1: U.S. Government Contract (SAM.gov Primary)**
```python
config = RuntimeConfig()
config.discovery.preferred_sources = ["sam_entity", "static_directory"]
config.discovery.enable_serper_discovery = False
config.discovery.enable_apollo_discovery = False
```

**Scenario 2: Commercial Contract (Apollo + Serper)**
```python
config = RuntimeConfig()
config.discovery.preferred_sources = ["apollo_search", "serper_search", "static_directory"]
config.discovery.enable_apollo_discovery = True
config.discovery.enable_serper_discovery = True
config.discovery.apollo_max_pages = 3
```

**Scenario 3: Canada Government Contract**
```python
config = RuntimeConfig()
config.discovery.preferred_sources = ["canada_contracts", "static_directory"]
config.discovery.enable_serper_discovery = True
config.discovery.serper_discovery_always_canada = True
```

---

### EnrichmentConfig

Controls contact discovery and vendor enrichment.

```python
@dataclass
class EnrichmentConfig:
    providers: List[str] = ["static_contacts"]
    enable_contact_scraping: bool = True
    enable_llm_fallback: bool = True
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
    sample_positions: List[int] = [150, 300]
    relevance_score_threshold: float = 40.0
    enable_website_search: bool = False
    enable_ddg_search: bool = True
    enable_serper_fallback: bool = True
    enable_targeted_serper_fallback: bool = True
    website_search_min_confidence: float = 0.5
```

**Contact Enrichment Providers:**

| Provider | Description | Requires |
|----------|-------------|----------|
| `static_contacts` | Pre-loaded contacts from database | Database |
| `apollo` | Apollo.io API contact search | `APOLLO_API_KEY` |
| `hunter` | Hunter.io email verification | `HUNTER_API_KEY` |
| `scraper` | Website scraping for contact pages | None |
| `duckduckgo` | DuckDuckGo search for contact info | None |
| `serper` | Google Search for contact info | `SERPER_API_KEY` |
| `google_maps` | (legacy) Google Maps enrichment – currently not registered in code | `GOOGLE_MAPS_API_KEY` |

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `providers` | `["static_contacts"]` | Ordered list of enrichment providers to try |
| `enable_contact_scraping` | `True` | Scrape vendor websites for contact pages |
| `enable_llm_fallback` | `True` | Use LLM to extract contacts from scraped HTML |
| `scraper_timeout_seconds` | `5` | Timeout for website scraping requests |
| `enable_google_maps` | `True` | Legacy flag retained for backward compatibility (provider removed) |
| `google_maps_min_confidence` | `0.7` | Legacy setting, no effect without provider |
| `google_maps_cache_ttl_days` | `90` | Legacy setting, no effect without provider |
| `enable_apollo_enrichment` | `True` | Use Apollo.io for contact enrichment |
| `max_enrichment_workers` | `10` | Maximum concurrent enrichment tasks |
| `batch_size` | `50` | Vendors processed per enrichment batch |
| `min_batch_success_rate` | `0.15` | Minimum success rate to continue enrichment (15%) |
| `max_enrichment_batches` | `5` | Maximum enrichment batches to process |
| `target_relevant_vendors` | `200` | Stop enriching after this many relevant vendors found |
| `enable_batch_quality_gates` | `True` | Stop enrichment when quality thresholds met |
| `enable_sampling_fallback` | `True` | Enrich sample vendors at specific positions if batch gates fail |
| `sample_positions` | `[150, 300]` | Vendor positions to sample for fallback enrichment |
| `relevance_score_threshold` | `40.0` | Minimum relevance score for quality gate |
| `enable_ddg_search` | `True` | Use DuckDuckGo search for contact discovery |
| `enable_serper_fallback` | `True` | Use Serper as fallback when other providers fail |
| `enable_targeted_serper_fallback` | `True` | Use Serper for high-scoring vendors without contacts |

**Usage Examples:**

**Scenario 1: Maximum Enrichment (All Providers)**
```python
config = RuntimeConfig()
config.enrichment.providers = [
    "static_contacts",
    "apollo",
    "google_maps",
    "scraper",
    "hunter",
    "serper"
]
config.enrichment.max_enrichment_workers = 20
config.enrichment.batch_size = 100
```

**Scenario 2: Fast Mode (Database Only)**
```python
config = RuntimeConfig()
config.enrichment.providers = ["static_contacts"]
config.enrichment.enable_contact_scraping = False
config.enrichment.enable_apollo_enrichment = False
```

**Scenario 3: Cost-Optimized (Free Tools Only)**
```python
config = RuntimeConfig()
config.enrichment.providers = ["static_contacts", "scraper", "duckduckgo"]
config.enrichment.enable_apollo_enrichment = False
config.enrichment.enable_serper_fallback = False
config.enrichment.enable_google_maps = False
```

---

### FilteringConfig

Controls vendor filtering and geographic matching.

```python
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
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `enable_geographic` | `True` | Apply geographic preference filtering |
| `enable_local_first` | `True` | Prioritize local vendors (same state/province) |
| `enable_geographic_sorting` | `True` | Sort vendors by geographic proximity |
| `local_preference_boost` | `20.0` | Score boost for local vendors |
| `regional_preference_boost` | `10.0` | Score boost for regional vendors (neighboring states) |
| `national_expansion_threshold` | `50` | Expand to national search if local results < threshold |
| `enable_duplicate_removal` | `True` | Remove duplicate vendors (by name/address) |
| `enable_eligibility_checks` | `True` | Check vendor eligibility (size, set-asides) |
| `max_candidates` | `500` | Maximum candidates to pass to next stage |
| `enable_size_heuristics` | `True` | Filter vendors by size relative to contract value |
| `minimum_contract_value_ratio` | `0.1` | Minimum ratio of vendor revenue to contract value |
| `enable_set_aside_filtering` | `True` | Apply set-aside filters (8(a), WOSB, SDVOSB, etc.) |
| `log_filtering_decisions` | `True` | Log filtering decisions for debugging |
| `geographic_search_radius_km` | `200` | Search radius for geographic matching (km) |
| `geographic_mode` | `"local_plus_regional"` | Mode: `"local_only"`, `"local_plus_regional"`, `"national"` |

**Geographic Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `local_only` | Same state/province only | Local services, strict local preference |
| `local_plus_regional` | Local + neighboring states/provinces | Standard government contracts |
| `national` | All vendors regardless of location | National contracts, specialized services |

**Set-Aside Types:**

- **8(a)**: Small disadvantaged businesses
- **WOSB**: Women-owned small businesses
- **SDVOSB**: Service-disabled veteran-owned small businesses
- **HUBZone**: Historically underutilized business zones
- **SBA**: Small Business Administration certified

**Usage Examples:**

**Scenario 1: Local Services (Strict Geographic)**
```python
config = RuntimeConfig()
config.filtering.enable_geographic = True
config.filtering.geographic_mode = "local_only"
config.filtering.local_preference_boost = 30.0
config.filtering.national_expansion_threshold = 20
```

**Scenario 2: National Contract (No Geographic Filter)**
```python
config = RuntimeConfig()
config.filtering.enable_geographic = False
config.filtering.geographic_mode = "national"
config.filtering.enable_local_first = False
```

**Scenario 3: Set-Aside Contract (8(a) Only)**
```python
config = RuntimeConfig()
config.filtering.enable_set_aside_filtering = True
# Note: Set-aside type comes from tender requirements, not config
```

---

### CapabilityMatchingConfig

Controls LLM-based capability assessment.

```python
@dataclass
class CapabilityMatchingConfig:
    enable_llm_assessment: bool = True
    llm_model: str = "gpt-5-mini"
    enable_website_scraping: bool = True
    scrape_timeout_seconds: int = 5
    max_content_chars: int = 3000
    fallback_to_rule_based: bool = True
    llm_parallelism: int = 5
    llm_batch_size: int = 5
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `enable_llm_assessment` | `True` | Use LLM to assess vendor capabilities from website content |
| `llm_model` | `"gpt-5-mini"` | LLM model for capability assessment |
| `enable_website_scraping` | `True` | Scrape vendor websites for capability information |
| `scrape_timeout_seconds` | `5` | Timeout for website scraping |
| `max_content_chars` | `3000` | Maximum website content characters to send to LLM |
| `fallback_to_rule_based` | `True` | Fallback to rule-based scoring if LLM fails |
| `llm_parallelism` | `5` | Number of parallel LLM assessment tasks |
| `llm_batch_size` | `5` | Number of vendors per LLM batch |

**Scoring Logic:**

1. **LLM Assessment** (if `enable_llm_assessment=True` and website content available):
   - Scrapes vendor website
   - Sends tender requirements + website content to LLM
   - LLM returns score (0-100) and rationale

2. **Rule-Based Fallback**:
   - Base score from contract history, certifications
   - NAICS code similarity boost (up to +20 points)
   - Geographic proximity boost (if enabled)

**Usage Examples:**

**Scenario 1: High Accuracy (LLM-Based)**
```python
config = RuntimeConfig()
config.capability_matching.enable_llm_assessment = True
config.capability_matching.llm_model = "gpt-4"
config.capability_matching.max_content_chars = 5000
config.capability_matching.llm_parallelism = 10
```

**Scenario 2: Fast Mode (Rule-Based Only)**
```python
config = RuntimeConfig()
config.capability_matching.enable_llm_assessment = False
config.capability_matching.enable_website_scraping = False
```

**Scenario 3: Cost-Optimized**
```python
config = RuntimeConfig()
config.capability_matching.enable_llm_assessment = True
config.capability_matching.llm_model = "gpt-5-mini"
config.capability_matching.max_content_chars = 1500
config.capability_matching.llm_batch_size = 10
```

---

### OutputConfig

Controls output file generation.

```python
@dataclass
class OutputConfig:
    base_filename: str = "tender_vendors"
    include_json: bool = True
    include_csv: bool = True
    include_xlsx: bool = True
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `base_filename` | `"tender_vendors"` | Base name for output files (extension added automatically) |
| `include_json` | `True` | Generate JSON output |
| `include_csv` | `True` | Generate CSV output |
| `include_xlsx` | `True` | Generate Excel output |

**Output Files Generated:**

- `{base_filename}.json`: Full vendor data with nested structures
- `{base_filename}.csv`: Flattened vendor data for spreadsheet analysis
- `{base_filename}.xlsx`: Excel workbook with formatted columns

**Usage:**
```python
config = RuntimeConfig()
config.output.base_filename = "dhs_uniforms_vendors"
config.output.include_json = True
config.output.include_csv = True
config.output.include_xlsx = False
```

---

### DatabaseConfig

Controls database connection.

```python
@dataclass
class DatabaseConfig:
    url: str = "postgresql://postgres:postgres@localhost:5432/vendor_ai"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `url` | `postgresql://...` | Database connection URL |
| `pool_size` | `10` | Connection pool size |
| `max_overflow` | `20` | Max connections beyond pool size |
| `echo` | `False` | Log SQL queries |

**Environment Variables:**
- `DATABASE_URL` → `url`
- `SQL_ECHO` → `echo`

**Supported Databases:**

| Database | URL Format | Notes |
|----------|------------|-------|
| PostgreSQL | `postgresql://user:pass@host:port/db` | **Recommended for production** |
| SQLite | `sqlite:///path/to/db.sqlite` | Development only, no concurrent writes |

**Usage:**
```python
config = RuntimeConfig()
config.database.url = "postgresql://user:pass@prod-db:5432/vendor_ai"
config.database.pool_size = 20
config.database.max_overflow = 40
config.database.echo = False
```

---

### SamApiConfig

Controls SAM.gov API integration.

```python
@dataclass
class SamApiConfig:
    base_url: str = "https://api.sam.gov/opportunities/v2/search"
    api_key: Optional[str] = None
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `base_url` | `https://api.sam.gov/...` | SAM.gov API endpoint |
| `api_key` | `None` | SAM.gov API key (from `SAM_API_KEY` env var) |

**Get API Key:** https://sam.gov/profile/apikeys

**Usage:**
```python
config = RuntimeConfig()
config.sam_api.api_key = os.getenv("SAM_API_KEY")
```

---

### CanadaOpenDataConfig

Controls Canada Open Data API integration.

```python
@dataclass
class CanadaOpenDataConfig:
    base_url: str = "https://open.canada.ca/data/en/api/3/action"
    tender_dataset_id: str = "6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
    tender_resource_id: Optional[str] = None
    contracts_dataset_id: str = "4fe645a1-ffcd-40c1-9385-2c771be956a4"
    contracts_resource_id: Optional[str] = None
```

**Key Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `base_url` | `https://open.canada.ca/...` | CKAN API endpoint |
| `tender_dataset_id` | `6abd20d4...` | Tender notices dataset ID |
| `contracts_dataset_id` | `4fe645a1...` | Contracts dataset ID |
| `tender_resource_id` | `None` | Specific tender resource (auto-detected if None) |
| `contracts_resource_id` | `None` | Specific contracts resource (auto-detected if None) |

**No API Key Required:** Canada Open Data is public and free.

---

## Configuration Patterns

### Pattern 1: Development Configuration

Fast iteration, minimal external dependencies.

```python
config = RuntimeConfig()

config.database.url = "sqlite:///vendor_ai.db"
config.database.echo = True

config.discovery.preferred_sources = ["static_directory"]
config.discovery.enable_apollo_discovery = False
config.discovery.enable_serper_discovery = False

config.enrichment.providers = ["static_contacts"]
config.enrichment.enable_contact_scraping = False
config.enrichment.enable_apollo_enrichment = False

config.capability_matching.enable_llm_assessment = False

config.llm.temperature = 0.1

pipeline = VendorDiscoveryPipeline(config=config)
```

---

### Pattern 2: Production Configuration

High accuracy, full capabilities, optimized for quality.

```python
config = RuntimeConfig()

config.database.url = os.getenv("DATABASE_URL")
config.database.pool_size = 20
config.database.max_overflow = 40
config.database.echo = False

config.llm.smart_model = "gpt-5.1"
config.llm.cheap_model = "gpt-5-mini"
config.llm.use_flex_tier = True

config.discovery.preferred_sources = ["sam_entity", "apollo_search", "static_directory"]
config.discovery.enable_apollo_discovery = True
config.discovery.enable_serper_discovery = True
config.discovery.target_results = 2000

config.enrichment.providers = [
    "static_contacts",
    "apollo",
    "google_maps",
    "scraper",
    "hunter",
    "serper"
]
config.enrichment.max_enrichment_workers = 20
config.enrichment.batch_size = 100
config.enrichment.target_relevant_vendors = 300

config.filtering.enable_geographic = True
config.filtering.enable_duplicate_removal = True
config.filtering.enable_eligibility_checks = True

config.capability_matching.enable_llm_assessment = True
config.capability_matching.llm_model = "gpt-5-mini"
config.capability_matching.llm_parallelism = 10

pipeline = VendorDiscoveryPipeline(config=config)
```

---

### Pattern 3: Cost-Optimized Configuration

Minimize API costs while maintaining quality.

```python
config = RuntimeConfig()

config.llm.smart_model = "gpt-5-mini"
config.llm.cheap_model = "gpt-5-mini"
config.llm.use_flex_tier = True

config.discovery.preferred_sources = ["static_directory", "serper_search"]
config.discovery.enable_apollo_discovery = False
config.discovery.enable_serper_discovery = True
config.discovery.serper_discovery_query_limit = 5

config.enrichment.providers = ["static_contacts", "scraper", "duckduckgo"]
config.enrichment.enable_apollo_enrichment = False
config.enrichment.enable_serper_fallback = False
config.enrichment.enable_google_maps = False
config.enrichment.max_enrichment_batches = 3

config.capability_matching.enable_llm_assessment = True
config.capability_matching.max_content_chars = 1500
config.capability_matching.llm_batch_size = 10

pipeline = VendorDiscoveryPipeline(config=config)
```

---

### Pattern 4: High-Speed Configuration

Maximize throughput, trade accuracy for speed.

```python
config = RuntimeConfig()

config.llm.cheap_model = "gpt-5-mini"

config.discovery.preferred_sources = ["static_directory"]
config.discovery.batch_size = 1000
config.discovery.target_results = 500

config.enrichment.providers = ["static_contacts"]
config.enrichment.enable_contact_scraping = False
config.enrichment.enable_apollo_enrichment = False
config.enrichment.max_enrichment_batches = 1
config.enrichment.enable_batch_quality_gates = False

config.filtering.enable_duplicate_removal = True
config.filtering.max_candidates = 200

config.capability_matching.enable_llm_assessment = False
config.capability_matching.enable_website_scraping = False

pipeline = VendorDiscoveryPipeline(config=config)
```

---

## Performance Tuning

### Database Performance

**Connection Pooling:**
```python
config.database.pool_size = 20
config.database.max_overflow = 40
```
- **Rule of Thumb:** `pool_size = 2 * num_workers`
- **For High Concurrency:** Increase both values

**Query Logging:**
```python
config.database.echo = True
```
- **Use:** Development and debugging only
- **Impact:** Significant performance overhead

---

### LLM Performance

**Model Selection:**
```python
config.llm.smart_model = "gpt-5.1"
config.llm.cheap_model = "gpt-5-mini"
```
- **Cost:** `gpt-5.1` is 10x more expensive than `gpt-5-mini`
- **Speed:** `gpt-5-mini` is 2-3x faster

**Parallel Processing:**
```python
config.capability_matching.llm_parallelism = 10
config.capability_matching.llm_batch_size = 10
```
- **Higher Parallelism:** Faster, but may hit rate limits
- **Larger Batches:** Better throughput, higher memory usage

**Token Optimization:**
```python
config.llm.max_tokens = 6000
config.capability_matching.max_content_chars = 1500
```
- **Lower `max_tokens`:** Faster responses, but may truncate
- **Lower `max_content_chars`:** Less context, lower LLM cost

---

### Discovery Performance

**Batch Size:**
```python
config.discovery.batch_size = 1000
```
- **Larger Batches:** Better database efficiency
- **Smaller Batches:** Lower memory usage

**Source Selection:**
```python
config.discovery.preferred_sources = ["static_directory"]
```
- **Static Directory:** Fastest, uses database only
- **SAM Entity:** Slower, requires API calls
- **Apollo/Serper:** Slowest, external API calls

---

### Enrichment Performance

**Worker Threads:**
```python
config.enrichment.max_enrichment_workers = 20
config.enrichment.batch_size = 100
```
- **More Workers:** Faster enrichment, higher concurrency
- **Larger Batches:** Better throughput

**Provider Selection:**
```python
config.enrichment.providers = ["static_contacts", "scraper"]
```
- **Static Contacts:** Fastest, database-only
- **Scraper/DuckDuckGo:** Fast, free, no API limits
- **Apollo/Hunter/Serper:** Slower, paid, rate-limited

**Quality Gates:**
```python
config.enrichment.enable_batch_quality_gates = True
config.enrichment.target_relevant_vendors = 200
```
- **Quality Gates Enabled:** Stops enrichment early when targets met
- **Higher Targets:** More enrichment, slower processing

---

## Security Best Practices

### 1. Never Commit API Keys

❌ **Bad:**
```python
config.apollo_api_key = "actual-api-key-here"
```

✅ **Good:**
```python
config.apollo_api_key = os.getenv("APOLLO_API_KEY")
```

---

### 2. Use Environment Files

Create `.env` file (add to `.gitignore`):
```bash
OPENAI_API_KEY=sk-your-key
APOLLO_API_KEY=your-key
SERPER_API_KEY=your-key
DATABASE_URL=postgresql://user:pass@host:5432/db
```

Load in code:
```python
from dotenv import load_dotenv
load_dotenv()

config = RuntimeConfig()
```

---

### 3. Validate API Keys Before Use

```python
from vendor_ai_agent.config import DEFAULT_CONFIG

if not DEFAULT_CONFIG.openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

if DEFAULT_CONFIG.discovery.enable_apollo_discovery and not DEFAULT_CONFIG.apollo_api_key:
    raise ValueError("APOLLO_API_KEY required when enable_apollo_discovery=True")
```

---

### 4. Use Different Configs for Dev/Prod

**Development:**
```python
config = RuntimeConfig()
config.database.url = "sqlite:///dev.db"
config.llm.smart_model = "gpt-5-mini"
```

**Production:**
```python
config = RuntimeConfig()
config.database.url = os.getenv("DATABASE_URL")
config.llm.smart_model = "gpt-5.1"
```

---

### 5. Restrict Database Permissions

```sql
CREATE USER vendor_agent WITH PASSWORD 'secure_password';
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO vendor_agent;
REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM vendor_agent;
```

---

### 6. Enable SQL Logging Carefully

```python
config.database.echo = True
```

⚠️ **Warning:** May log sensitive data (vendor names, addresses, etc.)

**Safe for:**
- Development
- Debugging specific issues

**Unsafe for:**
- Production
- Logs sent to third-party services

---

## Related Documentation

- **[API Reference](API_REFERENCE.md)**: Complete API documentation
- **[Pipeline Workflow](PIPELINE_WORKFLOW.md)**: Pipeline stages and data flow
- **[Observability Quickstart](OBSERVABILITY_QUICKSTART.md)**: LangSmith tracing setup
- **[Dashboard Guide](DASHBOARD_GUIDE.md)**: Dashboard configuration and usage

---

## Troubleshooting

### Issue: "OPENAI_API_KEY not found"

**Solution:**
```bash
export OPENAI_API_KEY=sk-your-key-here
```

Or add to `.env`:
```bash
OPENAI_API_KEY=sk-your-key-here
```

---

### Issue: "Connection refused" (Database)

**Check:**
1. Database is running: `pg_isready -h localhost -p 5432`
2. Connection URL is correct: `echo $DATABASE_URL`
3. Credentials are valid: `psql $DATABASE_URL`

---

### Issue: LLM rate limits

**Solution:**
```python
config.llm.use_flex_tier = True
config.capability_matching.llm_parallelism = 5
config.capability_matching.llm_batch_size = 10
```

---

### Issue: High API costs

**Solution:**
```python
config.llm.smart_model = "gpt-5-mini"
config.llm.cheap_model = "gpt-5-mini"
config.capability_matching.max_content_chars = 1500
config.enrichment.max_enrichment_batches = 3
```

---

### Issue: Slow performance

**Solution:**
```python
config.discovery.preferred_sources = ["static_directory"]
config.enrichment.providers = ["static_contacts"]
config.capability_matching.enable_llm_assessment = False
config.filtering.max_candidates = 200
```

---

**Last Updated:** 2025-01-24  
**Version:** 1.0.0
