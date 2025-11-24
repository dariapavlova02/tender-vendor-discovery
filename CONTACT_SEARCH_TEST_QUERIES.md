# Contact Search Query Testing - Real Examples

## Test Cases for Phone Discovery

### Case 1: HubSpoke Inc. (Proven Success ✅)
**Company**: HubSpoke Inc.
**Location**: Ottawa, Ontario, Canada
**Known Result**: `+1 888 482 7768`

**Query Variations to Test:**

1. `HubSpoke contact Ottawa`
   - **Expected**: High confidence, official contact
   
2. `HubSpoke phone number Ottawa Canada`
   - **Expected**: Business listings, directories
   
3. `HubSpoke headquarters phone`
   - **Expected**: Main office number
   
4. `HubSpoke Inc phone Ottawa`
   - **Expected**: May include legal name matches
   
5. `HubSpoke customer service phone`
   - **Expected**: Customer-facing number (if exists)

---

### Case 2: General Dynamics (Proven Success ✅)
**Company**: General Dynamics
**Location**: Various (multinational)
**Known Result**: Multiple phone numbers found

**Query Variations:**

1. `General Dynamics contact`
   - **Expected**: Corporate HQ contact
   
2. `General Dynamics phone number`
   - **Expected**: Main switchboard
   
3. `General Dynamics headquarters phone Falls Church`
   - **Expected**: Virginia HQ number
   
4. `General Dynamics corporate phone`
   - **Expected**: Executive offices

---

### Case 3: Small Local Business
**Company**: ABC Plumbing Services
**Location**: Toronto, Ontario, Canada

**Query Variations:**

1. `ABC Plumbing Services contact Toronto`
   - **Expected**: Local business listing
   
2. `ABC Plumbing phone number Toronto`
   - **Expected**: Google My Business, Yelp listings
   
3. `ABC Plumbing Services Toronto phone`
   - **Expected**: High snippet visibility (local businesses)

---

### Case 4: Government Contractor
**Company**: Lockheed Martin Canada
**Location**: Ottawa, Ontario, Canada

**Query Variations:**

1. `Lockheed Martin Canada contact Ottawa`
   - **Expected**: Branch office contact
   
2. `Lockheed Martin procurement contact Canada`
   - **Expected**: Government sales department
   
3. `Lockheed Martin Canada phone number`
   - **Expected**: Main office number

---

### Case 5: Acquired/Renamed Company (Hard Case)
**Company**: SIERRA SYSTEMS GROUP INC
**Location**: Vancouver, BC, Canada
**Context**: Acquired by NTT DATA

**Query Variations:**

1. `Sierra Systems contact Vancouver`
   - **Expected**: May redirect to NTT DATA
   
2. `NTT DATA Vancouver phone`
   - **Expected**: New parent company contact
   
3. `Sierra Systems legacy contact`
   - **Expected**: Historical records

---

## Query Pattern Analysis

### Pattern 1: "{Company} contact {City}"
**Pros:**
- Natural language, low 403 risk
- Captures "Contact Us" pages
- Good for official business contacts

**Cons:**
- May return LinkedIn profiles
- Generic directory sites

**Expected Success**: 50-60%

**Test Results Template:**
```
Query: HubSpoke contact Ottawa
Found: [Phone Numbers]
Confidence: [Score]
Source Domain: [URL]
Snippet Match: [Yes/No]
```

---

### Pattern 2: "{Company} phone number {City} {Country}"
**Pros:**
- Explicit phone request
- Location qualifier reduces ambiguity
- Good for business directories

**Cons:**
- May return customer service vs. procurement
- Directory aggregators (Yellowpages, etc.)

**Expected Success**: 40-50%

---

### Pattern 3: "{Company} headquarters phone"
**Pros:**
- Targets main office
- Good for corporate entities
- Clear intent

**Cons:**
- Small businesses may not have "headquarters"
- May return address without phone

**Expected Success**: 40-50%

---

### Pattern 4: "{Company} support phone number"
**Pros:**
- Public-facing departments
- Often published prominently

**Cons:**
- Technical support vs. business inquiries
- May not exist for B2B companies

**Expected Success**: 35-45%

---

### Pattern 5: "{Company} customer service phone {Country}"
**Pros:**
- High visibility for B2C companies
- Country qualifier for international

**Cons:**
- B2B companies rarely have customer service
- May return overseas call centers

**Expected Success**: 30-40% (B2C only)

---

## Query Complexity vs. 403 Risk

### Low Risk (Simple Queries) ✅
```
HubSpoke contact Ottawa
General Dynamics phone number
ABC Plumbing Toronto phone
```
**403 Rate**: <2%

### Medium Risk (Multiple Keywords) ⚠️
```
HubSpoke phone number Ottawa Canada
Lockheed Martin procurement contact Canada
Sierra Systems customer service phone
```
**403 Rate**: 5-10%

### High Risk (Operators/Quotes) ❌
```
"HubSpoke Inc" phone number
HubSpoke AND phone OR contact
site:hubspoke.com contact
```
**403 Rate**: 30-50%

**Recommendation**: Start with low-risk queries, fallback to medium-risk if needed

---

## Snippet Analysis Examples

### Example 1: High Confidence Phone Match
```
Query: HubSpoke contact Ottawa
Result:
  Title: "HubSpoke - Contact Us"
  URL: https://hubspoke.ca/contact
  Snippet: "Get in touch with HubSpoke. Call us at 888-482-7768 
            or email info@hubspoke.com. Located in Ottawa, Ontario."
  
Extracted Phone: +1 888 482 7768
Confidence Score: 0.9
  - Snippet match: 0.5 ✅
  - Title match: 0.2 ✅
  - Domain match: 0.2 ✅
  - Format valid: 0.1 ✅
```

### Example 2: Medium Confidence Phone Match
```
Query: ABC Plumbing phone number Toronto
Result:
  Title: "ABC Plumbing Services - Yelp"
  URL: https://yelp.com/biz/abc-plumbing-toronto
  Snippet: "ABC Plumbing Services in Toronto. Phone: (416) 555-1234. 
            Hours: Mon-Fri 8am-6pm. Reviews and ratings."
  
Extracted Phone: +1 (416) 555-1234
Confidence Score: 0.65
  - Snippet match: 0.5 ✅
  - Title match: 0.2 ✅
  - Domain match: 0.0 ❌ (Yelp, not company domain)
  - Format valid: 0.1 ✅
```

### Example 3: Low Confidence Phone Match
```
Query: Lockheed Martin contact
Result:
  Title: "Lockheed Martin Corporation - Wikipedia"
  URL: https://en.wikipedia.org/wiki/Lockheed_Martin
  Snippet: "Lockheed Martin Corporation is an American aerospace company. 
            Founded in 1995, headquartered in Bethesda, Maryland."
  
Extracted Phone: None
Confidence Score: 0.0
  - No phone in snippet
```

### Example 4: False Positive (Discard)
```
Query: General Dynamics phone
Result:
  Title: "General Dynamics Employee Directory - RocketReach"
  URL: https://rocketreach.co/general-dynamics
  Snippet: "Find contact info for General Dynamics employees. 
            John Smith: (202) 555-9999, Jane Doe: (202) 555-8888"
  
Extracted Phone: Multiple employee phones
Confidence Score: 0.3 (discard - not official company phone)
  - Snippet match: 0.5 ✅
  - Title match: 0.0 ❌ (employee directory)
  - Domain match: 0.0 ❌ (third-party site)
  - Format valid: 0.1 ✅
```

---

## Phone Number Validation Regex

### Pattern Testing

**Valid North American Formats:**
```
+1 888-482-7768      ✅
(888) 482-7768       ✅
888.482.7768         ✅
888 482 7768         ✅
1-888-482-7768       ✅
+1 (888) 482-7768    ✅
```

**Valid International Formats:**
```
+44 20 7123 4567     ✅
+33 1 42 86 82 00    ✅
+61 2 9999 8888      ✅
```

**Invalid/Edge Cases:**
```
888                  ❌ (too short)
123-4567             ⚠️ (7-digit local - may be valid with area code)
0000000000           ❌ (all zeros)
1111111111           ❌ (all same digit)
```

**Regex Pattern:**
```python
import re

PHONE_PATTERNS = [
    # North American: +1 (XXX) XXX-XXXX
    r'\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
    
    # International: +XX XXX XXX XXXX
    r'\+\d{1,3}[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}',
    
    # Toll-free: 1-800-XXX-XXXX
    r'1-8\d{2}-\d{3}-\d{4}',
]

def extract_phones(text: str) -> list[str]:
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        phones.extend(matches)
    return list(set(phones))  # Deduplicate

def is_valid_phone(phone: str) -> bool:
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Check length (10-15 digits typical)
    if len(digits) < 10 or len(digits) > 15:
        return False
    
    # Check for invalid patterns (all zeros, all same digit)
    if digits == '0' * len(digits):
        return False
    if len(set(digits)) == 1:
        return False
    
    return True
```

---

## Expected Results by Query Type

### Query Type Performance Matrix

| Query Pattern | Success Rate | Avg Confidence | 403 Risk | Best For |
|--------------|--------------|----------------|----------|----------|
| `{company} contact {city}` | 50-60% | 0.65 | Low | B2B, Professional Services |
| `{company} phone number {city} {country}` | 40-50% | 0.60 | Low | Small businesses, Local |
| `{company} headquarters phone` | 40-50% | 0.70 | Low | Large corporations |
| `{company} support phone` | 35-45% | 0.55 | Low | Tech companies, B2C |
| `{company} customer service phone` | 30-40% | 0.60 | Low | B2C, Retail |
| `{company} procurement contact` | 35-45% | 0.65 | Medium | Government contractors |

---

## Recommended Testing Sequence

### Step 1: Validate Proven Cases (5 vendors)
1. HubSpoke Inc. - Ottawa (✅ known working)
2. General Dynamics - Various (✅ known working)
3. IBM Canada - Toronto (expected: high confidence)
4. Shopify - Ottawa (expected: high confidence)
5. Tim Hortons - Oakville (expected: high confidence)

**Goal**: Verify 80%+ success on easy cases

---

### Step 2: Test Hard Cases (5 vendors)
1. Sierra Systems - Vancouver (acquired company)
2. Corel Corporation - Ottawa (multiple acquisitions)
3. Nortel Networks - Mississauga (bankrupt)
4. BlackBerry - Waterloo (rebranded from RIM)
5. Small local contractor (no web presence)

**Goal**: Measure edge case handling

---

### Step 3: Random Sample (50 vendors)
- 25 WITH websites (test fallback after scraping fails)
- 25 WITHOUT websites (test direct search)

**Goal**: Statistical significance for success rate

---

### Step 4: Query Optimization (20 vendors)
Test all 5 query patterns on same vendors:
- Measure which pattern performs best
- Identify company types where each works
- Optimize query selection logic

**Goal**: Smart query routing by vendor characteristics

---

## Implementation Checklist

### ✅ Core Functionality
- [ ] DuckDuckGoContactEnricher class
- [ ] 3 query templates (contact, phone, headquarters)
- [ ] Phone extraction from snippets
- [ ] Phone validation regex
- [ ] Confidence scoring (4 factors)
- [ ] Rate limiting (2.5 sec)
- [ ] Cache integration (7-day TTL)

### ✅ Testing
- [ ] Unit tests for phone extraction
- [ ] Unit tests for confidence scoring
- [ ] Integration test: HubSpoke (proven case)
- [ ] Integration test: General Dynamics (proven case)
- [ ] E2E test: 5 easy cases (IBM, Shopify, etc.)
- [ ] E2E test: 5 hard cases (acquisitions, etc.)
- [ ] E2E test: 50 random vendors

### ✅ Metrics Collection
- [ ] Success rate by query pattern
- [ ] Confidence distribution
- [ ] 403 error rate
- [ ] Average time per vendor
- [ ] Coverage improvement (before/after)

### ✅ Documentation
- [ ] Query strategy documentation
- [ ] Confidence scoring explanation
- [ ] Known limitations
- [ ] Usage examples

---

## Query Decision Tree

```
START: Vendor needs contact enrichment

├─ Has website?
│   ├─ YES → Try ContactScrapingProvider
│   │   ├─ Found contacts? → DONE ✅
│   │   └─ No contacts → Continue to DDG phone search
│   │
│   └─ NO → Continue to DDG phone search

├─ DDG Phone Search (Try 3 queries in order)
│   │
│   ├─ Query 1: "{company} contact {city}"
│   │   ├─ Confidence ≥ 0.7? → DONE ✅
│   │   └─ Confidence < 0.7? → Try Query 2
│   │
│   ├─ Query 2: "{company} phone number {city} {country}"
│   │   ├─ Confidence ≥ 0.5? → DONE ✅
│   │   └─ Confidence < 0.5? → Try Query 3
│   │
│   └─ Query 3: "{company} headquarters phone"
│       ├─ Confidence ≥ 0.5? → DONE ✅
│       └─ No results → StaticContactsProvider

└─ Static Fallback: Generate info@domain.com
```

---

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ 50% success rate on phone discovery
- ✅ <5% 403 error rate
- ✅ Confidence ≥ 0.7 for >60% of found phones
- ✅ <3 sec average time per vendor

### Stretch Goals
- 🎯 60% success rate on phone discovery
- 🎯 <2% 403 error rate
- 🎯 Confidence ≥ 0.7 for >70% of found phones
- 🎯 Smart query routing by company type

---

**Next Action**: Implement DuckDuckGoContactEnricher with top 3 query patterns and test on HubSpoke/General Dynamics proven cases.

