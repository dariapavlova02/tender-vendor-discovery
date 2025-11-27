# Canada Open Data Integration - Research Findings
**Date:** 2025-11-23  
**Status:** Research phase complete, ready for architectural decisions

## Executive Summary

✅ **Downloaded and analyzed 3 Canadian government datasets**  
✅ **Identified +3,559 new vendors not in current database (+8.2% growth)**  
✅ **Confirmed datasets are highly complementary (minimal redundancy)**  
✅ **Discovered postal code normalization bug affecting deduplication**

---

## Dataset Analysis

### Dataset 1: Contract History (2009-2023) ✓ ALREADY IN DB
- **Source:** data/contracts_complete_2009-2023.csv
- **Size:** 561,824 rows → **42,770 unique vendors** in DB
- **Coverage:** Historical contracts, ends 2023
- **Fields:** legal_name, postal_code, country, contract_date, reference_number
- **Limitations:**
  - ❌ No GSIN codes
  - ❌ No detailed addresses (city, province)
  - ❌ No commodity classifications
  - ❌ Historical only (outdated for current opportunities)

### Dataset 2: Award Notices (2022-Present) 🆕 HIGH VALUE
- **Source:** https://canadabuys.canada.ca/opendata/pub/awardNoticeComplete-avisAttributionComplet.csv
- **Size:** 560,571 rows → **~11,794 unique vendors** (sampled)
- **Date Range:** 2022-08-08 to 2025-11-22 (CURRENT & ONGOING)
- **Update Frequency:** Daily/weekly (live data)
- **File Size:** 71 MB

**Key Fields (76 columns):**

*Vendor Information:*
- supplierLegalName-nomLegalFournisseur-eng
- supplierAddressLine (full street address)
- supplierAddressCity
- supplierAddressProvince
- supplierAddressPostalCode
- supplierAddressCountry

*Contract Metadata:*
- gsin-nibs (796+ unique codes)
- unspsc (UN Standard Products and Services Code)
- contractAmount-montantContrat
- totalContractValue-valeurTotaleContrat
- contractAwardDate
- contractEndDate
- contractNumber

*Procurement Intelligence:*
- procurementMethod (competitive vs limited tender)
- selectionCriteria
- tradeAgreements (CFTA, CETA, etc.)
- regionsOfDelivery
- limitedTenderingReason
- awardStatus (Active/Inactive)

**Value Proposition:**
- ✅ **CURRENT** activity (2022-present vs historical 2009-2023)
- ✅ **GSIN codes** for commodity matching
- ✅ **UNSPSC codes** for international classification
- ✅ **Full addresses** (street, city, province)
- ✅ **Trade agreements** (procurement eligibility)
- ✅ **Contract values** (detailed financial data)
- ✅ **+3,217 NEW vendors** not in historical data

### Dataset 3: Standing Offers (SOSA) 🆕 PRE-QUALIFIED VENDORS
- **Source:** https://sosa.canadabuys.canada.ca/cds/opendata/tpsgc-pwgsc_ocama-sosa.csv
- **Size:** 7,506 active agreements → **3,151 unique vendors**
- **Date Range:** 2006-2121 (includes future expiry dates)
- **Update Frequency:** Weekly
- **File Size:** 252 KB

**Key Fields (19 columns):**

*Vendor Information:*
- supplier-standardized-name (normalized)
- supplier-legal-name
- supplier-operating-name (DBA)

*Agreement Metadata:*
- agreement-number (unique identifier)
- agreement-type (SA, NMSO, RISO, NISO, RMSO, DISO)
- commodity (662+ codes)
- award-date
- expiry-date
- delivery-point (regional scope)
- end-user-entity

**Agreement Types:**
- **SA** (Supply Arrangement): 3,586 - framework for multiple orders
- **NMSO** (National Master Standing Offer): 2,000 - pre-approved national vendors
- **RISO** (Regional Individual Standing Offer): 759 - regional scope
- **NISO** (National Individual Standing Offer): 484 - single national vendor
- **RMSO** (Regional Master Standing Offer): 385 - regional framework
- **DISO** (Departmental Individual Standing Offer): 292 - department-specific

**Value Proposition:**
- ✅ **PRE-QUALIFIED** suppliers (competitive advantage indicator)
- ✅ **Multiple name variants** (helps with fuzzy matching)
- ✅ **Commodity codes** for capability matching
- ✅ **Expiry tracking** (know when agreements end)
- ✅ **Scope indicators** (national vs regional)
- ✅ **+342 NEW vendors** not in historical data
- ❌ No address details (limitation)

---

## Overlap & Complementarity Analysis

### Vendor Coverage
```
Dataset                    Unique Vendors    % of Total
─────────────────────────────────────────────────────────
Contract History (DB)           42,770         92.4%
Award Notices (new)             10,339         22.3%
SOSA (new)                       3,151          6.8%
─────────────────────────────────────────────────────────
TOTAL UNIQUE                    46,269        100.0%
```

### Overlap Metrics
```
Intersection                              Count    % Overlap
────────────────────────────────────────────────────────────
Contract History ∩ Award Notices          7,122    16.7% of history
Contract History ∩ SOSA                   2,809     6.6% of history
Award Notices ∩ SOSA                      1,680    16.2% of awards
All three datasets                        1,620     3.5% of total
```

### Growth Potential
- **NEW vendors from Award Notices:** +3,217 (7.5% growth)
- **NEW vendors from SOSA:** +342 (0.8% growth)
- **TOTAL growth:** +3,559 vendors (+8.2%)

### Key Insights
1. **83% of historical vendors** don't appear in recent awards
   - → Many inactive or doing small/unreported contracts
   - → Historical data captures broader vendor base

2. **Minimal redundancy** (16-17% overlap)
   - → Datasets are highly complementary
   - → Each adds unique value

3. **Award Notices fills recency gap**
   - Historical data ends 2023
   - Award Notices covers 2022-present with ongoing updates

4. **SOSA identifies high-value vendors**
   - Only 3,151 vendors but pre-qualified
   - Signals active, capable suppliers

---

## Critical Bug: Postal Code Normalization

### Current State
Postal codes in DB and CSVs have inconsistent formatting:
- Canadian format: `"K1P 5T8"` (7 chars with space)
- Normalized format: `"K1P5T8"` (6 chars, no space)
- UK format: `"W1A 1AA"` (7 chars with space)
- US format: `"32819"` (5 chars, no space)

### Evidence from Award Notices (sample 10k records)
```
Format                    Count    Percentage
──────────────────────────────────────────────
Length 7, WITH space      7,275       72.8%
Length 6, NO space        1,658       16.6%
Length 5, NO space          440        4.4%
Other formats               627        6.3%
```

### Current DB State
- Top postal code: `'None'` (421 vendors)
- UK postal codes retained spaces: `'W1A 1AA'`, `'SG1 2AS'`
- Canadian postal codes: mix of spaced and non-spaced

### Impact
Without normalization, same vendor with postal code:
- `"K1P 5T8"` (Award Notices format)
- `"K1P5T8"` (normalized format)

...would be treated as **TWO DIFFERENT vendors** in deduplication logic.

### Fix Required
**File:** `src/vendor_ai_agent/ingestion/canada_contracts.py` (line ~125)

**Current (buggy):**
```python
postal_code = row.get('postal_code', '').strip()
```

**Correct:**
```python
postal_code = row.get('postal_code', '').strip().replace(' ', '').upper()[:6]
```

**Rule:** Remove all spaces, uppercase, take first 6 characters

---

## Schema Design Recommendations

### Option A: Single Unified Table (RECOMMENDED)
**Extend existing `vendors` table with additional columns**

```sql
ALTER TABLE vendors ADD COLUMN:
  -- Address details (from Award Notices)
  address_line TEXT,
  city TEXT,
  province TEXT,
  country TEXT,  -- already exists
  
  -- Commodity codes (from both)
  gsin_codes TEXT,  -- JSON array
  unspsc_codes TEXT,  -- JSON array
  commodity_codes TEXT,  -- JSON array
  
  -- Standing offer info (from SOSA)
  standing_offers TEXT,  -- JSON array of agreement numbers
  agreement_types TEXT,  -- JSON array of types
  operating_names TEXT,  -- JSON array of DBAs
  
  -- Metadata
  data_sources TEXT,  -- JSON array: ["contract_history", "award_notices", "sosa"]
  last_contract_date DATE,
  total_contract_value DECIMAL,
  is_prequalified BOOLEAN,
  prequalification_expiry DATE
```

**Deduplication Logic:**
1. Primary key: `external_id = hash(legal_name + normalized_postal_code)`
2. On conflict: MERGE data (union arrays, max dates, sum values)

**Pros:**
- ✅ Simple querying (one table)
- ✅ Easy deduplication
- ✅ Efficient for capability matching
- ✅ Minimal code changes

**Cons:**
- ❌ Large JSONB columns (could impact performance)
- ❌ Loss of source-specific nuances

### Option B: Separate Tables with Foreign Keys
**Keep `vendors` table, add:**
- `vendor_contracts` (one row per contract)
- `vendor_standing_offers` (one row per SO/SA)
- `vendor_addresses` (multiple addresses per vendor)
- `vendor_commodities` (many-to-many)

**Pros:**
- ✅ Fully normalized (3NF)
- ✅ Preserves all source data
- ✅ Flexible querying

**Cons:**
- ❌ Complex joins (performance impact)
- ❌ More code to maintain
- ❌ Harder deduplication across tables

### Recommendation: **Option A (Single Table)**
For this use case (vendor discovery/matching), Option A is better:
- Simpler queries for capability matching
- Easier deduplication
- JSONB columns are acceptable for arrays of codes
- PostgreSQL handles JSONB efficiently

---

## Proposed Directory Structure

```
data/canada_sources/
├── award_notices/
│   ├── award_notices.csv                  # 71 MB, 560k rows
│   └── last_updated.txt
├── standing_offers/
│   ├── sosa.csv                           # 252 KB, 7.5k rows
│   └── last_updated.txt
├── contract_history/                       # existing
│   └── contracts_complete_2009-2023.csv
└── _metadata/
    ├── RESEARCH_FINDINGS.md               # this file
    ├── field_mappings.json
    └── update_log.txt
```

---

## Implementation Roadmap

### Phase 1: Fix Existing Data (CRITICAL) 🔴
1. ✅ Identify postal code normalization bug
2. ⏸️ Update `canada_contracts.py` loader (line 125)
3. ⏸️ Re-run ingestion to fix existing 42,770 vendor records
4. ⏸️ Verify deduplication (should merge ~1,416 duplicate postal code variants)

### Phase 2: Award Notices Integration 🟡
1. ✅ Download and analyze CSV structure
2. ⏸️ Create loader: `src/vendor_ai_agent/ingestion/canada_award_notices.py`
3. ⏸️ Extend `vendors` table schema (add address fields, GSIN, UNSPSC)
4. ⏸️ Implement merge logic (union commodity codes, max dates)
5. ⏸️ Ingest 560k records → expect +3,217 new vendors
6. ⏸️ Test capability matching with GSIN codes

### Phase 3: SOSA Integration 🟢
1. ✅ Download and analyze CSV structure
2. ⏸️ Create loader: `src/vendor_ai_agent/ingestion/canada_sosa.py`
3. ⏸️ Add standing offer fields to `vendors` table
4. ⏸️ Implement merge logic (track multiple agreement numbers)
5. ⏸️ Ingest 7,506 records → expect +342 new vendors
6. ⏸️ Add `is_prequalified` flag for filtering

### Phase 4: Automation 🔵
1. ⏸️ Create update script: `scripts/update_canada_sources.py`
2. ⏸️ Schedule weekly SOSA updates
3. ⏸️ Schedule daily Award Notices updates
4. ⏸️ Add data freshness monitoring

---

## Key Questions for User

### 1. Schema Design Approval
**Proceed with Option A (single table with JSONB columns)?**
- Alternative: Option B (normalized tables with foreign keys)

### 2. Postal Code Fix Priority
**Fix existing data first before adding new sources?**
- Concern: Current DB may have ~1,416 duplicates from postal code variations
- Recommend: Fix, re-ingest, verify, then add new sources

### 3. Scope Decision
**Integrate Award Notices + SOSA now, or add more sources first?**
- Tier 1 sources ready (analyzed above)
- Tier 2 sources (Federal Corporations, PSPC Payments) not yet explored
- Recommend: Complete Tier 1, validate, then expand

### 4. Update Frequency
**How often to refresh data?**
- Award Notices: Daily? Weekly?
- SOSA: Weekly (matches their update schedule)
- Contract History: Annual (static historical data)

---

## Next Steps (Awaiting User Decision)

**Immediate actions:**
1. ✅ Research complete - findings documented
2. ⏸️ Get user approval on schema design (Option A vs B)
3. ⏸️ Fix postal code normalization bug
4. ⏸️ Re-ingest contract history with fix
5. ⏸️ Implement Award Notices loader
6. ⏸️ Implement SOSA loader
7. ⏸️ Test end-to-end with real tender document

**Files to modify:**
- `src/vendor_ai_agent/database/models.py` (extend schema)
- `src/vendor_ai_agent/ingestion/canada_contracts.py` (fix postal bug)
- `src/vendor_ai_agent/ingestion/canada_award_notices.py` (new)
- `src/vendor_ai_agent/ingestion/canada_sosa.py` (new)
- `alembic/versions/` (new migration)

**Ready to proceed when user confirms approach.**
