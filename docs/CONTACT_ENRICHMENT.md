# Contact Enrichment Implementation

## Overview

Added web scraping-based contact enrichment that extracts emails and phone numbers from vendor websites using a hybrid regex + LLM approach.

## Architecture

### 3-Phase Strategy

1. **Phase 1: Regex Extraction (80% cases)**
   - Fast, free pattern matching for standard formats
   - Email patterns (RFC 5322 compliant)
   - US/Canada phone formats
   - Contact name extraction

2. **Phase 2: LLM Fallback (20% cases)**
   - Activates when regex finds nothing
   - Handles JavaScript-protected emails
   - Complex HTML structures
   - Uses OpenAI JSON mode

3. **Phase 3: Static Fallback**
   - Generates `info@domain.com` if scraping fails
   - Explicitly marked as `fallback_static`
   - Low confidence score (0.1)

## Components

### 1. ContactExtractor
**File**: `src/vendor_ai_agent/modules/contact_extractor.py`

**Features**:
- Regex patterns for email/phone extraction
- Spam filtering (`noreply@`, `webmaster@`, etc.)
- Email prioritization (sales > contact > info > support)
- Phone normalization to E.164 format (`+1XXXXXXXXXX`)
- LLM fallback with structured JSON output

**API**:
```python
extractor = ContactExtractor(llm_provider=OpenAIProvider())
contacts = extractor.extract(html_text, use_llm_fallback=True)

# Returns:
# - emails: List[str]
# - phones: List[str]
# - contact_names: List[str]
# - extraction_method: "regex" | "llm" | "none"
# - confidence: 0.0-1.0
# - email_sources: List["scraped_regex" | "scraped_llm"]
# - phone_sources: List["scraped_regex" | "scraped_llm"]
```

### 2. WebsiteScraper Enhancement
**File**: `src/vendor_ai_agent/modules/website_scraper.py`

**Added**:
- `CONTACT_PATHS` constant with common contact page URLs
- `scrape_contacts()` method that:
  - Tries multiple contact page paths
  - Extracts up to 5000 chars of text
  - Passes to ContactExtractor
  - Returns ExtractedContacts

**Contact Paths**:
```python
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contactus",
    "/get-in-touch",
    "/contact-info",
    "/contact-information",
    "/reach-us",
    "/touch",
]
```

### 3. ContactScrapingProvider
**File**: `src/vendor_ai_agent/enrichment_providers/contact_scraping.py`

**Logic**:
- Skips vendors with real (non-fallback) contacts
- Scrapes contact pages via WebsiteScraper
- Extracts contacts via ContactExtractor
- Updates `vendor.email`, `vendor.phone`
- Stores metadata with source tracking

**Metadata Added**:
```python
vendor.filtering_metadata = {
    "email_source": "scraped_regex" | "scraped_llm" | "fallback_static",
    "email_confidence": 0.0-1.0,
    "phone_source": "scraped_regex" | "scraped_llm" | "fallback_na",
    "phone_confidence": 0.0-1.0,
    "all_emails": [...],  # All found emails
    "all_phones": [...],  # All found phones
    "contact_names": [...]  # Extracted names
}
```

### 4. StaticContactsProvider Update
**File**: `src/vendor_ai_agent/enrichment_providers/static_contacts.py`

**Changes**:
- Now adds `email_source: "fallback_static"` metadata
- Adds `email_confidence: 0.1` (low confidence)
- Adds `phone_source: "fallback_na"` for "N/A"
- Only fills missing fields (doesn't overwrite)

## Configuration

**File**: `src/vendor_ai_agent/config.py`

**New EnrichmentConfig fields**:
```python
@dataclass
class EnrichmentConfig:
    enable_contact_scraping: bool = True
    enable_llm_fallback: bool = True
    scraper_timeout_seconds: int = 10
```

## Pipeline Integration

**File**: `src/vendor_ai_agent/pipeline.py`

**Enrichment chain order**:
1. ContactScrapingProvider (extracts real contacts first)
2. WebsiteContentProvider (for capability matching)
3. StaticContactsProvider (final fallback)

**Code**:
```python
if cfg.enrichment.enable_contact_scraping:
    contact_provider = ContactScrapingProvider(
        llm_provider=llm_provider,
        scraper_timeout=cfg.enrichment.scraper_timeout_seconds,
        enable_llm_fallback=cfg.enrichment.enable_llm_fallback
    )
    enrichment_providers.append(contact_provider)

# ... other providers ...

static_provider = StaticContactsProvider()
enrichment_providers.append(static_provider)  # Always last
```

## Performance

**Per 300 filtered vendors**:
- Regex: 240 vendors × 5 sec = 20 min, $0
- LLM fallback: 60 vendors × 7 sec = 7 min, ~$0.006
- **Total**: ~27 minutes, ~$0.01

**Compared to Apollo API**: ~$18 per 300 vendors

## Usage

### Enabling/Disabling

In your config or environment:
```python
cfg.enrichment.enable_contact_scraping = True  # Enable scraping
cfg.enrichment.enable_llm_fallback = True      # Enable LLM for complex cases
cfg.enrichment.scraper_timeout_seconds = 10    # Timeout per page
```

### Filtering by Confidence

In post-processing:
```python
high_quality_vendors = [
    v for v in vendors 
    if v.filtering_metadata.get("email_confidence", 0) >= 0.7
]
```

### Checking Contact Source

```python
for vendor in vendors:
    source = vendor.filtering_metadata.get("email_source")
    if source == "scraped_regex":
        print(f"✓ High confidence: {vendor.email}")
    elif source == "scraped_llm":
        print(f"~ Medium confidence: {vendor.email}")
    elif source == "fallback_static":
        print(f"⚠ Low confidence (generated): {vendor.email}")
```

## Testing

**File**: `tests/test_contact_scraping.py`

**Test cases**:
1. `test_contact_extractor_regex` - Basic regex extraction
2. `test_contact_extractor_prioritization` - Email prioritization logic
3. `test_contact_extractor_spam_filtering` - Spam email filtering
4. `test_phone_normalization` - Phone number formatting
5. `test_llm_fallback` - LLM extraction (requires API key)
6. `test_contact_scraping_provider_skip_existing` - Skip logic
7. `test_static_contacts_fallback_metadata` - Metadata tracking

**Run tests**:
```bash
pytest tests/test_contact_scraping.py -v
```

## Key Features

### 1. Transparency
All contact sources are explicitly tracked - no silent fallbacks that mislead users.

### 2. Confidence Scoring
Users can filter/sort by quality:
- 0.9: Regex found both email and phone
- 0.7: Regex found one contact type
- 0.75: LLM extraction successful
- 0.1: Static fallback (generated)
- 0.0: No phone available

### 3. Cost Optimization
LLM only used for ~20% of complex cases where regex fails.

### 4. Separation of Concerns
- `ContactExtractor` is reusable, not tied to web scraping
- Can be used for extracting contacts from any text source
- Easy to test in isolation

### 5. Email Prioritization
Smart ordering by business value:
1. sales@
2. contact@, business@, inquiries@
3. hello@
4. info@
5. support@

### 6. Spam Filtering
Automatically filters out:
- noreply@, donotreply@, no-reply@
- webmaster@, admin@, postmaster@
- test@, example.com
- abuse@, bounce@, mailer@

## Files Modified/Created

### Created
- `src/vendor_ai_agent/modules/contact_extractor.py` ✅
- `src/vendor_ai_agent/enrichment_providers/contact_scraping.py` ✅
- `tests/test_contact_scraping.py` ✅
- `docs/CONTACT_ENRICHMENT.md` ✅

### Modified
- `src/vendor_ai_agent/modules/website_scraper.py` ✅
  - Added `CONTACT_PATHS`
  - Added `scrape_contacts()` method
- `src/vendor_ai_agent/enrichment_providers/static_contacts.py` ✅
  - Added metadata tracking
  - Only fills missing fields
- `src/vendor_ai_agent/enrichment_providers/__init__.py` ✅
  - Exported `ContactScrapingProvider`
- `src/vendor_ai_agent/config.py` ✅
  - Added `enable_contact_scraping`
  - Added `enable_llm_fallback`
  - Added `scraper_timeout_seconds`
- `src/vendor_ai_agent/pipeline.py` ✅
  - Integrated ContactScrapingProvider
  - Proper enrichment chain ordering

## Next Steps

### Testing
1. Run unit tests: `pytest tests/test_contact_scraping.py -v`
2. Test with real vendor list (10-20 vendors)
3. Validate metadata in output CSV/JSON

### Monitoring
1. Track extraction success rate (regex vs LLM vs fallback)
2. Monitor LLM costs
3. Log confidence score distribution

### Potential Improvements
1. Add more contact page paths for specific industries
2. Support international phone formats (UK, EU, etc.)
3. Cache extracted contacts to avoid re-scraping
4. Add rate limiting for web requests
5. Support LinkedIn profile scraping
6. Extract additional fields (address, hours, etc.)

## Example Output

**CSV with metadata**:
```csv
company_name,email,phone,email_source,email_confidence,phone_source,phone_confidence
"Acme Corp","sales@acme.com","+15551234567","scraped_regex",0.9,"scraped_regex",0.9
"Beta Inc","contact@beta.com","+15559876543","scraped_llm",0.75,"scraped_llm",0.75
"Gamma LLC","info@gammallc.com","N/A","fallback_static",0.1,"fallback_na",0.0
```

**JSON with all contacts**:
```json
{
  "company_name": "Acme Corp",
  "email": "sales@acme.com",
  "phone": "+15551234567",
  "filtering_metadata": {
    "email_source": "scraped_regex",
    "email_confidence": 0.9,
    "all_emails": ["sales@acme.com", "contact@acme.com", "info@acme.com"],
    "phone_source": "scraped_regex",
    "phone_confidence": 0.9,
    "all_phones": ["+15551234567", "+15551234568"],
    "contact_names": ["John Smith", "Jane Doe"]
  }
}
```
