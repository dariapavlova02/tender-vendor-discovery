# Tender Vendor AI Agent (MVP Scaffold)

This repository bootstraps the architecture for the Tender Vendor AI Agent described in the business plan. It wires together stub modules for the full pipeline so engineers can iterate on each stage independently while maintaining a consistent interface.

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

Outputs are written to `./outputs` by default, and generated artifacts include CSV, XLSX, and JSON files.

## Getting Started

1. **Create & activate venv** (Python 3.10 recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```
2. **Configure API keys** (optional, for ingestion):
   ```bash
   export SAM_API_KEY=your_sam_key
   ```
   CanadaBuys datasets are public; resource IDs can be overridden via `RuntimeConfig.canada_open_data`. _TODO: import the corporate proxy certificate into the trust store/`certifi` so SAM/CanadaBuys calls run with SSL verification enabled._
2. **Run the skeleton pipeline** with placeholder tender files:
   ```bash
   tender-vendor-agent path/to/tender1.pdf path/to/tender2.docx
   ```
   The current implementation uses mock logic but demonstrates the full control flow (parse → extract → discover → enrich → filter → score → export).

### API Ingestion

The `vendor_ai_agent.ingestion` package introduces:

- `SamClient` / `UsSamIngestor`: wraps `https://api.sam.gov/opportunities/v2/search` with mandatory `solnum`, `postedFrom`, `postedTo`, and maps results into the unified `tender_profile.api_metadata` schema.
- `CanadaCkanClient` / `CanadaBuysIngestor`: queries CanadaBuys tender notices & contract history via the CKAN `package_show/datastore_search` endpoints and hydrates metadata plus lists of attachments/awards.
- `TenderIngestionRouter`: orchestrates USA/CAN/manual ingestion. `TenderVendorPipeline.run(..., ingestion_request=...)` will pre-populate `api_metadata` before document parsing.

## Next Steps
- Replace placeholder logic in each module with the planned implementations (deterministic parsing, GPT requirement extraction, multi-source discovery, enrichment via Apollo/Hunter, LLM capability matching).
- Extend `RuntimeConfig` to load API keys from environment variables or a secrets manager.
- Add persistence/caching (e.g., SQLite) for vendor data to avoid redundant enrichment.
- Build automated tests per module as production logic is added.

Refer to `plan.md` for the business logic and `docs/ARCHITECTURE.md` for the technical mapping of each module (including ingestion flow, document parsing, and vendor scoring).
