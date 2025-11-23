# Vendor Discovery with SAM.gov Integration

## Overview

This implementation adds **vendor discovery** capabilities to the Tender Vendor AI Agent by integrating with the **SAM.gov Entity Management API**. The system can now discover and enrich vendor data from the official U.S. government registry of contractors.

## Features

- **SAM.gov Entity API Integration**: Search for registered vendors by NAICS code and location
- **Database-backed storage**: PostgreSQL database for vendor data persistence
- **API caching**: Intelligent caching to reduce API calls and stay within rate limits
- **Rate limiting**: Built-in rate limiting (1000 requests/day for SAM.gov)
- **Automatic sync**: Option to sync discovered vendors to local database

## Database Schema

The implementation includes 4 main tables:

### 1. `vendors`
Stores vendor information including:
- Identifiers (UEI, DUNS, CAGE code)
- Company details (legal name, DBA, website)
- Location (address, city, state, country)
- Certifications (small business, woman-owned, veteran-owned, 8(a), HUBZone)

### 2. `vendor_naics`
Stores NAICS codes associated with each vendor

### 3. `vendor_contacts`
Stores contact information (for future enrichment providers)

### 4. `api_cache`
Generic API response cache with TTL support

## Setup Instructions

### 1. Prerequisites

Ensure you have PostgreSQL installed and running:

```bash
# macOS (with Homebrew)
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt-get install postgresql
sudo systemctl start postgresql

# Or use Docker
docker run --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vendor_ai
SAM_API_KEY=your-sam-gov-api-key-here
```

**Get your SAM API key**: https://open.gsa.gov/api/entity-api/

### 3. Run Database Setup

```bash
poetry run python scripts/setup_database.py
```

This script will:
1. Create the `vendor_ai` database
2. Run Alembic migrations to create tables
3. Verify the setup

### 4. Manual Migration (Alternative)

If you prefer to run migrations manually:

```bash
# Create database manually
createdb vendor_ai

# Run migrations
poetry run alembic upgrade head
```

## Usage

### Basic Usage

```python
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.models import TenderProfile, CodesMetadata, APIMetadata

# Create a tender profile
profile = TenderProfile(
    country="US",
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=["541330", "541511"])
    )
)

# Search for vendors
sam_source = SamEntitySource()
vendors = sam_source.search(profile)

print(f"Found {len(vendors)} vendors")
for vendor in vendors:
    print(f"- {vendor.company_name} ({vendor.location})")
```

### Integration with Pipeline

Update your pipeline configuration:

```python
from src.vendor_ai_agent.config import RuntimeConfig, DiscoveryConfig

config = RuntimeConfig(
    discovery=DiscoveryConfig(
        target_results=1000,
        preferred_sources=["sam_entity", "static_directory"]
    )
)
```

### Advanced: Direct Database Access

```python
from src.vendor_ai_agent.database import get_session, Vendor, VendorNAICS

with get_session() as session:
    # Query vendors by NAICS code
    vendors = (
        session.query(Vendor)
        .join(VendorNAICS)
        .filter(VendorNAICS.naics_code == "541330")
        .filter(Vendor.state == "CA")
        .all()
    )
    
    for vendor in vendors:
        print(f"{vendor.legal_name} - {vendor.city}, {vendor.state}")
```

## API Rate Limits

**SAM.gov Entity API**:
- **Free tier**: 1,000 requests/day
- **Cache TTL**: 7 days (configurable)
- **Strategy**: Aggressive caching to maximize free tier usage

To customize rate limits:

```python
sam_source = SamEntitySource(
    rate_limit_per_day=1000,
    cache_ttl_days=7,
    use_cache=True
)
```

## Cost Optimization

The implementation uses several strategies to minimize API costs:

1. **Database caching**: Store vendors locally, refresh weekly
2. **API response caching**: 7-day TTL for API responses
3. **Smart pagination**: Only fetch what's needed
4. **Rate limiting**: Prevent accidental quota exhaustion

## Testing

Test the SAM.gov integration:

```bash
# Test database connection
poetry run python -c "from src.vendor_ai_agent.database import get_session; print('✓ Database OK')"

# Test SAM API (requires SAM_API_KEY in .env)
poetry run python -c "
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
sam = SamEntitySource()
results = sam.search_by_naics('541330', limit=5)
print(f'Found {len(results)} entities')
"
```

## Troubleshooting

### "Connection refused" error

PostgreSQL is not running. Start it:
```bash
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux
```

### "SAM_API_KEY is required" error

Set your API key in `.env`:
```
SAM_API_KEY=your-key-here
```

### "Rate limit exceeded" error

You've hit the daily limit (1000 requests). Wait 24 hours or:
- Use cached data
- Reduce search scope
- Optimize queries

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
