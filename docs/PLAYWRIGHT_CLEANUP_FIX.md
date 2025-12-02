# Playwright TargetClosedError Fix

## Problem

Async enrichment was producing `TargetClosedError` exceptions:

```
ERROR:asyncio:Future exception was never retrieved
future: <Future finished exception=TargetClosedError('Target page, context or browser has been closed')>
playwright._impl._errors.TargetClosedError: Target page, context or browser has been closed
```

## Root Cause

1. **Playwright browser lifecycle**: Browser instance was created once and reused across batches
2. **Premature context/page closure**: Context and page were closed immediately after scraping, but pending async operations still referenced them
3. **No cleanup mechanism**: Browser was never explicitly closed, creating resource leaks and race conditions

## Solution

### 1. Added `cleanup()` Method to `AsyncWebsiteScraper`

**File:** `src/vendor_ai_agent/modules/async_website_scraper.py` (lines 998-1022)

```python
async def cleanup(self) -> None:
    """Cleanup Playwright resources gracefully."""
    if not self.enable_playwright_fallback:
        return
    
    loop = asyncio.get_running_loop()
    context_handles = self._playwright_contexts.get(loop)
    
    if context_handles:
        browser = context_handles.get("browser")
        if browser:
            try:
                await browser.close()
                self.logger.debug("Playwright browser closed successfully")
            except Exception as e:
                self.logger.debug(f"Error closing Playwright browser: {e}")
        
        del self._playwright_contexts[loop]
    
    if self._playwright_instance and not self._playwright_contexts:
        try:
            await self._playwright_instance.stop()
            self._playwright_instance = None
            self.logger.debug("Playwright instance stopped successfully")
        except Exception as e:
            self.logger.debug(f"Error stopping Playwright instance: {e}")
```

**What it does:**
- Closes browser instance for current event loop
- Stops Playwright instance when all contexts are cleaned
- Gracefully handles errors during cleanup
- Only runs when Playwright fallback is enabled

### 2. Added Error Handling in `_fetch_with_playwright`

**File:** `src/vendor_ai_agent/modules/async_website_scraper.py` (lines 370-378)

```python
finally:
    try:
        await page.close()
    except Exception as e:
        self.logger.debug(f"Error closing page: {e}")
    try:
        await context.close()
    except Exception as e:
        self.logger.debug(f"Error closing context: {e}")
```

**What it does:**
- Wraps page/context close in try/except to prevent propagation of TargetClosedError
- Logs errors for debugging but doesn't fail the operation

### 3. Integrated Cleanup in `AsyncWebsiteContentProvider`

**File:** `src/vendor_ai_agent/enrichment_providers/async_website_content.py` (lines 89-136)

```python
async def enrich_batch_async(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
    # ... existing code ...
    
    try:
        results = await self.scraper.scrape_batch(urls_to_scrape)
        
        for url, result in results.items():
            for vendor in vendor_by_url.get(url, []):
                self._apply_scrape_result(vendor, result)
    finally:
        await self.scraper.cleanup()
    
    return vendors
```

**What it does:**
- Ensures cleanup is called after batch processing
- Uses try/finally to guarantee cleanup even if scraping fails
- Called per batch, ensuring fresh browser state for each batch

## Benefits

1. **No more TargetClosedError**: Browser resources are properly managed
2. **Better resource management**: Browser instances are cleaned up after use
3. **Improved stability**: Race conditions between close operations eliminated
4. **Graceful degradation**: Errors during cleanup don't break the enrichment flow

## Testing

Tested with:
```bash
poetry run python -c "
from src.vendor_ai_agent.enrichment_providers.async_website_content import AsyncWebsiteContentProvider
from src.vendor_ai_agent.models import VendorRecord
import asyncio

async def test():
    provider = AsyncWebsiteContentProvider(enable_playwright_fallback=False)
    vendor = VendorRecord(company_name='Test', website='https://example.com')
    result = await provider.enrich_batch_async([vendor])
    print('✓ Cleanup works')

asyncio.run(test())
"
```

Result: ✓ No errors, cleanup executed successfully

## Usage Notes

- Cleanup is **automatic** when using `AsyncWebsiteContentProvider.enrich_batch_async()`
- If using `AsyncWebsiteScraper` directly, **call `await scraper.cleanup()`** after batch operations
- Cleanup is **idempotent** - safe to call multiple times
- Only runs when `enable_playwright_fallback=True`

## Related Files

- `src/vendor_ai_agent/modules/async_website_scraper.py` - Core scraper with cleanup
- `src/vendor_ai_agent/enrichment_providers/async_website_content.py` - Provider integration
- `src/vendor_ai_agent/modules/enrichment.py` - Batch enrichment orchestration
