# Contract-Type-Aware Search: Quick Implementation Guide

## The Problem

**Current behavior:** System extracts atomic nouns (salt, equipment, training) → searches for salt suppliers instead of grounds maintenance contractors

**Result:** 11.9% enrichment success rate (5/42 vendors relevant in Waterloo test)

**Root cause:** No understanding of what vendors must **deliver** vs what they **use**

## The Solution: 3-Step Classification

```
TENDER → [1. Classify Contract Type] → [2. Identify Deliverables vs Inputs] → [3. Generate Role-Appropriate Queries]
```

### Step 1: Classify Contract Type

```
SERVICE    → vendor performs work (maintenance, cleaning, security)
PRODUCT    → vendor delivers items (equipment, materials, goods)
HYBRID     → vendor supplies AND installs (turnkey solutions)
CONSULTING → vendor provides advisory/design/training
```

### Step 2: Distinguish Procurement Targets vs Vendor Inputs

```
PROCUREMENT TARGET = what buyer purchases → SEARCH FOR THESE
VENDOR INPUTS      = what vendor uses      → DON'T SEARCH FOR THESE

Example: "Contractor shall provide grounds maintenance using salt"
✓ Search: "grounds maintenance contractors"
✗ DON'T search: "salt suppliers" (salt is contractor's INPUT)
```

### Step 3: Generate Contract-Type-Aware Queries

**Service Contracts:**
- 85% contractor/service provider queries
- 0% manufacturer queries

**Product Contracts:**
- 40% manufacturer/OEM queries
- 30% distributor queries

**Hybrid Contracts:**
- 50% full-service provider queries
- 25% manufacturer with installation

**Consulting Contracts:**
- 70% consultant/advisory queries
- 0% manufacturer queries

## Implementation Checklist

### Phase 1: Code Changes (2-3 hours)

#### File 1: `src/vendor_ai_agent/modules/tender_profiler.py`

- [ ] **Lines 13-23:** Add 6 new fields to `TenderContext` dataclass
  - `contract_type`, `contract_type_confidence`, `fulfillment_model`
  - `primary_deliverables`, `vendor_inputs`, `location`

- [ ] **Lines 264-316:** Replace LLM prompt with contract-type-aware version
  - Add 3-step classification instructions
  - Add deliverables vs inputs distinction
  - Add contract-type-specific query distribution rules

- [ ] **Lines 326-355:** Update response parsing to extract new fields
  - Parse contract type classification
  - Call `_validate_and_filter_search_terms()` for safety rails
  - Return TenderContext with new fields

- [ ] **After line 239:** Add `_validate_and_filter_search_terms()` method
  - Filter inappropriate queries (e.g., "salt supplier" for service contracts)
  - Only apply if confidence ≥ 0.75
  - Log rejected queries for monitoring

#### File 2: `src/vendor_ai_agent/models.py`

- [ ] **Lines 299-308:** Add 6 new fields to `DynamicTenderContext` dataclass
  - Same fields as TenderContext
  - All fields have defaults for backward compatibility

#### File 3: `src/vendor_ai_agent/modules/requirement_extractor.py`

- [ ] **Lines 48-57:** Update DynamicTenderContext instantiation
  - Use `getattr()` with fallbacks for new fields
  - Maintains backward compatibility

### Phase 2: Testing (1-2 hours)

- [ ] **Create:** `tests/test_contract_type_classification.py`
  - Test service contract (grounds maintenance)
  - Test product contract (hospital beds)
  - Test hybrid contract (HVAC system)
  - Test consulting contract (cybersecurity)
  - Test safety rails filter vendor inputs
  - Integration test with Waterloo PDF

- [ ] **Run tests:** `python tests/test_contract_type_classification.py`

### Phase 3: Validation (1-2 hours)

- [ ] Run on Waterloo PDF: verify "service" classification
- [ ] Verify search terms: "grounds maintenance contractors" ✓
- [ ] Verify NO queries: "salt suppliers" ✗
- [ ] Check enrichment success rate on test dataset (N=20)

## Expected Results

### Before Implementation
```
Waterloo Grounds Maintenance RFP
├─ Contract Type: Unknown
├─ Search Queries:
│  ├─ "salt manufacturers"           ✗ WRONG
│  ├─ "equipment suppliers"          ✗ WRONG
│  └─ "training companies"           ✗ WRONG
└─ Enrichment Success: 11.9% (5/42)
```

### After Implementation
```
Waterloo Grounds Maintenance RFP
├─ Contract Type: service (confidence: 0.92)
├─ Fulfillment Model: contractor
├─ Primary Deliverables: [grounds maintenance, landscaping, snow removal]
├─ Vendor Inputs: [salt, equipment, training]
├─ Search Queries:
│  ├─ "commercial grounds maintenance contractors Ontario"  ✓ CORRECT
│  ├─ "landscape maintenance service providers Canada"      ✓ CORRECT
│  └─ "property maintenance contractors municipal"          ✓ CORRECT
└─ Enrichment Success: 60%+ (expected)
```

## Key Files Modified

```
src/vendor_ai_agent/modules/tender_profiler.py     [MODIFIED - 3 changes]
src/vendor_ai_agent/models.py                      [MODIFIED - 1 change]
src/vendor_ai_agent/modules/requirement_extractor.py [MODIFIED - 1 change]
tests/test_contract_type_classification.py         [NEW FILE]
```

## Rollout Strategy

**Week 1:** Implementation + Unit Tests
**Week 2:** Integration Testing + Metrics Setup
**Week 3:** A/B Testing (10% → 50% traffic)
**Week 4:** Full Production Rollout (100%)

## Success Criteria

- ✅ **Enrichment success rate: ≥60%** (baseline: 11.9%)
- ✅ **Contract type confidence: ≥0.75** for 80%+ of tenders
- ✅ **Safety rails filter rate: <15%** of queries
- ✅ **Geographic extraction: ≥70%** of tenders

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM misclassifies contract type | Confidence threshold (0.75) prevents incorrect filtering |
| Safety rails too aggressive | Monitor filter rate, adjust threshold if needed |
| Increased LLM costs | Offset by reduced duplicate Serper queries, 5x better results |

## Quick Start Commands

```bash
# Run tests
python tests/test_contract_type_classification.py

# Test with Waterloo PDF
python -c "from tests.test_contract_type_classification import test_waterloo_grounds_maintenance_real_pdf; test_waterloo_grounds_maintenance_real_pdf()"

# Check metrics in logs
grep "METRICS: contract_type" logs/pipeline.log
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      TENDER DOCUMENT                             │
│  "Contractor shall provide grounds maintenance using salt..."    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1: CLASSIFY CONTRACT TYPE                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ SERVICE  │  │ PRODUCT  │  │  HYBRID  │  │CONSULTING│        │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘        │
│       │ ✓ confidence: 0.92                                      │
│       │ fulfillment_model: contractor                           │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 2: IDENTIFY DELIVERABLES vs INPUTS                  │
│                                                                  │
│  PRIMARY DELIVERABLES (buyer purchases):                         │
│  ┌─────────────────────────────────────────────┐                │
│  │ • Grounds maintenance services              │ → SEARCH       │
│  │ • Landscaping                               │                │
│  │ • Snow removal                              │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
│  VENDOR INPUTS (contractor uses):                               │
│  ┌─────────────────────────────────────────────┐                │
│  │ • Salt                                      │ → DON'T SEARCH │
│  │ • Equipment                                 │                │
│  │ • Training                                  │                │
│  └─────────────────────────────────────────────┘                │
└───────┬─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│      STEP 3: GENERATE CONTRACT-TYPE-AWARE QUERIES                │
│                                                                  │
│  SERVICE CONTRACT RULES:                                         │
│  ├─ 85% contractor/service queries                              │
│  ├─ 10% integrator/consultant queries                           │
│  ├─  5% specialized equipment suppliers                         │
│  └─  0% manufacturer/producer queries                           │
│                                                                  │
│  GENERATED QUERIES:                                              │
│  ✓ "commercial grounds maintenance contractors Ontario"         │
│  ✓ "landscape maintenance service providers Canada"             │
│  ✓ "snow removal and lawn care services"                        │
│  ✓ "property maintenance contractors municipal contracts"       │
│                                                                  │
│  SAFETY RAILS FILTERED:                                          │
│  ✗ "salt manufacturers"         (vendor input)                  │
│  ✗ "equipment suppliers"        (vendor input)                  │
│  ✗ "training companies"         (not primary deliverable)       │
└───────┬─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VENDOR DISCOVERY                               │
│  Apollo Search + Serper Places + Static Directory                │
│                                                                  │
│  RESULT: 200+ grounds maintenance contractors                    │
│  (instead of 5 relevant vendors from salt suppliers mix)        │
└─────────────────────────────────────────────────────────────────┘
```

## Example: Waterloo Grounds Maintenance

### Input Tender Excerpt
```
The Region of Waterloo requires grounds maintenance services. The contractor 
shall provide all necessary equipment, materials including salt, sand, fertilizers, 
and trained personnel to perform lawn care, snow removal, and landscaping.
```

### System Output
```json
{
  "contract_type": "service",
  "contract_type_confidence": 0.92,
  "fulfillment_model": "contractor",
  "primary_deliverables": [
    "grounds maintenance services",
    "lawn care",
    "snow removal",
    "landscaping"
  ],
  "vendor_inputs": [
    "salt",
    "sand",
    "fertilizers",
    "equipment",
    "trained personnel"
  ],
  "search_terms": [
    "commercial grounds maintenance contractors Ontario",
    "landscape maintenance service providers Canada",
    "snow removal and lawn care services",
    "property maintenance contractors municipal contracts",
    "grounds keeping services government contracts",
    "exterior maintenance contractors",
    "seasonal grounds maintenance providers",
    "landscape services commercial property"
  ]
}
```

### Validation
```
✓ Contract type: service (not product/hybrid)
✓ Search queries: ALL contractor-focused
✓ Safety rails: Filtered "salt supplier", "equipment distributor"
✓ Geographic: Ontario, Canada extracted
✓ Expected enrichment: 60%+ success rate
```

---

**For detailed line-by-line implementation, see:** `CONTRACT_TYPE_AWARE_IMPLEMENTATION_SPEC.md`
