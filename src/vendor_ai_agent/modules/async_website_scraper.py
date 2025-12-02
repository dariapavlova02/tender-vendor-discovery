"""Async website content scraper with caching and rate limiting."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


class DomainRateLimiter:
    def __init__(self, min_delay_seconds: float = 2.0):
        self.min_delay = min_delay_seconds
        self._last_request: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    async def wait_if_needed(self, domain: str):
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        
        async with self._locks[domain]:
            last_time = self._last_request.get(domain, 0)
            elapsed = time.time() - last_time
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                await asyncio.sleep(wait_time)
            self._last_request[domain] = time.time()


@dataclass
class CachedWebsiteContent:
    domain: str
    scraped_at: str
    ttl_hours: int
    content: Dict[str, Any]
    contacts: Dict[str, List[str]]
    metadata: Dict[str, Any]


class WebsiteCache:
    def __init__(self, cache_dir: Path | str = "outputs/cache/websites", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def _get_cache_path(self, domain: str) -> Path:
        domain_hash = hashlib.md5(domain.encode()).hexdigest()
        return self.cache_dir / f"{domain_hash}.json"
    
    def get(self, domain: str) -> Optional[CachedWebsiteContent]:
        cache_path = self._get_cache_path(domain)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            scraped_at = datetime.fromisoformat(data['scraped_at'])
            ttl = timedelta(hours=data.get('ttl_hours', self.ttl_hours))
            if datetime.now(timezone.utc) - scraped_at > ttl:
                cache_path.unlink()
                return None
            return CachedWebsiteContent(**data)
        except Exception:
            return None
    
    def set(self, domain: str, content: Dict[str, Any], contacts: Dict[str, List[str]], metadata: Dict[str, Any]) -> None:
        from dataclasses import asdict
        cache_path = self._get_cache_path(domain)
        cached = CachedWebsiteContent(
            domain=domain,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            ttl_hours=self.ttl_hours,
            content=content,
            contacts=contacts,
            metadata=metadata
        )
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(cached), f, indent=2)
        except Exception:
            pass


@dataclass
class ScrapedContent:
    content: str
    source_urls: List[str]
    status: str
    timestamp: str
    fetch_duration_ms: int
    error_message: Optional[str] = None
    from_cache: bool = False


@dataclass
class ContactScrapedContent:
    """Contact scraping result."""
    contact_text: str
    source_urls: List[str]
    status: str
    timestamp: str
    fetch_duration_ms: int
    error_message: Optional[str] = None
    from_cache: bool = False


class AsyncWebsiteScraper:
    
    PRIORITY_PATHS = {
        "tier1": ["/", "/about", "/services"],
        "tier2": ["/capabilities", "/solutions", "/products", "/expertise"],
        "tier3": ["/portfolio", "/industries", "/projects"],
    }
    
    CONTACT_PATHS = [
        "/contact",
        "/contact-us",
        "/contactus",
        "/contacts",
        "/contact.php",
        "/contact.html",
        "/contact.htm",
        "/get-in-touch",
        "/reach-us",
        "/reach",
        "/contact-info",
        "/contact-form",
        "/about/contact",
    ]
    
    TIMEOUT_TIER1 = 8.0
    TIMEOUT_TIER2 = 10.0
    TIMEOUT_TIER3 = 12.0
    TIMEOUT_CONTACT = 10.0
    DELAY_BETWEEN_REQUESTS = 2.0
    
    EARLY_STOP_TIER1 = 1000
    EARLY_STOP_TIER2 = 1500

    FORBIDDEN_RETRY_ATTEMPTS = 3
    FORBIDDEN_RETRY_BACKOFF_SECONDS = 1.5
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_10) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-G996B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    ]
    
    BROWSER_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    
    def __init__(
        self,
        timeout_seconds: float = 3.0,
        max_content_chars: int = 3000,
        min_content_chars: int = 500,
        max_concurrent_global: int = 15,
        max_concurrent_per_domain: int = 1,
        enable_cache: bool = True,
        cache_dir: str = "outputs/cache/websites",
        cache_ttl_hours: int = 24,
        max_batch_concurrency: int = 8,
        *,
        enable_playwright_fallback: bool = False,
        playwright_max_contexts: int = 2,
        playwright_wait_ms: int = 800,
    ):
        self.timeout = timeout_seconds
        self.max_chars = max_content_chars
        self.min_chars = min_content_chars
        self.max_concurrent_global = max_concurrent_global
        self.max_concurrent_per_domain = max_concurrent_per_domain
        self.logger = logging.getLogger(__name__)
        
        self._global_semaphore: Optional[asyncio.Semaphore] = None
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._init_lock: Optional[asyncio.Lock] = None
        
        self.cache: Optional[WebsiteCache] = None
        if enable_cache:
            self.cache = WebsiteCache(cache_dir=cache_dir, ttl_hours=cache_ttl_hours)
        self.max_batch_concurrency = max(1, max_batch_concurrency)
        self._domain_headers: Dict[str, Dict[str, str]] = {}
        self._rate_limiter = DomainRateLimiter(min_delay_seconds=2.0)

        self.enable_playwright_fallback = enable_playwright_fallback
        self.playwright_max_contexts = max(1, playwright_max_contexts)
        self.playwright_wait_ms = max(0, playwright_wait_ms)
        self._playwright_instance = None
        self._playwright_lock: Optional[asyncio.Lock] = None
        self._playwright_contexts: Dict[asyncio.AbstractEventLoop, dict] = {}
    
    def _get_random_headers(self) -> Dict[str, str]:
        """Get randomized browser headers."""
        import random
        headers = self.BROWSER_HEADERS.copy()
        headers["User-Agent"] = random.choice(self.USER_AGENTS)
        
        referers = [
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://duckduckgo.com/",
        ]
        headers["Referer"] = random.choice(referers)
        
        languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-CA,en;q=0.9",
            "en-US,en;q=0.8",
        ]
        headers["Accept-Language"] = random.choice(languages)
        
        return headers

    def _get_domain_headers(self, domain: str) -> Dict[str, str]:
        """Get persistent headers for a domain to reuse cookies + UA."""
        headers = self._domain_headers.get(domain)
        if headers is None:
            headers = self._get_random_headers()
            self._domain_headers[domain] = headers
        return headers.copy()

    def _extract_text_from_html(
        self,
        html: str,
        *,
        strip_navigation: bool,
        include_mailto: bool,
        min_length: int,
    ) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")

        mailto_emails: List[str] = []
        if include_mailto:
            for anchor in soup.find_all("a", href=True):
                href = str(anchor["href"]).strip()
                if href.lower().startswith("mailto:"):
                    email = href[7:].split("?")[0]
                    if email:
                        mailto_emails.append(email)
            for elem in soup.find_all(attrs={"data-email": True}):
                email_val = elem.get("data-email")
                if email_val and isinstance(email_val, str):
                    mailto_emails.append(email_val.strip())

        tags_to_strip = ["script", "style", "iframe"]
        if strip_navigation:
            tags_to_strip.extend(["nav", "footer", "header", "aside"])

        for tag in soup(tags_to_strip):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        if include_mailto and mailto_emails:
            text = f"{text} {' '.join(mailto_emails)}"
        text = " ".join(text.split())
        printable_ratio = sum(ch.isprintable() and not ch.isspace() for ch in text) / max(len(text), 1)
        if printable_ratio < 0.5:
            return None
        replacement_ratio = text.count("\ufffd") / max(len(text), 1)
        if replacement_ratio > 0.05:
            return None
        return text if len(text) > min_length else None

    async def _ensure_playwright_browser(self) -> dict:
        loop = asyncio.get_running_loop()
        context = self._playwright_contexts.get(loop)
        if context is not None:
            return context
        if self._playwright_lock is None:
            self._playwright_lock = asyncio.Lock()
        async with self._playwright_lock:
            context = self._playwright_contexts.get(loop)
            if context is not None:
                return context
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                self.logger.error("Playwright dependency missing: %s", exc)
                raise
            if self._playwright_instance is None:
                self._playwright_instance = await async_playwright().start()
            browser = await self._playwright_instance.chromium.launch(headless=True)
            semaphore = asyncio.Semaphore(self.playwright_max_contexts)
            context = {"browser": browser, "semaphore": semaphore}
            self._playwright_contexts[loop] = context
            return context

    async def _fetch_with_playwright(
        self,
        url: str,
        *,
        timeout: float,
        strip_navigation: bool,
        include_mailto: bool,
        min_length: int,
        domain: str,
    ) -> Optional[str]:
        if not self.enable_playwright_fallback:
            return None
        try:
            context_handles = await self._ensure_playwright_browser()
        except Exception as exc:
            self.logger.error("Disabling Playwright fallback: %s", exc)
            self.enable_playwright_fallback = False
            return None

        headers = self._get_domain_headers(domain)
        browser = context_handles["browser"]
        semaphore = context_handles["semaphore"]

        async with semaphore:
            context = await browser.new_context(
                user_agent=headers.get("User-Agent"),
                locale="en-US",
            )
            page = await context.new_page()
            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(max(timeout, self.timeout) * 1000),
                )
                if self.playwright_wait_ms:
                    await page.wait_for_timeout(self.playwright_wait_ms)
                html = await page.content()
                return self._extract_text_from_html(
                    html,
                    strip_navigation=strip_navigation,
                    include_mailto=include_mailto,
                    min_length=min_length,
                )
            except Exception as exc:
                self.logger.debug(f"Playwright fetch failed for {url}: {exc}")
                return None
            finally:
                try:
                    await page.close()
                except Exception as e:
                    self.logger.debug(f"Error closing page: {e}")
                try:
                    await context.close()
                except Exception as e:
                    self.logger.debug(f"Error closing context: {e}")
    
    async def _ensure_semaphores(self) -> asyncio.Semaphore:
        """Lazy initialization of semaphores in the current event loop."""
        if self._global_semaphore is None:
            if self._init_lock is None:
                self._init_lock = asyncio.Lock()
            
            async with self._init_lock:
                if self._global_semaphore is None:
                    self._global_semaphore = asyncio.Semaphore(self.max_concurrent_global)
                    self.logger.debug("Initialized global semaphore in current event loop")
        
        return self._global_semaphore
    
    async def _get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or create semaphore for a domain in the current event loop."""
        if domain not in self._domain_semaphores:
            self._domain_semaphores[domain] = asyncio.Semaphore(self.max_concurrent_per_domain)
        return self._domain_semaphores[domain]
    
    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        """Get or create lock for a domain in the current event loop."""
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        return self._domain_locks[domain]
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to base domain with scheme (removes paths)."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        return base_url
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme in ("http", "https") and parsed.netloc)
        except Exception:
            return False
    
    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        timeout: float,
        retry_on_403: bool = True,
        *,
        include_status: bool = False,
        domain: Optional[str] = None,
    ):
        """Fetch and extract text content from a single page."""
        status_code: Optional[int] = None

        def _result(value: Optional[str]):
            if include_status:
                return value, status_code
            return value

        attempts = self.FORBIDDEN_RETRY_ATTEMPTS if retry_on_403 else 0
        target_domain = domain or self._get_domain(self._normalize_url(url))
        
        await self._rate_limiter.wait_if_needed(target_domain)

        content_type = None

        for attempt in range(attempts + 1):
            try:
                response = await client.get(
                    url,
                    timeout=timeout,
                    follow_redirects=True,
                    headers=self._get_domain_headers(target_domain),
                )
                response.raise_for_status()
                status_code = response.status_code
                content_type = response.headers.get("Content-Type", "")

                text = None
                httpx_got_html = False
                if "text" in content_type or "html" in content_type:
                    httpx_got_html = True
                    text = self._extract_text_from_html(
                        response.text,
                        strip_navigation=True,
                        include_mailto=False,
                        min_length=100,
                    )
                
                if text:
                    return _result(text)
                
                if httpx_got_html and self.enable_playwright_fallback:
                    self.logger.debug(f"HTTPx got HTML but extraction failed for {url}, trying Playwright")
                    fallback = await self._fetch_with_playwright(
                        url,
                        timeout=timeout,
                        strip_navigation=True,
                        include_mailto=False,
                        min_length=100,
                        domain=target_domain,
                    )
                    if fallback:
                        status_code = 200
                        return _result(fallback)
                
                return _result(text)

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                should_retry = (
                    status_code == 403
                    and retry_on_403
                    and attempt < attempts
                )
                if should_retry:
                    delay = self.FORBIDDEN_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                    self.logger.debug(
                        f"403 Forbidden on {url}, retry {attempt + 1}/{attempts} after {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                self.logger.debug(f"Failed to fetch {url}: {status_code}")
                break
            except (httpx.TimeoutException, httpx.RequestError) as e:
                self.logger.debug(f"Failed to fetch {url}: {type(e).__name__}")
                break
            except Exception as e:
                self.logger.debug(f"Unexpected error fetching {url}: {e}")
                break

        if self.enable_playwright_fallback:
            fallback = await self._fetch_with_playwright(
                url,
                timeout=timeout,
                strip_navigation=True,
                include_mailto=False,
                min_length=100,
                domain=target_domain,
            )
            if fallback:
                status_code = 200
                return _result(fallback)

        return _result(None)
    
    async def _fetch_paths_parallel(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        domain: str,
    ) -> tuple[List[str], List[str], bool]:
        """Fetch multiple paths with 3-tier strategy and progressive timeouts."""
        content_parts: List[str] = []
        successful_urls: List[str] = []
        blocked = False

        domain_sem = await self._get_domain_semaphore(domain)

        async def _handle_path(target_url: str, timeout: float) -> bool:
            nonlocal blocked
            result = await self._fetch_page(
                client,
                target_url,
                timeout,
                include_status=True,
                domain=domain,
            )
            
            if result is None:
                return False
            
            content, status = result

            if status == 403:
                blocked = True
                self.logger.warning(f"403 Forbidden on {target_url}, throttling domain")
                return True

            if content:
                content_parts.append(content[:self.max_chars])
                successful_urls.append(target_url)
                self.logger.debug(f"  ✓ {target_url[len(base_url):] or '/'} ({len(content)} chars)")

            return len("".join(content_parts)) >= self.max_chars

        for path in self.PRIORITY_PATHS["tier1"]:
            target_url = urljoin(base_url, path)

            async with domain_sem:
                should_stop = await _handle_path(target_url, self.TIMEOUT_TIER1)
            if blocked or should_stop:
                break
            await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)

        if not blocked and len("".join(content_parts)) < self.EARLY_STOP_TIER1:
            self.logger.debug(
                f"Tier1 insufficient ({len(''.join(content_parts))} < {self.EARLY_STOP_TIER1}), proceeding to tier2"
            )
            for path in self.PRIORITY_PATHS["tier2"]:
                target_url = urljoin(base_url, path)

                async with domain_sem:
                    should_stop = await _handle_path(target_url, self.TIMEOUT_TIER2)
                if blocked or should_stop:
                    break
                await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)

        if not blocked and len("".join(content_parts)) < self.EARLY_STOP_TIER2:
            self.logger.debug(
                f"Tier2 insufficient ({len(''.join(content_parts))} < {self.EARLY_STOP_TIER2}), proceeding to tier3"
            )
            for path in self.PRIORITY_PATHS["tier3"]:
                target_url = urljoin(base_url, path)

                async with domain_sem:
                    should_stop = await _handle_path(target_url, self.TIMEOUT_TIER3)
                if blocked or should_stop:
                    break
                await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)

        return content_parts, successful_urls, blocked
    
    async def _scrape_domain(self, client: httpx.AsyncClient, website_url: str) -> ScrapedContent:
        """Scrape a single domain with caching support."""
        start_time = time.time()
        
        base_url = self._normalize_url(website_url)
        domain = self._get_domain(base_url)
        
        if not self._is_valid_url(base_url):
            return ScrapedContent(
                content="",
                source_urls=[],
                status="invalid_url",
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=0,
                error_message=f"Invalid URL: {website_url}"
            )
        
        if self.cache:
            cached = self.cache.get(domain)
            if cached:
                duration_ms = int((time.time() - start_time) * 1000)
                self.logger.debug(f"Cache hit: {domain}")
                return ScrapedContent(
                    content=cached.content.get("text", ""),
                    source_urls=cached.content.get("source_urls", []),
                    status="success",
                    timestamp=cached.scraped_at,
                    fetch_duration_ms=duration_ms,
                    from_cache=True
                )
        
        try:
            global_sem = await self._ensure_semaphores()
            
            async with global_sem:
                content_parts, successful_urls, blocked = await self._fetch_paths_parallel(
                    client, base_url, domain
                )

            full_content = " ".join(content_parts)[:self.max_chars]
            duration_ms = int((time.time() - start_time) * 1000)

            error_message = None
            if blocked and not full_content:
                status = "blocked"
                error_message = "403 Forbidden"
                self.logger.warning(f"Access blocked for {domain}")
            elif not full_content or len(full_content) < 100:
                status = "no_content"
                self.logger.warning(f"No content for {domain}")
            else:
                status = "success"
                self.logger.info(f"Scraped {domain}: {len(full_content)} chars from {len(successful_urls)} pages ({duration_ms}ms)")
            
            if self.cache and status == "success":
                self.cache.set(
                    domain=domain,
                    content={
                        "text": full_content,
                        "source_urls": successful_urls
                    },
                    contacts={"emails": [], "phones": []},
                    metadata={"fetch_duration_ms": duration_ms}
                )
            
            return ScrapedContent(
                content=full_content,
                source_urls=successful_urls,
                status=status,
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=duration_ms,
                error_message=error_message,
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.error(f"Error scraping {domain}: {e}")
            return ScrapedContent(
                content="",
                source_urls=[],
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=duration_ms,
                error_message=str(e)
            )
    
    async def scrape_batch(self, website_urls: List[str]) -> Dict[str, ScrapedContent]:
        """Scrape multiple websites in parallel."""
        if not website_urls:
            return {}
        
        unique_urls = list(dict.fromkeys(url for url in website_urls if url))
        self.logger.info(f"Starting async scrape: {len(unique_urls)} domains")
        
        async with httpx.AsyncClient(
            verify=False,
            http2=True,
        ) as client:
            semaphore = asyncio.Semaphore(self.max_batch_concurrency)

            async def run_with_limit(target_url: str):
                async with semaphore:
                    return await self._scrape_domain(client, target_url)

            tasks = [run_with_limit(url) for url in unique_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        results_dict = {}
        for url, result in zip(unique_urls, results):
            domain = self._get_domain(self._normalize_url(url))
            if isinstance(result, Exception):
                self.logger.error(f"Exception for {domain}: {result}")
                results_dict[url] = ScrapedContent(
                    content="",
                    source_urls=[],
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    fetch_duration_ms=0,
                    error_message=str(result)
                )
            else:
                results_dict[url] = result
        
        success_count = sum(1 for r in results_dict.values() if r.status == "success")
        cache_hits = sum(1 for r in results_dict.values() if r.from_cache)
        self.logger.info(
            f"Batch complete: {success_count}/{len(unique_urls)} successful "
            f"({cache_hits} from cache)"
        )
        
        return results_dict
    
    def scrape_batch_sync(self, website_urls: List[str]) -> Dict[str, ScrapedContent]:
        """Synchronous wrapper for scrape_batch."""
        return asyncio.run(self.scrape_batch(website_urls))
    
    async def _fetch_page_with_contacts(
        self,
        client: httpx.AsyncClient,
        url: str,
        timeout: float,
        retry_on_403: bool = True,
        *,
        domain: Optional[str] = None,
    ) -> Optional[str]:
        """Fetch page preserving contact information (no removal of nav/footer/header)."""
        attempts = self.FORBIDDEN_RETRY_ATTEMPTS if retry_on_403 else 0
        target_domain = domain or self._get_domain(self._normalize_url(url))

        content_type = None

        for attempt in range(attempts + 1):
            try:
                response = await client.get(
                    url,
                    timeout=timeout,
                    follow_redirects=True,
                    headers=self._get_domain_headers(target_domain),
                )
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")

                text = None
                httpx_got_html = False
                if "text" in content_type or "html" in content_type:
                    httpx_got_html = True
                    text = self._extract_text_from_html(
                        response.text,
                        strip_navigation=False,
                        include_mailto=True,
                        min_length=50,
                    )
                
                if text:
                    return text
                
                if httpx_got_html and self.enable_playwright_fallback:
                    self.logger.debug(f"HTTPx got HTML but extraction failed for contact page {url}, trying Playwright")
                    fallback = await self._fetch_with_playwright(
                        url,
                        timeout=timeout,
                        strip_navigation=False,
                        include_mailto=True,
                        min_length=50,
                        domain=target_domain,
                    )
                    if fallback:
                        return fallback
                
                return text
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                should_retry = (
                    status_code == 403
                    and retry_on_403
                    and attempt < attempts
                )
                if should_retry:
                    delay = self.FORBIDDEN_RETRY_BACKOFF_SECONDS * (attempt + 1)
                    self.logger.debug(
                        f"403 Forbidden on contact page {url}, retry {attempt + 1}/{attempts} after {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                self.logger.debug(f"Failed to fetch contact page {url}: {status_code}")
                break
            except (httpx.TimeoutException, httpx.RequestError) as e:
                self.logger.debug(f"Failed to fetch contact page {url}: {type(e).__name__}")
                break
            except Exception as e:
                self.logger.debug(f"Unexpected error fetching contact page {url}: {e}")
                break
        
        if self.enable_playwright_fallback:
            return await self._fetch_with_playwright(
                url,
                timeout=timeout,
                strip_navigation=False,
                include_mailto=True,
                min_length=50,
                domain=target_domain,
            )
        
        return None
    
    async def _scrape_contacts_domain(self, client: httpx.AsyncClient, website_url: str) -> ContactScrapedContent:
        """Scrape contact pages for a single domain."""
        start_time = time.time()
        
        base_url = self._normalize_url(website_url)
        domain = self._get_domain(base_url)
        
        if not self._is_valid_url(base_url):
            return ContactScrapedContent(
                contact_text="",
                source_urls=[],
                status="invalid_url",
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=0,
                error_message=f"Invalid URL: {website_url}"
            )
        
        if self.cache:
            cached = self.cache.get(domain)
            if cached:
                has_contacts = cached.contacts.get("emails") or cached.contacts.get("phones")
                if has_contacts:
                    duration_ms = int((time.time() - start_time) * 1000)
                    self.logger.debug(f"Contact cache hit: {domain}")
                    return ContactScrapedContent(
                        contact_text=cached.content.get("contact_text", ""),
                        source_urls=cached.content.get("contact_source_urls", []),
                        status="success",
                        timestamp=cached.scraped_at,
                        fetch_duration_ms=duration_ms,
                        from_cache=True
                    )
        
        try:
            global_sem = await self._ensure_semaphores()
            
            async with global_sem:
                contact_parts = []
                successful_urls = []
                
                self.logger.debug(f"Attempting to scrape {len(self.CONTACT_PATHS)} contact paths for {domain}")
                
                for path in self.CONTACT_PATHS:
                    target_url = urljoin(base_url, path)
                    
                    domain_sem = await self._get_domain_semaphore(domain)
                    async with domain_sem:
                        self.logger.debug(f"  Fetching contact page: {target_url}")
                        content = await self._fetch_page_with_contacts(
                            client,
                            target_url,
                            self.TIMEOUT_CONTACT,
                            domain=domain,
                        )
                        
                        if content:
                            contact_parts.append(content)
                            successful_urls.append(target_url)
                            self.logger.debug(f"  ✓ contact {path} ({len(content)} chars)")
                        else:
                            self.logger.debug(f"  ✗ contact {path} - no content")
                        
                        await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)
                
                if not contact_parts:
                    self.logger.debug(f"No contact pages found, trying homepage for {domain}")
                    domain_sem = await self._get_domain_semaphore(domain)
                    async with domain_sem:
                        homepage_content = await self._fetch_page_with_contacts(
                            client,
                            base_url,
                            self.TIMEOUT_CONTACT,
                            domain=domain,
                        )
                        if homepage_content:
                            contact_parts.append(homepage_content)
                            successful_urls.append(base_url)
                            self.logger.debug(f"  ✓ homepage contact ({len(homepage_content)} chars)")
                        else:
                            self.logger.warning(f"  ✗ homepage also failed for {domain}")
            
            full_contact_text = " ".join(contact_parts)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if not full_contact_text:
                status = "no_contact_page"
                self.logger.warning(f"No contact info for {domain}")
            else:
                status = "success"
                self.logger.info(f"Scraped contacts {domain}: {len(full_contact_text)} chars from {len(successful_urls)} pages ({duration_ms}ms)")
            
            return ContactScrapedContent(
                contact_text=full_contact_text,
                source_urls=successful_urls,
                status=status,
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.error(f"Error scraping contacts {domain}: {e}")
            return ContactScrapedContent(
                contact_text="",
                source_urls=[],
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                fetch_duration_ms=duration_ms,
                error_message=str(e)
            )
    
    async def scrape_contacts_batch(self, website_urls: List[str]) -> Dict[str, ContactScrapedContent]:
        """Scrape contact pages for multiple websites in parallel."""
        if not website_urls:
            return {}
        
        unique_urls = list(dict.fromkeys(url for url in website_urls if url))
        self.logger.info(f"Starting async contact scrape: {len(unique_urls)} domains")
        
        async with httpx.AsyncClient(
            verify=False,
            http2=True,
        ) as client:
            semaphore = asyncio.Semaphore(self.max_batch_concurrency)

            async def run_with_limit(target_url: str):
                async with semaphore:
                    return await self._scrape_contacts_domain(client, target_url)

            tasks = [run_with_limit(url) for url in unique_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        results_dict = {}
        for url, result in zip(unique_urls, results):
            domain = self._get_domain(self._normalize_url(url))
            if isinstance(result, Exception):
                self.logger.error(f"Exception for contact scrape {domain}: {result}")
                results_dict[url] = ContactScrapedContent(
                    contact_text="",
                    source_urls=[],
                    status="error",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    fetch_duration_ms=0,
                    error_message=str(result)
                )
            else:
                results_dict[url] = result
        
        success_count = sum(1 for r in results_dict.values() if r.status == "success")
        cache_hits = sum(1 for r in results_dict.values() if r.from_cache)
        self.logger.info(
            f"Contact batch complete: {success_count}/{len(unique_urls)} successful "
            f"({cache_hits} from cache)"
        )
        
        return results_dict
    
    def scrape_contacts_batch_sync(self, website_urls: List[str]) -> Dict[str, ContactScrapedContent]:
        """Synchronous wrapper for scrape_contacts_batch."""
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(self.scrape_contacts_batch(website_urls))
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(self.scrape_contacts_batch(website_urls))
    
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
