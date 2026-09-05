# Contributing

Use Python 3.11 and the committed Poetry lockfile:

```bash
poetry install --with dev
make check
```

Keep changes focused and preserve source provenance. Use fake provider responses and disposable
database fixtures for tests. Do not add API calls, real credentials or client documents to the
offline suite. Test expected behaviour independently of the current implementation.

Use Alembic migrations for schema changes. Keep public documentation aligned with executable
entry points, configured source wiring and observed results.
