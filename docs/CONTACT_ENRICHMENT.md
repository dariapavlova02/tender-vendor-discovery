# Contact Enrichment Guide

This guide reflects the current implementation in `src/vendor_ai_agent/enrichment_providers` and describes how vendor contact data is collected, validated, and stored.

## Components

| Provider | Module | Purpose |
| --- | --- | --- |
| `WebsiteContentProvider` | `enrichment_providers/website_content.py` | Scrapes public pages for capability text and stores extracted snippets in `filtering_metadata["website_content"]`. |
| `ContactScrapingProvider` | `enrichment_providers/contact_scraping.py` | Orchestrates 4-level contact enrichment cascade (see below). |
| `SmartEmailGeneratorProvider` | `enrichment_providers/smart_email_generator.py` | Level 4: Generates and validates email candidates using MX records and Serper context verification. |
| `SamContactProvider` | `enrichment_providers/sam_contact.py` | Retrieves SAM.gov points of contact for entities discovered via the SAM source. |
| `ManualEnrichmentService` | `modules/manual_enrichment.py` | Allows dashboard users to trigger Apollo enrichment for a single vendor or a batch. |
| `StaticContactsProvider` | `enrichment_providers/static_contacts.py` | Provides deterministic placeholder contacts when no other provider has data. |

The enrichment sequence is configured in `RuntimeConfig.enrichment.providers` and executed by `VendorEnricher`.

## 4-Level Contact Enrichment Cascade

`ContactScrapingProvider` implements a progressive fallback strategy to maximize contact coverage while minimizing API costs:

### Level 1: Direct Website Scraping
- **Method**: Parse HTML from vendor's website (contact/about pages)
- **Strategy**: Regex extraction followed by LLM fallback if no matches found
- **Coverage**: ~45-55% of vendors
- **Cost**: Website fetch only (already done by WebsiteContentProvider)

### Level 2: Serper Backup Contacts
- **Method**: Extract emails from Serper snippets cached during discovery phase
- **Strategy**: Reuse search results from initial vendor discovery
- **Coverage**: Additional ~10-15%
- **Cost**: Free (reuses existing data)

### Level 3: Targeted Serper Search
- **Method**: Structured Serper query targeting vendor's domain
- **Query Format**: `site:<domain> ("sales@" OR "contact@" OR "info@" OR "hello@" OR "inquiry@") "<Company Name>"`
- **Strategy**: Optimized to find actual email addresses (not generic "contact us" text)
- **Coverage**: Additional ~10-15%
- **Cost**: 1 Serper call per vendor (only when Levels 1-2 fail)

### Level 4: Smart Email Generation (New)
- **Method**: Generate and validate email candidates using MX records and contextual verification
- **Strategy**:
  1. Validate domain has valid MX records (fast rejection)
  2. Generate candidates: `{prefix}@{domain}` for prefixes: sales, contact, info, hello, inquiry, business
  3. Verify each candidate via Serper contextual search
  4. Require email + company name appear together in results
  5. Score confidence: 0.4 base + 0.2 (email found) + 0.3 (company found) + 0.1 (domain match)
  6. Accept candidates with confidence ≥ 0.6
- **Coverage**: Additional ~25-35% (total pipeline: 85-95%)
- **Cost**: ~0.2 Serper calls per vendor (only for ~15-20% that fail Level 3)

### Configuration

```python
# config.py - EnrichmentConfig
enable_smart_email_generation: bool = True            # Toggle Level 4
smart_email_enable_mx_check: bool = True             # Require valid MX records
smart_email_serper_validation: bool = True           # Require Serper context verification
smart_email_prefixes: List[str] = [                  # Email prefixes to try
    'sales', 'contact', 'info', 'hello', 'inquiry', 'business'
]
smart_email_max_candidates: int = 3                  # Max candidates to validate
smart_email_require_company_context: bool = True     # Require company name in results
smart_email_min_confidence: float = 0.6              # Minimum confidence threshold
```

## Workflow

1. **Website scraping** populates `website_content`, `content_source`, and scrape metadata.
2. **Contact scraping** attempts 4-level cascade (see above). Only proceeds to next level if current level fails.
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

### Level 3: Targeted Contact Search
The targeted Serper lookup (Level 3) builds structured queries optimized for email extraction:

- **With domain**: `site:<domain> ("sales@" OR "contact@" OR "info@" OR "hello@" OR "inquiry@") "<Company Name>"`
- **Without domain**: `"<Company Name>" ("sales@" OR "contact@" OR "info@" OR "hello@" OR "inquiry@")`
- **Rationale**: Specific email prefixes retrieve actual addresses instead of generic "contact us" text

### Level 4: Contextual Validation
Smart email generation uses Serper to verify generated candidates:

- **Query format**: `"<email>" "<Company Name>"`
- **Purpose**: Ensure email and company name appear together (not just domain matches)
- **Scoring**: Parses snippets to detect email presence (0.2), company name (0.3), domain match (0.1)
- **Threshold**: Requires 0.6 minimum confidence for acceptance

All responses are filtered via `filter_emails_for_vendor` before being applied.

## Dashboard Integration

- The Vendors tab now shows bulk buttons for “Fetch emails” and “Fetch phones.” They only enable when at least one matched vendor is missing the corresponding contact field.
- Each individual vendor row still has a “Fetch contacts” button if the user wants per-vendor control.
- After Apollo enrichment completes, the dashboard reruns automatically so the updated contacts appear without a manual refresh.

## Configuration Highlights

### Contact Enrichment
- `RuntimeConfig.enrichment.enable_contact_scraping` - Controls whether `ContactScrapingProvider` is registered
- `RuntimeConfig.enrichment.enable_targeted_serper_fallback` - Toggles Level 3 Serper search

### Smart Email Generation (Level 4)
- `RuntimeConfig.enrichment.enable_smart_email_generation` - Enable/disable Level 4
- `RuntimeConfig.enrichment.smart_email_enable_mx_check` - Require valid MX records (recommended: True)
- `RuntimeConfig.enrichment.smart_email_serper_validation` - Require contextual validation (recommended: True)
- `RuntimeConfig.enrichment.smart_email_prefixes` - Email prefixes to generate (default: sales, contact, info, hello, inquiry, business)
- `RuntimeConfig.enrichment.smart_email_max_candidates` - Maximum candidates to validate per vendor (default: 3)
- `RuntimeConfig.enrichment.smart_email_require_company_context` - Require company name in validation results (default: True)
- `RuntimeConfig.enrichment.smart_email_min_confidence` - Minimum confidence score to accept candidate (default: 0.6)

### Manual Enrichment
- `RuntimeConfig.enrichment.enable_apollo_enrichment` - Controls Apollo availability
- `APOLLO_API_KEY` environment variable must be set for Apollo enrichment

## Troubleshooting

### Debugging Contact Sources
- Enable debug logging (`LOG_LEVEL=DEBUG`) to see which provider supplied each contact
- Inspect `vendor.filtering_metadata["email_source"]` to understand origin:
  - `"website_regex"` - Level 1 regex extraction
  - `"website_llm"` - Level 1 LLM fallback
  - `"serper_backup"` - Level 2 cached snippets
  - `"targeted_serper"` - Level 3 structured search
  - `"smart_generation"` - Level 4 validated candidate
  - `"sam_entity"` - SAM.gov contact
  - `"apollo"` - Manual Apollo enrichment
  - `"fallback_static"` - Static placeholder
- Check `vendor.filtering_metadata["phone_source"]` for phone number origin

### Smart Email Generation Issues
- **No candidates generated**: Check `smart_email_enable_mx_check` - domain may lack valid MX records
- **Low acceptance rate**: Lower `smart_email_min_confidence` (default 0.6) or disable `smart_email_require_company_context`
- **High Serper costs**: Reduce `smart_email_max_candidates` or disable `smart_email_serper_validation`
- **Missing dnspython**: Install with `poetry add dnspython` or `pip install dnspython`

### Apollo Enrichment
- Confirm `APOLLO_API_KEY` is loaded into the dashboard process
- Ensure vendor has sufficient metadata (company name, domain) for Apollo resolution
- Check Apollo API quota limits
