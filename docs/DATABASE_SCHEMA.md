# Database Schema Reference

Complete documentation of the Vendor AI Agent database structure.

## Table of Contents

- [Overview](#overview)
- [Schema Diagram](#schema-diagram)
- [Tables](#tables)
  - [vendors](#vendors)
  - [vendor_naics](#vendor_naics)
  - [vendor_gsin](#vendor_gsin)
  - [vendor_unspsc](#vendor_unspsc)
  - [vendor_contacts](#vendor_contacts)
  - [api_cache](#api_cache)
- [Relationships](#relationships)
- [Indexes](#indexes)
- [Constraints](#constraints)
- [Migration History](#migration-history)
- [Query Examples](#query-examples)
- [Performance Considerations](#performance-considerations)

---

## Overview

The database schema supports:
- Multi-source vendor aggregation (SAM.gov, Canada, Apollo.io, etc.)
- Industry classification (NAICS, GSIN, UNSPSC codes)
- Contact information with multiple sources and verification
- Contract history tracking (U.S. and Canada)
- API response caching for performance
- Certification tracking (8(a), WOSB, SDVOSB, HUBZone, etc.)

**Database Support:**
- **PostgreSQL** (recommended for production)
- **SQLite** (development only)

**ORM:** SQLAlchemy 2.0 with declarative mapping

**Migrations:** Alembic

---

## Schema Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           vendors                                │
├─────────────────────────────────────────────────────────────────┤
│ PK  id                      INTEGER                              │
│     source                  VARCHAR(50)     NOT NULL  [indexed]  │
│     external_id             VARCHAR(255)    NOT NULL             │
│     uei                     VARCHAR(50)               [indexed]  │
│     duns                    VARCHAR(50)               [indexed]  │
│     cage_code               VARCHAR(20)               [indexed]  │
│     legal_name              VARCHAR(500)    NOT NULL  [indexed]  │
│     dba_name                VARCHAR(500)                         │
│     website                 VARCHAR(500)              [indexed]  │
│     country                 VARCHAR(2)                           │
│     state                   VARCHAR(50)                          │
│     city                    VARCHAR(200)                         │
│     address                 TEXT                                 │
│     postal_code             VARCHAR(20)                          │
│     business_types          JSON                                 │
│     is_small_business       BOOLEAN         NOT NULL  DEFAULT 0  │
│     is_woman_owned          BOOLEAN         NOT NULL  DEFAULT 0  │
│     is_veteran_owned        BOOLEAN         NOT NULL  DEFAULT 0  │
│     is_minority_owned       BOOLEAN         NOT NULL  DEFAULT 0  │
│     is_8a                   BOOLEAN         NOT NULL  DEFAULT 0  │
│     is_hubzone              BOOLEAN         NOT NULL  DEFAULT 0  │
│     employee_count_range    VARCHAR(50)                          │
│     total_contract_value    FLOAT                                │
│     contract_count          INTEGER                              │
│     first_contract_date     DATE                                 │
│     last_contract_date      DATE                                 │
│     contract_history_json   JSON                                 │
│     metadata_json           JSON                                 │
│     created_at              DATETIME        NOT NULL             │
│     updated_at              DATETIME        NOT NULL             │
│     last_enriched_at        DATETIME                             │
├─────────────────────────────────────────────────────────────────┤
│ UNIQUE (source, external_id)                                     │
│ INDEX (country, state, city)                                     │
│ INDEX (is_small_business, is_woman_owned, is_veteran_owned)     │
└─────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  vendor_naics    │       │   vendor_gsin    │       │ vendor_unspsc    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ PK id            │       │ PK id            │       │ PK id            │
│ FK vendor_id     │       │ FK vendor_id     │       │ FK vendor_id     │
│    naics_code    │       │    gsin_code     │       │    unspsc_code   │
│    description   │       │    description   │       │    description   │
│    is_primary    │       │    is_primary    │       │    is_primary    │
│    created_at    │       │    created_at    │       │    created_at    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ UNIQUE (vendor_  │       │ UNIQUE (vendor_  │       │ UNIQUE (vendor_  │
│  id, naics_code) │       │  id, gsin_code)  │       │  id, unspsc_code)│
└──────────────────┘       └──────────────────┘       └──────────────────┘

        ┌───────────────────────────┘
        │
        ▼
┌──────────────────────────────────┐
│      vendor_contacts             │
├──────────────────────────────────┤
│ PK  id                INTEGER    │
│ FK  vendor_id         INTEGER    │
│     source            VARCHAR(50)│
│     first_name        VARCHAR    │
│     last_name         VARCHAR    │
│     title             VARCHAR    │
│     email             VARCHAR    │
│     phone             VARCHAR    │
│     is_verified       BOOLEAN    │
│     confidence_score  INTEGER    │
│     metadata_json     JSON       │
│     created_at        DATETIME   │
│     updated_at        DATETIME   │
├──────────────────────────────────┤
│ INDEX (vendor_id, email)         │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│         api_cache                │
├──────────────────────────────────┤
│ PK  id                INTEGER    │
│     source            VARCHAR(50)│
│     cache_key         VARCHAR    │
│     response_data     JSON       │
│     created_at        DATETIME   │
│     expires_at        DATETIME   │
│     hit_count         INTEGER    │
│     last_accessed_at  DATETIME   │
├──────────────────────────────────┤
│ UNIQUE (source, cache_key)       │
│ INDEX (source, expires_at)       │
└──────────────────────────────────┘
```

---

## Tables

### vendors

Main vendor registry aggregating data from multiple sources.

**Purpose:** Store vendor/company information from SAM.gov, Canada contracts, Apollo.io, and other sources.

**Table:** `vendors`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `source` | VARCHAR(50) | NO | - | Data source: `sam_entity`, `canada_contracts`, `apollo_search`, `serper_search`, `static_directory` |
| `external_id` | VARCHAR(255) | NO | - | Source-specific unique identifier (UEI, BN, company ID) |
| `uei` | VARCHAR(50) | YES | NULL | Unique Entity Identifier (SAM.gov) |
| `duns` | VARCHAR(50) | YES | NULL | DUNS number (legacy identifier) |
| `cage_code` | VARCHAR(20) | YES | NULL | Commercial and Government Entity code |
| `legal_name` | VARCHAR(500) | NO | - | Legal business name |
| `dba_name` | VARCHAR(500) | YES | NULL | "Doing business as" name |
| `website` | VARCHAR(500) | YES | NULL | Company website URL |
| `country` | VARCHAR(2) | YES | NULL | ISO 3166-1 alpha-2 country code (US, CA) |
| `state` | VARCHAR(50) | YES | NULL | State/province code |
| `city` | VARCHAR(200) | YES | NULL | City name |
| `address` | TEXT | YES | NULL | Full street address |
| `postal_code` | VARCHAR(20) | YES | NULL | ZIP/postal code |
| `business_types` | JSON | YES | NULL | Array of business type codes |
| `is_small_business` | BOOLEAN | NO | false | SBA small business certified |
| `is_woman_owned` | BOOLEAN | NO | false | Woman-owned small business (WOSB) |
| `is_veteran_owned` | BOOLEAN | NO | false | Veteran-owned small business (VOSB/SDVOSB) |
| `is_minority_owned` | BOOLEAN | NO | false | Minority-owned business |
| `is_8a` | BOOLEAN | NO | false | SBA 8(a) Business Development program |
| `is_hubzone` | BOOLEAN | NO | false | Historically Underutilized Business Zone |
| `employee_count_range` | VARCHAR(50) | YES | NULL | Employee count range (e.g., "50-100", "500-1000") |
| `total_contract_value` | FLOAT | YES | NULL | Total value of all contracts (USD/CAD) |
| `contract_count` | INTEGER | YES | NULL | Number of contracts awarded |
| `first_contract_date` | DATE | YES | NULL | Date of first contract award |
| `last_contract_date` | DATE | YES | NULL | Date of most recent contract award |
| `contract_history_json` | JSON | YES | NULL | Array of contract records |
| `metadata_json` | JSON | YES | NULL | Source-specific metadata (flexible storage) |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Record creation timestamp |
| `updated_at` | DATETIME | NO | CURRENT_TIMESTAMP | Last update timestamp |
| `last_enriched_at` | DATETIME | YES | NULL | Last contact enrichment timestamp |

**Indexes:**
- `ix_vendors_source` on (`source`)
- `ix_vendors_uei` on (`uei`)
- `ix_vendors_duns` on (`duns`)
- `ix_vendors_cage_code` on (`cage_code`)
- `ix_vendors_legal_name` on (`legal_name`)
- `ix_vendors_website` on (`website`)
- `ix_vendor_location` on (`country`, `state`, `city`)
- `ix_vendor_certifications` on (`is_small_business`, `is_woman_owned`, `is_veteran_owned`)

**Constraints:**
- `uq_vendor_source_external_id` UNIQUE (`source`, `external_id`)

**Relationships:**
- One-to-many with `vendor_naics` (NAICS codes)
- One-to-many with `vendor_gsin` (GSIN codes)
- One-to-many with `vendor_unspsc` (UNSPSC codes)
- One-to-many with `vendor_contacts` (contacts)

**Example Data:**

```sql
INSERT INTO vendors (
    source, external_id, legal_name, country, state, city,
    is_small_business, is_8a, total_contract_value, contract_count
) VALUES (
    'sam_entity',
    'ABC123XYZ456',
    'ACME Defense Solutions Inc.',
    'US',
    'VA',
    'Arlington',
    true,
    true,
    15000000.00,
    12
);
```

---

### vendor_naics

NAICS (North American Industry Classification System) codes for vendors.

**Purpose:** Store industry classification codes for U.S. and Canadian vendors.

**Table:** `vendor_naics`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `vendor_id` | INTEGER | NO | - | Foreign key to `vendors.id` |
| `naics_code` | VARCHAR(10) | NO | - | 2-6 digit NAICS code |
| `naics_description` | VARCHAR(500) | YES | NULL | Human-readable description |
| `is_primary` | BOOLEAN | NO | false | Primary NAICS for this vendor |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes:**
- `ix_vendor_naics_vendor_id` on (`vendor_id`)
- `ix_vendor_naics_naics_code` on (`naics_code`)
- `ix_vendor_naics_lookup` on (`naics_code`, `vendor_id`)

**Constraints:**
- `uq_vendor_naics` UNIQUE (`vendor_id`, `naics_code`)
- `fk_vendor_naics_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors(id)` ON DELETE CASCADE

**Relationships:**
- Many-to-one with `vendors`

**NAICS Code Examples:**

| Code | Description |
|------|-------------|
| `541330` | Engineering Services |
| `541512` | Computer Systems Design Services |
| `541519` | Other Computer Related Services |
| `336411` | Aircraft Manufacturing |
| `325920` | Explosives Manufacturing |

**Example Data:**

```sql
INSERT INTO vendor_naics (vendor_id, naics_code, naics_description, is_primary)
VALUES (1, '541330', 'Engineering Services', true);

INSERT INTO vendor_naics (vendor_id, naics_code, naics_description, is_primary)
VALUES (1, '541512', 'Computer Systems Design Services', false);
```

---

### vendor_gsin

GSIN (Goods and Services Identification Number) codes for Canadian vendors.

**Purpose:** Store Canadian government goods/services classification codes.

**Table:** `vendor_gsin`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `vendor_id` | INTEGER | NO | - | Foreign key to `vendors.id` |
| `gsin_code` | VARCHAR(10) | NO | - | 5-digit GSIN code |
| `gsin_description` | VARCHAR(500) | YES | NULL | Human-readable description |
| `is_primary` | BOOLEAN | NO | false | Primary GSIN for this vendor |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes:**
- `ix_vendor_gsin_vendor_id` on (`vendor_id`)
- `ix_vendor_gsin_gsin_code` on (`gsin_code`)
- `ix_vendor_gsin_lookup` on (`gsin_code`, `vendor_id`)

**Constraints:**
- `uq_vendor_gsin` UNIQUE (`vendor_id`, `gsin_code`)
- `fk_vendor_gsin_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors(id)` ON DELETE CASCADE

**Relationships:**
- Many-to-one with `vendors`

**GSIN Code Examples:**

| Code | Description |
|------|-------------|
| `D7210` | Ordnance and Ammunition |
| `T008` | Professional Engineering Services |
| `N6810` | Computer Equipment and Accessories |

**Example Data:**

```sql
INSERT INTO vendor_gsin (vendor_id, gsin_code, gsin_description, is_primary)
VALUES (2, 'D7210', 'Ordnance and Ammunition', true);
```

---

### vendor_unspsc

UNSPSC (United Nations Standard Products and Services Code) codes for vendors.

**Purpose:** Store international product/service classification codes.

**Table:** `vendor_unspsc`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `vendor_id` | INTEGER | NO | - | Foreign key to `vendors.id` |
| `unspsc_code` | VARCHAR(10) | NO | - | 8-digit UNSPSC code |
| `unspsc_description` | VARCHAR(500) | YES | NULL | Human-readable description |
| `is_primary` | BOOLEAN | NO | false | Primary UNSPSC for this vendor |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes:**
- `ix_vendor_unspsc_vendor_id` on (`vendor_id`)
- `ix_vendor_unspsc_unspsc_code` on (`unspsc_code`)
- `ix_vendor_unspsc_lookup` on (`unspsc_code`, `vendor_id`)

**Constraints:**
- `uq_vendor_unspsc` UNIQUE (`vendor_id`, `unspsc_code`)
- `fk_vendor_unspsc_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors(id)` ON DELETE CASCADE

**Relationships:**
- Many-to-one with `vendors`

**UNSPSC Code Examples:**

| Code | Description |
|------|-------------|
| `43211500` | Pistols and Revolvers |
| `81111500` | Engineering Services |
| `43191500` | Tactical Vehicles |

**Example Data:**

```sql
INSERT INTO vendor_unspsc (vendor_id, unspsc_code, unspsc_description, is_primary)
VALUES (2, '43211500', 'Pistols and Revolvers', true);
```

---

### vendor_contacts

Contact information for vendor representatives.

**Purpose:** Store contact details from multiple sources (Apollo, Hunter, web scraping, Google Maps).

**Table:** `vendor_contacts`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `vendor_id` | INTEGER | NO | - | Foreign key to `vendors.id` |
| `source` | VARCHAR(50) | NO | - | Contact source: `apollo`, `hunter`, `scraper`, `google_maps`, `duckduckgo`, `serper`, `static_contacts` |
| `first_name` | VARCHAR(200) | YES | NULL | Contact first name |
| `last_name` | VARCHAR(200) | YES | NULL | Contact last name |
| `title` | VARCHAR(200) | YES | NULL | Job title/position |
| `email` | VARCHAR(255) | YES | NULL | Email address |
| `phone` | VARCHAR(50) | YES | NULL | Phone number |
| `is_verified` | BOOLEAN | NO | false | Email/phone verified by provider |
| `confidence_score` | INTEGER | YES | NULL | Confidence score (0-100) |
| `metadata_json` | JSON | YES | NULL | Source-specific metadata |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Record creation timestamp |
| `updated_at` | DATETIME | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:**
- `ix_vendor_contacts_vendor_id` on (`vendor_id`)
- `ix_vendor_contacts_email` on (`email`)
- `ix_vendor_contact_email` on (`vendor_id`, `email`)

**Constraints:**
- `fk_vendor_contacts_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors(id)` ON DELETE CASCADE

**Relationships:**
- Many-to-one with `vendors`

**Contact Sources:**

| Source | Description | Verification |
|--------|-------------|--------------|
| `apollo` | Apollo.io API | High (verified emails) |
| `hunter` | Hunter.io API | High (email verification) |
| `google_maps` | Google Maps API | Medium (business listings) |
| `scraper` | Website scraping | Low (unverified) |
| `duckduckgo` | DuckDuckGo search | Low (unverified) |
| `serper` | Google Search API | Low (unverified) |
| `static_contacts` | Pre-loaded contacts | Varies |

**Example Data:**

```sql
INSERT INTO vendor_contacts (
    vendor_id, source, first_name, last_name, title, email, phone,
    is_verified, confidence_score
) VALUES (
    1,
    'apollo',
    'John',
    'Smith',
    'Director of Government Contracts',
    'john.smith@acme-defense.com',
    '+1-703-555-1234',
    true,
    95
);
```

---

### api_cache

Cache for external API responses.

**Purpose:** Cache API responses to reduce costs and improve performance.

**Table:** `api_cache`

**Columns:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key |
| `source` | VARCHAR(50) | NO | - | API source: `sam_entity`, `apollo`, `hunter`, `google_maps`, `serper` |
| `cache_key` | VARCHAR(500) | NO | - | Unique cache key (hashed query) |
| `response_data` | JSON | NO | - | Cached API response |
| `created_at` | DATETIME | NO | CURRENT_TIMESTAMP | Cache creation timestamp |
| `expires_at` | DATETIME | NO | - | Cache expiration timestamp |
| `hit_count` | INTEGER | NO | 0 | Number of cache hits |
| `last_accessed_at` | DATETIME | NO | CURRENT_TIMESTAMP | Last access timestamp |

**Indexes:**
- `ix_api_cache_source` on (`source`)
- `ix_api_cache_created_at` on (`created_at`)
- `ix_api_cache_expires_at` on (`expires_at`)
- `ix_api_cache_expiry` on (`source`, `expires_at`)

**Constraints:**
- `uq_api_cache_source_key` UNIQUE (`source`, `cache_key`)

**Cache TTL by Source:**

| Source | Default TTL | Rationale |
|--------|------------|-----------|
| `sam_entity` | 30 days | SAM.gov data updates monthly |
| `apollo` | 90 days | Contact data stable over time |
| `hunter` | 90 days | Email verification rarely changes |
| `google_maps` | 90 days | Business listings stable |
| `serper` | 7 days | Search results change frequently |

**Example Data:**

```sql
INSERT INTO api_cache (
    source, cache_key, response_data,
    created_at, expires_at, hit_count
) VALUES (
    'apollo',
    'company:acme-defense-solutions',
    '{"company": {"name": "ACME Defense Solutions", ...}}',
    '2025-01-01 10:00:00',
    '2025-04-01 10:00:00',
    5
);
```

---

## Relationships

### Entity Relationship Summary

```
vendors (1) ─────────< (N) vendor_naics
vendors (1) ─────────< (N) vendor_gsin
vendors (1) ─────────< (N) vendor_unspsc
vendors (1) ─────────< (N) vendor_contacts

api_cache (independent, no foreign keys)
```

**Cascade Behavior:**

All child tables use `ON DELETE CASCADE`:
- Deleting a vendor automatically deletes all related NAICS, GSIN, UNSPSC codes and contacts
- This prevents orphaned records

**ORM Relationships (SQLAlchemy):**

```python
class Vendor(Base):
    naics_codes: Mapped[list["VendorNAICS"]] = relationship(
        "VendorNAICS", back_populates="vendor", cascade="all, delete-orphan"
    )
    gsin_codes: Mapped[list["VendorGSIN"]] = relationship(
        "VendorGSIN", back_populates="vendor", cascade="all, delete-orphan"
    )
    unspsc_codes: Mapped[list["VendorUNSPSC"]] = relationship(
        "VendorUNSPSC", back_populates="vendor", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["VendorContact"]] = relationship(
        "VendorContact", back_populates="vendor", cascade="all, delete-orphan"
    )

class VendorNAICS(Base):
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="naics_codes")
```

---

## Indexes

### Purpose of Each Index

**vendors table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_vendors_source` | `source` | Filter by data source |
| `ix_vendors_uei` | `uei` | Lookup by SAM.gov UEI |
| `ix_vendors_duns` | `duns` | Lookup by DUNS number |
| `ix_vendors_cage_code` | `cage_code` | Lookup by CAGE code |
| `ix_vendors_legal_name` | `legal_name` | Search by company name |
| `ix_vendors_website` | `website` | Lookup by website |
| `ix_vendor_location` | `country`, `state`, `city` | Geographic filtering |
| `ix_vendor_certifications` | `is_small_business`, `is_woman_owned`, `is_veteran_owned` | Set-aside filtering |

**vendor_naics table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_vendor_naics_vendor_id` | `vendor_id` | Join to vendors |
| `ix_vendor_naics_naics_code` | `naics_code` | Search by NAICS code |
| `ix_vendor_naics_lookup` | `naics_code`, `vendor_id` | Composite lookup |

**vendor_gsin table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_vendor_gsin_vendor_id` | `vendor_id` | Join to vendors |
| `ix_vendor_gsin_gsin_code` | `gsin_code` | Search by GSIN code |
| `ix_vendor_gsin_lookup` | `gsin_code`, `vendor_id` | Composite lookup |

**vendor_unspsc table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_vendor_unspsc_vendor_id` | `vendor_id` | Join to vendors |
| `ix_vendor_unspsc_unspsc_code` | `unspsc_code` | Search by UNSPSC code |
| `ix_vendor_unspsc_lookup` | `unspsc_code`, `vendor_id` | Composite lookup |

**vendor_contacts table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_vendor_contacts_vendor_id` | `vendor_id` | Join to vendors |
| `ix_vendor_contacts_email` | `email` | Search by email |
| `ix_vendor_contact_email` | `vendor_id`, `email` | Composite lookup |

**api_cache table:**

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_api_cache_source` | `source` | Filter by API source |
| `ix_api_cache_created_at` | `created_at` | Sort by creation time |
| `ix_api_cache_expires_at` | `expires_at` | Cleanup expired cache |
| `ix_api_cache_expiry` | `source`, `expires_at` | Composite cleanup |

---

## Constraints

### Unique Constraints

**vendors:**
- `uq_vendor_source_external_id` on (`source`, `external_id`)
  - **Purpose:** Prevent duplicate vendors from same source
  - **Example:** Cannot insert two `sam_entity` vendors with same UEI

**vendor_naics:**
- `uq_vendor_naics` on (`vendor_id`, `naics_code`)
  - **Purpose:** Prevent duplicate NAICS codes per vendor
  - **Example:** Vendor cannot have NAICS `541330` listed twice

**vendor_gsin:**
- `uq_vendor_gsin` on (`vendor_id`, `gsin_code`)
  - **Purpose:** Prevent duplicate GSIN codes per vendor

**vendor_unspsc:**
- `uq_vendor_unspsc` on (`vendor_id`, `unspsc_code`)
  - **Purpose:** Prevent duplicate UNSPSC codes per vendor

**api_cache:**
- `uq_api_cache_source_key` on (`source`, `cache_key`)
  - **Purpose:** Prevent duplicate cache entries
  - **Example:** Cannot cache same Apollo query twice

### Foreign Key Constraints

All child tables have foreign key constraints with `ON DELETE CASCADE`:

```sql
ALTER TABLE vendor_naics
ADD CONSTRAINT fk_vendor_naics_vendor_id
FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE;

ALTER TABLE vendor_gsin
ADD CONSTRAINT fk_vendor_gsin_vendor_id
FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE;

ALTER TABLE vendor_unspsc
ADD CONSTRAINT fk_vendor_unspsc_vendor_id
FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE;

ALTER TABLE vendor_contacts
ADD CONSTRAINT fk_vendor_contacts_vendor_id
FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE;
```

---

## Migration History

### Migration 1: Initial Schema
**Revision:** `6b4ee64b05c3`  
**Date:** 2025-11-22  
**Description:** Initial schema with vendors, NAICS, contacts, and API cache

**Created Tables:**
- `vendors` (basic fields, no contract history)
- `vendor_naics`
- `vendor_contacts`
- `api_cache`

**Key Features:**
- Multi-source vendor support
- NAICS classification
- Contact tracking
- API response caching

---

### Migration 2: Canada Contracts Support
**Revision:** `d8dfe206ccc1`  
**Date:** 2025-11-23  
**Parent:** `6b4ee64b05c3`  
**Description:** Add Canada contracts support - GSIN, UNSPSC, contract history

**Created Tables:**
- `vendor_gsin` (Canadian goods/services codes)
- `vendor_unspsc` (International product/service codes)

**Added Columns to `vendors`:**
- `employee_count_range` VARCHAR(50)
- `total_contract_value` FLOAT
- `contract_count` INTEGER
- `first_contract_date` DATE
- `last_contract_date` DATE
- `contract_history_json` JSON

**Purpose:** Enable Canada contract tracking and classification

---

### Running Migrations

**Upgrade to Latest:**
```bash
alembic upgrade head
```

**Downgrade One Version:**
```bash
alembic downgrade -1
```

**View Current Version:**
```bash
alembic current
```

**View Migration History:**
```bash
alembic history --verbose
```

**Create New Migration:**
```bash
alembic revision --autogenerate -m "Description of changes"
```

---

## Query Examples

### Find Vendors by NAICS Code

```sql
SELECT v.id, v.legal_name, v.state, v.city
FROM vendors v
JOIN vendor_naics vn ON v.id = vn.vendor_id
WHERE vn.naics_code = '541330'
AND v.is_small_business = true
ORDER BY v.total_contract_value DESC
LIMIT 100;
```

---

### Find Local Small Businesses with Contacts

```sql
SELECT 
    v.legal_name,
    v.city,
    v.state,
    vc.first_name,
    vc.last_name,
    vc.email,
    vc.phone
FROM vendors v
JOIN vendor_contacts vc ON v.id = vc.vendor_id
WHERE v.state = 'VA'
AND v.is_small_business = true
AND vc.is_verified = true
ORDER BY v.legal_name;
```

---

### Find 8(a) Vendors with Contract History

```sql
SELECT 
    v.legal_name,
    v.state,
    v.total_contract_value,
    v.contract_count,
    v.last_contract_date
FROM vendors v
WHERE v.is_8a = true
AND v.contract_count > 0
ORDER BY v.last_contract_date DESC
LIMIT 50;
```

---

### Find Vendors by GSIN Code (Canada)

```sql
SELECT v.id, v.legal_name, vg.gsin_code, vg.gsin_description
FROM vendors v
JOIN vendor_gsin vg ON v.id = vg.vendor_id
WHERE vg.gsin_code = 'D7210'
AND v.country = 'CA'
ORDER BY v.legal_name;
```

---

### Count Vendors by Source

```sql
SELECT 
    source,
    COUNT(*) as vendor_count,
    COUNT(DISTINCT uei) as unique_uei_count
FROM vendors
GROUP BY source
ORDER BY vendor_count DESC;
```

---

### Find Duplicate Vendors (Same Name, Different Sources)

```sql
SELECT 
    legal_name,
    COUNT(*) as source_count,
    STRING_AGG(source, ', ') as sources
FROM vendors
GROUP BY legal_name
HAVING COUNT(*) > 1
ORDER BY source_count DESC;
```

---

### Cache Hit Rate by Source

```sql
SELECT 
    source,
    COUNT(*) as total_entries,
    AVG(hit_count) as avg_hits,
    SUM(hit_count) as total_hits
FROM api_cache
WHERE expires_at > NOW()
GROUP BY source
ORDER BY total_hits DESC;
```

---

### Find Vendors with Multiple NAICS Codes

```sql
SELECT 
    v.legal_name,
    COUNT(vn.id) as naics_count,
    STRING_AGG(vn.naics_code, ', ') as naics_codes
FROM vendors v
JOIN vendor_naics vn ON v.id = vn.vendor_id
GROUP BY v.id, v.legal_name
HAVING COUNT(vn.id) > 1
ORDER BY naics_count DESC;
```

---

### Enrichment Coverage Report

```sql
SELECT 
    v.source,
    COUNT(*) as total_vendors,
    COUNT(vc.id) as vendors_with_contacts,
    ROUND(COUNT(vc.id)::numeric / COUNT(*)::numeric * 100, 2) as contact_coverage_pct
FROM vendors v
LEFT JOIN vendor_contacts vc ON v.id = vc.vendor_id
GROUP BY v.source
ORDER BY contact_coverage_pct DESC;
```

---

### Most Active Vendors (Contract History)

```sql
SELECT 
    legal_name,
    state,
    contract_count,
    total_contract_value,
    last_contract_date,
    (total_contract_value / NULLIF(contract_count, 0)) as avg_contract_value
FROM vendors
WHERE contract_count > 0
ORDER BY contract_count DESC, total_contract_value DESC
LIMIT 100;
```

---

## Performance Considerations

### Index Maintenance

**Analyze Tables Regularly:**
```sql
ANALYZE vendors;
ANALYZE vendor_naics;
ANALYZE vendor_contacts;
```

**Check Index Usage:**
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

---

### Query Optimization Tips

**1. Always Use Indexes for Filtering:**

❌ **Bad:**
```sql
SELECT * FROM vendors WHERE LOWER(legal_name) LIKE '%acme%';
```

✅ **Good:**
```sql
SELECT * FROM vendors WHERE legal_name ILIKE 'ACME%';
```

**2. Use Composite Indexes for Joins:**

❌ **Bad:**
```sql
SELECT * FROM vendor_naics WHERE naics_code = '541330';
```

✅ **Good (uses composite index):**
```sql
SELECT * 
FROM vendor_naics vn
JOIN vendors v ON vn.vendor_id = v.id
WHERE vn.naics_code = '541330';
```

**3. Limit Result Sets:**

❌ **Bad:**
```sql
SELECT * FROM vendors;
```

✅ **Good:**
```sql
SELECT * FROM vendors LIMIT 1000;
```

**4. Use JOINs Instead of Subqueries:**

❌ **Bad:**
```sql
SELECT * FROM vendors 
WHERE id IN (SELECT vendor_id FROM vendor_contacts WHERE email LIKE '%@example.com');
```

✅ **Good:**
```sql
SELECT DISTINCT v.* 
FROM vendors v
JOIN vendor_contacts vc ON v.id = vc.vendor_id
WHERE vc.email LIKE '%@example.com';
```

---

### Cache Management

**Clean Expired Cache Entries:**
```sql
DELETE FROM api_cache WHERE expires_at < NOW();
```

**Clean Low-Hit Cache Entries:**
```sql
DELETE FROM api_cache 
WHERE hit_count < 2 
AND created_at < NOW() - INTERVAL '30 days';
```

**Vacuum After Large Deletes:**
```sql
VACUUM ANALYZE api_cache;
```

---

### Scaling Considerations

**Connection Pooling:**
- Use connection pooling (PgBouncer, SQLAlchemy pool)
- Recommended pool size: `2 * num_workers`

**Read Replicas:**
- Use read replicas for reporting queries
- Direct writes to primary database
- Use `api_cache` to reduce API call load

**Partitioning (Future):**
- Consider partitioning `vendors` by `source` if table grows > 10M rows
- Consider partitioning `api_cache` by `created_at` (monthly partitions)

**Archiving:**
- Archive old API cache entries (> 1 year)
- Archive inactive vendors (no recent contracts)

---

## Related Documentation

- **[Configuration Reference](CONFIGURATION.md)**: Database configuration options
- **[API Reference](API_REFERENCE.md)**: Database connection and cache manager APIs
- **[Data Models](DATA_MODELS.md)**: Python dataclass models (VendorRecord, etc.)

---

**Last Updated:** 2025-01-24  
**Version:** 1.0.0  
**Schema Version:** `d8dfe206ccc1` (Migration 2)
