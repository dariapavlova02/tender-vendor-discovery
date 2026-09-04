# Historical adapter tests

`test_duckduckgo_enrichment.py` targets an older adapter contract. It expects methods such as
`_normalize_company_name` that the current adapter no longer exposes; URL normalization and
ranking assertions also diverge. It is retained unchanged for reference and is **not** included
in the maintained offline suite. No claim is made that this historical suite passes.

The maintained selection is `tests/unit/`. Other one-off experiments remain in Git history.
