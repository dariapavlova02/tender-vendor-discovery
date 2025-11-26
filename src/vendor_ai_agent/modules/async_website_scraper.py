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
        "/get-in-touch",
        "/contact-info",
        "/about/contact",
    ]
    
    TIMEOUT_TIER1 = 8.0
    TIMEOUT_TIER2 = 10.0
    TIMEOUT_TIER3 = 12.0
    TIMEOUT_CONTACT = 10.0
    DELAY_BETWEEN_REQUESTS = 0.15
    
    EARLY_STOP_TIER1 = 1000
    EARLY_STOP_TIER2 = 1500
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        max_concurrent_global: int = 50,
        max_concurrent_per_domain: int = 2,
        enable_cache: bool = True,
        cache_dir: str = "outputs/cache/websites",
        cache_ttl_hours: int = 24,
    ):
        self.timeout = timeout_seconds
        self.max_chars = max_content_chars
        self.min_chars = min_content_chars
        self.max_concurrent_global = max_concurrent_global
        self.max_concurrent_per_domain = max_concurrent_per_domain
        self.logger = logging.getLogger(__name__)
        
        self.global_semaphore = asyncio.Semaphore(max_concurrent_global)
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_concurrent_per_domain)
        )
        self._domain_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        self.cache: Optional[WebsiteCache] = None
        if enable_cache:
            self.cache = WebsiteCache(cache_dir=cache_dir, ttl_hours=cache_ttl_hours)
    
    def _get_random_headers(self) -> Dict[str, str]:
        """Get randomized browser headers."""
        import random
        headers = self.BROWSER_HEADERS.copy()
        headers["User-Agent"] = random.choice(self.USER_AGENTS)
        return headers
    
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
    
    async def _fetch_page(self, client: httpx.AsyncClient, url: str, timeout: float, retry_on_403: bool = True) -> Optional[str]:
        """Fetch and extract text content from a single page."""
        try:
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            
            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())
            
            return text if len(text) > 100 else None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and retry_on_403:
                self.logger.debug(f"403 Forbidden on {url}, retrying with different User-Agent")
                try:
                    new_headers = self._get_random_headers()
                    response = await client.get(
                        url,
                        timeout=timeout,
                        follow_redirects=True,
                        headers=new_headers
                    )
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()
                    
                    text = soup.get_text(separator=" ", strip=True)
                    text = " ".join(text.split())
                    
                    return text if len(text) > 100 else None
                except Exception:
                    self.logger.debug(f"Retry failed for {url}")
                    return None
            else:
                self.logger.debug(f"Failed to fetch {url}: {e.response.status_code}")
                return None
        except (httpx.TimeoutException, httpx.RequestError) as e:
            self.logger.debug(f"Failed to fetch {url}: {type(e).__name__}")
            return None
        except Exception as e:
            self.logger.debug(f"Unexpected error fetching {url}: {e}")
            return None
    
    async def _fetch_paths_parallel(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        domain: str
    ) -> tuple[List[str], List[str]]:
        """Fetch multiple paths with 3-tier strategy and progressive timeouts."""
        content_parts = []
        successful_urls = []
        
        for path in self.PRIORITY_PATHS["tier1"]:
            target_url = urljoin(base_url, path)
            
            async with self._domain_semaphores[domain]:
                content = await self._fetch_page(client, target_url, self.TIMEOUT_TIER1)
                
                if content:
                    content_parts.append(content[:self.max_chars])
                    successful_urls.append(target_url)
                    self.logger.debug(f"  ✓ tier1 {path} ({len(content)} chars)")
                    
                    if len("".join(content_parts)) >= self.max_chars:
                        break
                
                await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        if len("".join(content_parts)) < self.EARLY_STOP_TIER1:
            self.logger.debug(f"Tier1 insufficient ({len(''.join(content_parts))} < {self.EARLY_STOP_TIER1}), proceeding to tier2")
            for path in self.PRIORITY_PATHS["tier2"]:
                target_url = urljoin(base_url, path)
                
                async with self._domain_semaphores[domain]:
                    content = await self._fetch_page(client, target_url, self.TIMEOUT_TIER2)
                    
                    if content:
                        content_parts.append(content[:self.max_chars])
                        successful_urls.append(target_url)
                        self.logger.debug(f"  ✓ tier2 {path} ({len(content)} chars)")
                        
                        if len("".join(content_parts)) >= self.max_chars:
                            break
                    
                    await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        if len("".join(content_parts)) < self.EARLY_STOP_TIER2:
            self.logger.debug(f"Tier2 insufficient ({len(''.join(content_parts))} < {self.EARLY_STOP_TIER2}), proceeding to tier3")
            for path in self.PRIORITY_PATHS["tier3"]:
                target_url = urljoin(base_url, path)
                
                async with self._domain_semaphores[domain]:
                    content = await self._fetch_page(client, target_url, self.TIMEOUT_TIER3)
                    
                    if content:
                        content_parts.append(content[:self.max_chars])
                        successful_urls.append(target_url)
                        self.logger.debug(f"  ✓ tier3 {path} ({len(content)} chars)")
                        
                        if len("".join(content_parts)) >= self.max_chars:
                            break
                    
                    await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        return content_parts, successful_urls
    
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
            async with self.global_semaphore:
                content_parts, successful_urls = await self._fetch_paths_parallel(
                    client, base_url, domain
                )
            
            full_content = " ".join(content_parts)[:self.max_chars]
            duration_ms = int((time.time() - start_time) * 1000)
            
            if not full_content or len(full_content) < 100:
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
            headers=self._get_random_headers(),
            verify=False,
            http2=True,
        ) as client:
            tasks = [self._scrape_domain(client, url) for url in unique_urls]
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
    
    async def _fetch_page_with_contacts(self, client: httpx.AsyncClient, url: str, timeout: float, retry_on_403: bool = True) -> Optional[str]:
        """Fetch page preserving contact information (no removal of nav/footer/header)."""
        try:
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            mailto_emails = []
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
            
            for tag in soup(["script", "style", "iframe"]):
                tag.decompose()
            
            text = soup.get_text(separator=" ", strip=True)
            if mailto_emails:
                text = f"{text} {' '.join(mailto_emails)}"
            
            text = " ".join(text.split())
            
            return text if len(text) > 50 else None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and retry_on_403:
                self.logger.debug(f"403 Forbidden on contact page {url}, retrying with different User-Agent")
                try:
                    new_headers = self._get_random_headers()
                    response = await client.get(
                        url,
                        timeout=timeout,
                        follow_redirects=True,
                        headers=new_headers
                    )
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    mailto_emails = []
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
                    
                    for tag in soup(["script", "style", "iframe"]):
                        tag.decompose()
                    
                    text = soup.get_text(separator=" ", strip=True)
                    if mailto_emails:
                        text = f"{text} {' '.join(mailto_emails)}"
                    
                    text = " ".join(text.split())
                    
                    return text if len(text) > 50 else None
                except Exception:
                    self.logger.debug(f"Retry failed for contact page {url}")
                    return None
            else:
                self.logger.debug(f"Failed to fetch contact page {url}: {e.response.status_code}")
                return None
        except (httpx.TimeoutException, httpx.RequestError) as e:
            self.logger.debug(f"Failed to fetch contact page {url}: {type(e).__name__}")
            return None
        except Exception as e:
            self.logger.debug(f"Unexpected error fetching contact page {url}: {e}")
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
            async with self.global_semaphore:
                contact_parts = []
                successful_urls = []
                
                for path in self.CONTACT_PATHS:
                    target_url = urljoin(base_url, path)
                    
                    async with self._domain_semaphores[domain]:
                        content = await self._fetch_page_with_contacts(client, target_url, self.TIMEOUT_CONTACT)
                        
                        if content:
                            contact_parts.append(content)
                            successful_urls.append(target_url)
                            self.logger.debug(f"  ✓ contact {path} ({len(content)} chars)")
                        
                        await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)
                
                if not contact_parts:
                    self.logger.debug(f"No contact pages, trying homepage for {domain}")
                    async with self._domain_semaphores[domain]:
                        homepage_content = await self._fetch_page_with_contacts(client, base_url, self.TIMEOUT_CONTACT)
                        if homepage_content:
                            contact_parts.append(homepage_content)
                            successful_urls.append(base_url)
                            self.logger.debug(f"  ✓ homepage contact ({len(homepage_content)} chars)")
            
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
            headers=self._get_random_headers(),
            verify=False,
            http2=True,
        ) as client:
            tasks = [self._scrape_contacts_domain(client, url) for url in unique_urls]
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
        return asyncio.run(self.scrape_contacts_batch(website_urls))
