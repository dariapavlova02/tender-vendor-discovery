# Tender Vendor AI Agent – Technical Architecture

This document supplements the business plan by mapping each functional stage to code modules and contracts defined in `src/vendor_ai_agent`.

## Module Overview

| Stage | Module | Description |
| --- | --- | --- |
| API Ingestion | `ingestion/sam.py`, `ingestion/canada.py`, `ingestion/router.py` | `SamClient`/`UsSamIngestor` map `https://api.sam.gov/opportunities/v2/search` to `api_metadata`. `CanadaCkanClient`/`CanadaBuysIngestor` fetch CanadaBuys tender & award data via CKAN and unify attachments. `TenderIngestionRouter` selects the correct ingestor per request. |
| Document Processing | `modules/document_parser.py` | Deterministic parsers convert uploaded files into `TenderSection` objects. Future implementation will integrate pdfplumber/PyMuPDF/unstructured. |
| Requirement Extraction | `modules/requirement_extractor.py` | Wraps GPT prompts to produce a normalized `TenderProfile` JSON. Placeholder currently concatenates parsed text. |
| Vendor Discovery | `modules/vendor_discovery.py` + `sources/*` | Aggregates `VendorSource` implementations (SAM.gov, USAspending, association scrapers, etc.). New sources simply implement `search(profile)` and register with `VendorDiscovery`. |
| Data Enrichment | `modules/enrichment.py` + `enrichment_providers/*` | Sequentially runs `EnrichmentProvider`s (Apollo/Hunter/site scrapers) to attach contacts and metadata. Providers registerable at runtime. |
| Filtering & Scoring | `modules/filtering.py` | Applies geographic rules, deduping, and heuristics prior to LLM scoring. |
| Capability Matching | `modules/capability_matching.py` | Orchestrates LLM scoring per vendor, producing `VendorMatchResult` with rationale + references. |
| Output Compilation | `modules/output_generator.py` | Serializes final list to XLSX/CSV/JSON respecting runtime output config. |

`pipeline.py` ties these modules together through dependency injection via `PipelineContext`. CLI clients use `TenderVendorPipeline` to run the full stack.

## Contracts & Extensibility

`contracts.py` declares Protocols for every stage. Any module that conforms to these protocols can be dropped into the pipeline without cross-module refactors. Additional extension points:

- **Vendor Sources:** Implement `VendorSource` (or subclass `BaseVendorSource`) and pass to `VendorDiscovery` on construction.
- **Enrichment Providers:** Implement `EnrichmentProvider`/`BaseEnrichmentProvider` and register with `VendorEnricher` to chain enrichment logic.
- **Capability Matchers:** Swap `CapabilityMatcher` with an implementation that uses GPT/Claude, cached embeddings, or hybrid scoring.

## Configuration Layers

`config.py` defines nested dataclasses:

- `LLMConfig`: primary + fallback models, token cap, temperature.
- `DiscoveryConfig`: desired vendor counts, preferred source names.
- `EnrichmentConfig`: max vendors to pass through paid APIs, provider identifiers.
- `OutputConfig`: toggles for CSV/XLSX/JSON generations, default filename.

`RuntimeConfig` composes these alongside API keys (SAM) and CKAN dataset identifiers, ensuring future configuration (dotenv, CLI flags) has a single structure to populate.

## Execution Flow

1. CLI collects tender files and optionally an ingestion request; `TenderVendorPipeline.run` first hydrates `api_metadata` via `TenderIngestionRouter` (SAM or CanadaBuys) when provided.
2. Document parser + requirement extractor populate `doc_extracted` and a `vendor_capability_profile` compatible with downstream modules.
3. Vendor discovery/enrichment/filtering/matching operate on the unified `TenderProfile`, and `save_outputs` applies output toggles before writing to `paths.output_dir`.

This scaffold lets the engineering team implement business-logic-heavy stages incrementally while keeping interfaces stable and thoroughly documented.

## Field Extraction Strategy

### `project_type` Evolution (Nov 2025)

**Previous Approach:** Hardcoded keyword matching via `SECTOR_KEYWORDS` dictionary → resulted in misclassification (e.g., DHS Uniforms tender classified as "Vehicle project" due to "utility vehicle" mention in document).

**Current Approach:** LLM-based descriptive extraction via `project_summary` field in requirements prompt:
- **Cost:** ~50 tokens marginal cost = $0.00000075 per document (extends existing LLM call)
- **Latency:** 0ms additional (same API call)
- **Output Style:** Descriptive phrases (e.g., "law enforcement uniform supply and delivery") instead of categories
- **Fallback:** Hardcoded `_infer_project_type()` preserved if LLM extraction fails
- **Usage:** Primarily prose contexts (vendor rationales: "for {project_type} requirements", LLM prompts)

**Rationale:** Human-like semantic understanding vs keyword matching; aligns with existing LLM-based extraction for all other structured fields (min_years, licenses, certifications); no UI filtering/categorization dependencies found.

**Migration Path:** SECTOR_KEYWORDS retained as fallback only; monitor fallback usage via logging; deprecate if rarely used in production.

## Pipeline Optimization: Enrichment After Filtering (Nov 2025)

**Problem:** Enrichment (website scraping, Apollo/Hunter API calls) was performed on all discovered vendors before filtering, resulting in 94% wasted resources.

**Previous Flow:**
```
Discovery (5000) → Enrichment (5000) → Filtering (→300) → Capability Matching
```

**Optimized Flow:**
```
Discovery (5000) → Filtering (→300) → Enrichment (300) → Capability Matching
```

**Key Insights:**
- `enrichment_flags` (high_value_supplier, frequent_supplier) come from **source data** (canada_contracts.py), not enrichment providers
- `website_content` is only used by **LLM capability matching** (after filtering)
- Filtering stages (duplicate detection, eligibility, geographic, preliminary ranking) **do not use** enrichment data (email, phone, website_content)

**Impact:**
- Time: 7 hours → 25 minutes (94% reduction)
- Cost: $300 → $18 per run (94% reduction for Apollo/Hunter API calls)
- Implementation: Single reorder in `pipeline.py:140-144`

**Implementation:** `src/vendor_ai_agent/pipeline.py:140-144`
```python
discovered_vendors = self.context.vendor_discovery.discover(tender_profile)
filtered_vendors = self.context.vendor_filter.filter(tender_profile, discovered_vendors)
enriched_vendors = self.context.vendor_enricher.enrich(filtered_vendors)  # Only top candidates
matches = self.context.capability_matcher.score(tender_profile, enriched_vendors)
```
