# Architecture

The system performs supplier research in stages. A tender profile drives source selection
and queries; shared vendor records carry registry data, enrichment results and assessment
metadata into the dashboard and exports.

## Components

| Stage | Entry point | Responsibility |
| --- | --- | --- |
| Ingestion | [`ingestion/router.py`](../src/vendor_ai_agent/ingestion/router.py) | Tender metadata and attachment routing |
| Parsing | [`modules/document_parser.py`](../src/vendor_ai_agent/modules/document_parser.py) | Text sections, tables and optional OCR |
| Requirements | [`modules/requirement_extractor.py`](../src/vendor_ai_agent/modules/requirement_extractor.py) | Structured tender profile |
| Search context | [`modules/tender_profiler.py`](../src/vendor_ai_agent/modules/tender_profiler.py) | Sector, contract type, industry codes and search terms |
| Discovery | [`modules/vendor_discovery.py`](../src/vendor_ai_agent/modules/vendor_discovery.py) | Query compatible registered sources |
| Filtering | [`modules/vendor_filter.py`](../src/vendor_ai_agent/modules/vendor_filter.py) | Duplicate, geographic and eligibility rules |
| Enrichment | [`modules/enrichment.py`](../src/vendor_ai_agent/modules/enrichment.py) | Website and contact providers, batch execution |
| Assessment | [`modules/capability_matching.py`](../src/vendor_ai_agent/modules/capability_matching.py) | LLM scoring and heuristic fallback |
| Export | [`modules/output_generator.py`](../src/vendor_ai_agent/modules/output_generator.py) | CSV, XLSX and JSON records |

[`pipeline.py`](../src/vendor_ai_agent/pipeline.py) wires the stages together;
[`models.py`](../src/vendor_ai_agent/models.py) defines their shared records.

## Source wiring

The standard pipeline registers SAM entities and the Canadian database source, then checks
their compatibility with the tender profile. SAM requires appropriate industry codes and
API credentials. Canadian discovery queries imported supplier records rather than downloading
a complete registry at run time.

Optional primary discovery uses Apollo when enabled with a key, otherwise Serper when
enabled with a key. Additional Serper/Apollo searches can run before enrichment to fill
an undersized candidate pool. These are candidate-count checks, not relevance checks.

Serper discovery defaults to Places search. It can instead use organic web results.
Queries are generated from the tender context and expanded geographically. The implementation
also applies contract-type keyword rules and domain exclusions.

The automatically registered enrichment providers are:

- `HybridWebsiteEnricher`, when website lookup is enabled and a Serper key is available:
  DuckDuckGo lookup with Serper fallback.
- `AsyncWebsiteContentProvider`, when website scraping is enabled: retrieve text from
  company pages, reuse cached content and optionally render pages with Playwright.
- `ContactScrapingProvider`, when contact scraping is enabled and a Serper key is available:
  extract contacts from websites, use search fallbacks, and optionally try email candidates
  with provenance and validation metadata.

Apollo manual enrichment is available through the dashboard. Other adapter classes in the
repository are not automatically part of this provider list. The retained static directory
fixture source is disabled by default and is not a production information source.

## What the 500-company limit means

The default `filtering.max_candidates` is 500. The dashboard exposes this as **Maximum vendors
to analyze**. The same value sets the discovery target and the enrichment relevance target,
but filtering caps the pool before enrichment. A pool of 500 therefore cannot guarantee
500 relevant outputs: every data gap or rejection reduces the attainable total.

Before final assessment:

1. Discovery aggregates source results and may attempt supplemental searches.
2. Government-source candidates are capped at 70% of the configured analysis limit by
   default. This truncation currently also applies when Serper is unavailable.
3. Filtering merges duplicates, checks eligibility and ranks candidates. Geographic sorting
   is enabled by default; it does not impose a strict local-only exclusion.
4. The pool is capped and passed through the requested processing batch. The default
   discovery batch size is also 500.

There is no post-assessment discovery loop to replace rejected or unscorable candidates.
The numerical settings are implementation limits, not measured capacity or output guarantees.

## Assessment and result states

The assessment uses a tender summary and captured website text. The current prompt includes
only the first 2,500 characters of website content; tender sections are also shortened.
Relevant evidence elsewhere on the site or later in a section may therefore be absent from
the model input. Search and capture quality directly affect the information available to score.

The default shortlist threshold is 40. A scored record at or above that threshold can receive
`selected`; a heuristic fallback stays in `needs_review`. Candidates with missing website
content are skipped for scoring. They should not be interpreted as assessed non-matches.

`all_matches` contains scored records, not necessarily every discovered or enriched company.
In the streaming path, only scored records are written to the match output and reconstructed
as enriched results. This limits the visibility of candidates lost before assessment.
LLM quotations in rationales are not automatically checked against page text.

## Execution and persistence

The standard async configuration uses streaming for batches of at least 50 candidates.
The default streaming batch size is 50 with two concurrent consumers. Non-streaming enrichment
has separate batch limits and quality gates that can stop processing early; the streaming
path does not use those same gates.

Dashboard workers run in a background process and write Parquet artifacts. Existing pickle
metadata is intended for locally generated, trusted jobs. SQLAlchemy stores suppliers,
industry codes, contacts and API-cache entries; Alembic manages schema changes.

Candidate-cache keys include the full tender profile and discovery/filter settings. Changing
the requested batch preserves the cache identity. A source refresh with unchanged settings
requires clearing its cache. Website content uses a separate domain cache.

Uploads and attachment downloads use isolated paths. Downloads have a 20 MiB size cap,
a 20-second socket timeout and a 120-second deadline checked between reads. Failed downloads
are logged and exposed on the fetcher; incomplete files are removed.

Canada CSV imports record successful chunk digests in the same transaction as vendor updates.
See [Data](DATA.md) for replay and reconciliation boundaries.

## Extension points

Add sources through the `VendorSource` interface and enrichment providers through
`EnrichmentProvider`. Preserve source identifiers and provenance on shared records.
The Python import namespace remains `vendor_ai_agent` for existing integrations.
