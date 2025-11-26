# Dashboard Guide

This guide reflects the current Streamlit dashboard (`src/vendor_ai_agent/dashboard.py`). All instructions are written in English and describe the UI as shipped today.

## Launching the Dashboard

```bash
poetry run streamlit run src/vendor_ai_agent/dashboard.py
```

The command opens the Streamlit app in the default browser. Use the sidebar to configure a run before uploading tender files.

## Sidebar Configuration

- **Analysis mode** – presets that enable/disable website scraping, contact scraping, and LLM scoring.
- **Maximum vendors to analyze** – slider controlling how many candidates are allowed to pass the filtering stage.
- **Batch processing block** – `Vendors per batch`, `Batch number`, and `Reuse cached vendors` control batch slicing and cache usage.
- **Auto ingestion** – toggle that determines whether the pipeline attempts to fetch attachments based on identifiers present in the tender.
- **Manual review** – if enabled, the pipeline pauses after extraction so the user can adjust city/state/country and NAICS codes before discovery.
- **API key status** – indicators for OpenAI and Apollo keys; Apollo-specific controls remain disabled when the key is missing.

## Upload and Run Flow

1. Upload one or more tender files (PDF/DOCX/XLSX). The UI stores them under `data/temp_upload/`.
2. Optionally deselect irrelevant files using the “Document Selection” section.
3. Click **Run Pipeline**. While the run is in progress, the UI shows stage-by-stage progress bars.
4. After completion, review the tabs (Overview, Extracted Data, Document Content, Vendors, Debug).

## Vendors Tab

- Shows selected vendors, all scored candidates, and metrics (raw count, matches, scored candidates, average score, past winners, missing contacts).
- When an Apollo key is configured, the section exposes:
  - Bulk buttons “Fetch emails (N)” and “Fetch phones (M)” for vendors lacking the corresponding contact field.
  - Per-vendor buttons that allow targeted Apollo enrichment.
- The tab always displays the current batch ID and the list of processed batches when caching is enabled.

## Batch Navigation

- When `Reuse cached vendors` is enabled, the pipeline stores filtered vendors for future batches. The dashboard keeps the latest `PipelineArtifacts` in `st.session_state` so a page rerun (triggered by Streamlit) does not discard results.
- To move to the next batch, change `Batch number` in the sidebar and run the pipeline again. A cached batch is loaded instantly without repeating discovery.
- The “Clear cached results” button appears whenever the dashboard is showing artifacts from a previous run; clicking it removes cached session data so the next run starts cleanly.

## Export Controls

After a run completes, the Export section provides:
- CSV download of the current matches.
- Excel workbook with matches.
- “Save to outputs” button that writes the usual JSON/CSV/XLSX trio via `Pipeline.save_outputs`.

## Known Limitations

- Reloading the browser tab resets the Streamlit session. Cached artifacts in `st.session_state` are cleared, so keep the tab open while reviewing results.
- Only one batch can be processed at a time in the UI. To schedule multiple batches automatically, use the CLI or a background script.
- Apollo enrichment buttons require `APOLLO_API_KEY` to be present in the environment running Streamlit.
