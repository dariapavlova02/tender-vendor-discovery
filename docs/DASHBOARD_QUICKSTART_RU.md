# Dashboard Quickstart

This quickstart mirrors the Streamlit dashboard that ships with the repository. It is fully aligned with the current code and is written in English.

## Prerequisites

```bash
poetry install
```

## Launch

```bash
poetry run streamlit run src/vendor_ai_agent/dashboard.py
```

## Three-Step Workflow

1. **Configure** – adjust sidebar options (analysis mode, max vendors, batch size, caching).
2. **Upload** – drop the tender files into the uploader. The dashboard displays a summary of selected vs. excluded files.
3. **Run** – click **Run Pipeline** and wait for the progress indicator to reach 100%.

## Key Features

- Extraction editor for city/state/country and NAICS adjustments before discovery.
- Vendors tab showing selected candidates, full candidate list, and enrichment metrics.
- Apollo actions for refreshing all missing emails/phones or per-vendor contacts.
- Export controls producing CSV and Excel snapshots of current matches.

Keep the browser tab open while reviewing results because Streamlit resets the session on full refresh.
