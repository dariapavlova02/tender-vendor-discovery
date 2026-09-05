# Testing

This edition uses offline engineering checks. No LLM account, paid API, external database,
provider search or live website is required.

```bash
poetry install --with dev
make check
```

Recorded local check: **131 tests passed** on Python 3.11 / macOS ARM64.

`make check` runs pytest, source syntax and local Markdown-link validation, and package builds.
It then runs the built wheel outside the checkout with network access blocked and compares
its JSON results with the committed examples. The same sequence runs in GitHub Actions. The test configuration disables dotenv,
removes provider credentials, blocks Internet socket connections and isolates generated files.

## Scope

The retained tests exercise source adapters with fake clients, filtering, duplicate detection,
contact handling and scoring-response handling. Regression checks cover CLI dispatch,
late-candidate filtering, empty shortlists, heuristic review status, cache identity, export
provenance, isolated uploads and repeat-import protection with SQLite.

The local demo exercises parsing, section classification, deduplication and export. Checks
verify that changed input requirements change coverage and that missing evidence stays
visible. Attachment regressions cover isolated names, size limits, timeouts, partial-file
cleanup and unsupported URL schemes. Relevant Canadian suppliers are retained regardless
of sector words in their names.

The HTML report is also inspected locally at desktop and mobile sizes. This visual check
is separate from the automated suite.

## Historical experiments

The original tree mixed unit tests with one-off diagnostics, copied-algorithm experiments,
real API calls and paths into client tender packages. These operational experiments were
removed from the maintained tree during portfolio cleanup; they remain in Git history.
The current suite is an explicit offline scope, not a claim that every historical workflow
has been retested. Expected behavioural assertions are not relaxed to match implementation.

## Not measured

Supplier relevance, extraction accuracy, contact deliverability, latency under real provider
limits, PostgreSQL operation, OAuth and public deployment. Passing these checks does not
establish model quality or production readiness.

The [historical DuckDuckGo adapter suite](../tests/legacy/README.md) is retained separately
because it targets an obsolete adapter interface and has known failures. It is not included
in `make check`. The geographic-filter test explicitly selects filtering rather than the
current sorting-only default; its expected vendors are unchanged.
