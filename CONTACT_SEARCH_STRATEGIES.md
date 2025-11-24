# Contact Search Strategies for DuckDuckGo

## Current State Analysis

### What We Have
1. **Website Discovery**: ✅ DuckDuckGoWebsiteEnricher working (tested with HubSpoke)
2. **Website Scraping**: ✅ ContactScrapingProvider (70-80% success on found websites)
3. **Gap**: 49,804 vendors without websites need alternative contact discovery

### Success Metrics from Previous Session
- **Phones via DDG search**: ✅ 70-90% success (HubSpoke, General Dynamics proven)
- **Emails via DDG search**: ❌ 10-20% success (rarely in snippets)
- **Rate limiting**: ⚠️ 403 errors with complex queries (quotes, operators)

---

## Strategy 1: Direct Phone Number Search

### Query Templates (Ordered by Effectiveness)

#### 1.1 Basic Company + Location + Phone
```
"{company_name}" phone number {city} {country}
```
**Pros**: Simple, low 403 risk, captures official business listings
**Cons**: Generic results, may return directory sites
**Expected Success**: 40-50%

**Example Results:**
- ✅ HubSpoke phone Ottawa → Found `+1 888 482 7768`
- ✅ General Dynamics phone → Found 3 phone numbers

#### 1.2 Company + Contact
```
{company_name} contact {city}
```
**Pros**: Less restrictive than quotes, captures "Contact Us" pages
**Cons**: May return employee LinkedIn profiles
**Expected Success**: 50-60%

#### 1.3 Company + Customer Service
```
{company_name} customer service phone {country}
```
**Pros**: Targets customer-facing departments (likely to be public)
**Cons**: B2B companies may not have customer service
**Expected Success**: 30-40% (B2C companies)

#### 1.4 Company + Support
```
{company_name} support phone number
```
**Pros**: Good for tech/service companies
**Cons**: May return product support vs. procurement contacts
**Expected Success**: 35-45%

#### 1.5 Company + Headquarters
```
{company_name} headquarters phone {city}
```
**Pros**: Targets main office number
**Cons**: May return address info without phone
**Expected Success**: 40-50%

---

## Strategy 2: Email Search (Lower Priority)

### Query Templates

#### 2.1 Company + Email (No Quotes)
```
{company_name} email {city}
```
**Pros**: Simple, avoids 403
**Cons**: Emails rarely in snippets (10-20% success)
**Expected Success**: 10-20%

#### 2.2 Company + Contact Email
```
{company_name} contact email {country}
```
**Pros**: Slightly more targeted
**Cons**: Still low snippet visibility
**Expected Success**: 15-25%

#### 2.3 Sales/Info Email
```
{company_name} sales email OR info email
```
**Pros**: Common public-facing emails
**Cons**: OR operator may trigger 403
**Expected Success**: 10-20%

---

## Strategy 3: Multi-Stage Fallback Approach

### Recommended Pipeline

```
Stage 1: Website Discovery
├─ DuckDuckGoWebsiteEnricher
├─ Success: 40-50% (20K-25K websites)
└─ Output: website URL

Stage 2: Website Scraping
├─ ContactScrapingProvider (on found websites)
├─ Success: 70-80% of websites with contacts
└─ Output: emails (14K-18K), phones (12K-15K)

Stage 3: Direct Phone Search (NEW - for websites with no contacts)
├─ DuckDuckGoContactEnricher (phones only)
├─ Query Strategy: Try 3 queries in order
│   1. "{company}" contact {city}
│   2. {company} phone number {city} {country}
│   3. {company} headquarters phone
├─ Success: 50-70% on websites without scraped contacts
└─ Output: phones (+8K-12K additional)

Stage 4: Static Fallback
├─ StaticContactsProvider
└─ Generate info@domain.com, sales@domain.com
```

### Expected Total Coverage
- **Websites**: 20K-25K (40-50%)
- **Emails**: 14K-18K from scraping + ~2K from DDG = 16K-20K (32-40%)
- **Phones**: 12K-15K from scraping + 8K-12K from DDG = 20K-27K (40-54%)
- **Remaining gap**: ~25K-30K vendors (StaticContactsProvider)

---

## Strategy 4: Query Optimization Techniques

### What Works (Avoid 403)
- ✅ No quotes around company name
- ✅ Simple boolean keywords (phone, email, contact)
- ✅ Location qualifiers (city, country)
- ✅ 2-second delay between requests

### What Triggers 403
- ❌ Quotes around company name: `"HubSpoke Inc"`
- ❌ Boolean operators: `AND`, `OR`, `NOT`
- ❌ Special operators: `site:`, `intitle:`, `inurl:`
- ❌ Complex queries with multiple quotes

### Rate Limiting
```python
# Current implementation: 2 sec delay
time.sleep(2.0)

# Recommended for contact search: 2.5-3 sec
# (More aggressive queries need more conservative rate)
time.sleep(2.5)
```

---

## Strategy 5: Confidence Scoring for Contact Results

### Phone Number Confidence Factors

```python
confidence_score = (
    snippet_match * 0.5 +      # Phone appears in snippet
    title_match * 0.2 +         # Company name in title
    domain_match * 0.2 +        # Company domain in URL
    format_validity * 0.1       # Valid phone format (regex)
)
```

**Thresholds:**
- ≥ 0.7: HIGH (use immediately)
- 0.5-0.7: MEDIUM (use if no better option)
- < 0.5: LOW (discard)

### Phone Format Validation
```regex
# North American: +1 XXX-XXX-XXXX, (XXX) XXX-XXXX
# International: +XX XXX XXX XXXX
r'\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
r'\+\d{1,3}\s?\d{3}\s?\d{3}\s?\d{4}'
```

---

## Strategy 6: Query Sequence Logic

### Decision Tree for Each Vendor

```python
if vendor.website:
    # Stage 2: Try website scraping first
    contacts = ContactScrapingProvider.enrich(vendor)
    
    if contacts.email or contacts.phone:
        return contacts  # Success via scraping
    else:
        # Website exists but no contacts found
        # Try Stage 3: Direct phone search
        phone = DuckDuckGoContactEnricher.search_phone(vendor)
        return phone

else:
    # Stage 1: No website found
    # Skip directly to Stage 3: Direct phone search
    phone = DuckDuckGoContactEnricher.search_phone(vendor)
    
    if not phone:
        # Stage 4: Static fallback
        return StaticContactsProvider.generate(vendor)
```

---

## Strategy 7: Query Templating by Company Type

### Government Contractors (B2G)
```
{company} procurement contact {city}
{company} government sales phone
{company} contracts department phone
```
**Success Rate**: 35-45% (less public-facing)

### B2B Service Companies
```
{company} business inquiries {city}
{company} corporate contact
{company} sales department phone
```
**Success Rate**: 45-55%

### B2C Companies
```
{company} customer service phone
{company} support number {country}
{company} contact us
```
**Success Rate**: 60-70%

### Manufacturing/Industrial
```
{company} main office phone {city}
{company} plant location phone
{company} factory contact
```
**Success Rate**: 40-50%

---

## Strategy 8: Snippet Analysis Patterns

### Phone Number Extraction from Snippets

**Common Patterns Found:**
```
"Call us at 888-482-7768"
"Phone: +1 (613) 555-1234"
"Contact: 555-1234"
"Tel: 888.482.7768"
"1-800-COMPANY (1-800-266-7269)"
```

**Regex Pattern:**
```python
PHONE_PATTERNS = [
    r'\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',  # North American
    r'\+\d{1,3}[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}',  # International
    r'\d{3}[-.\s]?\d{4}',  # 7-digit local
    r'1-800-[A-Z-]+\s*\(1-800-\d{3}-\d{4}\)',  # Vanity numbers
]
```

### Email Extraction from Snippets (Low Success)

**Rare Patterns:**
```
"Contact us: info@company.com"
"Email: sales@company.com"
"Reach out to contact@company.com"
```

**Why Low Success:**
- Email addresses often obfuscated (contact [at] company [dot] com)
- Hidden behind contact forms
- Protected by anti-scraping measures
- Not rendered in HTML snippets

---

## Strategy 9: Implementation Priority

### Phase 1: High-Value Quick Wins ✅
1. ✅ **DuckDuckGoWebsiteEnricher** (DONE - tested working)
2. ✅ **ContactScrapingProvider** (DONE - existing, 70-80% success)

### Phase 2: Medium-Value Additions (RECOMMENDED NEXT)
3. **DuckDuckGoContactEnricher** - Phone search only
   - Focus on 3 query templates (contact, phone, headquarters)
   - 2.5 sec rate limiting
   - Confidence scoring ≥ 0.5
   - Expected: +8K-12K additional phone numbers

### Phase 3: Low-Value Optimizations (OPTIONAL)
4. **Company Type Detection** - Tailor queries by industry
5. **Email Search** - Only if phone success < 40%
6. **Multi-query Fallback** - Try 3 queries per vendor

---

## Strategy 10: Testing Plan

### Test Dataset: Random 100 Vendors
```python
# Selection Criteria
- 50 vendors WITH websites (test Stage 3 fallback)
- 50 vendors WITHOUT websites (test direct search)
- Mix of B2B, B2C, Government, Manufacturing
- Mix of large (>500 employees) and small companies
```

### Success Metrics
```
Phone Discovery:
- Target: 50-70% success rate
- Confidence ≥ 0.7: >60% of found contacts
- Confidence 0.5-0.7: <30% of found contacts
- Invalid formats: <5%

Email Discovery (if implemented):
- Target: 15-25% success rate
- Valid format: >95%
- Confidence ≥ 0.5: >70%

Performance:
- Avg time per vendor: 2.5-3 sec
- 403 errors: <5%
- Timeout errors: <2%
```

---

## Recommended Implementation

### **DuckDuckGoContactEnricher** Class Design

```python
class DuckDuckGoContactEnricher(BaseEnrichmentProvider):
    """
    Direct contact search via DuckDuckGo (phones only)
    Fallback for websites without scraped contacts
    """
    
    PHONE_QUERIES = [
        "{company} contact {city}",
        "{company} phone number {city} {country}",
        "{company} headquarters phone",
    ]
    
    PHONE_PATTERNS = [...]  # Regex patterns
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        # Skip if already has phone
        if vendor.primary_phone:
            return vendor
        
        # Try each query template
        for query_template in self.PHONE_QUERIES:
            query = query_template.format(
                company=vendor.company_name,
                city=vendor.city,
                country=vendor.country
            )
            
            results = self._search_duckduckgo(query)
            phone = self._extract_best_phone(results, vendor)
            
            if phone and phone["confidence"] >= 0.5:
                vendor.primary_phone = phone["number"]
                vendor.enrichment_flags.append("duckduckgo_phone")
                return vendor
        
        return vendor
    
    def _extract_best_phone(self, results: list, vendor: VendorRecord) -> dict:
        # Parse snippets for phone numbers
        # Score by confidence
        # Return best match
        pass
```

---

## Summary: Recommended Approach

### ✅ Implement Now
1. **DuckDuckGoContactEnricher** - Phone search only
2. **3 Query Templates**: contact, phone, headquarters
3. **Confidence threshold**: ≥ 0.5
4. **Rate limiting**: 2.5 sec delay

### ⏳ Test First
- Run on 100 random vendors
- Measure success rate (target: 50-70%)
- Check 403 error rate (target: <5%)

### ❌ Skip for Now
- Email search via DDG (low ROI: 10-20% success)
- Complex query operators (high 403 risk)
- Company type detection (premature optimization)

### 📊 Expected Impact
- **Current gap**: 49,804 vendors, 0% websites, 64.7% no contacts
- **After website discovery**: ~25K websites found
- **After website scraping**: ~18K emails, ~15K phones
- **After DDG phone search**: +8K-12K phones (20K-27K total)
- **Final coverage**: 40-54% phones, 32-40% emails

---

**Next Steps:**
1. Create `duckduckgo_contact_enricher.py` (phones only)
2. Create `test_duckduckgo_contact.py` (HubSpoke, General Dynamics cases)
3. Create `scripts/test_contact_discovery_100.py` (100 random vendors)
4. Measure actual performance vs. predictions
5. Decide: continue with email search or optimize phone search

