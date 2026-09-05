# Run locally

## Install

Use Python 3.11 and Poetry 2.1.4 from the repository root:

```bash
poetry env use python3.11
poetry install --with dev
```

The committed lockfile pins dependencies. PDF OCR additionally needs Tesseract and Poppler;
Playwright-based scraping requires `poetry run playwright install chromium`.
Neither is required for the local review example or offline tests.

## Inspect the example

```bash
make demo
```

Open `outputs/demo/review.html` in a browser. Expand candidate records to inspect evidence;
JSON, CSV and XLSX downloads are linked at the bottom.
The example contains fictional data and never calls external providers. Its source is
[`demo.py`](../src/vendor_ai_agent/demo.py).

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
OAuth application; the local review report is the credential-free entry point. Do not expose
this local workflow as a public multi-user service without a separate security review.

## Container

```bash
docker build -t tender-vendor-discovery .
docker run --rm -p 127.0.0.1:8501:8501 --env-file .env tender-vendor-discovery
```

The image includes OCR tools and Chromium and starts the original dashboard. Container
runtime, PostgreSQL and live provider compatibility are not part of the offline checks.
