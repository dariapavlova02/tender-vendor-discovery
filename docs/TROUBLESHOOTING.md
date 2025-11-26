# Troubleshooting Guide

This guide provides solutions for common issues encountered when using the Vendor AI Agent system.

**Related Documentation:**
- [Configuration Guide](CONFIGURATION.md) - Configuration options and environment variables
- [Pipeline Workflow](PIPELINE_WORKFLOW.md) - Understanding pipeline stages
- [API Reference](API_REFERENCE.md) - Module documentation

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Installation & Setup Issues](#installation--setup-issues)
3. [Configuration & Environment](#configuration--environment)
4. [Database Issues](#database-issues)
5. [API & External Services](#api--external-services)
6. [Document Processing](#document-processing)
7. [Vendor Discovery](#vendor-discovery)
8. [Contact Enrichment](#contact-enrichment)
9. [LLM & OpenAI Issues](#llm--openai-issues)
10. [Performance Issues](#performance-issues)
11. [Output Generation](#output-generation)
12. [Dashboard Issues](#dashboard-issues)
13. [Getting Help](#getting-help)

---

## Quick Diagnostics

### Check System Status

```bash
# Verify Python version (3.10+ required)
python --version

# Check installed packages
poetry show

# Verify environment variables
env | grep -E "(OPENAI|DATABASE|SAM|APOLLO|SERPER)"

# Test database connection
python -c "from vendor_ai_agent.database.connection import init_db; init_db(); print('✅ Database OK')"

# Test OpenAI connection
python -c "import openai; import os; openai.api_key = os.getenv('OPENAI_API_KEY'); print('✅ OpenAI Key Set')"
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

---

## Installation & Setup Issues

### Issue: `poetry install` fails

**Symptoms:**
```
ERROR: Failed building wheel for lxml
ERROR: Could not build wheels for lxml
```

**Solutions:**

1. **Install system dependencies (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y python3-dev libxml2-dev libxslt-dev
```

2. **Install system dependencies (macOS):**
```bash
brew install libxml2 libxslt
```

3. **Use pre-built wheel:**
```bash
pip install --only-binary :all: lxml
```

---

### Issue: `ModuleNotFoundError` when running scripts

**Symptoms:**
```
ModuleNotFoundError: No module named 'vendor_ai_agent'
```

**Solutions:**

1. **Set PYTHONPATH:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
# Or
PYTHONPATH=src python scripts/run_full_pipeline.py
```

2. **Install in editable mode:**
```bash
poetry install
```

3. **Activate virtual environment:**
```bash
source .venv/bin/activate
```

---

### Issue: Python version incompatibility

**Symptoms:**
```
ERROR: This project requires Python 3.10+
```

**Solutions:**

1. **Install Python 3.10+:**
```bash
# Ubuntu/Debian
sudo apt-get install python3.10

# macOS
brew install python@3.10
```

2. **Create venv with specific version:**
```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

---

## Configuration & Environment

### Issue: Missing `.env` file

**Symptoms:**
```
WARNING: OPENAI_API_KEY not set
AttributeError: 'NoneType' object has no attribute 'generate'
```

**Solutions:**

1. **Create `.env` from example:**
```bash
cp .env.example .env
```

2. **Add required keys:**
```bash
# Minimum required configuration
cat >> .env <<EOF
OPENAI_API_KEY=sk-your-key-here
DATABASE_URL=sqlite:///vendor_ai.db
EOF
```

3. **Verify environment loads:**
```python
from dotenv import load_dotenv
import os
load_dotenv()
print(os.getenv("OPENAI_API_KEY"))  # Should not be None
```

---

### Issue: Invalid API keys

**Symptoms:**
```
openai.error.AuthenticationError: Incorrect API key provided
```

**Solutions:**

1. **Verify key format:**
   - OpenAI: Starts with `sk-`
   - SAM.gov: UUID format
   - Apollo: Alphanumeric string
   - Serper: Alphanumeric string

2. **Test key validity:**
```python
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "test"}],
        max_tokens=5
    )
    print("✅ OpenAI key valid")
except Exception as e:
    print(f"❌ OpenAI key invalid: {e}")
```

3. **Check for whitespace:**
```bash
# Remove leading/trailing whitespace
OPENAI_API_KEY=$(echo $OPENAI_API_KEY | xargs)
```

---

### Issue: Configuration not being applied

**Symptoms:**
- Pipeline uses wrong settings
- Config changes have no effect

**Solutions:**

1. **Check config precedence:**
   - Environment variables override config file
   - Runtime config overrides defaults

2. **Verify config loading:**
```python
from vendor_ai_agent.config import DEFAULT_CONFIG
print(f"LLM Model: {DEFAULT_CONFIG.llm.smart_model}")
print(f"Database: {DEFAULT_CONFIG.database.url}")
print(f"Discovery Sources: {DEFAULT_CONFIG.discovery.preferred_sources}")
```

3. **Clear cache:**
```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

**See Also:** [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

---

## Database Issues

### Issue: Database connection fails

**Symptoms:**
```
sqlalchemy.exc.OperationalError: could not connect to server
FATAL: database "vendor_ai" does not exist
```

**Solutions:**

1. **PostgreSQL not running:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS

# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql  # macOS
```

2. **Database doesn't exist:**
```bash
# Create database
createdb vendor_ai

# Or with psql
psql -U postgres
CREATE DATABASE vendor_ai;
\q
```

3. **Wrong connection URL:**
```bash
# Check DATABASE_URL format
# PostgreSQL: postgresql://user:password@host:port/dbname
# SQLite: sqlite:///path/to/db.db

# Example .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vendor_ai
```

4. **Use SQLite for testing:**
```bash
# Simpler alternative - no PostgreSQL required
DATABASE_URL=sqlite:///vendor_ai.db
```

---

### Issue: Migration errors

**Symptoms:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xyz'
sqlalchemy.exc.ProgrammingError: relation "vendors" already exists
```

**Solutions:**

1. **Initialize Alembic:**
```bash
alembic upgrade head
```

2. **Reset migrations (⚠️ destroys data):**
```bash
# Drop all tables
python -c "from vendor_ai_agent.database.connection import get_engine; from vendor_ai_agent.database.models import Base; Base.metadata.drop_all(get_engine())"

# Recreate
alembic upgrade head
```

3. **Check migration history:**
```bash
alembic current
alembic history
```

4. **Manual table creation:**
```bash
python scripts/setup_database.py
```

---

### Issue: Database connection pool exhausted

**Symptoms:**
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached
```

**Solutions:**

1. **Increase pool size:**
```python
# In config.py or .env
database: DatabaseConfig = DatabaseConfig(
    pool_size=20,
    max_overflow=40
)
```

2. **Close sessions properly:**
```python
# Always use context manager
from vendor_ai_agent.database.connection import get_session

with get_session() as session:
    # Your database operations
    pass  # Session automatically closed
```

3. **Check for connection leaks:**
```bash
# Monitor active connections (PostgreSQL)
psql -U postgres -d vendor_ai -c "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='vendor_ai';"
```

---

### Issue: Slow database queries

**Symptoms:**
- Pipeline takes hours to run
- Vendor discovery is slow

**Solutions:**

1. **Check indexes:**
```sql
-- Verify indexes exist
\d vendors  -- PostgreSQL
.schema vendors  -- SQLite

-- Should see indexes on:
-- - uei
-- - company_name
-- - naics codes
```

2. **Add missing indexes:**
```bash
alembic upgrade head  # Applies index migrations
```

3. **Analyze query performance:**
```sql
EXPLAIN ANALYZE SELECT * FROM vendors WHERE uei = 'ABC123';
```

4. **Enable connection pooling:**
```python
database: DatabaseConfig = DatabaseConfig(
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

**See Also:** [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for schema details.

---

## API & External Services

### Issue: SAM.gov API rate limiting

**Symptoms:**
```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
WARNING: SAM.gov rate limit hit
```

**Solutions:**

1. **Reduce request rate:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    target_results=500,  # Default 1000
    batch_size=100       # Default 500
)
```

2. **Use API cache:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    enable_batch_cache=True  # Default True
)
```

3. **Check rate limit status:**
```python
import requests
response = requests.get(
    "https://api.sam.gov/opportunities/v2/search",
    params={"api_key": "your_key"}
)
print(response.headers.get("X-RateLimit-Remaining"))
```

4. **Get SAM.gov API key:**
   - Visit https://sam.gov/data-services/APIs
   - Register for free API key
   - Add to `.env`: `SAM_API_KEY=your_key`

---

### Issue: Apollo API authentication fails

**Symptoms:**
```
WARNING: Apollo enrichment request failed: 401 Unauthorized
apollo.error.AuthenticationError: Invalid API key
```

**Solutions:**

1. **Verify API key:**
```bash
curl -X POST https://api.apollo.io/v1/people/match \
  -H "Content-Type: application/json" \
  -H "Cache-Control: no-cache" \
  -d '{"api_key": "YOUR_API_KEY", "first_name": "Test"}'
```

2. **Disable Apollo if not needed:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_apollo_enrichment=False
)

discovery: DiscoveryConfig = DiscoveryConfig(
    enable_apollo_discovery=False,
    enable_apollo_booster=False
)
```

3. **Check credit balance:**
   - Login to https://app.apollo.io
   - Check API credit balance
   - Upgrade plan if needed

---

### Issue: Serper API errors

**Symptoms:**
```
ERROR: Serper API error: 403 Forbidden
WARNING: SERPER_API_KEY not found. SerperVendorSource will be disabled.
```

**Solutions:**

1. **Get Serper API key:**
   - Visit https://serper.dev
   - Sign up for free tier (2,500 searches/month)
   - Add to `.env`: `SERPER_API_KEY=your_key`

2. **Disable Serper if not needed:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    enable_serper_discovery=False
)

enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_serper_fallback=False,
    enable_targeted_serper_fallback=False
)
```

3. **Check rate limits:**
```bash
curl https://google.serper.dev/search \
  -X POST \
  -H 'X-API-KEY: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"q":"test"}'
```

---

### Issue: Google Maps API errors

**Symptoms:**
```
ERROR: Google Maps geocoding failed: REQUEST_DENIED
WARNING: Google Maps API key not configured
```

**Solutions:**

1. **Enable Google Maps Geocoding API:**
   - Visit https://console.cloud.google.com
   - Enable "Geocoding API"
   - Create API key
   - Add to `.env`: `GOOGLE_MAPS_API_KEY=your_key`

2. **Disable Google Maps enrichment:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_google_maps=False
)
```

3. **Check billing enabled:**
   - Google Maps requires billing account
   - Free tier: $200/month credit

---

### Issue: API cache issues

**Symptoms:**
- Stale data returned
- Cache not being used

**Solutions:**

1. **Clear API cache:**
```python
from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.database.models import APICache

with get_session() as session:
    session.query(APICache).delete()
    print("✅ API cache cleared")
```

2. **Adjust cache TTL:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    google_maps_cache_ttl_days=90  # Default 90 days
)
```

3. **Disable cache for testing:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    enable_batch_cache=False
)
```

---

## Document Processing

### Issue: PDF parsing fails

**Symptoms:**
```
ERROR: Failed to parse PDF: [file.pdf]
WARNING: No text extracted from PDF
```

**Solutions:**

1. **Check file format:**
```bash
file tender.pdf  # Should say "PDF document"
```

2. **Install PDF dependencies:**
```bash
# Ubuntu/Debian
sudo apt-get install -y poppler-utils

# macOS
brew install poppler
```

3. **Try manual extraction:**
```bash
pdftotext tender.pdf test.txt
cat test.txt  # Verify text is extractable
```

4. **Check if PDF is image-based:**
   - Image-based PDFs require OCR (not currently supported)
   - Solution: Use text-based PDFs or convert with OCR tool

5. **Enable debug logging:**
```python
from vendor_ai_agent.modules import DocumentParser
import logging
logging.basicConfig(level=logging.DEBUG)

parser = DocumentParser(llm_config=config.llm)
sections = parser.parse_documents([Path("tender.pdf")])
```

---

### Issue: Table extraction incomplete

**Symptoms:**
- Missing pricing tables
- Quantity information not captured

**Solutions:**

1. **Check table detection:**
```python
from vendor_ai_agent.modules import DocumentParser

parser = DocumentParser(llm_config=config.llm)
sections = parser.parse_documents([Path("tender.pdf")])

# Check extracted tables
tables = [s for s in sections if s.section_type == "table"]
print(f"Found {len(tables)} tables")
for t in tables:
    print(f"- {t.title}: {len(t.content)} chars")
```

2. **Use LLM-based extraction:**
   - Current system uses pdfplumber for tables
   - Complex tables may require manual review

3. **Extract tables manually:**
```bash
# Use tabula-py or camelot for complex tables
pip install tabula-py
python -c "import tabula; tabula.read_pdf('tender.pdf', pages='all')"
```

---

### Issue: DOCX parsing errors

**Symptoms:**
```
ERROR: Failed to parse DOCX: [file.docx]
zipfile.BadZipFile: File is not a zip file
```

**Solutions:**

1. **Verify DOCX format:**
```bash
file tender.docx  # Should say "Microsoft Word 2007+"
```

2. **Convert old DOC to DOCX:**
   - Use LibreOffice: `libreoffice --convert-to docx tender.doc`

3. **Check file corruption:**
   - Try opening in Word/LibreOffice
   - Re-save if corrupted

---

### Issue: Requirement extraction incomplete

**Symptoms:**
- Missing NAICS codes
- No location extracted
- Empty technical requirements

**Solutions:**

1. **Check source documents:**
   - Ensure PDF contains text (not just images)
   - Verify requirements are clearly stated

2. **Review extraction results:**
```python
from vendor_ai_agent.modules import RequirementExtractor

extractor = RequirementExtractor(llm_config=config.llm)
extracted = extractor.extract(sections)

print(f"Project Type: {extracted.structured.project_type}")
print(f"NAICS Codes: {extracted.structured.naics_codes}")
print(f"Location: {extracted.structured.location}")
print(f"Keywords: {extracted.structured.technical_keywords}")
```

3. **Use smarter LLM model:**
```python
llm: LLMConfig = LLMConfig(
    smart_model="gpt-5.1",  # Better extraction
    cheap_model="gpt-5-mini"
)
```

4. **Check LLM token limits:**
   - Long documents may be truncated
   - Current limit: 6000 tokens per request

---

## Vendor Discovery

### Issue: No vendors found

**Symptoms:**
```
WARNING: No vendors discovered
Total vendors: 0
```

**Solutions:**

1. **Check discovery sources:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    preferred_sources=["sam_entity", "static_directory"]
)
```

2. **Verify NAICS codes extracted:**
```python
print(f"Tender NAICS: {tender_profile.doc_extracted.structured.naics_codes}")
print(f"API NAICS: {tender_profile.api_metadata.codes.naics}")
```

3. **Check database vendor count:**
```sql
-- PostgreSQL/SQLite
SELECT COUNT(*) FROM vendors;
SELECT COUNT(*) FROM vendor_naics;
```

4. **Ingest vendors from SAM.gov:**
```bash
# Download SAM.gov CSV export
# Import using ingestion module
python scripts/setup_database.py  # Ingests sample data
```

5. **Enable additional sources:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    enable_apollo_discovery=True,
    enable_serper_discovery=True,
    preferred_sources=["sam_entity", "apollo", "serper"]
)
```

---

### Issue: Too many/too few vendors returned

**Symptoms:**
- 5000+ vendors returned (too broad)
- 5 vendors returned (too narrow)

**Solutions:**

1. **Adjust target results:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    target_results=500  # Default 1000
)
```

2. **Enable filtering:**
```python
filtering: FilteringConfig = FilteringConfig(
    enable_geographic=True,
    enable_eligibility_checks=True,
    max_candidates=500
)
```

3. **Adjust NAICS code specificity:**
   - Too broad: Use 6-digit NAICS codes (more specific)
   - Too narrow: Use 4-digit NAICS codes (less specific)

4. **Check filtering metrics:**
```python
metrics = artifacts.filtering_metrics
print(f"Input: {metrics.total_input}")
print(f"Duplicates: {metrics.duplicates_removed}")
print(f"Geographic: {metrics.geo_filtered}")
print(f"Final: {metrics.final_count}")
```

---

### Issue: Duplicate vendors in results

**Symptoms:**
- Same company appears multiple times
- Different names for same vendor

**Solutions:**

1. **Enable duplicate detection:**
```python
filtering: FilteringConfig = FilteringConfig(
    enable_duplicate_removal=True  # Default True
)
```

2. **Check UEI/DUNS matching:**
```python
from vendor_ai_agent.modules import DuplicateDetector

detector = DuplicateDetector()
unique_vendors = detector.remove_duplicates(vendors)
print(f"Removed {len(vendors) - len(unique_vendors)} duplicates")
```

3. **Verify database constraints:**
```sql
-- Check for duplicate UEIs
SELECT uei, COUNT(*) FROM vendors WHERE uei IS NOT NULL GROUP BY uei HAVING COUNT(*) > 1;
```

---

### Issue: Geographic filtering too restrictive

**Symptoms:**
- Local vendors only (missing national vendors)
- No vendors in target state

**Solutions:**

1. **Adjust geographic mode:**
```python
filtering: FilteringConfig = FilteringConfig(
    geographic_mode="local_plus_regional",  # Options: local_only, local_plus_regional, national
    geographic_search_radius_km=200
)
```

2. **Expand search radius:**
```python
filtering: FilteringConfig = FilteringConfig(
    geographic_search_radius_km=500  # Default 200km
)
```

3. **Enable national expansion:**
```python
filtering: FilteringConfig = FilteringConfig(
    national_expansion_threshold=50,  # If <50 local vendors, include national
    enable_local_first=True
)
```

4. **Disable geographic filtering:**
```python
filtering: FilteringConfig = FilteringConfig(
    enable_geographic=False  # Include all vendors regardless of location
)
```

---

## Contact Enrichment

### Issue: No contacts found for vendors

**Symptoms:**
```
WARNING: Contact enrichment failed for [vendor]
Primary contact: None
Email: None
```

**Solutions:**

1. **Check enrichment providers enabled:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    providers=["apollo", "hunter", "scraper"],
    enable_apollo_enrichment=True,
    enable_contact_scraping=True
)
```

2. **Verify vendor has website:**
```python
vendors_with_websites = [v for v in vendors if v.website]
print(f"{len(vendors_with_websites)}/{len(vendors)} have websites")
```

3. **Check scraper timeout:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    scraper_timeout_seconds=10  # Default 5, increase for slow sites
)
```

4. **Enable search fallback:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_website_search=True,  # Search for website if missing
    enable_serper_fallback=True
)
```

5. **Test manual enrichment:**
```python
from vendor_ai_agent.modules import VendorEnricher

enricher = VendorEnricher(config=config)
enriched = enricher.enrich_single(vendor)
print(f"Contact: {enriched.primary_contact}")
```

---

### Issue: Website scraping fails

**Symptoms:**
```
WARNING: Scraping failed: Timeout
requests.exceptions.Timeout: HTTPSConnectionPool
```

**Solutions:**

1. **Increase timeout:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    scraper_timeout_seconds=15  # Default 5
)

capability_matching: CapabilityMatchingConfig = CapabilityMatchingConfig(
    scrape_timeout_seconds=15  # Default 5
)
```

2. **Check firewall/proxy:**
```bash
# Test direct access
curl -I https://example-vendor.com

# Check if behind corporate proxy
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

3. **Disable website scraping:**
```python
capability_matching: CapabilityMatchingConfig = CapabilityMatchingConfig(
    enable_website_scraping=False  # Skip scraping, use only database data
)
```

---

### Issue: Rate limiting during enrichment

**Symptoms:**
```
WARNING: Rate limited on /contact, backing off
ERROR: 429 Too Many Requests
```

**Solutions:**

1. **Reduce parallelism:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    max_enrichment_workers=5,  # Default 10
    batch_size=25              # Default 50
)
```

2. **Enable retry logic:**
   - System automatically retries with exponential backoff
   - Wait for rate limit to reset (usually 60 seconds)

3. **Use caching:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_batch_cache=True  # Avoid re-enriching same vendors
)
```

---

### Issue: Enrichment quality low

**Symptoms:**
- Generic emails (info@, sales@)
- No decision-maker contacts

**Solutions:**

1. **Enable Apollo enrichment:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_apollo_enrichment=True,  # Best quality contacts
    providers=["apollo", "hunter", "scraper"]
)
```

2. **Adjust quality gates:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    min_batch_success_rate=0.20,  # Default 0.15 (15%)
    relevance_score_threshold=35.0  # Default 40.0
)
```

3. **Enable manual enrichment:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_manual_enrichment=True  # Use dashboard for manual enrichment
)
```

---

## LLM & OpenAI Issues

### Issue: OpenAI API rate limits

**Symptoms:**
```
openai.error.RateLimitError: Rate limit reached for gpt-5.1
ERROR: Request limit exceeded
```

**Solutions:**

1. **Use Tier 1 (Flex) limits:**
```python
llm: LLMConfig = LLMConfig(
    use_flex_tier=True  # Default True - higher limits
)
```

2. **Reduce parallelism:**
```python
capability_matching: CapabilityMatchingConfig = CapabilityMatchingConfig(
    llm_parallelism=3,  # Default 5
    llm_batch_size=3    # Default 5
)
```

3. **Use cheaper model:**
```python
llm: LLMConfig = LLMConfig(
    smart_model="gpt-5-mini",  # Cheaper, faster
    cheap_model="gpt-5-mini"
)
```

4. **Check your rate limits:**
   - Visit https://platform.openai.com/account/limits
   - Upgrade tier if needed

---

### Issue: OpenAI token limit exceeded

**Symptoms:**
```
openai.error.InvalidRequestError: This model's maximum context length is 128000 tokens
ERROR: Token limit exceeded in request
```

**Solutions:**

1. **Reduce max_tokens:**
```python
llm: LLMConfig = LLMConfig(
    max_tokens=4000  # Default 6000
)
```

2. **Truncate long documents:**
   - System automatically truncates
   - Check document length before processing

3. **Split large documents:**
```python
# Process in sections
for section in tender_sections:
    extracted = extractor.extract([section])
```

---

### Issue: LLM extraction returns invalid JSON

**Symptoms:**
```
json.JSONDecodeError: Expecting value: line 1 column 1
ERROR: Failed to parse LLM response
```

**Solutions:**

1. **Check LLM output:**
```python
# Enable debug logging to see raw LLM responses
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Use stricter model:**
```python
llm: LLMConfig = LLMConfig(
    smart_model="gpt-5.1",  # Better JSON adherence
    temperature=0.0         # Default - more deterministic
)
```

3. **Retry failed requests:**
   - System automatically retries with backoff
   - Check for persistent issues

---

### Issue: High OpenAI costs

**Symptoms:**
- Unexpected high API bills
- Cost per tender exceeds budget

**Solutions:**

1. **Use cost-optimized config:**
```python
from vendor_ai_agent.config import RuntimeConfig, LLMConfig

config = RuntimeConfig(
    llm=LLMConfig(
        smart_model="gpt-5-mini",  # Cheaper model
        cheap_model="gpt-5-mini",
        max_tokens=4000            # Reduce tokens
    )
)
```

2. **Disable expensive features:**
```python
capability_matching: CapabilityMatchingConfig = CapabilityMatchingConfig(
    enable_llm_assessment=False,  # Use rule-based scoring
    enable_website_scraping=False
)
```

3. **Monitor costs with LangSmith:**
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=vendor-agent
```

4. **Estimate costs before running:**
```python
# Rough estimates (as of 2024):
# gpt-5.1: $5-10 per tender (full pipeline)
# gpt-5-mini: $0.50-1 per tender (full pipeline)
```

**See Also:** [Cost Optimization Guide](CONFIGURATION.md#cost-optimized-configuration)

---

## Performance Issues

### Issue: Pipeline runs slowly

**Symptoms:**
- Pipeline takes hours instead of minutes
- Single tender takes >30 minutes

**Solutions:**

1. **Enable parallelism:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    max_enrichment_workers=10,  # Default 10
    batch_size=50               # Default 50
)

capability_matching: CapabilityMatchingConfig = CapabilityMatchingConfig(
    llm_parallelism=5,  # Default 5
    llm_batch_size=5
)
```

2. **Reduce target vendor count:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    target_results=500  # Default 1000
)

filtering: FilteringConfig = FilteringConfig(
    max_candidates=300  # Default 500
)
```

3. **Skip expensive features:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    enable_contact_scraping=False,  # Slow
    enable_google_maps=False        # External API call per vendor
)
```

4. **Use faster LLM model:**
```python
llm: LLMConfig = LLMConfig(
    smart_model="gpt-5-mini",  # Much faster than gpt-5.1
    cheap_model="gpt-5-mini"
)
```

5. **Enable batch caching:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    enable_batch_cache=True  # Avoid re-discovering vendors
)
```

---

### Issue: High memory usage

**Symptoms:**
```
MemoryError: Unable to allocate array
Process killed: Out of memory
```

**Solutions:**

1. **Process in batches:**
```python
discovery: DiscoveryConfig = DiscoveryConfig(
    batch_size=200,  # Default 500
    processing_batch=1
)

enrichment: EnrichmentConfig = EnrichmentConfig(
    batch_size=25  # Default 50
)
```

2. **Reduce vendor count:**
```python
filtering: FilteringConfig = FilteringConfig(
    max_candidates=200  # Default 500
)
```

3. **Clear cache periodically:**
```python
from vendor_ai_agent.database.cache import CacheManager

cache = CacheManager()
cache.clear_old_entries(days=30)
```

---

### Issue: Database locks/deadlocks

**Symptoms:**
```
sqlalchemy.exc.OperationalError: database is locked
psycopg2.extensions.TransactionRollbackError: deadlock detected
```

**Solutions:**

1. **Use PostgreSQL instead of SQLite:**
```bash
# SQLite has limited concurrency
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vendor_ai
```

2. **Reduce concurrent workers:**
```python
enrichment: EnrichmentConfig = EnrichmentConfig(
    max_enrichment_workers=5  # Default 10
)
```

3. **Increase connection pool:**
```python
database: DatabaseConfig = DatabaseConfig(
    pool_size=20,      # Default 10
    max_overflow=40    # Default 20
)
```

---

## Output Generation

### Issue: Output files not created

**Symptoms:**
- No CSV/JSON/XLSX files in `outputs/` folder
- Empty output directory

**Solutions:**

1. **Check output config:**
```python
output: OutputConfig = OutputConfig(
    include_json=True,
    include_csv=True,
    include_xlsx=True,
    base_filename="tender_vendors"
)
```

2. **Verify output directory exists:**
```bash
mkdir -p outputs
```

3. **Check file permissions:**
```bash
ls -la outputs/
chmod 755 outputs
```

4. **Check for errors in output generation:**
```python
from vendor_ai_agent.modules import OutputGenerator

generator = OutputGenerator(config=config.output)
generator.generate(artifacts, output_dir=Path("outputs"))
```

---

### Issue: Excel file won't open

**Symptoms:**
```
Excel cannot open the file because the format is invalid
openpyxl.utils.exceptions.InvalidFileException
```

**Solutions:**

1. **Check pandas/openpyxl installation:**
```bash
poetry add openpyxl
```

2. **Verify output file integrity:**
```python
import pandas as pd
df = pd.read_excel("outputs/tender_vendors.xlsx")
print(df.head())
```

3. **Use CSV as fallback:**
```python
output: OutputConfig = OutputConfig(
    include_xlsx=False,  # Disable Excel
    include_csv=True
)
```

---

### Issue: Missing fields in output

**Symptoms:**
- Contact info missing from CSV
- Score/rationale not exported

**Solutions:**

1. **Check enrichment completed:**
```python
enriched_count = len([v for v in artifacts.enriched_vendors if v.primary_contact])
print(f"{enriched_count} vendors have contacts")
```

2. **Verify capability matching ran:**
```python
scored_count = len(artifacts.final_matches)
print(f"{scored_count} vendors scored")
```

3. **Check OutputGenerator mapping:**
   - All `VendorMatchResult` fields should be exported
   - Contact info from `vendor.primary_contact`

---

## Dashboard Issues

### Issue: Dashboard won't start

**Symptoms:**
```
ModuleNotFoundError: No module named 'streamlit'
streamlit: command not found
```

**Solutions:**

1. **Install Streamlit:**
```bash
poetry add streamlit
# Or
pip install streamlit
```

2. **Run dashboard:**
```bash
streamlit run src/vendor_ai_agent/dashboard.py

# Or use script
./scripts/run_dashboard.sh
```

3. **Check port availability:**
```bash
# Dashboard runs on port 8501 by default
lsof -i :8501

# Use different port
streamlit run src/vendor_ai_agent/dashboard.py --server.port 8502
```

---

### Issue: Dashboard loads but shows errors

**Symptoms:**
- Dashboard UI appears but shows error messages
- Cannot upload files

**Solutions:**

1. **Check database connection:**
```python
# From dashboard: Settings → System Status
# Should show "✅ Database Connected"
```

2. **Verify file upload permissions:**
```bash
mkdir -p data/temp_upload
chmod 755 data/temp_upload
```

3. **Check OpenAI API key:**
```bash
# From dashboard: Settings → Configuration
# Should show "✅ OpenAI API Key Set"
```

4. **Enable debug mode:**
```bash
streamlit run src/vendor_ai_agent/dashboard.py --logger.level=debug
```

---

### Issue: Dashboard pipeline fails

**Symptoms:**
- Pipeline starts but fails midway
- "Pipeline execution failed" error

**Solutions:**

1. **Check logs in dashboard:**
   - Dashboard shows real-time logs
   - Look for specific error messages

2. **Run pipeline via CLI for better logs:**
```bash
PYTHONPATH=src python scripts/run_full_pipeline.py /path/to/tender
```

3. **Verify configuration:**
   - Check Settings tab for configuration issues
   - Ensure all required API keys set

---

## Getting Help

### Before Reporting Issues

1. **Check this troubleshooting guide**
2. **Review relevant documentation:**
   - [README.md](../README.md) - Quick start guide
   - [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
   - [API_REFERENCE.md](API_REFERENCE.md) - Module documentation
   - [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database details

3. **Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

4. **Gather diagnostic info:**
```bash
# Python version
python --version

# Package versions
poetry show | head -20

# Environment variables (redact keys)
env | grep -E "(DATABASE|OPENAI|SAM)" | sed 's/=.*/=***/'

# Database status
python -c "from vendor_ai_agent.database.connection import init_db; init_db(); print('OK')"
```

### Reporting Issues

Include the following in bug reports:

1. **System info:**
   - OS and version
   - Python version
   - Poetry version

2. **Configuration:**
   - Relevant config settings (redact API keys)
   - Database type (PostgreSQL/SQLite)

3. **Error details:**
   - Full error message and stack trace
   - Relevant log output
   - Steps to reproduce

4. **Context:**
   - What were you trying to do?
   - What did you expect to happen?
   - What actually happened?

### Common Resources

- **Documentation:** `docs/` folder
- **Sample Data:** `data/samples/`
- **Test Files:** `tests/` folder
- **Example Configurations:** [CONFIGURATION.md](CONFIGURATION.md)

---

## Quick Reference: Common Commands

```bash
# Database
python scripts/setup_database.py          # Initialize database
alembic upgrade head                       # Run migrations
alembic downgrade -1                       # Rollback migration

# Pipeline
PYTHONPATH=src scripts/run_full_pipeline.py /path/to/tender    # Run pipeline
streamlit run src/vendor_ai_agent/dashboard.py                  # Start dashboard

# Debugging
python -c "from vendor_ai_agent.config import DEFAULT_CONFIG; print(DEFAULT_CONFIG)"  # Check config
python -c "from vendor_ai_agent.database.connection import init_db; init_db()"       # Test DB

# Testing
pytest tests/                              # Run all tests
pytest tests/test_pipeline.py -v          # Run specific test

# Cleanup
find . -type d -name __pycache__ -exec rm -rf {} +   # Clear Python cache
rm -rf outputs/*                                      # Clear outputs
```

---

## Additional Resources

### Performance Optimization
- [CONFIGURATION.md - Performance Tuning](CONFIGURATION.md#performance-tuning)
- [CONFIGURATION.md - Cost Optimization](CONFIGURATION.md#cost-optimized-configuration)

### Development
- [API_REFERENCE.md](API_REFERENCE.md) - Module documentation
- [DATA_MODELS.md](DATA_MODELS.md) - Data structures
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture

### Operations
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database schema
- [PIPELINE_WORKFLOW.md](PIPELINE_WORKFLOW.md) - Pipeline stages

---

**Document Status:** ✅ Complete  
**Last Updated:** 2024-11-25  
**Covers:** Installation, Configuration, Database, APIs, Processing, Performance, Output
