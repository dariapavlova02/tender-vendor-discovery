# Tender Vendor AI Agent

Production-ready AI-powered system for automated tender analysis and vendor discovery. This system intelligently parses procurement documents, extracts requirements, discovers qualified vendors, and generates comprehensive matching reports.

## Repository Structure

```
src/vendor_ai_agent/
├── cli.py                  # CLI entrypoint
├── config.py               # Runtime + stage configs
├── contracts.py            # Protocols for module interfaces
├── models.py               # Shared dataclasses for tenders & vendors
├── modules/
│   ├── document_parser.py
│   ├── requirement_extractor.py
│   ├── vendor_discovery.py
│   ├── enrichment.py
│   ├── filtering.py
│   ├── capability_matching.py
│   └── output_generator.py
├── sources/                # Discovery source implementations
└── enrichment_providers/   # Contact/firmographic providers
```

Outputs are written to `./outputs` by default, and generated artifacts include CSV, XLSX, and JSON files with vendor matches, capability scores, and contact information.

## Key Features

- **Multi-format Document Parsing**: PDF, DOCX, XLSX with intelligent section extraction
- **Requirement Analysis**: LLM-powered extraction of technical specs, volumes, and certifications
- **Multi-Source Vendor Discovery**: SAM.gov, CanadaBuys, Apollo, Serper, static databases
- **Contact Enrichment**: Automated discovery of decision-maker contact information
- **Intelligent Matching**: Capability-based scoring with geographic and certification filters
- **Production Database**: PostgreSQL with migration support via Alembic
- **Visual Dashboard**: Real-time pipeline inspection and debugging interface

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <repository-url>
cd vendor_ai_agent

# Create and activate virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
poetry install
```

### 2. Configuration

Create `.env` file with required API keys:

```bash
# Required
OPENAI_API_KEY=your_openai_key

# Optional (for enhanced vendor discovery)
SAM_API_KEY=your_sam_key
APOLLO_API_KEY=your_apollo_key
SERPER_API_KEY=your_serper_key

# Optional (LLM tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=vendor-agent
```

See `.env.example` for full configuration options.

### 3. Database Setup

```bash
# Initialize database
python scripts/setup_database.py

# Run migrations
alembic upgrade head
```

### 4. Run Pipeline

```bash
# Process tender documents
PYTHONPATH=src scripts/run_full_pipeline.py "path/to/tender/folder"

# With API ingestion (CanadaBuys)
PYTHONPATH=src scripts/run_full_pipeline.py \
  --source-system CANADABUYS \
  --reference tender_12345 \
  "path/to/tender/folder"

# With API ingestion (SAM.gov)
PYTHONPATH=src scripts/run_full_pipeline.py \
  --source-system SAM \
  --solnum ABC123 \
  --posted-from 2024-01-01 \
  --posted-to 2024-12-31 \
  "path/to/tender/folder"
```

Pipeline stages: Document Parsing → Requirement Extraction → Vendor Discovery → Enrichment → Filtering → Capability Matching → Output Generation

## Stakeholder Quick Launch

Shipping the project to non-technical reviewers? Provide the folder with the prepared `.env` file and ask them to run the one-click scripts:

- **macOS:** double-click `start_dashboard_mac.sh`
- **Windows:** double-click `start_dashboard_windows.bat`

The scripts create a local virtual environment, install dependencies on first launch, and open the dashboard at http://localhost:8501. See [`STAKEHOLDER_README.md`](STAKEHOLDER_README.md) for the full step-by-step guide you can forward to stakeholders.

## Architecture

### Core Components

**Ingestion Layer**
- `SamClient` / `UsSamIngestor`: SAM.gov API integration for US federal opportunities
- `CanadaCkanClient` / `CanadaBuysIngestor`: CanadaBuys CKAN integration for Canadian tenders
- `TenderIngestionRouter`: Multi-source ingestion orchestration with auto-detection

**Document Processing**
- Multi-format parser (PDF, DOCX, XLSX)
- Table extraction and classification
- Q&A pair extraction
- Section-aware content analysis

**Vendor Discovery**
- SAM.gov Entity API
- CanadaBuys vendor database
- Apollo B2B search
- Serper web search
- Static directory sources

**Enrichment & Matching**
- Contact information scraping
- Website content analysis
- NAICS code enrichment
- Geographic scoring
- Capability-based matching with LLM evaluation

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/PIPELINE_WORKFLOW.md`](docs/PIPELINE_WORKFLOW.md) for detailed technical documentation.

## Dashboard & Monitoring

### Visual Inspection Dashboard

Launch the Streamlit dashboard for real-time pipeline inspection:

```bash
./scripts/run_dashboard.sh
```

Dashboard (http://localhost:8501) provides:
- **Overview**: Pipeline metrics, keywords, search terms
- **Extracted Data**: Requirements, volumes, certifications, contacts
- **Document Content**: Parsed sections with filtering
- **Vendors**: Discovery results, matching scores, enrichment status
- **Debug**: Full profile dumps, API metadata, error tracking

See [`docs/DASHBOARD_GUIDE.md`](docs/DASHBOARD_GUIDE.md) for detailed usage.

### LLM Observability

LangSmith integration for prompt debugging and performance monitoring:

```bash
# Configure in .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=vendor-agent
```

See [`docs/LANGSMITH_INTEGRATION.md`](docs/LANGSMITH_INTEGRATION.md) and [`docs/OBSERVABILITY_QUICKSTART.md`](docs/OBSERVABILITY_QUICKSTART.md) for setup.

## Testing

Run test suite:

```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_document_parser.py

# With coverage
pytest --cov=src/vendor_ai_agent tests/
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - System architecture and design
- [`docs/PIPELINE_WORKFLOW.md`](docs/PIPELINE_WORKFLOW.md) - Pipeline stages and data flow
- [`docs/DASHBOARD_GUIDE.md`](docs/DASHBOARD_GUIDE.md) - Dashboard usage guide
- [`docs/CONTACT_ENRICHMENT.md`](docs/CONTACT_ENRICHMENT.md) - Contact discovery strategies
- [`docs/SAM_INTEGRATION.md`](docs/SAM_INTEGRATION.md) - SAM.gov integration guide
- [`docs/LANGSMITH_INTEGRATION.md`](docs/LANGSMITH_INTEGRATION.md) - Observability setup
- [`docs/reports/`](docs/reports/) - Milestone reports and analysis
- [`docs/archive/`](docs/archive/) - Historical documentation and test reports

## Project Status

**Current Version**: Production-ready MVP  
**Last Updated**: November 2024

**Completed Features:**
- ✅ Multi-format document parsing (PDF, DOCX, XLSX)
- ✅ LLM-powered requirement extraction
- ✅ Multi-source vendor discovery (SAM, CanadaBuys, Apollo, Serper)
- ✅ Contact enrichment and scraping
- ✅ Geographic and capability-based matching
- ✅ PostgreSQL database with migrations
- ✅ Visual dashboard for pipeline inspection
- ✅ LangSmith observability integration

**Recent Milestones:**
- Milestone 1: Core pipeline implementation
- Milestone 2: Multi-source discovery and enrichment

See [`docs/reports/`](docs/reports/) for detailed milestone documentation.

## Contributing

For development setup and contribution guidelines, see project documentation. Test files are located in `tests/` directory.

## License

[Add license information]
