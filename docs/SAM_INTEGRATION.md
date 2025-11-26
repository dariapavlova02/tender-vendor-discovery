# SAM.gov Integration Guide

## Overview

The Vendor AI Agent integrates with **SAM.gov (System for Award Management)**, the official U.S. government registry of contractors. This integration provides two primary capabilities:

1. **Tender Ingestion**: Fetch tender/opportunity metadata from the SAM Opportunities API
2. **Vendor Discovery**: Search for registered vendors using the SAM Entity Management API

SAM.gov is the authoritative source for:
- Federal procurement opportunities
- Registered government contractors
- Contractor certifications and business classifications
- Contract award history
- Points of contact for registered entities

This guide covers setup, API usage, data models, configuration, troubleshooting, and best practices.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [API Endpoints](#api-endpoints)
3. [Database Schema](#database-schema)
4. [Setup Instructions](#setup-instructions)
5. [SAM Opportunities API (Tender Ingestion)](#sam-opportunities-api-tender-ingestion)
6. [SAM Entity Management API (Vendor Discovery)](#sam-entity-management-api-vendor-discovery)
7. [SAM Contact Enrichment](#sam-contact-enrichment)
8. [CSV Bulk Import](#csv-bulk-import)
9. [Data Mapping](#data-mapping)
10. [Configuration](#configuration)
11. [Rate Limits and Caching](#rate-limits-and-caching)
12. [Error Handling](#error-handling)
13. [Troubleshooting](#troubleshooting)
14. [Performance Optimization](#performance-optimization)
15. [Integration Examples](#integration-examples)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     SAM.gov Integration                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│  SAM Opportunities   │         │   SAM Entity Mgmt    │
│       API v2         │         │      API v3          │
│  (Tender Search)     │         │  (Vendor Search)     │
└──────────┬───────────┘         └──────────┬───────────┘
           │                                 │
           │ GET /opportunities/v2/search    │ GET /entity-information/v3/entities
           │                                 │
           v                                 v
┌──────────────────────┐         ┌──────────────────────┐
│   UsSamIngestor      │         │  SamEntitySource     │
│  (sam.py)            │         │  (sam_entity.py)     │
└──────────┬───────────┘         └──────────┬───────────┘
           │                                 │
           │ TenderProfile                   │ VendorRecord[]
           │ with APIMetadata                │
           v                                 v
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   vendors    │  │ vendor_naics │  │vendor_contacts│         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ vendor_gsin  │  │vendor_unspsc │  │  api_cache   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
           │                                 │
           v                                 v
┌──────────────────────┐         ┌──────────────────────┐
│    Pipeline Stage 0  │         │  Pipeline Stage 3    │
│   (API Ingestion)    │         │ (Vendor Discovery)   │
└──────────────────────┘         └──────────────────────┘
```

**Key Components:**

- **`UsSamIngestor`**: Fetches tender metadata from SAM Opportunities API
- **`SamEntitySource`**: Searches for vendors by NAICS code using Entity Management API
- **`SamContactProvider`**: Enriches vendor records with POC data from database
- **`SamCsvIngestor`**: Bulk imports vendor data from SAM CSV exports
- **Database Models**: Stores vendors, NAICS codes, contacts, and API cache

---

## API Endpoints

### SAM Opportunities API (v2)

**Purpose:** Search for federal procurement opportunities

**Base URL:** `https://api.sam.gov/opportunities/v2/search`

**Authentication:** API key passed as query parameter `api_key`

**Key Parameters:**
- `solnum`: Solicitation number (exact match)
- `postedFrom`: Start date (YYYY-MM-DD)
- `postedTo`: End date (YYYY-MM-DD)
- `limit`: Results per page (default: 10, max: 1000)
- `offset`: Pagination offset

**Response Format:** JSON with `opportunitiesData` array

### SAM Entity Management API (v3)

**Purpose:** Search for registered government contractors

**Base URL:** `https://api.sam.gov/entity-information/v3/entities`

**Authentication:** API key passed as query parameter `api_key`

**Key Parameters:**
- `naicsCode`: 6-digit NAICS code (required for bulk search)
- `includeSections`: Sections to include (e.g., `entityRegistration,coreData,assertions`)
- `format`: Response format (`json` or `csv`)

**Response:** Returns a download URL for bulk extract file (gzip-compressed JSON)

**Note:** The Entity API uses an asynchronous extract model:
1. Initial request returns a file generation URL
2. File may take 5-300 seconds to generate
3. Client must poll the download URL until file is ready
4. File contains all entities matching the NAICS code

---

## Database Schema

The SAM integration uses 6 database tables to store vendor data:

### 1. `vendors`

**Purpose:** Core vendor information from SAM.gov

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `source` | String(50) | Always "sam_entity" for SAM vendors |
| `external_id` | String(255) | UEI or CAGE code (unique per source) |
| `uei` | String(50) | Unique Entity Identifier (replaces DUNS) |
| `duns` | String(50) | DUNS number (deprecated, often NULL) |
| `cage_code` | String(20) | Commercial and Government Entity code |
| `legal_name` | String(500) | Official legal business name |
| `dba_name` | String(500) | "Doing Business As" name |
| `website` | String(500) | Company website URL |
| `country` | String(2) | ISO country code (e.g., "US") |
| `state` | String(50) | State/province code |
| `city` | String(200) | City name |
| `address` | Text | Street address |
| `postal_code` | String(20) | ZIP/postal code |
| `business_types` | JSON | Array of business type descriptions |
| `is_small_business` | Boolean | Small business designation |
| `is_woman_owned` | Boolean | Woman-owned small business (WOSB) |
| `is_veteran_owned` | Boolean | Veteran-owned small business (VOSB) |
| `is_minority_owned` | Boolean | Minority/disadvantaged owned |
| `is_8a` | Boolean | 8(a) program participant |
| `is_hubzone` | Boolean | HUBZone certified |
| `employee_count_range` | String(50) | Employee count range (for future use) |
| `total_contract_value` | Float | Total value of past contracts |
| `contract_count` | Integer | Number of past contracts |
| `first_contract_date` | Date | Date of first contract |
| `last_contract_date` | Date | Date of most recent contract |
| `contract_history_json` | JSON | Detailed contract history |
| `metadata_json` | JSON | Full SAM API response |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |
| `last_enriched_at` | DateTime | Last enrichment timestamp |

**Indexes:**
- `ix_vendors_source`: On `source`
- `ix_vendors_uei`: On `uei`
- `ix_vendors_duns`: On `duns`
- `ix_vendors_cage_code`: On `cage_code`
- `ix_vendors_legal_name`: On `legal_name`
- `ix_vendors_website`: On `website`
- `ix_vendor_location`: On `(country, state, city)`
- `ix_vendor_certifications`: On `(is_small_business, is_woman_owned, is_veteran_owned)`
- `uq_vendor_source_external_id`: Unique constraint on `(source, external_id)`

### 2. `vendor_naics`

**Purpose:** NAICS codes associated with each vendor

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `vendor_id` | Integer | Foreign key to `vendors.id` |
| `naics_code` | String(10) | 6-digit NAICS code |
| `naics_description` | String(500) | NAICS description |
| `is_primary` | Boolean | Primary NAICS code flag |
| `created_at` | DateTime | Record creation timestamp |

**Indexes:**
- `ix_vendor_naics_vendor_id`: On `vendor_id`
- `ix_vendor_naics_naics_code`: On `naics_code`
- `ix_vendor_naics_lookup`: On `(naics_code, vendor_id)`
- `uq_vendor_naics`: Unique constraint on `(vendor_id, naics_code)`

### 3. `vendor_gsin`

**Purpose:** GSIN codes (Canada) associated with each vendor

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `vendor_id` | Integer | Foreign key to `vendors.id` |
| `gsin_code` | String(10) | GSIN code |
| `gsin_description` | String(500) | GSIN description |
| `is_primary` | Boolean | Primary GSIN code flag |
| `created_at` | DateTime | Record creation timestamp |

### 4. `vendor_unspsc`

**Purpose:** UNSPSC codes associated with each vendor

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `vendor_id` | Integer | Foreign key to `vendors.id` |
| `unspsc_code` | String(10) | UNSPSC code |
| `unspsc_description` | String(500) | UNSPSC description |
| `is_primary` | Boolean | Primary UNSPSC code flag |
| `created_at` | DateTime | Record creation timestamp |

### 5. `vendor_contacts`

**Purpose:** Contact information for vendors (POCs from SAM, enriched contacts)

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `vendor_id` | Integer | Foreign key to `vendors.id` |
| `source` | String(50) | Source of contact (e.g., "sam_gov_poc", "apollo", "scraper") |
| `first_name` | String(200) | Contact first name |
| `last_name` | String(200) | Contact last name |
| `title` | String(200) | Job title |
| `email` | String(255) | Email address |
| `phone` | String(50) | Phone number |
| `is_verified` | Boolean | Verification status |
| `confidence_score` | Integer | Confidence score (0-100) |
| `metadata_json` | JSON | Additional metadata |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Indexes:**
- `ix_vendor_contacts_vendor_id`: On `vendor_id`
- `ix_vendor_contacts_email`: On `email`
- `ix_vendor_contact_email`: On `(vendor_id, email)`

### 6. `api_cache`

**Purpose:** Generic API response cache with TTL

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `source` | String(50) | API source (e.g., "sam_entity", "apollo") |
| `cache_key` | String(500) | Unique cache key (hashed params) |
| `response_data` | JSON | Cached API response |
| `created_at` | DateTime | Cache creation timestamp |
| `expires_at` | DateTime | Cache expiration timestamp |

**Indexes:**
- `ix_api_cache_source`: On `source`
- `ix_api_cache_created_at`: On `created_at`
- `ix_api_cache_expires_at`: On `expires_at`
- `uq_api_cache_source_key`: Unique constraint on `(source, cache_key)`

---

## Setup Instructions

### 1. Prerequisites

Ensure you have **PostgreSQL 12+** installed and running:

```bash
# macOS (with Homebrew)
brew install postgresql@14
brew services start postgresql@14

# Ubuntu/Debian
sudo apt-get install postgresql-14 postgresql-contrib-14
sudo systemctl start postgresql

# Or use Docker (recommended for development)
docker run --name vendor-ai-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=vendor_ai \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  -d postgres:14
```

### 2. Obtain SAM.gov API Key

1. Visit: https://open.gsa.gov/api/entity-api/
2. Click "Request an API Key"
3. Complete the registration form (free tier: 1,000 requests/day)
4. Check your email for the API key (usually instant)
5. Store the key securely - you'll need it for `.env` configuration

**API Key Validation:**
```bash
# Test your API key (replace YOUR_KEY with actual key)
curl "https://api.sam.gov/entity-information/v3/entities?api_key=YOUR_KEY&ueiSAM=L3DQ1QV22P24&includeSections=entityRegistration"
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vendor_ai

# SAM.gov API Configuration
SAM_API_KEY=your-sam-gov-api-key-here

# Optional: Database performance tuning
SQL_ECHO=false
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

**Security Note:** Never commit `.env` to version control. Add to `.gitignore` if not already present.

### 4. Run Database Setup

**Automated Setup (Recommended):**

```bash
poetry run python scripts/setup_database.py
```

This script will:
1. Create the `vendor_ai` database (if not exists)
2. Run Alembic migrations to create all tables
3. Create necessary indexes and constraints
4. Verify the database schema
5. Display connection status

**Expected Output:**
```
✓ Database 'vendor_ai' created successfully
✓ Running migrations...
INFO  [alembic.runtime.migration] Running upgrade -> 6b4ee64b05c3, initial schema
INFO  [alembic.runtime.migration] Running upgrade 6b4ee64b05c3 -> d8dfe206ccc1, add canada support
✓ Database setup complete
✓ Verified 6 tables created: vendors, vendor_naics, vendor_gsin, vendor_unspsc, vendor_contacts, api_cache
```

### 5. Manual Migration (Alternative)

If you prefer manual control or the setup script fails:

```bash
# Create database manually
createdb vendor_ai

# Or using psql
psql -U postgres -c "CREATE DATABASE vendor_ai;"

# Run migrations
poetry run alembic upgrade head

# Verify tables were created
psql -U postgres -d vendor_ai -c "\dt"
```

### 6. Verify Installation

Test database connectivity and SAM API access:

```bash
# Test database connection
poetry run python -c "
from src.vendor_ai_agent.database import get_session
with get_session() as session:
    print('✓ Database connection OK')
"

# Test SAM API (requires SAM_API_KEY in .env)
poetry run python -c "
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
sam = SamEntitySource()
if sam.api_key:
    print('✓ SAM API key configured')
else:
    print('✗ SAM API key not found')
"
```

### 7. Test End-to-End Integration

Run a simple vendor search to verify everything works:

```bash
poetry run python -c "
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata

sam = SamEntitySource()
profile = TenderProfile(
    country='US',
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=['541330'])  # IT Services
    )
)

vendors = sam.search(profile)
print(f'✓ Found {len(vendors)} vendors for NAICS 541330')
if vendors:
    print(f'  First vendor: {vendors[0].company_name}')
"
```

**Troubleshooting:** See [Troubleshooting](#troubleshooting) section if any step fails.

---

## SAM Opportunities API (Tender Ingestion)

### Purpose

The SAM Opportunities API (v2) allows the system to fetch tender metadata for federal procurement opportunities. This is used in **Pipeline Stage 0** (API Ingestion) when processing US tenders.

### Implementation: `UsSamIngestor`

**File:** `src/vendor_ai_agent/ingestion/sam.py`

**Class:** `UsSamIngestor`

### Basic Usage

```python
from src.vendor_ai_agent.ingestion.sam import UsSamIngestor, SamClient
from src.vendor_ai_agent.ingestion.models import SamIngestionRequest, DateRange
from src.vendor_ai_agent.config import SamApiConfig

# Initialize client and ingestor
config = SamApiConfig()  # Loads SAM_API_KEY from environment
client = SamClient(base_url="https://api.sam.gov/opportunities/v2/search")
ingestor = UsSamIngestor(client=client, config=config)

# Create ingestion request
request = SamIngestionRequest(
    solicitation_number="70RSAT20R00000003",
    date_range=DateRange(
        start="2024-01-01",
        end="2024-12-31"
    )
)

# Ingest tender metadata
result = ingestor.ingest(request)

print(f"Title: {result.api_metadata.title}")
print(f"NAICS: {result.api_metadata.codes.naics}")
print(f"Buyer: {result.api_metadata.buyer.name}")
print(f"Deadline: {result.api_metadata.dates.response_deadline}")
print(f"Attachments: {len(result.attachments)}")
```

### What Gets Extracted

The ingestor maps SAM Opportunities API responses to `APIMetadata`:

| SAM Field | TenderProfile Field | Description |
|-----------|---------------------|-------------|
| `solicitationNumber` | `external_id` | Unique solicitation identifier |
| `title` | `title` | Opportunity title |
| `description` | `description` | Full text description |
| `naicsCode` | `codes.naics` | NAICS codes (as array) |
| `unspsc` | `codes.unspsc` | UNSPSC codes |
| `classificationCode` | `codes.classification` | PSC/FSC code |
| `organizationName` | `buyer.name` | Contracting office |
| `department` | `buyer.department` | Parent department |
| `fullParentPathName` | `buyer.organization_path` | Full org hierarchy |
| `officeAddress` | `buyer.address` | Contracting office address |
| `placeOfPerformance` | `place_of_performance` | Work location |
| `postedDate` | `dates.posted` | Publication date |
| `responseDeadLine` | `dates.response_deadline` | Submission deadline |
| `awardDate` | `dates.tender_start` | Expected award date |
| `archiveDate` | `dates.tender_end` | Archive date |
| `typeOfSetAside` | `set_aside.code` | Set-aside code |
| `typeOfSetAsideDescription` | `set_aside.description` | Set-aside description |
| `baseAndAllOptionsValue` | `estimated_value.amount` | Total estimated value |
| `award` | `awards[]` | Award metadata (if awarded) |
| `resourceLinks` | `attachments[]` | Attachment URLs |

### Pipeline Integration

The SAM Opportunities API is automatically invoked in **Stage 0** when:

1. Tender country is "US"
2. `solicitation_number` is provided
3. `enable_auto_ingestion` is enabled in config

**Pipeline Code:**
```python
# In pipeline.py Stage 0
if profile.country == "US" and profile.external_id:
    sam_client = SamClient(base_url=config.sam_api.base_url)
    sam_ingestor = UsSamIngestor(client=sam_client, config=config.sam_api)
    
    request = SamIngestionRequest(
        solicitation_number=profile.external_id,
        date_range=DateRange(start="2020-01-01", end="2025-12-31")
    )
    
    result = sam_ingestor.ingest(request)
    profile.api_metadata = result.api_metadata
```

### Error Handling

**Common Errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: SAM API key is not configured` | `SAM_API_KEY` not in `.env` | Add API key to `.env` file |
| `ValueError: No SAM opportunities returned` | No matching solicitation found | Check solicitation number and date range |
| `HTTPError: 401 Unauthorized` | Invalid API key | Verify API key is correct |
| `HTTPError: 429 Too Many Requests` | Rate limit exceeded | Wait and retry, or use caching |
| `Timeout` | Slow API response | Increase timeout or retry |

---

## SAM Entity Management API (Vendor Discovery)

### Purpose

The SAM Entity Management API (v3) provides access to all registered government contractors. This is used in **Pipeline Stage 3** (Vendor Discovery) to find vendors matching the tender's NAICS codes.

### Implementation: `SamEntitySource`

**File:** `src/vendor_ai_agent/sources/sam_entity.py`

**Class:** `SamEntitySource`

### How It Works

The SAM Entity API uses an **asynchronous extract model**:

1. **Initial Request**: Client requests entities by NAICS code
2. **File Generation**: SAM generates a bulk extract file (5-300 seconds)
3. **Download URL**: API returns a temporary download URL
4. **Polling**: Client polls the URL until file is ready
5. **Download**: Client downloads gzip-compressed JSON file
6. **Parse**: Client decompresses and parses entity data

**Flow Diagram:**

```
Client                      SAM API                       File Storage
  │                           │                               │
  ├─ GET /entities?naics=541330─────────────────────────────> │
  │                           │                               │
  │                           ├─ Generate extract file ─────> │
  │                           │   (5-300 seconds)             │
  │ <─────────────────────────┤                               │
  │  202: Download URL        │                               │
  │                           │                               │
  ├─ GET download_url ──────────────────────────────────────> │
  │                           │                               │
  │ <───────────────────────────────────────────────────────┤
  │  400: File pending (retry)│                               │
  │                           │                               │
  ├─ GET download_url (retry) ────────────────────────────────> │
  │                           │                               │
  │ <───────────────────────────────────────────────────────┤
  │  200: gzip JSON data      │                               │
  │                           │                               │
  ├─ Decompress & parse       │                               │
```

### Basic Usage

```python
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata

# Initialize SAM source
sam_source = SamEntitySource(
    use_cache=True,           # Enable caching
    cache_ttl_days=7,         # Cache for 7 days
    sync_to_db=True,          # Sync to database
    initial_fetch_limit=2000  # Max vendors per NAICS
)

# Create tender profile
profile = TenderProfile(
    country="US",
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=["541330", "541511"]),  # IT Services
        place_of_performance=PlaceOfPerformance(state_province="CA")
    )
)

# Search for vendors
vendors = sam_source.search(profile)

print(f"Found {len(vendors)} vendors")
for vendor in vendors[:5]:
    print(f"- {vendor.company_name} ({vendor.city}, {vendor.state})")
    print(f"  UEI: {vendor.uei}")
    print(f"  CAGE: {vendor.cage_code}")
    print(f"  Small Business: {vendor.business_types}")
```

### Search Parameters

The `search()` method accepts a `TenderProfile` and uses these fields:

| Field | Usage | Example |
|-------|-------|---------|
| `api_metadata.codes.naics` | NAICS codes to search (max 3 processed) | `["541330", "541511"]` |
| `api_metadata.place_of_performance.state_province` | Optional state filter | `"CA"` |
| `country` | Must be "US" (Canada not supported) | `"US"` |

### Advanced: Direct NAICS Search

For more control, use `search_by_naics()` directly:

```python
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.database import get_session

sam = SamEntitySource()

with get_session() as db_session:
    # Search for IT services vendors in California
    entities = sam.search_by_naics(
        naics_code="541330",
        state="CA",
        limit=1000,
        db_session=db_session
    )
    
    print(f"Found {len(entities)} entities")
    
    for entity in entities[:5]:
        core_data = entity.get("coreData", {})
        entity_reg = entity.get("entityRegistration", {})
        
        name = entity_reg.get("legalBusinessName")
        uei = entity_reg.get("ueiSAM")
        
        physical_addr = core_data.get("physicalAddress", {})
        city = physical_addr.get("city")
        state = physical_addr.get("stateOrProvinceCode")
        
        print(f"- {name} ({city}, {state})")
        print(f"  UEI: {uei}")
```

### Database Synchronization

When `sync_to_db=True` (default), the source automatically:

1. **Upserts vendors** to `vendors` table (by `external_id`)
2. **Updates NAICS codes** in `vendor_naics` table
3. **Extracts POCs** to `vendor_contacts` table
4. **Stores metadata** in `metadata_json` field (full API response)

**Benefits:**
- Reduces API calls (vendors cached in database)
- Enables offline operation (use cached vendors)
- Supports contact enrichment (SAM POC data available)
- Allows custom queries (filter by location, certs, etc.)

**Database Sync Code (from sam_entity.py):**

```python
if self.sync_to_db:
    vendor_obj = self._parse_entity(entity_data)
    if vendor_obj:
        # Check if vendor exists
        existing = db_session.query(Vendor).filter(
            Vendor.source == "sam_entity",
            Vendor.external_id == vendor_obj.external_id
        ).first()
        
        if existing:
            existing.updated_at = datetime.utcnow()
        else:
            # Insert new vendor
            db_session.add(vendor_obj)
            db_session.flush()
            
            # Add NAICS codes
            assertions = entity_data.get("assertions", {})
            goods_services = assertions.get("goodsAndServices", {})
            naics_list = goods_services.get("naicsList", [])
            
            for naics_item in naics_list:
                naics_code = naics_item.get("naicsCode")
                naics_obj = VendorNAICS(
                    vendor_id=vendor_obj.id,
                    naics_code=naics_code,
                    naics_description=naics_item.get("naicsDescription"),
                    is_primary=(naics_code == primary_naics)
                )
                db_session.add(naics_obj)
            
            # Add POC contacts
            poc = entity_data.get("entityRegistration", {}).get("pointsOfContact", {})
            if poc and poc.get("email"):
                contact_obj = VendorContact(
                    vendor_id=vendor_obj.id,
                    source="sam_gov_poc",
                    email=poc.get("email"),
                    phone=poc.get("usPhone"),
                    is_verified=True,
                    confidence_score=90
                )
                db_session.add(contact_obj)
        
        db_session.commit()
```

### Pipeline Integration

The SAM Entity source is automatically used in **Stage 3** (Vendor Discovery) when:

1. Tender country is "US"
2. NAICS codes are available in `api_metadata.codes.naics`
3. "sam_entity" is in `config.discovery.preferred_sources`

**Pipeline Configuration:**

```python
from src.vendor_ai_agent.config import RuntimeConfig, DiscoveryConfig

config = RuntimeConfig(
    discovery=DiscoveryConfig(
        target_results=1000,
        preferred_sources=["sam_entity", "static_directory"]
    )
)

# Run pipeline
result = pipeline.run(config)
```

### Entity Data Structure

**SAM Entity API Response Structure:**

```json
{
  "entityData": [
    {
      "entityRegistration": {
        "ueiSAM": "L3DQ1QV22P24",
        "cageCode": "7QBD9",
        "legalBusinessName": "ACME CORPORATION",
        "dbaName": "Acme Corp",
        "registrationStatus": "Active",
        "registrationDate": "2020-01-15",
        "expirationDate": "2025-01-14",
        "pointsOfContact": {
          "governmentBusinessPOC": {
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@acme.com",
            "usPhone": "555-123-4567"
          }
        }
      },
      "coreData": {
        "physicalAddress": {
          "addressLine1": "123 Main St",
          "city": "San Francisco",
          "stateOrProvinceCode": "CA",
          "zipCode": "94102",
          "countryCode": "USA"
        },
        "entityInformation": {
          "entityURL": "https://www.acme.com"
        },
        "businessTypes": {
          "businessTypeList": [
            {"businessTypeDesc": "Small Business"},
            {"businessTypeDesc": "Woman Owned Small Business"}
          ]
        }
      },
      "assertions": {
        "goodsAndServices": {
          "primaryNaics": "541330",
          "naicsList": [
            {
              "naicsCode": "541330",
              "naicsDescription": "Engineering Services"
            },
            {
              "naicsCode": "541511",
              "naicsDescription": "Custom Computer Programming Services"
            }
          ]
        }
      }
    }
  ]
}
```

---

## SAM Contact Enrichment

### Purpose

The `SamContactProvider` enriches vendor records with **Points of Contact (POCs)** extracted from SAM.gov registrations. This runs in **Pipeline Stage 5** (Enrichment).

### Implementation: `SamContactProvider`

**File:** `src/vendor_ai_agent/enrichment_providers/sam_contact.py`

**Class:** `SamContactProvider`

### How It Works

1. **Checks for existing contacts**: Skips if vendor already has real contacts
2. **Finds vendor in database**: Matches by UEI, CAGE code, or legal name
3. **Retrieves POC contacts**: Queries `vendor_contacts` table for "sam_gov_poc" source
4. **Enriches vendor record**: Adds email, phone, and contact name
5. **Applies email filtering**: Ensures email is from company domain (not generic)

### Basic Usage

```python
from src.vendor_ai_agent.enrichment_providers.sam_contact import SamContactProvider
from src.vendor_ai_agent.models import VendorRecord

# Initialize provider
sam_contact = SamContactProvider()

# Create vendor record (from SAM Entity search)
vendor = VendorRecord(
    company_name="ACME CORPORATION",
    uei="L3DQ1QV22P24",
    cage_code="7QBD9",
    website="https://www.acme.com",
    city="San Francisco",
    state="CA",
    source="sam_entity"
)

# Enrich with SAM POC data
enriched = sam_contact.enrich(vendor)

if enriched.email:
    print(f"✓ Email: {enriched.email}")
    print(f"  Source: {enriched.filtering_metadata.get('email_source')}")
    print(f"  Confidence: {enriched.filtering_metadata.get('email_confidence')}")

if enriched.phone:
    print(f"✓ Phone: {enriched.phone}")
```

### Pipeline Integration

Enable SAM contact enrichment in config:

```python
from src.vendor_ai_agent.config import RuntimeConfig, EnrichmentConfig

config = RuntimeConfig(
    enrichment=EnrichmentConfig(
        providers=["sam_contact", "apollo", "static_contacts"],
        enable_manual_enrichment=True
    )
)
```

### Email Filtering

The provider uses `filter_emails_for_vendor()` to ensure quality:

**Rules:**
- ✓ Company domain emails (e.g., john@acme.com for acme.com)
- ✗ Generic domains (gmail.com, yahoo.com, hotmail.com)
- ✗ Government domains (@mil, @gov)
- ✗ Mismatched domains (john@other.com for acme.com)

**Example:**

```python
vendor.website = "https://www.acme.com"

# ✓ Accepted
poc_email = "john.doe@acme.com"  # Matches domain

# ✗ Rejected
poc_email = "john.doe@gmail.com"  # Generic domain
poc_email = "john.doe@other.com"  # Different domain
```

### Contact Priority

SAM provides multiple POC types. Priority order:

1. **Government Business POC** (most relevant for contracting)
2. **Electronic Business POC** (fallback)
3. **Past Performance POC** (fallback)

**Code:**
```python
poc = (
    points_of_contact.get("governmentBusinessPOC") or
    points_of_contact.get("electronicBusinessPOC") or
    points_of_contact.get("pastPerformancePOC")
)
```

---

## CSV Bulk Import

### Purpose

For large-scale vendor synchronization, SAM.gov offers **CSV exports** that can be bulk-imported into the database. This is useful for:

- Initial database population (millions of vendors)
- Periodic full refreshes
- Offline operation (no API calls needed)

### Implementation: `ingest_sam_csv()`

**File:** `src/vendor_ai_agent/ingestion/sam_csv.py`

**Function:** `ingest_sam_csv(csv_path: Path) -> int`

### How to Get SAM CSV Exports

1. Visit: https://sam.gov/data-services/Entity%20Management/Public%20V2
2. Click "Download Entity Management Public Data Package"
3. Select date range and entity types
4. Request download (file generated within 24 hours)
5. Download large ZIP file (~10-50 GB compressed)
6. Extract CSV files by state/region

**CSV Files Included:**
- `Public_V2_01012025.dat` - Main entity data (pipe-delimited)
- State-specific files (e.g., `CA_Public_V2.csv`)

### CSV Import Usage

```python
from pathlib import Path
from src.vendor_ai_agent.ingestion.sam_csv import ingest_sam_csv

# Import vendors from CSV
csv_path = Path("data/sam_export/CA_Public_V2.csv")
count = ingest_sam_csv(csv_path)

print(f"✓ Imported {count} vendors from CSV")
```

### CSV Field Mapping

**Standard SAM CSV Export Fields:**

| CSV Header | Database Field | Notes |
|------------|----------------|-------|
| `UNIQUE ENTITY ID` / `UEI` | `uei` | Primary identifier |
| `LEGAL BUSINESS NAME` | `legal_name` | Required field |
| `CAGE CODE` | `cage_code` | Commercial and Government Entity code |
| `DUNS NUMBER` | `duns` | Often empty in new exports |
| `DBA NAME` | `dba_name` | Doing Business As name |
| `PHYSICAL ADDRESS LINE 1` | `address` | Street address |
| `PHYSICAL ADDRESS CITY` | `city` | City |
| `PHYSICAL ADDRESS PROVINCE OR STATE` | `state` | State code |
| `PHYSICAL ADDRESS ZIP/POSTAL CODE` | `postal_code` | ZIP code |
| `PHYSICAL ADDRESS COUNTRY CODE` | `country` | Country code |
| `BUSINESS TYPES` | `business_types` | Tilde-delimited (~) |
| `SMALL BUSINESS` | `is_small_business` | Y/N flag |
| `WOMAN OWNED` | `is_woman_owned` | Y/N flag |
| `NAICS CODES` | `vendor_naics` | Tilde-delimited codes |
| `PRIMARY NAICS` | `vendor_naics.is_primary` | Primary NAICS flag |
| `GOVT BUS POC NAME` | `vendor_contacts.first_name` | Government POC |
| `GOVT BUS POC EMAIL` | `vendor_contacts.email` | POC email |
| `GOVT BUS POC US PHONE` | `vendor_contacts.phone` | POC phone |

### CSV Import Process

The `ingest_sam_csv()` function:

1. **Reads CSV** with UTF-8-BOM encoding (handles special characters)
2. **Normalizes headers** (case-insensitive matching)
3. **For each row:**
   - Validates UEI and legal name (required fields)
   - Upserts vendor record (by `source=sam_entity`, `external_id=uei`)
   - Clears and re-inserts NAICS codes (avoids stale data)
   - Upserts POC contact (if email provided)
4. **Batch commits** every 100 rows (performance optimization)
5. **Error handling** (logs errors, continues processing)

**Performance:**
- **Speed**: ~1,000-5,000 vendors/second (depending on hardware)
- **Memory**: Streams rows (doesn't load entire file)
- **Disk**: Minimal (database handles storage)

### Example: Full State Import

```bash
# Download California vendors CSV from SAM.gov
# Unzip and place in data/ directory

poetry run python -c "
from pathlib import Path
from src.vendor_ai_agent.ingestion.sam_csv import ingest_sam_csv

csv_path = Path('data/sam_export/CA_Public_V2.csv')
count = ingest_sam_csv(csv_path)
print(f'✓ Imported {count} California vendors')
"
```

### CSV Import vs. API

| Feature | CSV Import | Entity API |
|---------|------------|------------|
| **Volume** | Millions of vendors | 2,000 vendors per NAICS |
| **Speed** | Very fast (bulk insert) | Slow (async extract, polling) |
| **Freshness** | Stale (daily/weekly exports) | Real-time |
| **Cost** | Free (no API calls) | 1,000 requests/day limit |
| **Use Case** | Initial population, full refresh | Targeted NAICS searches |
| **Setup** | Manual download required | API key required |

**Recommendation:**
- Use **CSV import** for initial database population
- Use **Entity API** for targeted searches and real-time updates

---

## Data Mapping

### SAM Entity → Vendor Model

**Mapping Logic (from sam_entity.py:\_parse_entity()):**

```python
def _parse_entity(self, entity_data: dict) -> Optional[Vendor]:
    core_data = entity_data.get("coreData", {})
    entity_reg = entity_data.get("entityRegistration", {})
    
    # Identifiers
    uei = entity_reg.get("ueiSAM")
    cage_code = entity_reg.get("cageCode")
    
    # Names
    legal_name = entity_reg.get("legalBusinessName", "")
    dba_name = entity_reg.get("dbaName")
    
    # Location
    physical_address = core_data.get("physicalAddress", {})
    country = physical_address.get("countryCode")
    state = physical_address.get("stateOrProvinceCode")
    city = physical_address.get("city")
    address = physical_address.get("addressLine1")
    postal_code = physical_address.get("zipCode")
    
    # Website
    entity_info = core_data.get("entityInformation", {})
    website_url = entity_info.get("entityURL")
    
    # Business Types
    business_types_data = core_data.get("businessTypes", {})
    business_type_list = business_types_data.get("businessTypeList", [])
    business_types = [bt.get("businessTypeDesc", "") for bt in business_type_list]
    
    # Certifications (derived from business types)
    is_small_business = any("Small" in bt for bt in business_types)
    is_woman_owned = any("Woman" in bt for bt in business_types)
    is_veteran_owned = any("Veteran" in bt for bt in business_types)
    is_minority_owned = any("Minority" in bt or "Disadvantaged" in bt for bt in business_types)
    is_8a = any("8(a)" in bt for bt in business_types)
    is_hubzone = any("HUBZone" in bt for bt in business_types)
    
    # Create Vendor model
    vendor = Vendor(
        source="sam_entity",
        external_id=uei or cage_code,
        uei=uei,
        duns=None,  # Deprecated in SAM v3/v4
        cage_code=cage_code,
        legal_name=legal_name,
        dba_name=dba_name,
        website=website_url,
        country=country,
        state=state,
        city=city,
        address=address,
        postal_code=postal_code,
        business_types=business_types,
        is_small_business=is_small_business,
        is_woman_owned=is_woman_owned,
        is_veteran_owned=is_veteran_owned,
        is_minority_owned=is_minority_owned,
        is_8a=is_8a,
        is_hubzone=is_hubzone,
        metadata_json=entity_data,  # Store full API response
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return vendor
```

### SAM Entity → VendorRecord

**Mapping Logic (from sam_entity.py:\_entity_to_vendor_record()):**

```python
def _entity_to_vendor_record(self, entity_data: dict) -> Optional[VendorRecord]:
    vendor = self._parse_entity(entity_data)
    if not vendor:
        return None
    
    # Extract POC contact
    contact_info = None
    points_of_contact = entity_data.get("entityRegistration", {}).get("pointsOfContact", {})
    if points_of_contact:
        poc = (
            points_of_contact.get("governmentBusinessPOC") or
            points_of_contact.get("electronicBusinessPOC") or
            points_of_contact.get("pastPerformancePOC")
        )
        
        if poc:
            contact_info = ContactInfo(
                name=f"{poc.get('firstName', '')} {poc.get('lastName', '')}".strip(),
                email=poc.get("email"),
                phone=poc.get("usPhone"),
                organization=vendor.legal_name
            )
    
    # Convert business_types to list
    business_types_list = []
    if vendor.business_types:
        if isinstance(vendor.business_types, list):
            business_types_list = vendor.business_types
        elif isinstance(vendor.business_types, str):
            business_types_list = [vendor.business_types]
    
    # Create VendorRecord
    return VendorRecord(
        company_name=vendor.legal_name,
        website=vendor.website,
        email=contact_info.email if contact_info else None,
        phone=contact_info.phone if contact_info else None,
        location=f"{vendor.city}, {vendor.state}" if vendor.city and vendor.state else vendor.state,
        city=vendor.city,
        state=vendor.state,
        country=vendor.country,
        industry=None,  # Not available from SAM
        source="sam_entity",
        is_past_winner=False,  # Requires USAspending integration
        enrichment_flags=["sam_registered"],
        uei=vendor.uei,
        duns=vendor.duns,
        cage_code=vendor.cage_code,
        business_types=business_types_list,
        primary_contact=contact_info,
        total_contract_value=vendor.total_contract_value,
        contract_count=vendor.contract_count
    )
```

### SAM Opportunity → TenderProfile

**Mapping Logic (from sam.py:\_build_api_metadata()):**

See [SAM Opportunities API](#sam-opportunities-api-tender-ingestion) section for full field mapping table.

---

## Configuration

### Environment Variables

**Required:**

```bash
# SAM API Key (required for API access)
SAM_API_KEY=your-key-here
```

**Optional:**

```bash
# Database URL (defaults to localhost)
DATABASE_URL=postgresql://user:pass@host:port/vendor_ai

# SQL query logging (useful for debugging)
SQL_ECHO=false

# Database pool settings
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

### Runtime Configuration

**SAM API Config (config.py):**

```python
@dataclass
class SamApiConfig:
    base_url: str = "https://api.sam.gov/opportunities/v2/search"
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("SAM_API_KEY"))
```

**Discovery Config (for SAM Entity source):**

```python
@dataclass
class DiscoveryConfig:
    target_results: int = 1000                     # Target vendor count
    preferred_sources: List[str] = ["sam_entity"]  # Enable SAM source
    enable_batch_cache: bool = True                # Enable vendor caching
    batch_size: int = 500                          # Batch size for processing
```

**Enrichment Config (for SAM Contact provider):**

```python
@dataclass
class EnrichmentConfig:
    providers: List[str] = ["sam_contact", "apollo"]  # Enable SAM contact enrichment
    enable_manual_enrichment: bool = True             # Allow manual enrichment
    batch_size: int = 50                              # Enrichment batch size
```

### SamEntitySource Configuration

**Constructor Parameters:**

```python
sam_source = SamEntitySource(
    api_key=None,                # API key (defaults to SAM_API_KEY env var)
    use_cache=True,              # Enable API response caching
    cache_ttl_days=7,            # Cache TTL (7 days recommended)
    rate_limit_per_day=1000,     # Daily rate limit (free tier)
    sync_to_db=True,             # Sync vendors to database
    initial_fetch_limit=2000     # Max vendors per NAICS code
)
```

**Configuration Examples:**

**Conservative (API-conscious):**
```python
sam_source = SamEntitySource(
    use_cache=True,
    cache_ttl_days=14,        # Longer cache (less API calls)
    sync_to_db=True,          # Always sync to DB
    initial_fetch_limit=500   # Smaller batches
)
```

**Aggressive (Real-time):**
```python
sam_source = SamEntitySource(
    use_cache=False,          # No caching (always fresh)
    sync_to_db=True,
    initial_fetch_limit=5000  # Large batches
)
```

**Offline (Database-only):**
```python
# Don't provide API key - will use database only
sam_source = SamEntitySource(
    api_key=None,             # No API access
    use_cache=True,
    sync_to_db=False          # Read from DB only
)
```

---

## Rate Limits and Caching

### SAM.gov Rate Limits

**Free Tier:**
- **1,000 requests per day** (rolling 24-hour window)
- **No burst limits** (but individual requests can take 30-300 seconds)
- **No paid tier** (free for all registered users)

**Rate Limit Headers:** SAM API does not return rate limit headers, so client-side tracking is required.

**Rate Limit Enforcement (in sam_entity.py):**

```python
def _check_rate_limit(self) -> None:
    now = datetime.utcnow()
    elapsed = (now - self._request_window_start).total_seconds()
    
    # Reset counter after 24 hours
    if elapsed >= 86400:
        self._request_count = 0
        self._request_window_start = now
    
    # Raise exception if limit exceeded
    if self._request_count >= self.rate_limit_per_day:
        raise Exception(f"Rate limit exceeded: {self.rate_limit_per_day} requests/day")
```

### API Response Caching

**Cache Strategy:**
- **Storage**: PostgreSQL `api_cache` table
- **TTL**: 7 days default (configurable via `cache_ttl_days`)
- **Key**: Hash of request parameters (NAICS code, state, etc.)
- **Benefit**: Reduces API calls by ~90% for repeated searches

**Cache Usage:**

```python
with get_session() as db_session:
    cache_manager = CacheManager(db_session, source="sam_entity")
    
    # Check cache first
    cached = cache_manager.get(params)
    if cached:
        return cached  # Return cached response
    
    # Make API request if not cached
    response = self._make_request(params)
    
    # Store in cache
    cache_manager.set(params, response, ttl_days=7)
```

### Database Vendor Caching

**Benefits:**
- **Offline operation**: Use cached vendors without API access
- **Fast queries**: Database queries much faster than API calls
- **Historical data**: Track vendor changes over time

**Cache Freshness:**
- Vendors updated when:
  - New API search performed
  - CSV import executed
  - Manual sync triggered

**Stale Data Handling:**
- Check `vendors.updated_at` timestamp
- Re-fetch if older than threshold (e.g., 30 days)

**Query Cached Vendors:**

```python
from src.vendor_ai_agent.database import get_session, Vendor, VendorNAICS

with get_session() as session:
    # Find vendors by NAICS, last updated within 30 days
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    vendors = (
        session.query(Vendor)
        .join(VendorNAICS)
        .filter(VendorNAICS.naics_code == "541330")
        .filter(Vendor.state == "CA")
        .filter(Vendor.updated_at >= thirty_days_ago)
        .all()
    )
    
    print(f"Found {len(vendors)} recently updated vendors")
```

### Cost Optimization Strategies

**1. Use Database-First Approach:**
```python
# Check database first, fallback to API
with get_session() as session:
    db_vendors = session.query(Vendor).join(VendorNAICS).filter(
        VendorNAICS.naics_code == naics_code,
        Vendor.state == state
    ).all()
    
    if len(db_vendors) >= min_threshold:
        # Use cached vendors
        return db_vendors
    else:
        # Fetch from API
        return sam_source.search_by_naics(naics_code, state)
```

**2. Bulk CSV Import for Initial Population:**
```bash
# Import all California vendors (no API calls)
poetry run python -c "
from pathlib import Path
from src.vendor_ai_agent.ingestion.sam_csv import ingest_sam_csv
ingest_sam_csv(Path('data/sam_export/CA_Public_V2.csv'))
"
```

**3. Increase Cache TTL:**
```python
# Cache for 30 days instead of 7
sam_source = SamEntitySource(cache_ttl_days=30)
```

**4. Limit NAICS Codes Processed:**
```python
# Only process top 2 NAICS codes (instead of all)
profile.api_metadata.codes.naics = profile.api_metadata.codes.naics[:2]
```

**5. Use State Filtering:**
```python
# Filter by state early (reduces data transfer)
sam_source.search_by_naics(naics_code="541330", state="CA", limit=1000)
```

**Cost Breakdown (Example Tender):**

| Operation | API Calls | Time |
|-----------|-----------|------|
| Search 3 NAICS codes (no cache) | 3 | 5-15 min |
| Search 3 NAICS codes (cached) | 0 | <1 sec |
| CSV import (1M vendors) | 0 | 10-30 min |
| Database query (10K vendors) | 0 | <1 sec |

**Recommendation:** Use **CSV import for initial setup**, then **API for incremental updates**.

---

## Error Handling

### API Error Responses

**Common SAM API Errors:**

| Status Code | Error | Cause | Solution |
|-------------|-------|-------|----------|
| **400 Bad Request** | Invalid parameters | Missing required params, invalid format | Validate NAICS code format (6 digits) |
| **400 JSON_CSV_PENDING** | File not ready yet | Extract file still generating | Retry with exponential backoff (5-300s) |
| **401 Unauthorized** | Invalid API key | Wrong/expired API key | Check SAM_API_KEY in .env |
| **403 Forbidden** | Access denied | API key not activated | Wait 24h after registration |
| **404 Not Found** | No results | No entities match criteria | Broaden search (remove state filter) |
| **429 Too Many Requests** | Rate limit exceeded | >1000 requests/day | Wait 24h, use cache, or reduce queries |
| **500 Internal Server Error** | SAM server error | SAM.gov downtime | Retry later, check status.data.gov |
| **503 Service Unavailable** | SAM maintenance | Scheduled downtime | Check sam.gov status page |
| **Timeout** | Request timeout | Slow API response | Increase timeout, retry with backoff |

### Error Handling in Code

**1. Retry Logic with Exponential Backoff:**

```python
# From sam_entity.py
max_retries = 3
retry_delays = [30, 60, 90]  # seconds

for attempt in range(max_retries):
    try:
        response = self.session.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except (Timeout, HTTPError) as e:
        if attempt < max_retries - 1:
            delay = retry_delays[attempt]
            print(f"Request error: {e}. Retrying in {delay}s...")
            time.sleep(delay)
        else:
            raise Exception(f"Failed after {max_retries} attempts: {e}")
```

**2. File Generation Polling:**

```python
# Poll download URL until file is ready
max_retries = 10
retry_delays = [5, 10, 15, 20, 30, 30, 30, 30, 30, 30]

for attempt in range(max_retries):
    try:
        response = self.session.get(download_url, timeout=120)
        
        if response.status_code == 400:
            error_data = response.json()
            if error_data.get("errorCode") == "JSON_CSV_PENDING":
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"File still generating, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delays[attempt])
        else:
            raise Exception(f"File not ready after {sum(retry_delays)}s")
```

**3. Database Transaction Safety:**

```python
with get_session() as session:
    try:
        # Upsert vendor
        vendor = Vendor(...)
        session.add(vendor)
        session.flush()
        
        # Add NAICS codes
        for naics in naics_list:
            session.add(VendorNAICS(...))
        
        # Commit transaction
        session.commit()
    except IntegrityError as e:
        # Handle duplicate key errors
        session.rollback()
        print(f"Duplicate vendor: {e}")
    except Exception as e:
        # Handle other errors
        session.rollback()
        raise
```

**4. Graceful Degradation:**

```python
# Fallback to database if API fails
try:
    vendors = sam_source.search_by_naics(naics_code, state)
except Exception as e:
    print(f"SAM API error: {e}. Falling back to database...")
    
    with get_session() as session:
        vendors = session.query(Vendor).join(VendorNAICS).filter(
            VendorNAICS.naics_code == naics_code,
            Vendor.state == state
        ).all()
```

---

## Troubleshooting

### Database Issues

#### "Connection refused" / "Could not connect to server"

**Cause:** PostgreSQL is not running

**Solutions:**

```bash
# Check if PostgreSQL is running
ps aux | grep postgres

# macOS (Homebrew)
brew services start postgresql@14

# Linux (systemd)
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Auto-start on boot

# Docker
docker start vendor-ai-postgres

# Verify connection
psql -U postgres -c "SELECT version();"
```

#### "Database does not exist"

**Cause:** `vendor_ai` database not created

**Solutions:**

```bash
# Create database
createdb vendor_ai

# Or using psql
psql -U postgres -c "CREATE DATABASE vendor_ai;"

# Run migrations
poetry run alembic upgrade head
```

#### "Relation 'vendors' does not exist"

**Cause:** Database migrations not run

**Solutions:**

```bash
# Check migration status
poetry run alembic current

# Run migrations
poetry run alembic upgrade head

# Verify tables created
psql -U postgres -d vendor_ai -c "\dt"
```

#### "Could not parse database URL"

**Cause:** Invalid `DATABASE_URL` in `.env`

**Solutions:**

```bash
# Correct format
DATABASE_URL=postgresql://username:password@host:port/database

# Example (local)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vendor_ai

# Example (remote)
DATABASE_URL=postgresql://user:pass@db.example.com:5432/vendor_ai
```

### SAM API Issues

#### "SAM_API_KEY is required"

**Cause:** API key not configured

**Solutions:**

```bash
# Check if API key is set
echo $SAM_API_KEY

# Add to .env file
echo "SAM_API_KEY=your-key-here" >> .env

# Or export temporarily
export SAM_API_KEY=your-key-here
```

#### "401 Unauthorized"

**Cause:** Invalid or expired API key

**Solutions:**

1. **Verify API key format** (should be alphanumeric, ~32 chars)
2. **Check API key on SAM.gov:** https://open.gsa.gov/api/entity-api/
3. **Request new API key** if expired
4. **Wait 24 hours** if newly registered (activation delay)

**Test API key:**
```bash
curl "https://api.sam.gov/entity-information/v3/entities?api_key=YOUR_KEY&ueiSAM=L3DQ1QV22P24&includeSections=entityRegistration"
```

#### "Rate limit exceeded: 1000 requests/day"

**Cause:** Exceeded daily API quota

**Solutions:**

1. **Wait 24 hours** for quota reset
2. **Enable caching:**
   ```python
   sam_source = SamEntitySource(use_cache=True, cache_ttl_days=7)
   ```
3. **Use database-first approach:**
   ```python
   # Check database before API
   with get_session() as session:
       vendors = session.query(Vendor).filter(...).all()
       if len(vendors) < threshold:
           vendors = sam_source.search(profile)
   ```
4. **Import CSV exports** (no API calls needed)
5. **Reduce NAICS codes processed:**
   ```python
   profile.api_metadata.codes.naics = profile.api_metadata.codes.naics[:1]
   ```

#### "File not ready after X attempts"

**Cause:** SAM extract file taking longer than expected

**Solutions:**

1. **Increase retry timeout:**
   ```python
   # Modify sam_entity.py
   max_retries = 20  # Increase from 10
   retry_delays = [5, 10, 15, 20, 30] * 4  # Longer wait
   ```
2. **Use smaller NAICS searches** (fewer results = faster generation)
3. **Try during off-peak hours** (weekends, early morning EST)
4. **Use CSV export instead** (no async generation)

#### "No download URL found in response"

**Cause:** Unexpected API response format

**Solutions:**

1. **Check API response:**
   ```python
   print(f"Raw response: {response.text[:500]}")
   ```
2. **Verify NAICS code exists:**
   ```bash
   # Search NAICS at https://www.census.gov/naics/
   ```
3. **Try different NAICS code** (some codes may have no vendors)
4. **Contact SAM support** if persistent

### Data Issues

#### "No vendors found for NAICS"

**Cause:** No registered vendors for that NAICS code

**Solutions:**

1. **Verify NAICS code is valid** (6 digits, exists in NAICS system)
2. **Try parent NAICS code** (e.g., 5413 instead of 541330)
3. **Remove state filter** (may be too restrictive)
   ```python
   vendors = sam_source.search_by_naics(naics_code, state=None)
   ```
4. **Check alternate classification systems** (PSC, UNSPSC)

#### "Vendor has no contact information"

**Cause:** Vendor POC not provided or filtered out

**Solutions:**

1. **Check `vendor_contacts` table:**
   ```sql
   SELECT * FROM vendor_contacts WHERE vendor_id = 123;
   ```
2. **Review POC in SAM registration:**
   - Visit sam.gov
   - Search by UEI/CAGE code
   - View entity details
3. **Try other enrichment providers** (Apollo, web scraping)
4. **Use generic company contact methods** (website form, main line)

#### "Duplicate vendors in results"

**Cause:** Same company with multiple registrations (UEI, CAGE code)

**Solutions:**

1. **Enable deduplication:**
   ```python
   config = RuntimeConfig(
       filtering=FilteringConfig(enable_duplicate_removal=True)
   )
   ```
2. **Query by UEI first (most authoritative):**
   ```python
   vendors = session.query(Vendor).filter(Vendor.uei == uei).first()
   ```
3. **Merge duplicates manually:**
   ```sql
   -- Keep vendor with UEI, merge data from CAGE-only record
   UPDATE vendors SET uei = 'L3DQ1QV22P24' WHERE cage_code = '7QBD9';
   ```

### Performance Issues

#### "API search taking too long (>5 minutes)"

**Cause:** Large NAICS code with many results

**Solutions:**

1. **Add state filter:**
   ```python
   vendors = sam_source.search_by_naics(naics_code, state="CA")
   ```
2. **Reduce fetch limit:**
   ```python
   sam_source = SamEntitySource(initial_fetch_limit=500)
   ```
3. **Use database cache:**
   ```python
   sam_source = SamEntitySource(use_cache=True)
   ```
4. **Process in background:**
   ```python
   import asyncio
   asyncio.create_task(sam_source.search(profile))
   ```

#### "Database queries slow"

**Cause:** Missing indexes or large dataset

**Solutions:**

1. **Verify indexes exist:**
   ```sql
   \di  -- List all indexes
   ```
2. **Run VACUUM ANALYZE:**
   ```sql
   VACUUM ANALYZE vendors;
   VACUUM ANALYZE vendor_naics;
   ```
3. **Add custom indexes:**
   ```sql
   CREATE INDEX idx_vendors_state_city ON vendors(state, city);
   ```
4. **Increase PostgreSQL memory:**
   ```sql
   -- In postgresql.conf
   shared_buffers = 256MB
   effective_cache_size = 1GB
   ```

---

## Performance Optimization

### Database Indexing

**Existing Indexes (from schema):**
- `ix_vendors_source`, `ix_vendors_uei`, `ix_vendors_cage_code`
- `ix_vendor_location` (country, state, city)
- `ix_vendor_certifications` (is_small_business, is_woman_owned, is_veteran_owned)
- `ix_vendor_naics_lookup` (naics_code, vendor_id)

**Custom Indexes for Common Queries:**

```sql
-- Speed up NAICS + State queries
CREATE INDEX idx_vendor_naics_state ON vendor_naics(naics_code) 
  INCLUDE (vendor_id) WHERE vendor_id IN (
    SELECT id FROM vendors WHERE state = 'CA'
  );

-- Speed up location-based searches
CREATE INDEX idx_vendors_state_small_business 
  ON vendors(state, is_small_business) WHERE country = 'US';

-- Speed up contact lookups
CREATE INDEX idx_vendor_contacts_vendor_email 
  ON vendor_contacts(vendor_id, email) WHERE email IS NOT NULL;
```

### Query Optimization

**Use EXISTS instead of JOIN for existence checks:**

```python
# Slow (loads all vendors)
vendors = session.query(Vendor).join(VendorNAICS).filter(
    VendorNAICS.naics_code == "541330"
).all()

# Fast (uses index scan)
vendors = session.query(Vendor).filter(
    exists().where(
        and_(
            VendorNAICS.vendor_id == Vendor.id,
            VendorNAICS.naics_code == "541330"
        )
    )
).all()
```

**Use pagination for large result sets:**

```python
# Paginate results (reduces memory)
page_size = 1000
offset = 0

while True:
    vendors = session.query(Vendor).filter(...).limit(page_size).offset(offset).all()
    if not vendors:
        break
    
    # Process batch
    for vendor in vendors:
        process_vendor(vendor)
    
    offset += page_size
```

**Use selective column loading:**

```python
# Only load needed columns (reduces I/O)
vendors = session.query(
    Vendor.id, Vendor.legal_name, Vendor.state, Vendor.uei
).filter(...).all()
```

### Caching Strategies

**1. Application-Level Cache (Redis/Memcached):**

```python
import redis
cache = redis.Redis(host='localhost', port=6379, db=0)

def get_vendors_by_naics(naics_code: str):
    cache_key = f"vendors:naics:{naics_code}"
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query database
    vendors = session.query(Vendor).join(VendorNAICS).filter(
        VendorNAICS.naics_code == naics_code
    ).all()
    
    # Store in cache (24 hour TTL)
    cache.setex(cache_key, 86400, json.dumps([v.to_dict() for v in vendors]))
    
    return vendors
```

**2. Materialized Views (PostgreSQL):**

```sql
-- Pre-compute vendor counts by NAICS + State
CREATE MATERIALIZED VIEW vendor_naics_state_summary AS
SELECT 
    vn.naics_code,
    v.state,
    COUNT(*) as vendor_count,
    COUNT(vc.id) as vendors_with_contacts
FROM vendors v
JOIN vendor_naics vn ON v.id = vn.vendor_id
LEFT JOIN vendor_contacts vc ON v.id = vc.vendor_id
GROUP BY vn.naics_code, v.state;

-- Create index on materialized view
CREATE INDEX idx_mv_naics_state ON vendor_naics_state_summary(naics_code, state);

-- Refresh daily
REFRESH MATERIALIZED VIEW vendor_naics_state_summary;
```

**3. Eager Loading (SQLAlchemy):**

```python
# Avoid N+1 queries - load relationships upfront
vendors = session.query(Vendor).options(
    joinedload(Vendor.naics_codes),
    joinedload(Vendor.contacts)
).filter(...).all()

# Now accessing vendor.naics_codes doesn't trigger additional queries
for vendor in vendors:
    for naics in vendor.naics_codes:
        print(naics.naics_code)
```

### Batch Processing

**Process vendors in batches to reduce memory:**

```python
def process_vendors_in_batches(naics_code: str, batch_size: int = 500):
    with get_session() as session:
        # Get total count
        total = session.query(Vendor).join(VendorNAICS).filter(
            VendorNAICS.naics_code == naics_code
        ).count()
        
        print(f"Processing {total} vendors in batches of {batch_size}...")
        
        # Process in batches
        for offset in range(0, total, batch_size):
            batch = session.query(Vendor).join(VendorNAICS).filter(
                VendorNAICS.naics_code == naics_code
            ).limit(batch_size).offset(offset).all()
            
            # Process batch
            for vendor in batch:
                enrich_vendor(vendor)
            
            # Commit after each batch
            session.commit()
            
            print(f"Processed {min(offset + batch_size, total)}/{total} vendors")
```

---

## Integration Examples

### Example 1: Simple Vendor Search

**Goal:** Find all IT services vendors in California

```python
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata, PlaceOfPerformance

# Initialize SAM source
sam = SamEntitySource()

# Create tender profile
profile = TenderProfile(
    country="US",
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=["541330"]),  # Engineering Services
        place_of_performance=PlaceOfPerformance(state_province="CA")
    )
)

# Search vendors
vendors = sam.search(profile)

print(f"✓ Found {len(vendors)} vendors")
for vendor in vendors[:10]:
    print(f"  - {vendor.company_name} ({vendor.city}, {vendor.state})")
    print(f"    UEI: {vendor.uei} | CAGE: {vendor.cage_code}")
    if vendor.email:
        print(f"    Email: {vendor.email}")
```

### Example 2: Full Pipeline with SAM Integration

**Goal:** Run complete pipeline for US tender

```python
from src.vendor_ai_agent.pipeline import TenderVendorPipeline
from src.vendor_ai_agent.config import RuntimeConfig, DiscoveryConfig, EnrichmentConfig
from pathlib import Path

# Configure pipeline with SAM integration
config = RuntimeConfig(
    discovery=DiscoveryConfig(
        target_results=1000,
        preferred_sources=["sam_entity"],  # Use SAM for vendor discovery
        enable_serper_discovery=True
    ),
    enrichment=EnrichmentConfig(
        providers=["sam_contact", "apollo", "scraper"],  # SAM POC first
        enable_apollo_enrichment=True,
        enable_contact_scraping=True
    )
)

# Initialize pipeline
pipeline = TenderVendorPipeline(config=config)

# Run pipeline
tender_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP.pdf")
result = pipeline.run(
    tender_path=tender_path,
    output_dir=Path("outputs"),
    country="US"
)

print(f"✓ Pipeline complete")
print(f"  Total vendors: {result.summary['total_vendors']}")
print(f"  With contacts: {result.summary['vendors_with_contacts']}")
print(f"  SAM registered: {result.summary.get('sam_registered', 0)}")
```

### Example 3: Tender Ingestion from SAM.gov

**Goal:** Fetch tender metadata by solicitation number

```python
from src.vendor_ai_agent.ingestion.sam import UsSamIngestor, SamClient
from src.vendor_ai_agent.ingestion.models import SamIngestionRequest, DateRange
from src.vendor_ai_agent.config import SamApiConfig

# Initialize
config = SamApiConfig()
client = SamClient(base_url="https://api.sam.gov/opportunities/v2/search")
ingestor = UsSamIngestor(client=client, config=config)

# Ingest tender
request = SamIngestionRequest(
    solicitation_number="70RSAT24R00000003",
    date_range=DateRange(start="2024-01-01", end="2024-12-31")
)

result = ingestor.ingest(request)

# Print metadata
print(f"Title: {result.api_metadata.title}")
print(f"Buyer: {result.api_metadata.buyer.name}")
print(f"NAICS: {', '.join(result.api_metadata.codes.naics)}")
print(f"State: {result.api_metadata.place_of_performance.state_province}")
print(f"Deadline: {result.api_metadata.dates.response_deadline}")
print(f"Set-Aside: {result.api_metadata.set_aside.description}")
print(f"Est. Value: ${result.api_metadata.estimated_value.amount:,.0f}")
print(f"Attachments: {len(result.attachments)}")
```

### Example 4: CSV Bulk Import

**Goal:** Import 100,000 California vendors from CSV

```python
from pathlib import Path
from src.vendor_ai_agent.ingestion.sam_csv import ingest_sam_csv
import time

csv_path = Path("data/sam_export/CA_Public_V2.csv")

print(f"Starting CSV import from {csv_path}...")
start_time = time.time()

count = ingest_sam_csv(csv_path)

elapsed = time.time() - start_time
print(f"✓ Imported {count:,} vendors in {elapsed:.1f} seconds")
print(f"  Rate: {count/elapsed:,.0f} vendors/second")

# Verify import
from src.vendor_ai_agent.database import get_session, Vendor

with get_session() as session:
    total = session.query(Vendor).filter(Vendor.state == "CA").count()
    print(f"✓ Total CA vendors in database: {total:,}")
```

### Example 5: Database Query with Filters

**Goal:** Find small businesses with specific certifications

```python
from src.vendor_ai_agent.database import get_session, Vendor, VendorNAICS

with get_session() as session:
    # Find woman-owned small businesses in IT services (NAICS 541330)
    vendors = (
        session.query(Vendor)
        .join(VendorNAICS)
        .filter(VendorNAICS.naics_code == "541330")
        .filter(Vendor.state == "CA")
        .filter(Vendor.is_small_business == True)
        .filter(Vendor.is_woman_owned == True)
        .order_by(Vendor.legal_name)
        .all()
    )
    
    print(f"Found {len(vendors)} woman-owned small businesses")
    
    for vendor in vendors[:10]:
        print(f"\n{vendor.legal_name}")
        print(f"  Location: {vendor.city}, {vendor.state}")
        print(f"  UEI: {vendor.uei}")
        print(f"  CAGE: {vendor.cage_code}")
        print(f"  Website: {vendor.website}")
        
        # Show certifications
        certs = []
        if vendor.is_8a:
            certs.append("8(a)")
        if vendor.is_hubzone:
            certs.append("HUBZone")
        if vendor.is_veteran_owned:
            certs.append("VOSB")
        if certs:
            print(f"  Certifications: {', '.join(certs)}")
```

### Example 6: Contact Enrichment with SAM POC

**Goal:** Enrich vendor contact information using SAM Point of Contact (POC)

```python
from src.vendor_ai_agent.enrichment_providers.sam_contact import SamContactProvider
from src.vendor_ai_agent.database import get_session, Vendor
from src.vendor_ai_agent.models import VendorRecord

# Initialize SAM contact provider
sam_contacts = SamContactProvider()

# Fetch vendor from database
with get_session() as session:
    vendor = session.query(Vendor).filter(Vendor.uei == "L3DQ1QV22P24").first()
    
    # Convert to VendorRecord
    vendor_record = VendorRecord(
        company_name=vendor.legal_name,
        uei=vendor.uei,
        cage_code=vendor.cage_code,
        city=vendor.city,
        state=vendor.state,
        country=vendor.country,
        source="sam_entity"
    )
    
    # Enrich with SAM POC
    enriched = sam_contacts.enrich(vendor_record)
    
    # Display results
    if enriched.email:
        print(f"✓ Found contact for {enriched.company_name}")
        print(f"  Name: {enriched.contact_name}")
        print(f"  Title: {enriched.contact_title}")
        print(f"  Email: {enriched.email}")
        print(f"  Phone: {enriched.phone}")
        print(f"  Source: {enriched.metadata.get('poc_type', 'Unknown')}")
        print(f"  Quality: {enriched.metadata.get('email_quality', 'Unknown')}")
    else:
        print(f"✗ No contact found for {vendor.legal_name}")
        print(f"  Try alternate enrichment providers (Apollo, Hunter)")
```

**Output:**
```
✓ Found contact for ACME Corporation
  Name: John Smith
  Title: Government Business POC
  Email: john.smith@acme.com
  Phone: +1-555-123-4567
  Source: gov_business_poc
  Quality: personal
```

### Example 7: Set-Aside Filtering

**Goal:** Find vendors eligible for specific set-aside requirements

```python
from src.vendor_ai_agent.database import get_session, Vendor, VendorNAICS

def find_eligible_vendors(naics_code: str, set_aside: str, state: str = None):
    """
    Find vendors eligible for specific set-aside requirements.
    
    Args:
        naics_code: 6-digit NAICS code
        set_aside: Set-aside type (see mapping below)
        state: Optional state filter
    
    Returns:
        List of eligible vendors
    """
    
    # Map set-aside types to database fields
    set_aside_mapping = {
        "SBA": "is_small_business",          # Small Business Set-Aside (SBA)
        "8A": "is_8a",                       # 8(a) Business Development
        "SDVOSB": "is_service_disabled_veteran",  # Service-Disabled Veteran-Owned
        "WOSB": "is_woman_owned",            # Women-Owned Small Business
        "HUBZONE": "is_hubzone",             # Historically Underutilized Business Zone
        "VOSB": "is_veteran_owned",          # Veteran-Owned Small Business
        "EDWOSB": "is_economically_disadvantaged_woman_owned"  # Economically Disadvantaged WOSB
    }
    
    if set_aside not in set_aside_mapping:
        raise ValueError(f"Unknown set-aside type: {set_aside}")
    
    field_name = set_aside_mapping[set_aside]
    
    with get_session() as session:
        query = (
            session.query(Vendor)
            .join(VendorNAICS)
            .filter(VendorNAICS.naics_code == naics_code)
            .filter(getattr(Vendor, field_name) == True)
        )
        
        if state:
            query = query.filter(Vendor.state == state)
        
        vendors = query.all()
        
        print(f"Found {len(vendors)} {set_aside} vendors for NAICS {naics_code}")
        if state:
            print(f"  Location: {state}")
        
        return vendors

# Example: Find 8(a) certified IT services vendors in Maryland
vendors = find_eligible_vendors(
    naics_code="541330",  # Engineering Services
    set_aside="8A",
    state="MD"
)

for vendor in vendors[:5]:
    print(f"\n{vendor.legal_name}")
    print(f"  {vendor.city}, {vendor.state}")
    print(f"  UEI: {vendor.uei}")
    
    # Show all certifications
    certs = []
    if vendor.is_small_business:
        certs.append("SBA")
    if vendor.is_8a:
        certs.append("8(a)")
    if vendor.is_woman_owned:
        certs.append("WOSB")
    if vendor.is_veteran_owned:
        certs.append("VOSB")
    if vendor.is_hubzone:
        certs.append("HUBZone")
    
    print(f"  Certifications: {', '.join(certs)}")
```

**Output:**
```
Found 247 8A vendors for NAICS 541330
  Location: MD

Acme Engineering Services LLC
  Baltimore, MD
  UEI: A1B2C3D4E5F6
  Certifications: SBA, 8(a), WOSB

Tech Solutions Group Inc
  Rockville, MD
  UEI: G7H8I9J0K1L2
  Certifications: SBA, 8(a)
```

---

## Best Practices

### When to Use API vs CSV

**Use SAM Entity Management API when:**
- ✓ Need real-time vendor data
- ✓ Searching by specific NAICS codes (< 5,000 results)
- ✓ State/location filtering applied
- ✓ Need specific UEI/CAGE code lookups
- ✓ Integrating with live pipeline

**Use CSV Bulk Import when:**
- ✓ Initial database population (> 100,000 vendors)
- ✓ Need complete vendor registry for a state
- ✓ Offline/air-gapped environment
- ✓ Rate limits exhausted (1,000 requests/day)
- ✓ Historical snapshot needed

**Hybrid Approach (Recommended):**
```python
# 1. Import CSV for baseline (monthly)
ingest_sam_csv("sam_export/US_Public_V2.csv")

# 2. Use API for targeted searches (daily)
sam_source = SamEntitySource(use_cache=True, cache_ttl_days=7)
vendors = sam_source.search_by_naics(naics_code, state)

# 3. Fallback to database if API fails
try:
    vendors = sam_source.search(profile)
except Exception as e:
    vendors = session.query(Vendor).filter(...).all()
```

### Cache Management

**Cache Expiration Strategy:**

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Vendor registration | 7-14 days | Rarely changes |
| Contact information | 3-7 days | Moderate change rate |
| NAICS codes | 30 days | Very stable |
| Certifications | 7 days | May change quarterly |
| API search results | 24 hours | Depends on use case |

**Cache Invalidation:**

```python
# Manual cache clearing
from src.vendor_ai_agent.database.cache import clear_api_cache

# Clear all SAM API cache
clear_api_cache(source="sam_entity")

# Clear specific NAICS cache
clear_api_cache(source="sam_entity", pattern="naics:541330")

# Clear expired cache (older than 7 days)
clear_api_cache(source="sam_entity", older_than_days=7)
```

**Database Refresh Schedule:**

```bash
# Cron job: Refresh database monthly
0 2 1 * * /usr/local/bin/poetry run python scripts/refresh_sam_database.py
```

### Database Maintenance

**Regular Maintenance Tasks:**

```sql
-- Weekly: Vacuum and analyze
VACUUM ANALYZE vendors;
VACUUM ANALYZE vendor_naics;
VACUUM ANALYZE vendor_contacts;

-- Monthly: Rebuild indexes
REINDEX TABLE vendors;
REINDEX TABLE vendor_naics;

-- Monthly: Update statistics
ANALYZE vendors;
ANALYZE vendor_naics;

-- Quarterly: Check table bloat
SELECT 
    schemaname, 
    tablename, 
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Backup Strategy:**

```bash
# Daily backup (automated)
pg_dump vendor_ai > backups/vendor_ai_$(date +%Y%m%d).sql

# Weekly full backup
pg_dump -Fc vendor_ai > backups/vendor_ai_$(date +%Y%m%d).backup

# Restore from backup
pg_restore -d vendor_ai backups/vendor_ai_20240115.backup
```

### Security Considerations

**API Key Protection:**

```bash
# ✓ Good: Store in .env file (never commit)
SAM_API_KEY=abc123xyz789

# ✗ Bad: Hardcode in source code
# sam_api_key = "abc123xyz789"  # NEVER DO THIS

# ✓ Good: Use environment variable
export SAM_API_KEY=$(cat ~/.sam_api_key)

# ✓ Good: Use secret manager (production)
SAM_API_KEY=$(aws secretsmanager get-secret-value --secret-id sam-api-key --query SecretString --output text)
```

**Database Security:**

```sql
-- Create read-only user for reporting
CREATE USER sam_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE vendor_ai TO sam_readonly;
GRANT USAGE ON SCHEMA public TO sam_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sam_readonly;

-- Restrict network access (postgresql.conf)
listen_addresses = 'localhost'

-- Enable SSL connections
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
```

**Data Privacy:**

- **PII Handling:** SAM vendor data contains PII (names, emails, addresses)
- **Compliance:** Follow data retention policies (e.g., GDPR, CCPA if applicable)
- **Access Control:** Restrict database access to authorized users only
- **Audit Logging:** Enable PostgreSQL logging for compliance

```sql
-- Enable audit logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
SELECT pg_reload_conf();
```

---

## References and Resources

### Official SAM.gov Documentation

**Primary Resources:**
- **SAM.gov Home:** https://sam.gov/
- **API Portal:** https://open.gsa.gov/api/
- **Entity Management API v3:** https://open.gsa.gov/api/entity-api/
- **Opportunities API v2:** https://open.gsa.gov/api/opportunities-api/
- **API Key Registration:** https://open.gsa.gov/api/entity-api/#getting-started

**Data Dictionaries:**
- **SAM Entity Data Dictionary:** https://www.gsa.gov/reference/reports/sam-entity-data-dictionary
- **Opportunities Data Dictionary:** https://www.gsa.gov/reference/reports/opportunities-data-dictionary

### NAICS and Classification

**NAICS Resources:**
- **NAICS Search Tool:** https://www.census.gov/naics/
- **NAICS Manual:** https://www.census.gov/naics/reference_files_tools/
- **PSC Manual:** https://www.acquisition.gov/psc-manual
- **UNSPSC Browser:** https://www.unspsc.org/

### Set-Aside Programs

**SBA Resources:**
- **8(a) Business Development:** https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program
- **HUBZone Program:** https://www.sba.gov/federal-contracting/contracting-assistance-programs/hubzone-program
- **Women-Owned Small Business (WOSB):** https://www.sba.gov/federal-contracting/contracting-assistance-programs/women-owned-small-business-federal-contracting-program
- **Veteran Programs:** https://www.sba.gov/federal-contracting/contracting-assistance-programs/veteran-contracting-assistance-programs

### Database and Infrastructure

**PostgreSQL:**
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **SQLAlchemy Documentation:** https://docs.sqlalchemy.org/
- **Alembic Documentation:** https://alembic.sqlalchemy.org/

**Performance:**
- **PostgreSQL Performance Tuning:** https://wiki.postgresql.org/wiki/Performance_Optimization
- **Indexing Best Practices:** https://www.postgresql.org/docs/current/indexes.html

### Support and Community

**SAM.gov Support:**
- **Federal Service Desk:** 866-606-8220 (option 1)
- **Email Support:** fsd.gov@gsa.gov
- **Hours:** Monday-Friday, 8 AM - 8 PM EST

**API Issues:**
- **GitHub Issues:** https://github.com/GSA/sam_api/issues
- **API Status:** https://status.open.gsa.gov/

**Community:**
- **GSA Open Data:** https://open.gsa.gov/
- **GitHub Discussions:** https://github.com/GSA/sam_api/discussions

---

## Next Steps

### Sprint 2 (Week 2)
- [ ] Add USAspending.gov integration for contract history
- [ ] Implement Apollo.io enrichment provider
- [ ] Add Hunter.io as fallback enrichment

### Sprint 3 (Week 3)
- [ ] Canadian Company Capabilities (CCC) source
- [ ] Deduplication logic
- [ ] Performance optimization

## Architecture

```
src/vendor_ai_agent/
├── database/
│   ├── models.py         # SQLAlchemy models
│   ├── connection.py     # Database session management
│   └── cache.py          # API cache manager
├── sources/
│   ├── base.py           # BaseVendorSource protocol
│   ├── sam_entity.py     # SAM.gov integration (NEW)
│   └── static_directory.py
└── enrichment_providers/
    ├── base.py           # BaseEnrichmentProvider protocol
    └── static_contacts.py
```

## References

- [SAM.gov Entity Management API](https://open.gsa.gov/api/entity-api/)
- [NAICS Code Search](https://www.census.gov/naics/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
