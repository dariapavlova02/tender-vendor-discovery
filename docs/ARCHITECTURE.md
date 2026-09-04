# Architecture

The application is a staged procurement-research pipeline. Source adapters isolate external
services from shared tender and vendor records; the orchestrator carries those records
through filtering, enrichment, scoring and export.

## Components

| Stage | Entry point | Responsibility |
| --- | --- | --- |
| Ingestion | [`ingestion/router.py`](../src/vendor_ai_agent/ingestion/router.py) | Tender metadata and attachment routing |
| Parsing | [`modules/document_parser.py`](../src/vendor_ai_agent/modules/document_parser.py) | File traversal, text, tables and optional OCR |
| Requirements | [`modules/requirement_extractor.py`](../src/vendor_ai_agent/modules/requirement_extractor.py) | Structured profile and search context |
| Discovery | [`sources/`](../src/vendor_ai_agent/sources/) | Registry, local database and web candidates |
| Filtering | [`modules/vendor_filter.py`](../src/vendor_ai_agent/modules/vendor_filter.py) | Duplicate, geographic and eligibility rules |
| Enrichment | [`enrichment_providers/`](../src/vendor_ai_agent/enrichment_providers/) | Websites, contacts and supporting metadata |
| Matching | [`modules/capability_matching.py`](../src/vendor_ai_agent/modules/capability_matching.py) | LLM assessment or explicit heuristic fallback |
| Export | [`modules/output_generator.py`](../src/vendor_ai_agent/modules/output_generator.py) | CSV, XLSX and JSON review records |

[`contracts.py`](../src/vendor_ai_agent/contracts.py) defines the stage interfaces;
[`models.py`](../src/vendor_ai_agent/models.py) defines the shared records.
[`pipeline.py`](../src/vendor_ai_agent/pipeline.py) coordinates the stages.

## Candidate lifecycle

The pipeline filters discovered vendors, optionally retrieves additional candidates,
and applies the same filters to the combined set. Synthetic directory vendors are
available only through an explicit configuration flag and are disabled by default.

Enrichment captures website material and contact metadata. Matching can use an LLM
provider or retain a heuristic ranking when assessment is unavailable. The score origin
is recorded as `llm` or `rule_based`; heuristic results stay in `needs_review` regardless
of their numeric score. If no assessed candidate meets the configured threshold, the
final shortlist is empty while `all_matches` remains available for inspection.

LLM rationales currently contain free-text evidence. Their quotations are not automatically
verified against page text. A score passing the threshold is not a certification of compliance.

## Execution and storage

The synchronous entry point supports asynchronous enrichment and a queue-based streaming
path for larger batches. Background dashboard jobs use a worker process and Parquet
artifacts. Existing pickle metadata is intended only for locally generated, trusted jobs.

Each upload request receives its own directory. Candidate-cache keys include the complete
tender profile and discovery/filter configuration; changing the requested batch does not
change the key. A source refresh with identical settings still requires clearing its cache.

SQLAlchemy stores vendor identities, industry codes, contacts and API cache entries.
The Canada CSV loader records successful chunk digests transactionally to avoid recounting
an identical chunk on a retry. It stops on a failed chunk instead of reporting a partial
import as successful. See [Data](DATA.md) for the boundaries of replay protection.

## Extension points

Add a source through the `VendorSource` interface or an enrichment provider through
`EnrichmentProvider`. Keep source identifiers and provenance on the resulting records,
and cover provider behaviour with a fake client before enabling a real integration.
The Python import namespace remains `vendor_ai_agent` for compatibility with existing adapters.
