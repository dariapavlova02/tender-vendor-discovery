# Pipeline Workflow

**Complete end-to-end pipeline documentation for vendor discovery and matching**

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Unified Tender Profile Schema](#3-unified-tender-profile-schema)
4. [Stage-by-Stage Workflow](#4-stage-by-stage-workflow)
5. [Performance Characteristics](#5-performance-characteristics)
6. [Configuration Impact](#6-configuration-impact)
7. [Troubleshooting by Stage](#7-troubleshooting-by-stage)
8. [Data Flow Examples](#8-data-flow-examples)

---

## 1. Overview

The Tender Vendor AI Agent implements an 8-stage pipeline that transforms government tender documents into ranked, enriched vendor recommendations. The pipeline supports both manual mode (local files only) and API-assisted mode (SAM.gov/CanadaBuys integration).

**Pipeline Modes:**
- **Manual Mode**: Process local PDF/DOCX/XLSX files without external API calls
- **API-Assisted Mode**: Fetch tender metadata and attachments from SAM.gov or CanadaBuys, then process

**Key Capabilities:**
- Multi-format document parsing (PDF, DOCX, XLSX, TXT)
- OCR fallback for scanned documents
- Multi-source vendor discovery (SAM, CanadaBuys, Apollo, Serper, static directory)
- Intelligent filtering with geographic/eligibility checks
- Batch enrichment with quality gates
- LLM-based capability assessment
- Multiple output formats (CSV, XLSX, JSON)

---

## 2. Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TENDER VENDOR AI PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────┐
│  STAGE 0 (Optional)    │
│  API Ingestion         │────────────────────────┐
│  - SAM.gov             │                        │
│  - CanadaBuys          │                        ▼
└────────────────────────┘             ┌──────────────────┐
                                       │  TenderProfile   │
         ┌─────────────────┐           │  (Metadata)      │
         │  User Files     │           └──────────────────┘
         │  PDF/DOCX/XLSX  │                     │
         └─────────────────┘                     │
                 │                               │
                 ▼                               ▼
        ┌────────────────────────┐    ┌─────────────────┐
        │  STAGE 1               │◄───┤ Downloaded      │
        │  Document Parsing      │    │ Attachments     │
        │  - PDF extraction      │    └─────────────────┘
        │  - Table extraction    │
        │  - Section detection   │
        └────────────────────────┘
                 │
                 │ TenderSection[]
                 ▼
        ┌────────────────────────┐
        │  STAGE 2               │
        │  Requirement Extract   │
        │  - LLM profiling       │
        │  - Field extraction    │
        │  - Context generation  │
        └────────────────────────┘
                 │
                 │ TenderProfile (enriched)
                 ▼
        ┌────────────────────────┐
        │  STAGE 3               │
        │  Vendor Discovery      │
        │  - SAM registry        │
        │  - CanadaBuys registry │
        │  - Apollo search       │
        │  - Serper web search   │
        │  - Static directory    │
        └────────────────────────┘
                 │
                 │ VendorRecord[] (raw)
                 ▼
        ┌────────────────────────┐
        │  STAGE 4               │
        │  Filtering             │
        │  - Duplicate removal   │
        │  - Geographic filter   │
        │  - Eligibility checks  │
        │  - Preliminary ranking │
        └────────────────────────┘
                 │
                 │ VendorRecord[] (filtered)
                 ▼
        ┌────────────────────────┐
        │  STAGE 5               │
        │  Contact Enrichment    │
        │  - Website scraping    │
        │  - Apollo enrichment   │
        │  - Batch processing    │
        │  - Quality gates       │
        └────────────────────────┘
                 │
                 │ VendorRecord[] (enriched)
                 ▼
        ┌────────────────────────┐
        │  STAGE 6               │
        │  Capability Matching   │
        │  - LLM assessment      │
        │  - Rule-based scoring  │
        │  - NAICS matching      │
        └────────────────────────┘
                 │
                 │ VendorMatchResult[]
                 ▼
        ┌────────────────────────┐
        │  STAGE 7               │
        │  Output Generation     │
        │  - CSV export          │
        │  - XLSX export         │
        │  - JSON export         │
        └────────────────────────┘
                 │
                 ▼
         ┌──────────────┐
         │  Final       │
         │  Vendor List │
         └──────────────┘
```

**Pipeline Characteristics:**
- **Linear flow** with optional branches (API ingestion, fallback strategies)
- **Batch processing** for large vendor sets (Stage 5)
- **Caching support** to resume from Stage 3 (vendor discovery)
- **Quality gates** to stop enrichment when success rate drops
- **Parallel execution** for enrichment (ThreadPoolExecutor) and LLM calls (asyncio)

---

## 3. Unified Tender Profile Schema

Every module reads/writes the same JSON-compatible structure (`TenderProfile`):

```json
{
  "tender_id": "string",
  "country": "USA | CAN",
  "source_system": "SAM | CANADABUYS | MANUAL",
  "api_metadata": {
    "external_id": "string",
    "title": "string",
    "description": "string",
    "codes": { "naics": [], "unspsc": [], "gsin": [], "classification": null },
    "buyer": { "name": "", "department": "", "organization_path": [], "address": { ... } },
    "place_of_performance": { ... },
    "dates": { "posted": "", "response_deadline": "", "tender_start": null, "tender_end": null },
    "set_aside": { "code": null, "description": null },
    "estimated_value": { "amount": null, "currency": null },
    "trade_agreements": [],
    "awards": [ { "award_id": "", "supplier_name": "", ... } ],
    "attachments": [ { "url": "", "filename": "", "source": "API | USER_UPLOAD" } ]
  },
  "doc_extracted": {
    "sections": {
      "scope_of_work": "...",
      "technical_requirements": "...",
      "mandatory_requirements": "...",
      "vendor_qualifications": "...",
      "evaluation_criteria": "...",
      "location_details": "...",
      "timeline_details": "..."
    },
    "structured": {
      "project_type": "...",
      "sector": "construction | ammo_supply | it | ...",
      "location": { "city": "", "state_province": "", "country": "" },
      "volumes": [ { "item": "", "quantity": 0, "unit": "m2" } ],
      "technical_keywords": [],
      "required_experience": { "min_years": null, "required_project_types": [] },
      "required_licenses": [],
      "required_certifications": [],
      "vendor_constraints": { "allowed_jurisdictions": [], "business_size": null, "special_status": [] },
      "packaging_logistics": { "special_requirements": [], "lead_times_days": { "samples": null, "regular_orders": null } },
      "solicitation_number": "",
      "reference_number": ""
    }
  },
  "vendor_capability_profile": {
    "summary": "string",
    "key_requirements": [ { "id": "REQ-001", "type": "experience", "description": "", "must_have": true } ],
    "target_industry_codes": { "naics": [], "gsin": [], "unspsc": [] }
  }
}
```

`DocExtracted.structures` also stores the solicitation/reference numbers derived directly from uploaded documents, so we can call APIs even when the user only provides partial files.

---

## 4. Stage-by-Stage Workflow

### STAGE 0: API Ingestion (Optional)

**Purpose:** Fetch tender metadata and attachments from government procurement systems

**Trigger:** Pipeline run with `ingestion_request` parameter (contains country/source/tender_id)

**Components:**
- `TenderIngestionRouter` - Routes requests to appropriate source
- `SamClient` + `UsSamIngestor` - SAM.gov integration (US)
- `CanadaCkanClient` + `CanadaBuysIngestor` - CanadaBuys integration (Canada)
- `DocumentFetcher` - Downloads attachments to local storage

**Input:**
```python
TenderIngestionRequest(
    country="USA",           # or "Canada"
    source="SAM",           # or "CANADABUYS"
    tender_id="OPP-1984",   # Solicitation number
    reference_number="20070" # Optional reference
)
```

**Process:**
1. Router selects appropriate client based on country/source
2. Client queries API (e.g., `api.sam.gov/opportunities/v2/search?solnum=OPP-1984`)
3. Response mapped to `TenderProfile.api_metadata`:
   - External ID, title, description
   - NAICS/GSIN/UNSPSC codes
   - Buyer information
   - Place of performance
   - Dates (posted, response deadline)
   - Set-aside codes
   - Estimated value
   - Awards history
4. Attachments collected from API response
5. DocumentFetcher downloads attachments to `data/attachments/{tender_id}/`

**Output:**
- `TenderProfile` with populated `api_metadata`
- List of attachment URLs
- Downloaded files in local storage

**Timing:**
- SAM API call: 1-3 seconds
- Attachment downloads: 5-30 seconds (depends on file count/size)

**Common Issues:**
- Network connectivity (proxy/firewall)
- Invalid tender ID format
- Attachments require authentication
- Rate limiting on API

**Related Config:**
```python
[api]
sam_api_key = "your_key"
sam_base_url = "https://api.sam.gov"
canada_ckan_base = "https://open.canada.ca"
attachment_download_dir = "data/attachments"
```

---

### STAGE 1: Document Parsing

**Purpose:** Convert tender documents into structured sections with semantic classification

**Components:**
- `DocumentParser` - Main orchestrator
- `DocumentClassifier` - Classifies document types
- `SectionExtractor` - Detects section boundaries
- `FieldExtractor` - Extracts structured fields

**Supported Formats:**
- PDF (with OCR fallback for scanned pages)
- DOCX (Word documents with tables)
- XLSX/XLS (Excel spreadsheets)
- TXT/MD/CSV (plain text)

**Input:**
- List of `Path` objects (files or directories)
- Files from user upload + downloaded attachments

**Process:**

1. **File Collection:** Recursively scan directories, collect all supported files
2. **Format Detection:** Check file extension, select appropriate parser
3. **Document Classification:** Analyze filename/content to determine doc_type:
   - `CORE_SCOPE` - Main RFB/RFP document
   - `TECH_SPEC` - Technical specifications
   - `ADDENDUM` - Addenda/amendments
   - `LEGAL` - Legal terms/conditions
   - `OTHER` - Miscellaneous

4. **PDF Parsing:**
   - Extract text using `pdfplumber`
   - Detect base font size (most common font = body text)
   - Extract tables separately (converted to markdown)
   - Identify section headers using:
     - Font size (larger than base)
     - ALL CAPS format
     - Keyword matching (SCOPE, REQUIREMENT, DELIVERABLE, etc.)
     - Numbered sections (SECTION 1.2.3)
   - Filter out headers/footers (page numbers, tender IDs)
   - Apply OCR (pytesseract) if text extraction fails (<50 chars)

5. **DOCX Parsing:**
   - Iterate document elements (paragraphs + tables)
   - Detect headers using:
     - Word styles (Heading 1-6)
     - Bold text with short length
     - Keyword matching
   - Extract tables separately (preserve structure)

6. **Excel Parsing:**
   - Each sheet becomes a separate section
   - All cells converted to markdown table format

7. **Section Creation:** Each chunk becomes a `TenderSection`:
   ```python
   TenderSection(
       title="Scope of Work",
       content="...",  # markdown text
       source_path=Path("..."),
       section_type="text" | "table",
       metadata={
           "file_type": "pdf",
           "doc_type": "CORE_SCOPE",
           "page": 5
       }
   )
   ```

**Output:**
- `List[TenderSection]` - Typically 10-50 sections per tender
- Each section classified and tagged with metadata

**Timing:**
- Single PDF (20 pages): 2-5 seconds
- PDF with OCR (10 pages): 15-30 seconds
- DOCX (30 pages): 1-3 seconds
- Excel workbook (5 sheets): 1-2 seconds
- **Total for typical tender (5 files):** 10-30 seconds

**Common Issues:**
- **Scanned PDFs:** No text layer → requires OCR (slow, less accurate)
- **Complex tables:** Multi-page tables split across sections
- **Headers not detected:** Font size detection fails, use keyword fallback
- **Large files:** Memory issues with 100+ page documents

**Debug Commands:**
```bash
python -m tests.test_document_parser
python -m tests.debug_extraction_detail
```

**Related Config:**
```python
[parsing]
enable_ocr = true
ocr_min_confidence = 50
max_section_length = 5000  # chars
```

---

### STAGE 2: Requirement Extraction

**Purpose:** Transform parsed sections into structured tender requirements and vendor capability profile

**Components:**
- `RequirementExtractor` - Main orchestrator
- `TenderProfiler` - LLM-based context generation
- `SectionExtractor` - Maps sections to semantic categories
- `FieldExtractor` - Extracts structured fields using regex/LLM

**Input:**
- `List[TenderSection]` from Stage 1
- Optional `TenderProfile` base (from Stage 0)

**Process:**

1. **Section Classification:** Map raw sections to semantic categories:
   - `scope_of_work`
   - `technical_requirements`
   - `mandatory_requirements`
   - `vendor_qualifications`
   - `evaluation_criteria`
   - `location_details`
   - `timeline_details`

2. **Dynamic Context Generation (LLM):**
   - Smart section filtering (prioritize "scope", "specifications"; skip "instructions to bidders")
   - Assemble up to 8000 chars of high-value content
   - LLM prompt extracts:
     - Sector (e.g., "Ammunition Supply", "Construction")
     - Industry description (1-2 sentences)
     - Technical keywords (15-20 terms for vendor search)
     - Search terms (5-10 optimized queries like "ammunition suppliers ontario")
     - GSIN codes (Canadian goods/services codes)
     - UNSPSC codes (universal product/service codes)
     - Province/country detection

3. **Structured Field Extraction:**
   - **Project type:** Construction, goods supply, services, etc.
   - **Location:** City, state/province, country (regex + LLM)
   - **Volumes:** Item quantities and units (from tables)
   - **Experience requirements:** Minimum years, project types
   - **Licenses:** Required business licenses
   - **Certifications:** ISO, safety, industry-specific
   - **NAICS codes:** Industry classification codes
   - **Solicitation/reference numbers:** For API lookups

4. **Vendor Capability Profile Generation (LLM):**
   - Summary: 2-sentence recap of buyer needs
   - Key requirements (REQ-001, REQ-002, etc.):
     - Type: capability | experience | license | certification | logistics | compliance
     - Description: Plain sentence
     - Must-have: boolean flag
   - Target industry codes (NAICS, GSIN, UNSPSC)
   
   **Fallback (if LLM fails):**
   - Summary: First 600 chars of scope_of_work
   - Requirements derived from structured fields (experience, licenses, certs)
   - NAICS codes from field extraction

**Output:**
- `TenderProfile` with populated:
  - `doc_extracted.sections` (DocSections)
  - `doc_extracted.structured` (StructuredDocData)
  - `vendor_capability_profile` (VendorCapabilityProfile)
  - `dynamic_context` (DynamicTenderContext)

**Timing:**
- Section classification: <1 second
- LLM context generation: 3-8 seconds (depends on model)
- Field extraction (with LLM): 5-10 seconds
- Capability profile (with LLM): 3-6 seconds
- **Total:** 12-25 seconds (with LLM), 2-5 seconds (without LLM)

**Example Output:**
```json
{
  "vendor_capability_profile": {
    "summary": "Ontario government seeks 5.56mm frangible ammunition (5M rounds) complying with SAAMI specs. Requires Canadian manufacturing capability and explosives licensing.",
    "key_requirements": [
      {
        "requirement_id": "REQ-001",
        "type": "license",
        "description": "Valid explosives manufacturing/storage license (Canada)",
        "must_have": true
      },
      {
        "requirement_id": "REQ-002",
        "type": "capability",
        "description": "5.56mm NATO frangible bullet manufacturing (SAAMI compliant)",
        "must_have": true
      }
    ],
    "target_industry_codes": {
      "naics": ["332993", "332994"],
      "gsin": ["M120", "M1203"],
      "unspsc": ["41115000"]
    }
  }
}
```

**Common Issues:**
- **LLM failures:** Network timeout, quota exceeded → falls back to rule-based
- **Missing sections:** Poor PDF quality → sections empty → sparse profile
- **Over-extraction:** LLM hallucinates requirements not in document
- **NAICS mismatch:** LLM picks wrong industry code

**Debug Commands:**
```bash
python -m tests.test_extraction
python -m tests.test_llm_field_extraction
python -m tests.debug_qa_extraction
```

**Related Config:**
```python
[llm]
provider = "openai"
model = "gpt-4o-mini"
max_tokens = 4000
temperature = 0.2

[extraction]
enable_llm = true
fallback_to_rules = true
```

---

### STAGE 3: Vendor Discovery

**Purpose:** Find candidate vendors from multiple sources using tender requirements

**Components:**
- `VendorDiscovery` - Multi-source orchestrator
- `SamClient` - US SAM.gov registry
- `CanadaCkanClient` - Canadian contracts database
- `ApolloSearchSource` - Apollo.io B2B database
- `SerperSearchSource` - Web search via Serper API
- `StaticDirectorySource` - Local vendor database

**Input:**
- `TenderProfile` with `vendor_capability_profile` and `dynamic_context`

**Process:**

1. **Source Selection:** Check each source's compatibility:
   - US tenders → SAM registry + Apollo + Serper
   - Canada tenders → CanadaBuys registry + Apollo + Serper
   - Manual tenders → All sources

2. **Search Query Construction:**
   - NAICS codes from `target_industry_codes`
   - Geographic constraints from `place_of_performance`
   - Keywords from `dynamic_context.technical_keywords`
   - Search terms from `dynamic_context.search_terms`

3. **Parallel Source Queries:**

   **SAM Registry Search:**
   ```python
   # Search by NAICS code
   GET /entity/v3/entities?naicsCodes=332993&samRegistered=Y
   # Filter by state if specified
   # Extract: name, UEI, CAGE, address, website, NAICS codes
   ```

   **CanadaBuys Contract History:**
   ```python
   # Search pspc_payments dataset
   POST /api/3/action/datastore_search
   {
       "resource_id": "pspc_payments",
       "q": "ammunition",  # from search_terms
       "filters": {"province": "ON"}  # if specified
   }
   # Group by vendor, aggregate contract values
   # Flag high-value (>$100M) and frequent (>50 contracts) suppliers
   ```

   **Apollo Search:**
   ```python
   POST /v1/mixed_companies/search
   {
       "q_keywords": "ammunition manufacturing",
       "locations": ["Ontario, Canada"],
       "page_size": 100
   }
   # Extract: name, domain, employees, revenue, phone
   ```

   **Serper Web Search:**
   ```python
   POST /search
   {
       "q": "ammunition suppliers ontario frangible bullets",
       "num": 50
   }
   # Parse organic results for company names, domains
   ```

   **Static Directory:**
   ```python
   # Load vendors.json
   # Filter by keywords/location if specified
   ```

4. **Vendor Record Creation:**
   ```python
   VendorRecord(
       company_name="ABC Ammunition Inc.",
       website="https://abc-ammo.ca",
       email="sales@abc-ammo.ca",
       phone="+1-416-555-1234",
       location="Toronto, ON, Canada",
       industry="Ammunition Manufacturing",
       source="canada_contracts",
       is_past_winner=True,
       total_contract_value=15_000_000,
       contract_count=8,
       enrichment_flags=["frequent_supplier"],
       filtering_metadata={
           "naics_codes": ["332993"],
           "source_rank": 1
       }
   )
   ```

5. **Aggregation:** Combine vendors from all sources (duplicates handled in Stage 4)

**Output:**
- `List[VendorRecord]` - Typically 200-2000 vendors
- Each vendor tagged with source, preliminary metadata

**Timing:**
- SAM registry search: 2-5 seconds (500-1000 vendors)
- CanadaBuys search: 3-8 seconds (100-500 vendors)
- Apollo search: 3-6 seconds (50-100 vendors)
- Serper search: 2-4 seconds (30-50 vendors)
- **Total:** 10-25 seconds (parallel), yields 500-2000 vendors

**Fallback Strategies:**

1. **Apollo Booster:** If initial discovery yields <100 vendors, trigger extra Apollo search with relaxed filters
2. **Serper Expansion:** If <50 vendors, use additional search terms from `dynamic_context`
3. **National Expansion:** If <30 local vendors, expand search nationwide (disabled by default)

**Common Issues:**
- **API quota exceeded:** Apollo/Serper rate limits hit
- **No NAICS codes:** Falls back to keyword search
- **Geolocation failures:** Address parsing fails, no location filtering
- **Incompatible sources:** US tender querying CanadaBuys (router should prevent)

**Debug Commands:**
```bash
python -m tests.test_vendor_discovery
python -m tests.test_sam_integration_e2e
python -m tests.test_canada_source
```

**Related Config:**
```python
[discovery]
max_vendors_per_source = 1000
enable_apollo = true
enable_serper = true
serper_result_count = 50
apollo_page_size = 100
enable_national_expansion = false
national_expansion_threshold = 30
```

---

### STAGE 4: Filtering

**Purpose:** Apply multi-stage filtering to reduce vendor set to high-quality candidates

**Components:**
- `VendorFilter` - Main orchestrator
- `DuplicateDetector` - Merge duplicate vendors
- `GeographicMatcher` - Location-based filtering/ranking
- `EligibilityChecker` - Business rule validation

**Input:**
- `TenderProfile`
- `List[VendorRecord]` (500-2000 vendors from Stage 3)

**Process:**

**Stage 4.1: Duplicate Removal**
- Compare vendors using:
  - Exact company name match (normalized, case-insensitive)
  - Website domain match
  - Email domain match
  - Phone number match (normalized)
  - Address similarity (Levenshtein distance)
- Merge strategy:
  - Keep record with most complete data
  - Combine enrichment flags
  - Preserve highest contract value
  - Aggregate contract counts
- Result: Typically removes 10-30% of vendors

**Stage 4.2: Geographic Filtering**

Three modes:

1. **Geographic Sorting (default):**
   - Rank all vendors by distance to place of performance
   - Calculate geo_score (0-100):
     - Same city: 100
     - Same state/province: 85
     - Same region: 70
     - Same country: 50
     - International: 25
   - All vendors kept, sorted by proximity

2. **Local-First Filtering:**
   - Keep all local vendors (same state/province)
   - Add top national vendors if <threshold local vendors
   - Threshold: `national_expansion_threshold` (default: 30)

3. **Strict Local-Only:**
   - Remove all vendors outside state/province
   - Used for set-aside contracts (e.g., "Small business, Ontario only")

**Geocoding:**
- Parse place of performance: "Washington, DC" → lat/lon
- Parse vendor location: "1234 Main St, Seattle, WA" → lat/lon
- Calculate haversine distance
- Cache results to avoid repeated API calls

**Stage 4.3: Eligibility Filtering**

Business rule checks:

1. **Set-Aside Compliance:**
   - If tender specifies "Small Business", check vendor size
   - If "HUBZone", check vendor location
   - If "Women-Owned", check ownership flags
   - Remove non-compliant vendors

2. **Size Heuristics (optional):**
   - Large contracts (>$10M) → prefer vendors with >$100M total contracts
   - Small contracts (<$100K) → prefer vendors with <50 employees
   - Filter out obvious mismatches (1-person consultancy bidding $50M construction)

3. **Contract Value Ratio:**
   - Minimum ratio: `minimum_contract_value_ratio` (default: 0.1)
   - If tender value = $5M, vendor must have past contracts ≥ $500K
   - Prevents under-qualified vendors

4. **NAICS Code Match (soft filter):**
   - Boost vendors with matching NAICS codes
   - Don't remove non-matches (may be legitimate adjacent industries)

**Stage 4.4: Preliminary Ranking**

Calculate `preliminary_score` (0-100):
- Base: 30 points
- Past winner: +10
- High-value supplier (>$100M): +20
- Frequent supplier (>50 contracts): +15
- NAICS exact match: +20
- NAICS 4-digit prefix match: +10
- Has website: +5
- Has contact info: +5

Sort vendors by `preliminary_score + geo_score` descending.

**Stage 4.5: Candidate Limiting**

If `max_candidates` set (e.g., 500), keep only top N vendors.

**Output:**
- `List[VendorRecord]` - Typically 200-500 filtered vendors
- `FilteringMetrics`:
  ```python
  FilteringMetrics(
      total_input=1523,
      duplicates_removed=187,
      local_vendors=42,
      national_vendors=1294,
      geo_filtered=0,  # (if geographic_sorting=true)
      eligibility_filtered=89,
      filter_reasons={
          "set_aside_mismatch": 34,
          "size_heuristic_fail": 28,
          "contract_value_too_low": 27
      },
      final_count=447
  )
  ```

**Timing:**
- Duplicate removal: 1-3 seconds (1000 vendors)
- Geographic filtering: 2-5 seconds (geocoding cached)
- Eligibility checks: 1-2 seconds
- Ranking: <1 second
- **Total:** 5-12 seconds

**Common Issues:**
- **Over-filtering:** Too strict eligibility rules → <10 vendors remain
- **Geocoding failures:** Address not found → vendor excluded
- **NAICS mismatch:** Tender NAICS too specific, excludes valid adjacent industries
- **Set-aside confusion:** Tender flags wrong set-aside code

**Debug Commands:**
```bash
python -m tests.test_filtering_integration
python -m tests.test_geographic_matcher
python -m tests.test_eligibility_checker
python -m tests.test_multi_stage_filtering
```

**Related Config:**
```python
[filtering]
enable_duplicate_removal = true
enable_geographic = true
enable_geographic_sorting = true
enable_local_first = false
national_expansion_threshold = 30
enable_eligibility_checks = true
enable_set_aside_filtering = true
enable_size_heuristics = true
minimum_contract_value_ratio = 0.1
max_candidates = 500
local_preference_boost = 100
regional_preference_boost = 70
log_filtering_decisions = true
```

---

### STAGE 5: Contact Enrichment

**Purpose:** Scrape vendor websites and enrich contact information in batches with quality gates

**Components:**
- `VendorEnricher` - Batch orchestrator
- `WebsiteContentProvider` - Web scraping
- `ApolloEnrichmentProvider` - Apollo.io data enrichment
- `StaticContactsProvider` - Fallback to local database

**Input:**
- `TenderProfile`
- `List[VendorRecord]` (200-500 filtered vendors)
- Scoring function (for quality gates)

**Process:**

**Batch Processing Loop:**

1. **Initialize:**
   - Target: `target_relevant_vendors` (default: 200)
   - Batch size: `batch_size` (default: 50)
   - Min success rate: `min_batch_success_rate` (default: 0.15 = 15%)
   - Relevance threshold: `relevance_score_threshold` (default: 70.0)

2. **Process Batch N:**
   - Take next 50 vendors from filtered list
   - Enrich in parallel (ThreadPoolExecutor, 10 workers):
     
     **Website Scraping:**
     ```python
     # Fetch vendor.website using requests (timeout: 10s)
     response = requests.get(vendor.website, timeout=10)
     html = response.text
     
     # Extract visible text (BeautifulSoup)
     soup = BeautifulSoup(html, "html.parser")
     for script in soup(["script", "style", "header", "footer", "nav"]):
         script.decompose()
     text = soup.get_text(separator="\n", strip=True)
     
     # Store in metadata
     vendor.filtering_metadata["website_content"] = text[:5000]  # First 5000 chars
     vendor.filtering_metadata["content_source"] = vendor.website
     ```
     
     **Apollo Enrichment (optional):**
     ```python
     # Search Apollo for company
     POST /v1/companies/search
     { "domain": vendor.website }
     
     # Enrich with:
     # - Employee count
     # - Revenue estimate
     # - Contact phone/email
     # - LinkedIn URL
     ```
   
   - Timing: 50 vendors @ 10 workers = ~15-30 seconds per batch

3. **Score Batch:**
   - Pass enriched vendors to `scoring_fn` (Stage 6 capability matcher)
   - Get `VendorMatchResult[]` with `capability_match_score`
   - Count vendors with score ≥ 70: `relevant_count`
   - Calculate success rate: `relevant_count / batch_size`

4. **Quality Gate Check:**
   - If success_rate ≥ 15%: Continue to next batch
   - If success_rate < 15%:
     - **First batch only:** Trigger sampling fallback
       - Sample 20 vendors at position 150, 300
       - If sample success rate >15%, skip ahead to that position
       - Else: Stop enrichment
     - **Later batches:** Stop enrichment (diminishing returns)

5. **Stop Conditions:**
   - Reached `target_relevant_vendors` (200)
   - Exhausted all vendors
   - Quality gate failed

**Sampling Fallback (First Batch Only):**

If first 50 vendors have low success rate, the list may be poorly ranked. Sample deeper:

```python
sample_positions = [150, 300]  # Check vendors at positions 150-170, 300-320

for pos in sample_positions:
    sample = vendors[pos:pos+20]
    sample_enriched = enrich(sample)
    sample_scored = score(sample_enriched)
    sample_rate = count_relevant(sample_scored) / 20
    
    if sample_rate > 0.15:
        # Found better vendors deeper in the list
        current_position = pos
        break
```

**Output:**
- `List[VendorRecord]` (enriched subset, typically 100-300 vendors)
  - Each has `filtering_metadata["website_content"]` (if successful)
  - Each has `filtering_metadata["scrape_error"]` (if failed)
- `List[VendorMatchResult]` (relevant vendors, score ≥70)
- Enrichment stats:
  ```python
  {
      "total_enriched": 250,
      "batches_processed": 5,
      "relevant_found": 203,
      "success_rate": 0.81
  }
  ```

**Timing:**
- Batch 1 (50 vendors): 15-30 seconds (scraping) + 5-10 seconds (scoring) = 20-40 seconds
- Batch 2-5: Same per batch
- **Total:** 100-200 seconds for 250 vendors (with quality gates)
- **Without quality gates:** 300-600 seconds for 500 vendors (all enriched)

**Website Scraping Success Rates:**
- Valid website + responsive: 70-85% success
- No website URL: 0% success (skip)
- Website down/timeout: 10-15% of attempts
- Robot detection/CAPTCHA: 5-10% of attempts

**Common Issues:**
- **Low first-batch success:** Poor vendor ranking, triggers sampling
- **Website timeouts:** Slow sites exceed 10s timeout
- **Rate limiting:** Too many requests to same domain
- **CAPTCHA/bot detection:** Cloudflare blocks scraping
- **No website content:** Contact page only, no capability description

**Debug Commands:**
```bash
python -m tests.test_enrichment_utils
python -m tests.test_website_content_provider
python -m tests.test_stage5_integration
```

**Related Config:**
```python
[enrichment]
max_workers = 10
batch_size = 50
min_batch_success_rate = 0.15
max_enrichment_batches = 10
target_relevant_vendors = 200
enable_batch_quality_gates = true
enable_sampling_fallback = true
sample_positions = [150, 300]
website_timeout_seconds = 10
enable_apollo_enrichment = true
```

---

### STAGE 6: Capability Matching

**Purpose:** Assess vendor capability match using LLM or rule-based scoring

**Components:**
- `CapabilityMatcher` - Main orchestrator
- LLM provider (OpenAI/Anthropic) - For semantic assessment
- NAICS similarity calculator
- Rule-based scoring fallback

**Input:**
- `TenderProfile` with `vendor_capability_profile`
- `List[VendorRecord]` (enriched with website content)

**Process:**

**Assessment Strategy:**

1. **Pre-filter:** Skip vendors without website content
   - Mark as `match_status: "needs_data"`
   - Add to output but don't score

2. **Parallel LLM Assessment (if enabled):**
   - Use asyncio with semaphore (default: 5 concurrent)
   - For each vendor with website content:
   
   **Build Tender Requirements Summary:**
   - Adaptive content strategy based on information density:
     - High density (>1500 chars structured sections): Use structured sections only
     - Medium density (500-1500 chars): Add dynamic_context keywords
     - Low density (<500 chars): Heavy use of dynamic_context (keywords, search terms, codes)
   - Include:
     - Project type, sector
     - Scope of work (trimmed to 600 chars)
     - Technical requirements (trimmed to 600 chars)
     - Mandatory requirements (trimmed to 600 chars)
     - Technical keywords (10-25 based on density)
     - GSIN/UNSPSC codes
   - Character limit: 1500-2500 chars total
   
   **LLM Prompt:**
   ```
   You are evaluating whether a vendor is qualified for a government contract.
   
   TENDER REQUIREMENTS:
   Sector: Ammunition Supply
   Scope: Ontario government seeks 5.56mm frangible ammunition (5M rounds)...
   Technical: Must comply with SAAMI specifications, NATO standards...
   Keywords: frangible bullets, 5.56mm NATO, SAAMI compliant, explosives license...
   GSIN Codes: M120, M1203
   
   VENDOR INFORMATION:
   Company: ABC Ammunition Inc.
   Website: https://abc-ammo.ca
   Location: Toronto, ON, Canada
   
   VENDOR CAPABILITIES (from website):
   ABC Ammunition is a leading Canadian manufacturer of small arms ammunition...
   [website_content first 2500 chars]
   
   CONTRACT HISTORY:
   - Past winner: Yes
   - Total contract value: $15,000,000
   - Contract count: 8
   - Enrichment flags: frequent_supplier
   
   TASK:
   1. Assess capability match (0-100 score)
   2. Provide one-sentence rationale with specific evidence
   3. Do not hallucinate - use only provided information
   
   Return valid JSON:
   {
     "score": 85,
     "rationale": "Specializes in 5.56mm NATO ammunition with SAAMI compliance and Canadian explosives licensing"
   }
   ```
   
   **Response Parsing:**
   - Extract score (0-100)
   - Extract rationale
   - Clamp score to valid range
   - Add NAICS bonus: +20 for exact match, +14 for 4-digit prefix, +8 for 2-digit sector

3. **Rule-Based Scoring (fallback or if LLM disabled):**
   ```python
   base_score = 45  # If has website content
   
   # Enrichment flag bonuses
   if "high_value_supplier" in flags: score += 20
   if "frequent_supplier" in flags: score += 15
   if is_past_winner: score += 10
   if source == "canada_contracts": score += 5
   
   # NAICS match bonus
   if NAICS exact match: score += 20
   elif NAICS 4-digit match: score += 14
   elif NAICS 2-digit match: score += 8
   
   # Contact penalty
   if no email and no phone: score -= 10
   
   # Cap at 100
   score = min(score, 100.0)
   ```

4. **Create Match Results:**
   ```python
   VendorMatchResult(
       vendor=vendor,
       capability_match_score=85.0,
       rationale="ABC Ammunition specializes in 5.56mm NATO ammunition with SAAMI compliance and Canadian explosives licensing - located in Toronto, ON",
       references=["https://abc-ammo.ca"]
   )
   ```

5. **Sort by Score:** Descending order of `capability_match_score`

**Output:**
- `List[VendorMatchResult]` - Sorted by score (highest first)
- Typical distribution:
  - Score 80-100: 10-20 vendors (excellent match)
  - Score 70-79: 30-50 vendors (good match)
  - Score 60-69: 50-80 vendors (fair match)
  - Score <60: Remaining vendors (poor match)

**Timing:**
- LLM assessment (parallel, 5 concurrent): 
  - 200 vendors @ 3 seconds each = 120 seconds (40 batches of 5)
- Rule-based scoring: 200 vendors @ <1ms each = <1 second
- **Total (LLM):** 120-180 seconds
- **Total (rule-based):** 1-2 seconds

**LLM Model Comparison:**
| Model | Speed | Cost | Quality |
|-------|-------|------|---------|
| gpt-4o-mini | 2-4s | $0.001/vendor | Good |
| gpt-4o | 4-8s | $0.01/vendor | Excellent |
| claude-3-haiku | 2-3s | $0.001/vendor | Good |
| claude-3-sonnet | 5-10s | $0.015/vendor | Excellent |

**Common Issues:**
- **LLM timeouts:** Network issues, quota exceeded → falls back to rule-based
- **Score inflation:** LLM too generous (scores all 80+) → adjust prompt
- **Score deflation:** LLM too strict (scores all 40-60) → adjust prompt
- **Hallucination:** LLM invents capabilities not in website content
- **Context overflow:** Tender summary + website content >4000 tokens

**Debug Commands:**
```bash
python -m tests.test_capability_matching_llm
python -m tests.test_llm_context
```

**Related Config:**
```python
[capability_matching]
enable_llm_assessment = true
fallback_to_rule_based = true
llm_model = "gpt-4o-mini"
llm_parallelism = 5
llm_timeout_seconds = 30
relevance_score_threshold = 70.0
```

---

### STAGE 7: Output Generation

**Purpose:** Export vendor match results to multiple file formats

**Components:**
- `OutputGenerator` - Format conversion
- pandas DataFrame - Data manipulation

**Input:**
- `List[VendorMatchResult]` (sorted by capability_match_score)

**Process:**

1. **Convert to DataFrame:**
   ```python
   columns = [
       "company_name",
       "website",
       "email",
       "phone",
       "location",
       "industry",
       "source",
       "capability_match_score",
       "rationale",
       "references",
       "enrichment_flags"
   ]
   ```

2. **Export Formats:**

   **CSV (default):**
   ```python
   df.to_csv("output/tender_vendors.csv", index=False)
   ```
   - Plain text, easy to open in Excel
   - Formatting lost
   - Good for large datasets (100k+ rows)

   **Excel (XLSX):**
   ```python
   df.to_excel("output/tender_vendors.xlsx", index=False)
   ```
   - Preserves formatting
   - Click-through hyperlinks
   - Limited to 1M rows
   - Slower for large datasets

   **JSON:**
   ```python
   json.dump(
       [match.dict() for match in matches],
       open("output/tender_vendors.json", "w"),
       indent=2
   )
   ```
   - Full structure preservation
   - Includes nested objects (primary_contact, filtering_metadata)
   - Easy to programmatically process
   - Larger file size

3. **File Naming:**
   - Pattern: `{tender_id}_stage{N}.{ext}`
   - Example: `OPP-1984_stage7.xlsx`
   - Includes timestamp if multiple runs

**Output:**
- `Path` to generated file(s)
- Files written to `output/` directory

**Timing:**
- CSV export: 200 vendors = <1 second
- XLSX export: 200 vendors = 1-3 seconds
- JSON export: 200 vendors = <1 second
- **Total:** 1-5 seconds

**Example CSV Output:**
```csv
company_name,website,email,phone,location,industry,source,capability_match_score,rationale,references,enrichment_flags
ABC Ammunition Inc.,https://abc-ammo.ca,sales@abc-ammo.ca,+1-416-555-1234,"Toronto, ON, Canada",Ammunition Manufacturing,canada_contracts,85.0,"Specializes in 5.56mm NATO ammunition with SAAMI compliance and Canadian explosives licensing - located in Toronto, ON",https://abc-ammo.ca,"['frequent_supplier']"
XYZ Defense Co.,https://xyz-defense.com,info@xyz-defense.com,+1-613-555-5678,"Ottawa, ON, Canada",Defense Manufacturing,apollo,82.5,"Produces frangible ammunition for law enforcement and military with ISO 9001 certification",https://xyz-defense.com,"['high_value_supplier']"
...
```

**Common Issues:**
- **Encoding errors:** Non-ASCII characters in company names
- **Excel cell limits:** Rationale >32k chars exceeds Excel cell limit
- **File permissions:** Output directory not writable
- **Large files:** 10k+ vendors = 50MB+ Excel file

**Debug Commands:**
```bash
python -m tests.test_output_generator
ls -lh output/
```

**Related Config:**
```python
[output]
directory = "output"
default_format = "xlsx"  # or "csv", "json"
include_timestamp = true
include_metadata = true
```

---

---

## 5. Performance Characteristics

### End-to-End Timing

**Typical Small Tender (10-30 page RFB, 200-500 vendors):**
| Stage | Time | Notes |
|-------|------|-------|
| 0. API Ingestion | 5-15s | If enabled |
| 1. Document Parsing | 10-30s | Depends on page count, OCR usage |
| 2. Requirement Extraction | 12-25s | With LLM; 2-5s without |
| 3. Vendor Discovery | 10-25s | Parallel API calls |
| 4. Filtering | 5-12s | Geocoding cached |
| 5. Contact Enrichment | 100-200s | Batch processing, quality gates |
| 6. Capability Matching | 120-180s | LLM; 1-2s rule-based |
| 7. Output Generation | 1-5s | XLSX slower than CSV |
| **Total (LLM)** | **263-492s** | **4.4-8.2 minutes** |
| **Total (no LLM)** | **133-257s** | **2.2-4.3 minutes** |

**Large Tender (100+ pages, 1000+ vendors):**
| Stage | Time | Notes |
|-------|------|-------|
| 1. Document Parsing | 60-120s | Large PDFs, multiple files |
| 2. Requirement Extraction | 20-40s | More content to analyze |
| 3. Vendor Discovery | 15-40s | More API calls |
| 4. Filtering | 10-20s | More vendors to process |
| 5. Contact Enrichment | 300-600s | More batches, quality gates stop earlier |
| 6. Capability Matching | 300-600s | More vendors (but capped) |
| 7. Output Generation | 3-10s | Large XLSX files |
| **Total** | **708-1430s** | **11.8-23.8 minutes** |

### Resource Usage

**Memory:**
- Base: 200-500 MB
- Per 1000 vendors: +50-100 MB
- Per 100-page PDF: +50-150 MB (pdfplumber)
- LLM context: +10-50 MB per request
- **Peak:** 500 MB - 2 GB (large tender with LLM)

**API Calls:**
- SAM registry: 1-5 calls per tender
- CanadaBuys: 2-10 calls per tender
- Apollo: 1-3 calls per tender (50-100 vendors each)
- Serper: 1-5 calls per tender
- Website scraping: 50-500 requests per tender (batch controlled)
- LLM: 200-500 requests per tender (parallel, rate limited)

**Disk:**
- Attachments: 5-50 MB per tender
- Cache: 1-10 MB per tender (vendor records)
- Output: 1-10 MB per tender (CSV/XLSX/JSON)

### Bottlenecks

1. **Stage 5 (Enrichment):** 40-60% of total time
   - Website scraping waits for responses (10s timeout)
   - Mitigation: Batch processing, quality gates stop early

2. **Stage 6 (Matching):** 30-50% of total time (with LLM)
   - LLM API calls have network latency
   - Mitigation: Parallel processing (5 concurrent), caching

3. **Stage 1 (Parsing):** 10-20% of total time for large PDFs
   - OCR is slow (15-30s per page)
   - Mitigation: Only apply OCR to pages with no text

4. **Stage 2 (Extraction):** 5-10% of total time
   - LLM context generation
   - Mitigation: Smart section filtering, context size limits

### Optimization Strategies

**For Speed:**
```python
[llm]
enable = false  # Use rule-based only (5x faster)

[enrichment]
enable_batch_quality_gates = true  # Stop early if low quality
target_relevant_vendors = 100     # Reduce target (default: 200)

[capability_matching]
enable_llm_assessment = false     # Rule-based scoring (100x faster)

[filtering]
max_candidates = 300              # Reduce vendor set (default: 500)
```

**For Quality:**
```python
[llm]
enable = true
model = "gpt-4o"  # Better quality than gpt-4o-mini

[enrichment]
target_relevant_vendors = 300
min_batch_success_rate = 0.20  # Higher threshold (default: 0.15)

[capability_matching]
enable_llm_assessment = true
llm_parallelism = 10  # More concurrent (default: 5)
```

**For Cost:**
```python
[llm]
model = "gpt-4o-mini"  # 10x cheaper than gpt-4o

[enrichment]
enable_batch_quality_gates = true  # Stop early, reduce scraping

[discovery]
enable_apollo = false  # Disable paid API
enable_serper = false  # Disable paid API
```

---

## 6. Configuration Impact

Configuration settings dramatically affect pipeline behavior. See table below for impact analysis:

### Discovery Configuration

| Setting | Values | Impact |
|---------|--------|--------|
| `enable_apollo` | true/false | +50-100 vendors from B2B database |
| `enable_serper` | true/false | +30-50 vendors from web search |
| `enable_national_expansion` | true/false | +500-1000 vendors if local count low |
| `national_expansion_threshold` | 10-100 | Trigger for national search |
| `max_vendors_per_source` | 100-2000 | Limits each source's contribution |
| `batch_size` | 20-100 | Controls caching granularity |

**Example:**
```python
# Conservative (fast, fewer vendors)
[discovery]
enable_apollo = false
enable_serper = false
max_vendors_per_source = 500
Result: 300-600 vendors, 10-15 seconds

# Aggressive (slow, more vendors)
[discovery]
enable_apollo = true
enable_serper = true
enable_national_expansion = true
max_vendors_per_source = 2000
Result: 1500-3000 vendors, 20-40 seconds
```

### Filtering Configuration

| Setting | Values | Impact |
|---------|--------|--------|
| `enable_geographic_sorting` | true/false | Keep all vendors (ranked) vs strict filtering |
| `enable_local_first` | true/false | Prefer local vendors, expand if needed |
| `national_expansion_threshold` | 10-100 | Minimum local vendors before national |
| `enable_set_aside_filtering` | true/false | Enforce set-aside compliance |
| `max_candidates` | 100-1000 | Hard cap on vendor count |

**Example:**
```python
# Local-focused (small vendor set)
[filtering]
enable_local_first = true
national_expansion_threshold = 50
max_candidates = 200
Result: 50-200 vendors, mostly local

# National-focused (large vendor set)
[filtering]
enable_geographic_sorting = true
enable_local_first = false
max_candidates = 1000
Result: 500-1000 vendors, nationwide
```

### Enrichment Configuration

| Setting | Values | Impact |
|---------|--------|--------|
| `enable_batch_quality_gates` | true/false | Stop early vs enrich all |
| `target_relevant_vendors` | 50-500 | Target for quality gate |
| `min_batch_success_rate` | 0.10-0.30 | Threshold to continue |
| `batch_size` | 20-100 | Vendors per batch |
| `max_workers` | 5-20 | Parallel scraping threads |

**Example:**
```python
# Fast (quality gates, early stop)
[enrichment]
enable_batch_quality_gates = true
target_relevant_vendors = 100
min_batch_success_rate = 0.15
batch_size = 50
Result: 100-200 vendors enriched, 60-120 seconds

# Thorough (enrich all)
[enrichment]
enable_batch_quality_gates = false
batch_size = 100
max_workers = 20
Result: All 500 vendors enriched, 300-500 seconds
```

### Capability Matching Configuration

| Setting | Values | Impact |
|---------|--------|--------|
| `enable_llm_assessment` | true/false | LLM vs rule-based |
| `llm_model` | gpt-4o-mini, gpt-4o | Quality vs speed |
| `llm_parallelism` | 1-20 | Concurrent LLM calls |
| `fallback_to_rule_based` | true/false | Graceful degradation |
| `relevance_score_threshold` | 50-90 | Defines "relevant" vendor |

**Example:**
```python
# Fast (rule-based only)
[capability_matching]
enable_llm_assessment = false
fallback_to_rule_based = true
Result: 200 vendors scored in 1-2 seconds

# Accurate (LLM, high parallelism)
[capability_matching]
enable_llm_assessment = true
llm_model = "gpt-4o"
llm_parallelism = 10
Result: 200 vendors scored in 60-120 seconds, high quality
```

---

## 7. Troubleshooting by Stage

### STAGE 0: API Ingestion

**Issue: "Connection timeout to api.sam.gov"**
- **Cause:** Network/firewall blocking API calls
- **Fix:** Check proxy settings, add SAM domain to allowlist
- **Workaround:** Use manual mode, skip API ingestion

**Issue: "Invalid API key"**
- **Cause:** SAM API key missing/expired
- **Fix:** Regenerate API key at sam.gov, update config
- **Workaround:** Use CanadaBuys or manual mode

**Issue: "Tender not found: OPP-1984"**
- **Cause:** Wrong tender ID, closed tender, wrong system
- **Fix:** Verify tender ID format, check tender status
- **Debug:** `python -m tests.test_sam_integration_e2e`

### STAGE 1: Document Parsing

**Issue: "No text extracted from PDF"**
- **Cause:** Scanned PDF without text layer
- **Fix:** Enable OCR: `parsing.enable_ocr = true`
- **Debug:** `python -m tests.debug_extraction_detail`

**Issue: "Sections not detected, entire document as one chunk"**
- **Cause:** No clear section headers, unusual formatting
- **Fix:** Manually review PDF, adjust `HEADER_KEYWORDS` in `DocumentParser`
- **Debug:** `python -m tests.test_sections`

**Issue: "Tables garbled in output"**
- **Cause:** Complex table spanning pages, merged cells
- **Fix:** pdfplumber table extraction has limits; manually extract if critical
- **Debug:** `python -m tests.test_table_extraction`

**Issue: "Memory error parsing 500-page PDF"**
- **Cause:** pdfplumber loads entire PDF into memory
- **Fix:** Split PDF into chunks, process separately
- **Workaround:** Use summary documents only

### STAGE 2: Requirement Extraction

**Issue: "LLM returned empty context"**
- **Cause:** No relevant sections found, filtering too aggressive
- **Fix:** Check section classification, adjust `HIGH_PRIORITY_KEYWORDS`
- **Debug:** `python -m tests.test_llm_context`

**Issue: "Wrong NAICS codes extracted"**
- **Cause:** LLM misinterpreted industry, or no NAICS in document
- **Fix:** Add explicit NAICS codes in document, or override in config
- **Debug:** Check `tender_profile.doc_extracted.structured.naics_codes`

**Issue: "Location extraction failed"**
- **Cause:** Ambiguous location ("Washington" - DC or state?), no location in doc
- **Fix:** Use place_of_performance from API metadata as fallback
- **Debug:** `python -m tests.test_location_extraction_enhanced`

**Issue: "Vendor capability profile is generic"**
- **Cause:** Poor document quality, no technical sections
- **Fix:** Supplement with manual keywords, use better source documents
- **Workaround:** Edit `vendor_capability_profile` manually before Stage 3

### STAGE 3: Vendor Discovery

**Issue: "Only 10 vendors found"**
- **Cause:** Overly specific search terms, wrong NAICS codes, API failures
- **Fix:** 
  - Enable Apollo/Serper: `discovery.enable_apollo = true`
  - Enable national expansion: `discovery.enable_national_expansion = true`
  - Check API logs for errors
- **Debug:** `python -m tests.test_vendor_discovery`

**Issue: "Apollo API quota exceeded"**
- **Cause:** Too many API calls, daily limit reached
- **Fix:** Reduce `apollo_page_size`, disable Apollo temporarily
- **Workaround:** Use SAM/CanadaBuys only

**Issue: "Serper returns irrelevant results"**
- **Cause:** Poor search terms, too generic keywords
- **Fix:** Review `dynamic_context.search_terms`, make more specific
- **Debug:** Check `tender_profile.dynamic_context.search_terms`

### STAGE 4: Filtering

**Issue: "All vendors filtered out"**
- **Cause:** Too strict eligibility rules, wrong place_of_performance
- **Fix:**
  - Disable set-aside filtering: `filtering.enable_set_aside_filtering = false`
  - Check place_of_performance parsing
  - Review `filtering.filter_reasons` in logs
- **Debug:** `python -m tests.test_filtering_integration`

**Issue: "No local vendors found"**
- **Cause:** Geocoding failed, vendors have no location
- **Fix:**
  - Check geocoding logs
  - Use `enable_geographic_sorting = true` (keep all vendors)
- **Debug:** `python -m tests.test_geographic_matcher`

**Issue: "Duplicate vendors not merged"**
- **Cause:** Slight name differences, different domains
- **Fix:** Adjust duplicate detection thresholds in `DuplicateDetector`
- **Debug:** `python -m tests.test_duplicate_detector`

### STAGE 5: Contact Enrichment

**Issue: "First batch quality gate failed"**
- **Cause:** Poorly ranked vendors, no websites, websites down
- **Fix:**
  - Sampling fallback should trigger automatically
  - Check `sample_positions` in logs
  - Verify vendor ranking in Stage 4
- **Debug:** `python -m tests.test_stage5_integration`

**Issue: "Website scraping timeouts"**
- **Cause:** Slow websites, network issues, CAPTCHA
- **Fix:**
  - Increase `website_timeout_seconds` (default: 10)
  - Check website manually in browser
- **Workaround:** Disable website scraping, use Apollo enrichment only

**Issue: "All batches have low success rate"**
- **Cause:** Vendor websites lack capability descriptions (contact pages only)
- **Fix:**
  - Lower `min_batch_success_rate` threshold
  - Increase `max_enrichment_batches` to process more vendors
- **Expected:** 15-30% success rate is normal

### STAGE 6: Capability Matching

**Issue: "All vendors scored 40-50 (low scores)"**
- **Cause:** Rule-based scoring (no LLM), poor website content
- **Fix:** Enable LLM: `capability_matching.enable_llm_assessment = true`
- **Debug:** `python -m tests.test_capability_matching_llm`

**Issue: "LLM scoring failed for all vendors"**
- **Cause:** API timeout, quota exceeded, model unavailable
- **Fix:**
  - Check LLM provider logs
  - Enable fallback: `capability_matching.fallback_to_rule_based = true`
- **Workaround:** Use rule-based scoring only

**Issue: "LLM scores are inflated (all 80-90)"**
- **Cause:** LLM prompt too lenient, or truly excellent vendor set
- **Fix:** Adjust prompt to be more critical, or accept high scores
- **Debug:** Review sample LLM responses in logs

**Issue: "LLM hallucinating capabilities"**
- **Cause:** Prompt doesn't emphasize "do not hallucinate"
- **Fix:** Update prompt to stress "use only provided information"
- **Mitigation:** Manual review of top 20 vendors

### STAGE 7: Output Generation

**Issue: "Excel file corrupted"**
- **Cause:** Rationale >32k chars, special characters
- **Fix:** Truncate rationale, sanitize special characters
- **Workaround:** Use CSV output instead

**Issue: "File not found: output/tender_vendors.xlsx"**
- **Cause:** Output directory doesn't exist, permission denied
- **Fix:** Create output directory, check permissions
- **Command:** `mkdir -p output && chmod 755 output`

---

## 8. Data Flow Examples

### Example 1: Small US Tender (Manual Mode)

**Input:**
- Files: `RFB_Uniforms.pdf` (25 pages)
- No API ingestion

**Stage 1 Output (TenderSection[]):**
```json
[
  {
    "title": "Section 1: Scope of Work",
    "content": "The Department of Homeland Security seeks tactical uniforms...",
    "section_type": "text",
    "metadata": {"file_type": "pdf", "doc_type": "CORE_SCOPE"}
  },
  {
    "title": "Section 2: Technical Specifications",
    "content": "All uniforms must meet...",
    "section_type": "text"
  },
  {
    "title": "Attachment A - Pricing List (Table)",
    "content": "| Item | Qty | Unit Price |\n|------|-----|------------|\n| Shirt | 1000 | $45.00 |",
    "section_type": "table"
  }
]
```

**Stage 2 Output (TenderProfile):**
```json
{
  "doc_extracted": {
    "sections": {
      "scope_of_work": "The Department of Homeland Security seeks tactical uniforms...",
      "technical_requirements": "All uniforms must meet..."
    },
    "structured": {
      "project_type": "Goods Supply",
      "sector": "Uniform Supply",
      "naics_codes": ["315220"],
      "location": {
        "city": "Washington",
        "state_province": "DC",
        "country": "United States"
      }
    }
  },
  "vendor_capability_profile": {
    "summary": "DHS requires tactical uniforms meeting mil-spec standards with GSA contract experience.",
    "key_requirements": [
      {
        "requirement_id": "REQ-001",
        "type": "capability",
        "description": "Manufacturing tactical/law enforcement uniforms to mil-spec standards",
        "must_have": true
      }
    ],
    "target_industry_codes": {
      "naics": ["315220", "315990"]
    }
  },
  "dynamic_context": {
    "sector": "Uniform Supply",
    "technical_keywords": ["tactical uniforms", "mil-spec", "law enforcement apparel", "DHS uniforms"],
    "search_terms": ["tactical uniform manufacturers", "law enforcement uniform suppliers"]
  }
}
```

**Stage 3 Output (VendorRecord[]):**
```json
[
  {
    "company_name": "Propper International",
    "website": "https://propper.com",
    "location": "St. Charles, MO",
    "source": "sam_registry",
    "is_past_winner": true,
    "total_contract_value": 45000000,
    "filtering_metadata": {
      "naics_codes": ["315220"],
      "source_rank": 1
    }
  },
  {
    "company_name": "Flying Cross Uniforms",
    "website": "https://flyingcross.com",
    "location": "Cincinnati, OH",
    "source": "apollo"
  }
  // ... 400 more vendors
]
```

**Stage 4 Output (filtered):**
```json
[
  {
    "company_name": "Propper International",
    "preliminary_score": 85.0,
    "geo_score": 50.0  // National vendor
  },
  {
    "company_name": "Tactical Gear Inc.",
    "preliminary_score": 70.0,
    "geo_score": 100.0  // Local vendor (DC metro)
  }
  // ... 250 more vendors (filtered from 400)
]
```

**Stage 5 Output (enriched):**
```json
[
  {
    "company_name": "Propper International",
    "filtering_metadata": {
      "website_content": "Propper International manufactures tactical uniforms for military, law enforcement, and public safety professionals. Specializes in flame-resistant clothing, duty uniforms, and tactical gear meeting mil-spec standards...",
      "content_source": "https://propper.com/about"
    }
  }
  // ... 150 vendors enriched (stopped at target)
]
```

**Stage 6 Output (VendorMatchResult[]):**
```json
[
  {
    "vendor": {
      "company_name": "Propper International"
    },
    "capability_match_score": 92.0,
    "rationale": "Leading tactical uniform manufacturer with extensive DHS contract history, mil-spec certified, produces flame-resistant and duty apparel",
    "references": ["https://propper.com/about"]
  },
  {
    "vendor": {
      "company_name": "Flying Cross Uniforms"
    },
    "capability_match_score": 88.0,
    "rationale": "Specializes in law enforcement uniforms with 75+ years experience, meets mil-spec standards, GSA contract holder"
  }
  // ... 150 more results
]
```

**Stage 7 Output (tender_vendors.xlsx):**
| company_name | capability_match_score | rationale | website | location |
|--------------|------------------------|-----------|---------|----------|
| Propper International | 92.0 | Leading tactical uniform manufacturer... | https://propper.com | St. Charles, MO |
| Flying Cross Uniforms | 88.0 | Specializes in law enforcement uniforms... | https://flyingcross.com | Cincinnati, OH |

---

### Example 2: Large Canada Tender (API-Assisted Mode)

**Input:**
```python
TenderIngestionRequest(
    country="Canada",
    source="CANADABUYS",
    tender_id="rfx_18106",
    reference_number="OPP-1984"
)
```

**Stage 0 Output:**
```json
{
  "api_metadata": {
    "external_id": "rfx_18106",
    "title": "Supply and Delivery of 5.56mm Frangible Ammunition",
    "codes": {
      "gsin": ["M120", "M1203"]
    },
    "buyer": {
      "name": "Ontario Provincial Police",
      "organization_path": ["Public Safety", "Ontario Government"]
    },
    "place_of_performance": {
      "state_province": "ON",
      "country": "Canada"
    },
    "attachments": [
      {
        "url": "https://buyandsell.gc.ca/..../RFB_OPP-1984.pdf",
        "filename": "RFB_OPP-1984.pdf"
      },
      {
        "url": "https://buyandsell.gc.ca/..../Addendum_1.pdf",
        "filename": "Addendum_1.pdf"
      }
    ]
  }
}
```

**Stage 1:** Parses downloaded attachments + user uploads → TenderSection[]

**Stage 2:**
```json
{
  "vendor_capability_profile": {
    "summary": "Ontario government seeks 5.56mm frangible ammunition (5M rounds) complying with SAAMI specs. Requires Canadian manufacturing capability and explosives licensing.",
    "key_requirements": [
      {
        "requirement_id": "REQ-001",
        "type": "license",
        "description": "Valid explosives manufacturing/storage license (Canada)",
        "must_have": true
      },
      {
        "requirement_id": "REQ-002",
        "type": "capability",
        "description": "5.56mm NATO frangible bullet manufacturing (SAAMI compliant)",
        "must_have": true
      },
      {
        "requirement_id": "REQ-003",
        "type": "logistics",
        "description": "Capacity for 5M round production within 12 months",
        "must_have": true
      }
    ]
  },
  "dynamic_context": {
    "sector": "Ammunition Supply",
    "technical_keywords": ["frangible bullets", "5.56mm NATO", "SAAMI specifications", "explosives license", "small arms ammunition"],
    "search_terms": ["ammunition manufacturers ontario", "frangible bullet suppliers canada", "5.56mm ammo production"],
    "gsin_codes": ["M120", "M1203"],
    "province": "ON",
    "country": "Canada"
  }
}
```

**Stage 3:** Discovers 800 vendors (CanadaBuys: 450, Apollo: 200, Serper: 150)

**Stage 4:** Filters to 380 vendors (local-first, eligibility checks)

**Stage 5:** Enriches in batches:
- Batch 1 (50): 12 relevant → continue
- Batch 2 (50): 18 relevant → continue
- Batch 3 (50): 21 relevant → continue
- ... continues until 200 relevant vendors found
- Total enriched: 350 vendors

**Stage 6:** LLM scores 200 relevant vendors (those with website content)

**Stage 7:** Exports top 200 to XLSX

---

## 9. Caching and Resumption

The pipeline supports caching at Stage 3 (vendor discovery) to enable resumption:

**Cache Location:** `output/cache/{tender_id}_vendors.json`

**Cache Structure:**
```json
{
  "tender_id": "OPP-1984",
  "batch_size": 50,
  "processed_batches": [1, 2, 3],
  "vendors": [
    { "company_name": "...", "website": "...", ... }
  ]
}
```

**Usage:**
```bash
# Initial run (processes batches 1-3, enriches 150 vendors)
python scripts/run_full_pipeline.py --tender-id OPP-1984 --batch 1

# Cache written to output/cache/OPP-1984_vendors.json
# Manual review of batch 1-3 results

# Resume from batch 4 (uses cached vendor list)
python scripts/run_full_pipeline.py --tender-id OPP-1984 --batch 4

# Process batch 4-6, enriches another 150 vendors
# Cache updated: "processed_batches": [1, 2, 3, 4, 5, 6]
```

**Benefits:**
- Avoid re-running expensive discovery stage
- Process vendors in chunks for manual review
- Resume after enrichment failures
- Iterate on enrichment/matching without re-discovery

**Limitations:**
- Cache invalidated if tender profile changes
- No cache for stages 1-2 (parsing/extraction)
- Manual cache clearing required if vendors need refresh
