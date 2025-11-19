# Tender Vendor AI Agent – Ingestion & Document Processing Workflow

This document captures the full set of work implemented so far, along with the intended pipeline between API ingestion and document parsing. Use it as the reference for future builds and for onboarding new engineers.

## 1. Unified Tender Profile Schema

Every module reads/writes the same JSON-compatible structure (`TenderProfile`):

```json
{
  "tender_id": "string",
  "country": "USA | CAN",
  "source_system": "SAM | CANADABUYS | MANUAL",
  "api_metadata": {
    "external_id": "string",
    "title": "string",
    "description": "string",
    "codes": { "naics": [], "unspsc": [], "gsin": [], "classification": null },
    "buyer": { "name": "", "department": "", "organization_path": [], "address": { ... } },
    "place_of_performance": { ... },
    "dates": { "posted": "", "response_deadline": "", "tender_start": null, "tender_end": null },
    "set_aside": { "code": null, "description": null },
    "estimated_value": { "amount": null, "currency": null },
    "trade_agreements": [],
    "awards": [ { "award_id": "", "supplier_name": "", ... } ],
    "attachments": [ { "url": "", "filename": "", "source": "API | USER_UPLOAD" } ]
  },
  "doc_extracted": {
    "sections": {
      "scope_of_work": "...",
      "technical_requirements": "...",
      "mandatory_requirements": "...",
      "vendor_qualifications": "...",
      "evaluation_criteria": "...",
      "location_details": "...",
      "timeline_details": "..."
    },
    "structured": {
      "project_type": "...",
      "sector": "construction | ammo_supply | it | ...",
      "location": { "city": "", "state_province": "", "country": "" },
      "volumes": [ { "item": "", "quantity": 0, "unit": "m2" } ],
      "technical_keywords": [],
      "required_experience": { "min_years": null, "required_project_types": [] },
      "required_licenses": [],
      "required_certifications": [],
      "vendor_constraints": { "allowed_jurisdictions": [], "business_size": null, "special_status": [] },
      "packaging_logistics": { "special_requirements": [], "lead_times_days": { "samples": null, "regular_orders": null } },
      "solicitation_number": "",
      "reference_number": ""
    }
  },
  "vendor_capability_profile": {
    "summary": "string",
    "key_requirements": [ { "id": "REQ-001", "type": "experience", "description": "", "must_have": true } ],
    "target_industry_codes": { "naics": [], "gsin": [], "unspsc": [] }
  }
}
```

`DocExtracted.structures` also stores the solicitation/reference numbers derived directly from uploaded documents, so we can call APIs even when the user only provides partial files.

## 2. Modules Implemented

### 2.1 Document Parsing
- **DocumentParser**: walks a folder/tree, parses PDF/Excel/Text using PyPDF2/openpyxl/plain text. Each chunk becomes a `TenderSection` with metadata (including `doc_type` from classifier).
- **DocumentClassifier**: filename heuristics to tag `CORE_SCOPE`, `TECH_SPEC`, `ADDENDUM`, `LEGAL`, `OTHER`.
- **SectionExtractor**: detects sections using `SECTION_HEADING_PATTERNS` + contextual hints; supports fallback to first non-empty chunk.
- **FieldExtractor**: fills structured fields using dictionaries/regEX (experience/volumes/timelines/licenses/certs/SAAMI keywords). Now supports extraction of solicitation/reference numbers.

### 2.2 Ingestion & Attachments
- **SamClient + UsSamIngestor**: GET `https://api.sam.gov/opportunities/v2/search` with `solnum`, date range. Maps fields to `api_metadata`, collects `resourceLinks` as attachments.
- **CanadaCkanClient + CanadaBuysIngestor**: `package_show` + `datastore_search` for tender notices/contract history. Returns `api_metadata` + attachments. (Note: dataset lacks Datastore-active resources; next step is parsing HTML/CSV.)
- **TenderIngestionRouter**: takes `TenderIngestionRequest` (country/source, solnum/reference), routes to SAM or CanadaBuys, returns `api_metadata` and attachments.
- **DocumentFetcher**: downloads attachments (currently with SSL verification disabled – TODO to trust the proxy certificate) into `data/attachments/` so the parser sees them alongside user uploads.

### 2.3 Pipeline Orchestration
`TenderVendorPipeline.run(...)` now works in both modes:
1. **Manual** (no ingestion request): parse only supplied files.
2. **API-assisted**: call ingestion → fetch attachments → parse combined set. Lifts `tender_profile.api_metadata` + `doc_extracted` simultaneously.

## 3. Extracting Identifiers from Documents
When users only upload addenda or amendments, we still need the solicitation/reference numbers to query APIs. The pipeline now:
- Reads every section for `Request for Bids ... # OPP-1984 / Tender# 20070`
- Extracts `solicitation_number = "OPP-1984"` and `reference_number = "20070"`
- These values can be plugged into `TenderIngestionRequest`, which in turn allows DocumentFetcher to download everything else automatically.

## 4. Tests & Smoke Runs
- `tests/test_document_parser.py`, `tests/test_pipeline.py`, `tests/test_ingestion.py` ensure baseline coverage.
- Manual smoke run with `data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda` verified that even addenda-only uploads produce `scope_of_work`, timeline, and identifier fields.
- Ingestion with external API currently fails due to the corporate proxy (python’s urllib cannot resolve `open.canada.ca`). TODO: import the proxy’s root certificate and/or configure the proxy variables so CanadaBuys/SAM calls succeed.

## 5. Remaining TODOs
1. **Network**: install corporate proxy certificate or route Python traffic through curl-style settings so ingestion fetches data online.
2. **CanadaBuys attachments**: since CKAN datasets don’t expose attachments via Datastore, parse the HTML tender page or secondary feed to grab actual documents.
3. **DocumentFetcher**: allow user inputs to explicitly tag files as core scope vs addendum when classification is ambiguous.
4. **Section extraction**: refine heuristics for ammo-specific addenda (Q&A), so technical requirements & vendor qualifications propagate even without the base RFB.
5. **LLM integration**: once doc sections are stable, implement the actual GPT prompts for `RequirementExtractorLLM` and `CapabilityMatcher`.

With this pipeline, we can run the end-to-end workflow as soon as API connectivity is sorted: user uploads whatever documents they have → parser extracts identifiers → router fetches `api_metadata` + attachments → DocumentFetcher downloads them → DocumentParser rehydrates the complete tender profile.
