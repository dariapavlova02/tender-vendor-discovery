# API Reference

Complete API documentation for Vendor AI Agent modules, classes, and methods.

## Table of Contents

1. [Core Pipeline](#core-pipeline)
2. [Document Processing](#document-processing)
3. [Filtering](#filtering)
4. [Enrichment](#enrichment)
5. [Matching & Scoring](#matching--scoring)
6. [Sources](#sources)
7. [Ingestion](#ingestion)
8. [Database](#database)
9. [Data Models](#data-models)

---

## Core Pipeline

### TenderVendorPipeline

Primary orchestration class for the end-to-end tender processing workflow.

**Module:** `src/vendor_ai_agent/pipeline.py`

#### Methods

##### `run(tender_files: Iterable[Path], *, ingestion_request: Optional[TenderIngestionRequest] = None, disable_auto_ingestion: bool = False) -> PipelineArtifacts`

Execute the complete discovery pipeline and return a `PipelineArtifacts` object that the dashboard and CLI consume.

**Parameters:**
- `tender_files` – iterable of paths to local tender files (PDF, DOCX, XLSX)
- `ingestion_request` – optional request describing attachments to fetch from SAM.gov/CanadaBuys
- `disable_auto_ingestion` – override to skip automatic ingestion even when enabled globally

**Returns:** `PipelineArtifacts` with parsed sections, tender profile, filtered/enriched vendors, match results, metrics, and batch metadata.

**Example:**
```python
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

pipeline = TenderVendorPipeline()
artifacts = pipeline.run([Path("data/tender.pdf")])

print(f"Matched vendors: {len(artifacts.final_matches)}")
print(f"All scored vendors: {len(artifacts.all_matches)}")
```

---

## Document Processing

### DocumentParser

Parses PDF documents and extracts structured content.

**Module:** `src/vendor_ai_agent/modules/document_parser.py`

#### Methods

##### `parse(file_path: Path) -> ParsedDocument`

Extract text, tables, sections from PDF.

**Parameters:**
- `file_path` - Path to PDF document

**Returns:** `ParsedDocument` with sections, tables, text

**Example:**
```python
from vendor_ai_agent.modules.document_parser import DocumentParser

parser = DocumentParser()
doc = parser.parse(Path("tender.pdf"))

print(f"Sections: {len(doc.sections)}")
print(f"Tables: {len(doc.tables)}")
```

---

### RequirementExtractor

Extracts structured requirements from tender documents using LLM.

**Module:** `src/vendor_ai_agent/modules/requirement_extractor.py`

#### Methods

##### `extract(parsed_doc: ParsedDocument) -> ExtractedRequirements`

Extract NAICS codes, project type, location, technical specs.

**Parameters:**
- `parsed_doc` - Parsed document from DocumentParser

**Returns:** `ExtractedRequirements` with structured fields

**Example:**
```python
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor

extractor = RequirementExtractor(llm_provider=llm)
requirements = extractor.extract(parsed_doc)

print(f"Project Type: {requirements.structured.project_type}")
print(f"NAICS: {requirements.structured.naics_codes}")
```

---

### TenderProfiler

Generates dynamic search context from tender scope using LLM.

**Module:** `src/vendor_ai_agent/modules/tender_profiler.py`

#### Constructor

```python
TenderProfiler(llm_provider: Optional[LLMProvider] = None)
```

#### Methods

##### `generate_context(raw_sections: List[Section], max_tokens: int = 3000) -> TenderContext`

Analyze tender scope and extract search keywords, industry context.

**Parameters:**
- `raw_sections` - List of document sections
- `max_tokens` - Max tokens for LLM context (default: 3000)

**Returns:** `TenderContext` with sector, keywords, search terms

**Example:**
```python
from vendor_ai_agent.modules.tender_profiler import TenderProfiler

profiler = TenderProfiler(llm_provider=llm)
context = profiler.generate_context(doc.sections)

print(f"Sector: {context.sector}")
print(f"Keywords: {context.technical_keywords[:5]}")
print(f"Search Terms: {context.search_terms}")
```

---

### Document Processing Submodules

#### Classification

**Module:** `src/vendor_ai_agent/modules/document_processing/classifier.py`

Classifies document sections by content type.

#### Field Extraction

**Module:** `src/vendor_ai_agent/modules/document_processing/field_extractor.py`

Extracts specific fields using LLM and regex patterns.

#### Keywords

**Module:** `src/vendor_ai_agent/modules/document_processing/keywords.py`

Sector-aware keyword extraction with priority classification.

#### QA Handler

**Module:** `src/vendor_ai_agent/modules/document_processing/qa_handler.py`

Processes Question-Answer pairs from tender documents.

#### Sections

**Module:** `src/vendor_ai_agent/modules/document_processing/sections.py`

Extracts structured sections (scope of work, technical requirements).

#### Table Classifier

**Module:** `src/vendor_ai_agent/modules/document_processing/table_classifier.py`

Classifies tables by content type (pricing, specifications, etc.).

---

## Filtering

### DuplicateDetector

Detects and merges duplicate vendor records.

**Module:** `src/vendor_ai_agent/modules/filtering/duplicate_detector.py`

#### Constructor

```python
DuplicateDetector(merge_duplicates: bool = True)
```

#### Methods

##### `deduplicate(vendors: List[VendorRecord]) -> tuple[List[VendorRecord], int]`

Remove duplicates based on company name, website, identifiers.

**Parameters:**
- `vendors` - List of vendor records

**Returns:** Tuple of (deduplicated_vendors, duplicates_removed_count)

**Example:**
```python
from vendor_ai_agent.modules.filtering.duplicate_detector import DuplicateDetector

detector = DuplicateDetector(merge_duplicates=True)
unique_vendors, removed_count = detector.deduplicate(vendors)

print(f"Removed {removed_count} duplicates")
```

**Deduplication Keys:**
- UEI (Unique Entity ID)
- DUNS number
- CAGE code
- Normalized company name
- Normalized website domain

---

### EligibilityChecker

Filters vendors by eligibility criteria.

**Module:** `src/vendor_ai_agent/modules/filtering/eligibility_checker.py`

#### Constructor

```python
EligibilityChecker(
    enable_set_aside: bool = True,
    enable_size_heuristics: bool = True,
    minimum_contract_value_ratio: float = 0.1
)
```

#### Methods

##### `filter_eligible(profile: TenderProfile, vendors: List[VendorRecord]) -> tuple[List[VendorRecord], Dict[str, int]]`

Filter by set-aside requirements, size constraints.

**Parameters:**
- `profile` - Tender profile with requirements
- `vendors` - List of vendor candidates

**Returns:** Tuple of (eligible_vendors, filter_reasons_dict)

**Example:**
```python
from vendor_ai_agent.modules.filtering.eligibility_checker import EligibilityChecker

checker = EligibilityChecker()
eligible, reasons = checker.filter_eligible(profile, vendors)

print(f"Eligible: {len(eligible)}/{len(vendors)}")
print(f"Reasons: {reasons}")
```

**Filter Criteria:**
- Set-aside requirements (8(a), WOSB, SDVOSB, HUBZone)
- Size capacity (contract history vs tender value)
- Business type matching

---

### GeographicMatcher

Geographic filtering and scoring for local preference.

**Module:** `src/vendor_ai_agent/modules/filtering/geographic_matcher.py`

#### Constructor

```python
GeographicMatcher(
    local_boost: float = 20.0,
    regional_boost: float = 10.0,
    enable_local_first: bool = True
)
```

#### Methods

##### `filter_by_geography(profile: TenderProfile, vendors: List[VendorRecord], expansion_mode: bool = False) -> tuple[List[VendorRecord], int, int]`

Filter/sort vendors by geographic proximity.

**Parameters:**
- `profile` - Tender profile with location
- `vendors` - List of vendors
- `expansion_mode` - Include national vendors if True

**Returns:** Tuple of (filtered_vendors, local_count, national_count)

**Example:**
```python
from vendor_ai_agent.modules.filtering.geographic_matcher import GeographicMatcher

matcher = GeographicMatcher(local_boost=20.0)
filtered, local, national = matcher.filter_by_geography(profile, vendors)

print(f"Local: {local}, National: {national}")
```

**Geographic Tiers:**
- **Local**: Same state/province
- **Regional**: Neighboring state/province
- **National**: All other locations

---

## Enrichment

### VendorEnricher

Enriches vendor records with contact info and metadata.

**Module:** `src/vendor_ai_agent/modules/enrichment.py`

#### Constructor

```python
VendorEnricher(
    providers: Sequence[EnrichmentProvider] | None = None,
    max_workers: int = 10,
    batch_size: int = 50,
    min_batch_success_rate: float = 0.15,
    target_relevant_vendors: int = 200,
    enable_batch_quality_gates: bool = True
)
```

#### Methods

##### `enrich(vendors: Iterable[VendorRecord]) -> List[VendorRecord]`

Enrich all vendors with contact info and metadata.

**Parameters:**
- `vendors` - Vendor records to enrich

**Returns:** Enriched vendor records

##### `enrich_with_scoring(profile: TenderProfile, vendors: List[VendorRecord], scoring_fn: Callable) -> tuple[List[VendorRecord], List[VendorMatchResult], List[VendorMatchResult]]`

Enrich vendors in batches with LLM scoring and quality gates.

**Parameters:**
- `profile` - Tender profile
- `vendors` - Vendor candidates
- `scoring_fn` - Scoring function (usually CapabilityMatcher.score)

**Returns:** Tuple of (all_enriched, relevant_matches, all_scored_results)

**Example:**
```python
from vendor_ai_agent.modules.enrichment import VendorEnricher

enricher = VendorEnricher(
    providers=[contact_provider, website_provider],
    batch_size=50,
    target_relevant_vendors=200
)

enriched, relevant, all_scored = enricher.enrich_with_scoring(
    profile, vendors, capability_matcher.score
)

print(f"Enriched: {len(enriched)}, Relevant: {len(relevant)}")
```

**Batch Quality Gates:**
- Stops early if success rate < min_batch_success_rate
- Samples deeper positions if first batch fails
- Targets `target_relevant_vendors` threshold

---

### ContactExtractor

Extracts contact information from HTML text using regex + LLM fallback.

**Module:** `src/vendor_ai_agent/modules/contact_extractor.py`

#### Constructor

```python
ContactExtractor(llm_provider: Optional[LLMProvider] = None)
```

#### Methods

##### `extract(text: str, use_llm_fallback: bool = True) -> ExtractedContacts`

Extract emails, phones, contact names from HTML.

**Parameters:**
- `text` - Raw HTML text from contact page
- `use_llm_fallback` - Use LLM if regex finds nothing

**Returns:** `ExtractedContacts` with emails, phones, names

**Example:**
```python
from vendor_ai_agent.modules.contact_extractor import ContactExtractor

extractor = ContactExtractor(llm_provider=llm)
contacts = extractor.extract(html_text, use_llm_fallback=True)

print(f"Emails: {contacts.emails}")
print(f"Phones: {contacts.phones}")
print(f"Method: {contacts.extraction_method}")  # "regex" or "llm"
```

**Email Prioritization:**
1. sales@, contact@, business@
2. inquiries@, hello@
3. info@
4. support@

**Filters:** Excludes noreply@, webmaster@, test@, etc.

---

### Enrichment Providers

#### ContactScrapingProvider

**Module:** `src/vendor_ai_agent/enrichment_providers/contact_scraping.py`

Scrapes contact pages and extracts emails/phones.

#### WebsiteContentProvider

**Module:** `src/vendor_ai_agent/enrichment_providers/website_content.py`

Scrapes vendor website content for LLM capability matching.

#### SAMContactProvider

**Module:** `src/vendor_ai_agent/enrichment_providers/sam_contact.py`

Enriches US vendors with SAM.gov contact data.

#### CanadaNAICSEnricher

**Module:** `src/vendor_ai_agent/enrichment_providers/canada_naics_enricher.py`

Enriches Canadian vendors with NAICS codes.

#### SBAEnrichmentProvider

**Module:** `src/vendor_ai_agent/enrichment_providers/sba_enrichment.py`

Enriches with SBA certifications (8(a), WOSB, etc.).

#### StaticContactsProvider

**Module:** `src/vendor_ai_agent/enrichment_providers/static_contacts.py`

Fallback provider with static/placeholder contacts.

#### SerperClient

**Module:** `src/vendor_ai_agent/enrichment_providers/serper_client.py`

Google Search API client for vendor discovery.

---

## Matching & Scoring

### CapabilityMatcher

LLM-backed capability scoring of vendors.

**Module:** `src/vendor_ai_agent/modules/capability_matching.py`

#### Constructor

```python
CapabilityMatcher(
    llm_provider: Optional[LLMProvider] = None,
    config: Optional[CapabilityMatchingConfig] = None
)
```

#### Methods

##### `score(profile: TenderProfile, vendors: Iterable[VendorRecord]) -> List[VendorMatchResult]`

Score vendors based on contract history, website content, LLM assessment.

**Parameters:**
- `profile` - Tender profile with requirements
- `vendors` - Vendor records to score

**Returns:** List of `VendorMatchResult` sorted by score (0-100)

**Example:**
```python
from vendor_ai_agent.modules.capability_matching import CapabilityMatcher

matcher = CapabilityMatcher(llm_provider=llm)
matches = matcher.score(profile, vendors)

for match in matches[:10]:
    print(f"{match.vendor.company_name}: {match.capability_match_score}/100")
    print(f"  Rationale: {match.rationale}")
```

**Scoring Components:**
- **Base score** (25-45): Website presence, enrichment quality
- **Contract history** (0-35): High-value/frequent supplier flags, past winner
- **NAICS alignment** (0-20): Industry code similarity
- **LLM assessment** (0-100): Deep capability matching from website content

**LLM Assessment:**
- Requires `website_content` in vendor metadata
- Parallel processing (configurable parallelism)
- Fallback to rule-based if LLM fails

---

### GeographicScorer

Distance-based geographic scoring.

**Module:** `src/vendor_ai_agent/modules/geographic_scoring.py`

#### Methods

##### `score_vendor_by_location(vendor_coords: Tuple[float, float], project_coords: Tuple[float, float]) -> Dict[str, float]`

Calculate distance and score.

**Parameters:**
- `vendor_coords` - Vendor (latitude, longitude)
- `project_coords` - Project (latitude, longitude)

**Returns:** Dict with `distance_miles` and `distance_score`

**Distance Tiers:**
- ≤50 miles: 1.0
- ≤200 miles: 0.9
- ≤500 miles: 0.7
- ≤1000 miles: 0.5
- ≤2000 miles: 0.3
- >2000 miles: 0.05

---

## Sources

Discovery sources for finding vendor candidates.

### BaseVendorSource

**Module:** `src/vendor_ai_agent/sources/base.py`

Base class for all vendor sources.

#### Methods

##### `search(profile: TenderProfile) -> List[VendorRecord]`

Search for vendors matching tender profile.

##### `is_compatible(profile: TenderProfile) -> bool`

Check if source is compatible with tender country/type.

---

### SAM Entity Source

**Module:** `src/vendor_ai_agent/sources/sam_entity.py`

US federal vendor database (SAM.gov).

#### Constructor

```python
SamEntitySource(
    api_key: Optional[str] = None,
    use_cache: bool = True,
    cache_ttl_days: int = 7,
    rate_limit_per_day: int = 1000,
    initial_fetch_limit: int = 2000
)
```

#### Methods

##### `search(profile: TenderProfile) -> List[VendorRecord]`

Search SAM.gov by NAICS codes and optional state filter.

**Example:**
```python
from vendor_ai_agent.sources.sam_entity import SamEntitySource

sam = SamEntitySource(api_key=os.getenv("SAM_API_KEY"))
vendors = sam.search(profile)

print(f"Found {len(vendors)} SAM vendors")
```

**Features:**
- Extract API for bulk downloads
- State filtering
- Set-aside filtering
- Automatic caching

---

### Apollo Search Source

**Module:** `src/vendor_ai_agent/sources/apollo_search.py`

Apollo.io commercial vendor database.

#### Constructor

```python
ApolloSearchSource(
    api_key: Optional[str] = None,
    per_page: int = 100,
    max_pages: int = 1
)
```

#### Methods

##### `search(profile: TenderProfile) -> List[VendorRecord]`

Search Apollo.io by industry, location, headcount.

**Example:**
```python
from vendor_ai_agent.sources.apollo_search import ApolloSearchSource

apollo = ApolloSearchSource(api_key=os.getenv("APOLLO_API_KEY"))
vendors = apollo.search(profile)
```

**Search Filters:**
- Industry/sector
- Location (country/state)
- Employee headcount
- Relevance-based ranking

---

### Serper Search Source

**Module:** `src/vendor_ai_agent/sources/serper_search.py`

Google Search via Serper API for vendor discovery.

#### Constructor

```python
SerperSearchSource(
    api_key: Optional[str] = None,
    results_per_query: int = 10
)
```

---

### Canada Contracts Source

**Module:** `src/vendor_ai_agent/sources/canada_contracts.py`

Canadian government contract history database.

#### Methods

##### `search(profile: TenderProfile) -> List[VendorRecord]`

Search Canadian vendor database by GSIN codes, province.

---

### SBA DSBS Source

**Module:** `src/vendor_ai_agent/sources/sba_dsbs.py`

SBA Dynamic Small Business Search for certified small businesses.

---

### Static Directory Source

**Module:** `src/vendor_ai_agent/sources/static_directory.py`

Static vendor directory (CSV import).

---

## Ingestion

### SAM CSV Ingestion

**Module:** `src/vendor_ai_agent/ingestion/sam_csv.py`

Imports SAM.gov bulk CSV exports to database.

#### Functions

##### `ingest_sam_csv(csv_path: Path, db_session: Session) -> int`

Ingest SAM.gov CSV extract.

**Returns:** Number of vendors imported

**Example:**
```python
from vendor_ai_agent.ingestion.sam_csv import ingest_sam_csv
from vendor_ai_agent.database import get_session

session = get_session()
count = ingest_sam_csv(Path("sam_export.csv"), session)
print(f"Imported {count} vendors")
```

---

### Canada CKAN Ingestion

**Module:** `src/vendor_ai_agent/ingestion/canada.py`

Imports Canadian contract data from CKAN API.

#### Functions

##### `ingest_canada_ckan(resource_id: str, db_session: Session) -> int`

Ingest Canada Open Data contracts.

---

### Canada CSV Ingestion

**Module:** `src/vendor_ai_agent/ingestion/canada_csv.py`

Imports Canadian contract CSV files.

---

### Ingestion Router

**Module:** `src/vendor_ai_agent/ingestion/router.py`

Auto-detects file format and routes to appropriate ingestion handler.

#### Functions

##### `ingest_file(file_path: Path, db_session: Session) -> dict`

Auto-detect format and ingest.

**Returns:** Dict with ingestion statistics

---

## Database

### Connection

**Module:** `src/vendor_ai_agent/database/connection.py`

#### Functions

##### `get_session() -> Session`

Get SQLAlchemy database session.

##### `init_database()`

Initialize database schema.

---

### Models

**Module:** `src/vendor_ai_agent/database/models.py`

SQLAlchemy ORM models for persistence.

#### Vendor

Main vendor entity table.

**Fields:**
- `id` - Primary key
- `company_name` - Company legal name
- `website` - Company website URL
- `uei` - Unique Entity ID (SAM.gov)
- `duns` - DUNS number
- `cage_code` - CAGE code
- `city`, `state`, `country` - Location
- `total_contract_value` - Historical contract value
- `contract_count` - Number of past contracts
- `is_past_winner` - Past contract winner flag
- `source` - Discovery source

#### VendorContact

Contact information table.

**Fields:**
- `vendor_id` - Foreign key to Vendor
- `email` - Contact email
- `phone` - Contact phone
- `contact_name` - Contact person name
- `source` - Contact source

#### VendorNAICS

NAICS code associations.

**Fields:**
- `vendor_id` - Foreign key to Vendor
- `naics_code` - NAICS code (2-6 digits)

---

### Cache Manager

**Module:** `src/vendor_ai_agent/database/cache.py`

API response caching.

#### Methods

##### `get(key: dict) -> Optional[dict]`

Get cached API response.

##### `set(key: dict, value: dict, ttl_days: int)`

Cache API response with TTL.

---

## Data Models

### VendorRecord

**Module:** `src/vendor_ai_agent/models.py`

In-memory vendor record (dataclass).

**Fields:**
```python
@dataclass
class VendorRecord:
    company_name: str
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    
    uei: Optional[str] = None
    duns: Optional[str] = None
    cage_code: Optional[str] = None
    
    source: str = "unknown"
    is_past_winner: bool = False
    total_contract_value: Optional[float] = None
    contract_count: Optional[int] = None
    
    enrichment_flags: List[str] = field(default_factory=list)
    business_types: List[str] = field(default_factory=list)
    filtering_metadata: Dict[str, Any] = field(default_factory=dict)
```

---

### TenderProfile

**Module:** `src/vendor_ai_agent/models.py`

Complete tender requirements and context.

**Fields:**
```python
@dataclass
class TenderProfile:
    doc_extracted: Optional[ExtractedRequirements] = None
    dynamic_context: Optional[TenderContext] = None
    api_metadata: Optional[APIMetadata] = None
    country: Optional[str] = None
```

---

### VendorMatchResult

**Module:** `src/vendor_ai_agent/models.py`

Scored vendor match result.

**Fields:**
```python
@dataclass
class VendorMatchResult:
    vendor: VendorRecord
    capability_match_score: float  # 0-100
    rationale: str
    references: List[str]
```

---

### TenderContext

**Module:** `src/vendor_ai_agent/modules/tender_profiler.py`

Dynamic search context from LLM analysis.

**Fields:**
```python
@dataclass
class TenderContext:
    sector: str
    industry_description: str
    technical_keywords: List[str]
    search_terms: List[str]
    gsin_codes: List[str]
    unspsc_codes: List[str]
    province: Optional[str]
    country: Optional[str]
```

---

### ExtractedContacts

**Module:** `src/vendor_ai_agent/modules/contact_extractor.py`

Contact extraction results.

**Fields:**
```python
@dataclass
class ExtractedContacts:
    emails: List[str]
    phones: List[str]
    contact_names: List[str]
    extraction_method: str  # "regex", "llm", "none"
    confidence: float  # 0.0-1.0
    email_sources: List[str]
    phone_sources: List[str]
```

---

## Configuration

### Config

**Module:** `src/vendor_ai_agent/config.py`

Pipeline configuration dataclass.

**Key Settings:**
```python
@dataclass
class Config:
    # LLM
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    
    # Discovery
    enable_sam_search: bool = True
    enable_apollo_search: bool = True
    enable_serper_search: bool = False
    
    # Filtering
    enable_eligibility_filtering: bool = True
    enable_geographic_filtering: bool = True
    enable_deduplication: bool = True
    
    # Enrichment
    enable_contact_scraping: bool = True
    enable_website_content: bool = True
    enrichment_batch_size: int = 50
    enrichment_max_workers: int = 10
    
    # Capability Matching
    enable_llm_assessment: bool = True
    llm_parallelism: int = 5
    fallback_to_rule_based: bool = True
```

---

## Error Handling

All modules use Python's built-in logging. Configure logging level:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vendor_ai_agent")
```

Common exceptions:
- `ValueError` - Invalid configuration
- `FileNotFoundError` - Missing input file
- `requests.RequestException` - API request failures
- `json.JSONDecodeError` - LLM response parsing errors

---

## Performance Tips

1. **Batch Processing**: Use enrichment batches (50-100 vendors)
2. **Caching**: Enable API caching for SAM.gov (7-day TTL)
3. **Parallelism**: Increase `max_workers` for I/O-bound operations
4. **LLM Parallelism**: Set `llm_parallelism=5-10` for capability matching
5. **Database**: Use database for large vendor datasets (>10K records)

---

## Related Documentation

- [Architecture Guide](ARCHITECTURE.md) - System design and data flow
- [Pipeline Workflow](PIPELINE_WORKFLOW.md) - Stage-by-stage processing
- [Configuration Reference](CONFIGURATION.md) - Complete config options
- [Database Schema](DATABASE_SCHEMA.md) - Database structure
