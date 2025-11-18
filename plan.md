# Tender Vendor AI Agent – Business Logic & Architecture Plan

## 1. Project Overview
The Tender Vendor AI Agent ingests public tender packages (USA & Canada), extracts structured requirements, discovers 500–2500 suitable vendors, verifies capabilities, and outputs transparent, source-backed vendor lists. The system emphasizes ethical data collection (only public/legal sources, ToS-compliant scraping, limited paid APIs) and explainability (match rationale + reference URLs per vendor). Target throughput is 3–5 tenders per day, each averaging 100–150 pages.

## 2. End-to-End Workflow
1. **Document Upload** – User supplies PDFs/DOCX/XLSX/ZIP per tender.
2. **Deterministic Parsing** – Python parsers convert each file to normalized text, remove headers/footers, segment by headings (scope, requirements, timelines, etc.), and extract critical data fields.
3. **Structured Tender Profile** – Aggregated JSON containing project type, geography, scope summary, mandatory criteria, timelines, and discovered codes/keywords.
4. **LLM Requirement Extraction** – GPT-based prompt refines profile, classifies project category, enumerates skills/certs/experience, identifies NAICS/NIGP codes, and generates an “Ideal Vendor Capability Profile.”
5. **Initial Vendor Discovery** – Multi-source harvesting (registries, awards databases, industry directories, association lists, tender artefacts) guided by keywords, NAICS codes, and geography.
6. **Data Enrichment** – Deduplicate vendors, resolve websites/domains, collect contact info via public sites and limited paid APIs (Apollo/Hunter) for prioritized subsets.
7. **Filtering & Geographic Pass** – Score vendors by proximity, compliance with regional constraints, and provenance (past awards, industry lists). Optional expansion widens geography when local pool is insufficient.
8. **Capability Matching (LLM)** – Compare each shortlisted vendor’s public profile vs. tender requirements, generate capability match score + rationale, capture supporting URLs.
9. **Output Compilation** – Produce CSV/XLSX/JSON with company data, contact details, industry codes, scores, rationales, source links, and enrichment flags. Results sorted by score; highlight local vs. expanded vendors.
10. **Review & Iteration** – User can adjust parameters (e.g., broaden geography) and re-run pipeline.

## 3. Document Processing & Parsing Strategy
- **Supported Formats**: PDF (pdfplumber/PyMuPDF), DOCX (python-docx/unstructured), XLSX (pandas/openpyxl), TXT/HTML (BeautifulSoup), ZIP bundles.
- **Segmentation**: Use layout cues + regex on headings ("Scope", "Requirements", etc.), leveraging `unstructured` partitioners for better section detection.
- **Data Extraction Targets**: Scope summary, location, timeline, mandatory & technical requirements, scale indicators, supplier restrictions, evaluation criteria.
- **Noise Reduction**: Strip repeated headers/footers, page numbers, boilerplate clauses. Flag low-quality OCR needs.
- **QA Checks**: Ensure critical sections are populated; validate language, length, completeness before LLM ingestion.

## 4. Requirement Extraction (LLM)
- **Models**: GPT-4 for critical reasoning, GPT-3.5 for lightweight classification; Claude considered for large contexts if cost allows.
- **Prompting**: Feed structured sections, request JSON with project_type, scope_summary, location, keywords, experience/cert requirements, NAICS/NIGP codes, vendor_profile, eligibility constraints. Emphasize quoting tender text for critical criteria and avoiding assumptions.
- **Cost Controls**: Only supply relevant sections, enforce concise outputs, optionally split tasks across cheaper models, maintain mapping of NAICS codes for validation.

## 5. Vendor Discovery Strategy
- **Search Parameters**: Combine project type, NAICS/NIGP codes, geography, mandatory keywords/certs to form queries per source.
- **Primary Data Sources**:
  - SAM.gov, USAspending/FPDS (US vendors & past awards)
  - Canadian registries (Buyandsell, provincial vendor lists, licensed contractor databases)
  - Provincial/state licensing boards
  - Industry associations/directories (e.g., Roofing Contractors Association)
  - Published award announcements (MERX, provincial portals)
  - Open business registries (OpenCorporates) and targeted web queries
  - Tender artifacts (site-visit attendee lists, incumbents)
- **Ethics & Compliance**: Use official APIs where possible, respect robots.txt/rate limits, avoid disallowed scraping (e.g., Google Maps mass scraping).
- **Captured Fields**: Company name, location, industry/category, source reference. Merge duplicates early.

## 6. Vendor Data Enrichment
- **Paid APIs**: Apollo.io for domain lookup + limited contact retrieval; Hunter.io or similar fallback. Apply only to top N prioritized vendors to stay within credit limits.
- **Website Scraping**: Requests + BeautifulSoup to capture contact info, services, certifications from vendor sites (home/contact/services pages only).
- **Normalization**: Standardize names, ensure single canonical entry per company, store website/email/phone/location, tag source(s) and enrichment path (web vs. API).

## 7. Multi-Stage Filtering & Ranking
1. **Geographic Scoring**: Assign proximity points (same city/province/state/country) and enforce mandatory regional restrictions.
2. **Experience Weighting**: Boost vendors from past awards or specialized directories; downgrade generic entries.
3. **Deduplication & Pruning**: Remove mismatches (wrong industry) prior to expensive steps.
4. **Optional Expansion**: On-demand national pass reinserts broader vendors, tagged distinctly.
5. **Capability Matching (LLM)**:
   - Scrape relevant site sections (About/Services/Projects) and condense text.
   - Prompt LLM with tender vendor profile + vendor text; request numeric score (0–100) and rationale citing evidence. Instruct model to avoid assumptions when evidence missing.
   - Optionally run verification prompt listing matched requirements to guard against hallucinations.
   - Discard low-scoring vendors; retain others with match_score + rationale + supporting URL.

## 8. Output Specification
- **Formats**: XLSX (primary), CSV, JSON. Use pandas for export, add filters and clear headers.
- **Columns**: company_name, website, email, phone, location, industry/NAICS, capability_match_score, why_relevant, source_url(s), enrichment_flags (e.g., `apollo_enriched`, `past_winner`).
- **Sorting**: Descending by match score, optionally grouped by local vs. expanded vendors.
- **Quality Checks**: Ensure all mandatory columns populated, contact info valid, rationales specific, references clickable.

## 9. Technology Stack & Infrastructure
- **Language**: Python 3.x
- **Libraries**: pdfplumber, PyMuPDF, unstructured, python-docx, pandas, openpyxl/xlsxwriter, requests, BeautifulSoup4, optional Selenium/Playwright, OpenAI SDK, Apollo API client, asyncio for batched requests.
- **Storage/Caching**: In-memory dicts/DataFrames for runs; optional SQLite cache for vendors/tenders to avoid re-processing.
- **Deployment**: CLI first, optional Streamlit/Flask UI later. Containerize with Docker for dependency consistency. Implement logging (token usage, API hits) and dotenv-based config for API keys.
- **Cost Guardrails**: Token counting, strategic model selection, throttle enrichment API calls, cache results.

## 10. Modular Architecture
- **Module A – Document Parser**: `parse_documents(files) -> tender_sections`
- **Module B – Requirement Extractor (LLM)**: `extract_requirements(sections) -> tender_profile`
- **Module C – Vendor Discovery**: Source-specific collectors returning vendor candidates.
- **Module D – Enrichment**: Website discovery, contact scraping, Apollo/Hunter enrichment, dedupe.
- **Module E – Filtering**: Geography + rule-based pruning, optional expansion.
- **Module F – Capability Matching (LLM)**: Website text harvesting + scoring prompt per vendor.
- **Module G – Output Generator**: Build DataFrame, export XLSX/CSV/JSON, attach metadata.
- **Interface Layer**: CLI / minimal UI orchestrating modules with configurable parameters.

## 11. Development Timeline (One-Week MVP)
- **Milestone 1 (Days 1–3)**
  - Implement Modules A & B with sample tenders; verify structured outputs.
  - Build initial vendor discovery pipeline with key sources; produce raw vendor lists.
  - Prototype enrichment (website detection) and filtering; generate sample CSV.
- **Milestone 2 (Days 4–7)**
  - Integrate Apollo/Hunter enrichment with caching and prioritization logic.
  - Expand discovery sources (US + Canada registries, awards) and parametrize queries.
  - Finalize LLM capability matching and rationale generation; optimize token use.
  - Implement end-to-end orchestration + CLI/UI, add logging, run multi-tender tests, document setup/run instructions.

## 12. Post-MVP Enhancements (Future Work)
- Robust retry/exception handling for all external calls.
- Persistent caching of parsed tenders and enriched vendors (SQLite/Redis).
- Automated monitoring (token usage, per-stage timing, number of vendors by source).
- Additional data sources and OCR integration for scanned PDFs.
- Direct CRM/email integration or outreach automation once data is validated.

This blueprint balances accuracy, explainability, and operational efficiency, ensuring the Tender Vendor AI Agent can reliably deliver high-quality vendor lists within the stated budget and timeline.
