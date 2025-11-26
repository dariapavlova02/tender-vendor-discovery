# Contact Enrichment Guide

This guide reflects the current implementation in `src/vendor_ai_agent/enrichment_providers` and describes how vendor contact data is collected, validated, and stored.

## Components

| Provider | Module | Purpose |
| --- | --- | --- |
| `WebsiteContentProvider` | `enrichment_providers/website_content.py` | Scrapes public pages for capability text and stores extracted snippets in `filtering_metadata["website_content"]`. |
| `ContactScrapingProvider` | `enrichment_providers/contact_scraping.py` | Collects emails/phones via contact pages, regex extraction, LLM fallback, and Serper/Apollo lookups. |
| `SamContactProvider` | `enrichment_providers/sam_contact.py` | Retrieves SAM.gov points of contact for entities discovered via the SAM source. |
| `ManualEnrichmentService` | `modules/manual_enrichment.py` | Allows dashboard users to trigger Apollo enrichment for a single vendor or a batch. |
| `StaticContactsProvider` | `enrichment_providers/static_contacts.py` | Provides deterministic placeholder contacts when no other provider has data. |

The enrichment sequence is configured in `RuntimeConfig.enrichment.providers` and executed by `VendorEnricher`.

## Workflow

1. **Website scraping** populates `website_content`, `content_source`, and scrape metadata.
2. **Contact scraping** attempts to extract emails/phones from the scraped contact text. It uses regex first, then an LLM fallback if the regex pass finds nothing. If the vendor still lacks contacts, it tries Serper queries that are biased toward the vendor's domain.
3. **SAM contacts** are applied when the vendor has a matching SAM record. Emails from SAM are passed through the same filtering helper used by Serper to avoid assigning government-domain addresses to commercial vendors.
4. **Manual/Apollo enrichment** can be triggered from the dashboard. Bulk buttons (for all vendors missing emails/phones) call `ManualEnrichmentService.batch_enrich_apollo` so that users can fill gaps without leaving the UI.
5. **Static fallback** assigns deterministic `info@<slug>` email addresses only when no prior provider produced data. The fallback is tagged with `email_source = "fallback_static"` so downstream consumers can ignore it.

## Email Filtering

`filter_emails_for_vendor` (see `enrichment_providers/utils.py`) enforces domain-level safeguards:

- Accept addresses matching the vendor's website domain or a domain whose root matches the vendor's root.
- Accept addresses whose domain string contains a normalized company token.
- Reject government domains (e.g., `.gc.ca`, `.gov`, `.mil`) unless the vendor's own domain also ends with one of those suffixes.
- Remove common placeholder addresses (`noreply@`, `test@`, etc.).

Only filtered addresses are written back to `vendor.email`, which prevents situations where vendors inherit procurement-contact emails from tender documents.

## Serper Query Strategy

The targeted Serper lookup builds structured queries:

- When the vendor has a website domain, the query uses `site:<domain> ("contact" OR "email" OR "support") "<Company Name>"` to bias results toward that domain.
- When the site is unknown, the query falls back to a quoted company name with generic contact keywords.
- Responses are filtered via `filter_emails_for_vendor` before being applied.

## Dashboard Integration

- The Vendors tab now shows bulk buttons for “Fetch emails” and “Fetch phones.” They only enable when at least one matched vendor is missing the corresponding contact field.
- Each individual vendor row still has a “Fetch contacts” button if the user wants per-vendor control.
- After Apollo enrichment completes, the dashboard reruns automatically so the updated contacts appear without a manual refresh.

## Configuration Highlights

- `RuntimeConfig.enrichment.enable_contact_scraping` controls whether `ContactScrapingProvider` is registered.
- `RuntimeConfig.enrichment.enable_apollo_enrichment` and the presence of `APOLLO_API_KEY` control manual enrichment availability.
- `RuntimeConfig.enrichment.enable_targeted_serper_fallback` toggles the Serper-based lookup used when scraping fails.

## Troubleshooting

- Enable debug logging (`LOG_LEVEL=DEBUG`) to see which provider supplied each contact.
- Inspect `vendor.filtering_metadata["email_source"]` and `vendor.filtering_metadata["phone_source"]` to understand whether the value came from scraping, Serper, Apollo, SAM, or static fallback.
- If Apollo enrichment appears to do nothing, confirm that the API key is loaded into the dashboard process and that the vendor has enough metadata (company name, domain) for Apollo to resolve the record.
