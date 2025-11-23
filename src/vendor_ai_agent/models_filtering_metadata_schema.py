"""VendorRecord.filtering_metadata Schema Documentation

The `filtering_metadata` field is a flexible Dict[str, Any] that stores dynamic data
used by enrichment providers and filtering logic during pipeline execution.

## Website Content Provider Keys

When WebsiteContentProvider enriches a vendor, it populates the following keys:

### Success Case:
- `website_content` (str): Scraped content from vendor website (2-3K chars max)
- `content_source` (str): Source URL that was scraped
- `scrape_status` (str): "success"
- `scrape_timestamp` (str): ISO 8601 timestamp (e.g., "2024-01-15T10:30:00Z")

### Failure Cases:
- `scrape_status` (str): "timeout" | "404" | "no_url" | "invalid_url" | "no_content" | "error"
- `scrape_error` (str): Error message explaining why scraping failed
- `scrape_timestamp` (str): ISO 8601 timestamp
- `content_source` (str): URL that was attempted (may be empty if no_url)

## Geographic Filtering Keys

- `geo_match_reason` (str): Reason for geographic match/mismatch
- `local_match` (bool): Whether vendor is in local area
- `regional_match` (bool): Whether vendor is in regional area

## Eligibility Filtering Keys

- `eligibility_reason` (str): Reason for eligibility pass/fail
- `size_match` (bool): Whether vendor size meets requirements
- `set_aside_match` (bool): Whether vendor meets set-aside requirements

## Example Usage

```python
vendor = VendorRecord(
    company_name="Acme Corp",
    website="https://acme.com",
    filtering_metadata={}
)

# After WebsiteContentProvider enrichment:
vendor.filtering_metadata = {
    "website_content": "Acme Corp specializes in tactical uniforms...",
    "content_source": "https://acme.com",
    "scrape_status": "success",
    "scrape_timestamp": "2024-01-15T10:30:00Z"
}

# Check if content is available for LLM assessment:
if "website_content" in vendor.filtering_metadata:
    content = vendor.filtering_metadata["website_content"]
    # Use content for capability matching
```

## Notes

- All keys are optional and may not be present depending on which providers/filters ran
- New providers should document their keys here
- Keys should be namespaced if there's potential for conflicts (e.g., "geo_*", "scrape_*")
"""
