# Run locally

## Install

Use Python 3.11 and Poetry 2.1.4 from the repository root:

```bash
poetry env use python3.11
poetry install --with dev
```

The committed lockfile pins dependencies. PDF OCR additionally needs Tesseract and Poppler;
Playwright-based scraping requires `poetry run playwright install chromium`.
Neither is required for the offline unit tests.

## Configure live processing

```bash
cp .env.example .env
```

Set only the credentials for providers you intend to use. `OPENAI_API_KEY` enables LLM
extraction/assessment; `SAM_API_KEY`, `SERPER_API_KEY` and `APOLLO_API_KEY` support the
corresponding adapters. Keys alone do not enable every optional feature: stage switches
live in [`config.py`](../src/vendor_ai_agent/config.py).

`DATABASE_URL` defaults to `sqlite:///vendor_ai.db`. For PostgreSQL, point it at an existing
database, then apply migrations:

```bash
poetry run alembic upgrade head
```

Run migrations before importing data into a new database. When using an existing installation,
back it up first; databases created directly by `create_all` may need reconciliation with
Alembic's revision history. Do not stamp an unknown schema as current.

## Import a local export

```bash
poetry run tender-vendor-discovery ingest-canada-contracts /path/to/contracts.csv
poetry run tender-vendor-discovery ingest-sam-csv /path/to/sam-export.csv
```

CID CSV and CCC CSV/JSON loaders are also exposed through `--help`.
The expected Canada columns are documented in [Data](DATA.md).

## Process documents

```bash
poetry run tender-vendor-discovery run /path/to/tender.pdf \
  --no-auto-ingestion --output-dir outputs/review
```

This invokes real configured providers and can incur their normal usage costs.
`--no-auto-ingestion` disables automatic tender-metadata lookup, not vendor discovery.
The `tender-vendor-agent` executable remains as a compatibility alias.

For explicit SAM/CanadaBuys tender metadata, see:

```bash
poetry run python scripts/run_full_pipeline.py --help
```

## Analysis settings

The default limit is 500 candidates before enrichment and scoring. In the dashboard,
**Maximum vendors to analyze** changes that limit. The **Standard** preset enables lookup
of missing websites; the CLI's default `RuntimeConfig` leaves website lookup disabled.

For programmatic processing with website lookup enabled:

```python
from pathlib import Path
from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.pipeline import TenderVendorPipeline

config = RuntimeConfig()
config.enrichment.enable_website_search = True  # Requires SERPER_API_KEY
pipeline = TenderVendorPipeline(config)
result = pipeline.run([Path("tender.pdf")], disable_auto_ingestion=True)
pipeline.save_outputs(result.final_matches, directory=Path("outputs/review"))
```

Configure keys through the environment. Provider keys do not automatically enable all
optional adapters; see [source wiring and processing limits](ARCHITECTURE.md).
`--no-auto-ingestion` does not disable website research or LLM assessment.

## Dashboard

The original Streamlit dashboard provides intermediate profiles, candidate tables and
background job inspection. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`OAUTH_REDIRECT_URI`, `ALLOWED_EMAILS` and a stable `AUTH_COOKIE_SECRET` in `.env`.
Register the matching redirect URL in your OAuth application. For loopback HTTP only,
set `AUTH_SESSION_COOKIE_SECURE=false`.

```bash
make dashboard
```

The dashboard listens on loopback through the launch script. Its login requires a real
OAuth application. The CLI processes documents without dashboard authentication.

## Container

```bash
docker build -t tender-vendor-discovery .
docker run --rm -p 127.0.0.1:8501:8501 --env-file .env tender-vendor-discovery
```

The image includes OCR tools and Chromium and starts the original dashboard. Container
runtime, PostgreSQL and live provider compatibility are not part of the offline checks.
