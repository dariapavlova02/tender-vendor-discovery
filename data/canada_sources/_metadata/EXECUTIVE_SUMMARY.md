# Canada Open Data Integration - Executive Summary
**Research Phase Complete** | **Awaiting Architectural Decision**

## 📊 What We Discovered

### Current State
- **Database:** 42,770 unique vendors from contract history (2009-2023)
- **Bug Found:** Postal code normalization missing (causing potential duplicates)
- **New Sources:** Downloaded 2 additional datasets (71 MB + 252 KB)

### Growth Potential
```
Dataset                Vendors    Status
─────────────────────────────────────────────────
Contract History       42,770     ✅ In DB
Award Notices (new)    +3,217     ⏸️ Ready to add
SOSA (new)               +342     ⏸️ Ready to add
─────────────────────────────────────────────────
TOTAL                  46,329     +8.2% growth
```

### Data Quality
- **83% of historical vendors** are inactive (not in recent awards)
- **16-17% overlap** between datasets → highly complementary
- **Award Notices** adds CURRENT activity (2022-present)
- **SOSA** identifies PRE-QUALIFIED vendors

---

## 🚨 Critical Issue: Postal Code Bug

**Problem:** Postal codes not normalized before deduplication
- Award Notices format: `"K1P 5T8"` (with space)
- Some DB records: `"K1P5T8"` (no space)
- **Result:** Same vendor counted twice

**Fix Required:** 1 line change in `canada_contracts.py:125`
```python
# Current (buggy)
postal_code = row.get('postal_code', '').strip()

# Fixed
postal_code = row.get('postal_code', '').strip().replace(' ', '').upper()[:6]
```

**Impact:** Must fix before adding new sources (or duplicates will persist)

---

## 🎯 Key Decision Required

### Schema Design: Option A vs Option B

#### ✅ Option A: Single Table (RECOMMENDED)
**Extend existing `vendors` table with new columns**

**Pros:**
- Simple queries (one table)
- Easy deduplication
- Minimal code changes
- Fast capability matching

**Cons:**
- JSONB columns for arrays (commodity codes, agreements)
- Some source-specific details in JSON

**New columns needed:** 14 fields
- Address: `address_line`, `city`, `province`
- Codes: `gsin_codes`, `unspsc_codes`, `commodity_codes`
- Offers: `standing_offers`, `agreement_types`, `operating_names`
- Meta: `data_sources`, `last_contract_date`, `total_contract_value`
- Flags: `is_prequalified`, `prequalification_expiry`

#### ⚠️ Option B: Normalized Tables
**Create separate tables with foreign keys**

**Tables:**
- `vendors` (core info)
- `vendor_contracts` (one row per contract)
- `vendor_standing_offers` (one row per SO/SA)
- `vendor_addresses` (multiple addresses)
- `vendor_commodities` (many-to-many)

**Pros:**
- Fully normalized (3NF)
- Preserves all source details

**Cons:**
- Complex joins (performance)
- More code to maintain
- Harder deduplication

---

## 📋 Recommended Implementation Plan

### Phase 1: Fix Foundation (1-2 hours)
1. Fix postal code normalization bug
2. Re-ingest contract history with fix
3. Verify deduplication works

### Phase 2: Extend Schema (2-3 hours)
1. Create Alembic migration (add 14 columns)
2. Run migration on database
3. Update `models.py`

### Phase 3: Award Notices Integration (4-6 hours)
1. Create loader: `canada_award_notices.py`
2. Implement merge logic (union arrays, max dates)
3. Ingest 560k records
4. Verify +3,217 new vendors added

### Phase 4: SOSA Integration (2-3 hours)
1. Create loader: `canada_sosa.py`
2. Implement merge logic (track agreements)
3. Ingest 7,506 records
4. Verify +342 new vendors added

### Phase 5: Validation (1-2 hours)
1. Test capability matching with GSIN codes
2. Test pre-qualified vendor filtering
3. Run full pipeline on real tender
4. Document update procedures

**Total Effort:** 10-16 hours

---

## 💡 What New Data Enables

### Before (Contract History Only)
- Historical vendor names and postal codes
- Contract dates (outdated)
- No commodity codes
- No address details

### After (All 3 Sources)
✅ **CURRENT** vendor activity (2022-present)  
✅ **GSIN/UNSPSC codes** for capability matching  
✅ **Full addresses** (street, city, province)  
✅ **Pre-qualification status** (competitive advantage)  
✅ **Contract values** (financial data)  
✅ **Trade agreements** (eligibility info)  
✅ **Agreement expiry dates** (opportunity timing)

---

## ❓ Questions for User

### 1. Schema Design
**Approve Option A (single table with JSONB columns)?**
- [ ] Yes, proceed with Option A
- [ ] No, use Option B (normalized tables)
- [ ] Need more information

### 2. Priority Order
**Fix postal bug first, then add new sources?**
- [ ] Yes, fix foundation first (recommended)
- [ ] No, add new sources with bug present (not recommended)

### 3. Scope
**Integrate Award Notices + SOSA now, or explore more sources?**
- [ ] Yes, integrate these 2 sources (Tier 1 complete)
- [ ] No, research Tier 2 sources first (Federal Corporations, etc.)

### 4. Update Automation
**How often to refresh data?**
- [ ] Award Notices: Daily
- [ ] Award Notices: Weekly
- [ ] SOSA: Weekly (matches their schedule)
- [ ] Manual updates only

---

## 📂 Files Ready for Implementation

### Research Complete ✅
- `data/canada_sources/award_notices/award_notices.csv` (71 MB)
- `data/canada_sources/standing_offers/sosa.csv` (252 KB)
- `data/canada_sources/_metadata/RESEARCH_FINDINGS.md`
- `data/canada_sources/_metadata/field_mappings.json`

### Files to Modify ⏸️
- `src/vendor_ai_agent/database/models.py` (extend schema)
- `src/vendor_ai_agent/ingestion/canada_contracts.py` (fix line 125)
- `alembic/versions/` (new migration)

### Files to Create ⏸️
- `src/vendor_ai_agent/ingestion/canada_award_notices.py`
- `src/vendor_ai_agent/ingestion/canada_sosa.py`
- `scripts/update_canada_sources.py` (automation)

---

## 🚀 Next Step

**Awaiting your decision on:**
1. Schema design (Option A vs B)
2. Priority (fix bug first vs add sources)
3. Scope (Tier 1 only vs explore more)

**Once approved, ready to implement in ~10-16 hours of work.**
