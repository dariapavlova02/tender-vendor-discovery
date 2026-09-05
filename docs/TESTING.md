# Testing

The maintained suite checks software behaviour offline. It requires no LLM account, paid
API, external database or live website.

```bash
poetry install --with dev
make check
```

`make check` runs pytest, source syntax and local Markdown-link validation, then builds the
package. A separate smoke check loads the built wheel outside the checkout and exercises
CLI argument parsing, document parsing and empty-result exports with network access blocked.
GitHub Actions runs the same sequence.

## Scope

The tests cover source adapters with fake clients, duplicate and eligibility filtering,
contact handling and scoring-response parsing. Regression checks cover:

- CLI dispatch, late-candidate filtering and cache identity.
- Empty shortlists, heuristic review status and exported contact provenance.
- Markdown section parsing, isolated uploads, attachment size/time limits and partial-file cleanup.
- Canadian supplier filtering and transactionally recorded repeat-import protection in SQLite.

The test configuration disables dotenv, removes provider credentials, blocks Internet socket
connections and isolates generated files. The fixtures are test inputs, not production results.

## Production history and current verification

The application was used in a commercial production workflow. This suite checks the retained
implementation and subsequent maintenance changes; it does not recreate those historical runs.
Supplier relevance, extraction accuracy, contact deliverability and current provider behaviour
need separate checks with representative tenders and current credentials. OAuth, PostgreSQL,
container runtime and public deployment are outside this offline scope.

## Historical experiments

The original tree included one-off diagnostics, real API calls and paths into client tender
packages. Removed operational experiments remain in Git history.

The [historical DuckDuckGo adapter suite](../tests/legacy/README.md) is retained separately
because it targets an obsolete adapter interface and has known failures. It is not included
in `make check`. Expected behavioural assertions in the maintained suite are not relaxed to
match implementation.
