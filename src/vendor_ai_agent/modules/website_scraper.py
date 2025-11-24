"""Website content scraper for vendor capability assessment."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class ScrapedContent:
    content: str
    source_url: str
    status: str
    timestamp: str
    error_message: Optional[str] = None


class WebsiteScraper:
    
    TARGET_PATHS = [
        "/about",
        "/about-us",
        "/services",
        "/products",
        "/portfolio",
        "/projects",
        "/capabilities",
        "/solutions",
        "/what-we-do",
    ]
    
    CONTACT_PATHS = [
        "/contact",
        "/contact-us",
        "/contactus",
        "/get-in-touch",
        "/contact-info",
        "/contact-information",
        "/reach-us",
        "/touch",
        "/customer-service",
        "/request-info",
        "/sales",
        "/support",
        "/about/contact",
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    ]
    
    def __init__(
        self,
        timeout_seconds: int = 10,
        max_content_chars: int = 3000,
        enable_logging: bool = True,
        request_delay: float = 0.3,
        max_requests_per_domain: float = 2.0,
    ):
        self.timeout = timeout_seconds
        self.max_chars = max_content_chars
        self.logger = logging.getLogger(__name__) if enable_logging else None
        self._request_count = 0
        self.request_delay = request_delay
        self.max_requests_per_domain = max_requests_per_domain
        
        self._domain_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._domain_last_request: Dict[str, float] = {}
        self._domain_lock = threading.Lock()
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    def _rate_limit_delay(self, url: str) -> None:
        """Apply per-domain rate limiting to prevent bans."""
        domain = self._get_domain(url)
        
        with self._domain_lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = threading.Lock()
        
        domain_lock = self._domain_locks[domain]
        
        with domain_lock:
            last_request = self._domain_last_request.get(domain, 0)
            min_interval = 1.0 / self.max_requests_per_domain
            
            elapsed = time.time() - last_request
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            time.sleep(self.request_delay)
            self._domain_last_request[domain] = time.time()
    
    def scrape(self, website_url: str) -> ScrapedContent:
        if not website_url:
            return self._error_result("", "No website URL provided", "no_url")
        
        base_url = self._normalize_url(website_url)
        
        if not self._is_valid_url(base_url):
            return self._error_result(website_url, f"Invalid URL: {website_url}", "invalid_url")
        
        if self.logger:
            self.logger.info(f"Scraping vendor website: {base_url}")
        
        content_parts = []
        successful_pages = []
        backoff_multiplier = 1.0
        
        for path in ["/"] + self.TARGET_PATHS:
            if len("".join(content_parts)) >= self.max_chars:
                break
            
            target_url = urljoin(base_url, path)
            
            try:
                page_content = self._fetch_page(target_url)
                
                if page_content and len(page_content) > 100:
                    content_parts.append(page_content)
                    successful_pages.append(path)
                    
                    if self.logger:
                        self.logger.debug(f"  ✓ Scraped {path} ({len(page_content)} chars)")
                
                backoff_multiplier = 1.0
                self._rate_limit_delay(target_url)
                
            except requests.Timeout:
                if self.logger:
                    self.logger.debug(f"  ⏱ Timeout on {path}")
                continue
            
            except requests.HTTPError as exc:
                if exc.response and exc.response.status_code in [429, 503]:
                    if self.logger:
                        self.logger.warning(f"  ⚠ Rate limited on {path}, backing off")
                    backoff_multiplier *= 2
                    time.sleep(self.request_delay * backoff_multiplier)
                elif self.logger:
                    self.logger.debug(f"  ✗ Failed {path}: {exc}")
                continue
            
            except requests.RequestException as exc:
                if self.logger:
                    self.logger.debug(f"  ✗ Failed {path}: {exc}")
                continue
        
        combined_content = " ".join(content_parts)[:self.max_chars]
        
        if not combined_content or len(combined_content) < 50:
            return self._error_result(
                base_url, 
                f"No content extracted from {len(successful_pages)} pages",
                "no_content"
            )
        
        if self.logger:
            self.logger.info(
                f"Scraped {len(successful_pages)} pages, "
                f"extracted {len(combined_content)} chars"
            )
        
        return ScrapedContent(
            content=combined_content,
            source_url=base_url,
            status="success",
            timestamp=self._get_timestamp(),
        )
    
    def _fetch_page(self, url: str) -> str:
        headers = {
            "User-Agent": self.USER_AGENTS[self._request_count % len(self.USER_AGENTS)],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        self._request_count += 1
        
        response = requests.get(
            url,
            headers=headers,
            timeout=self.timeout,
            allow_redirects=True,
        )
        
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        for element in soup(["script", "style", "nav", "footer", "header", "iframe"]):
            element.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        
        cleaned = " ".join(text.split())
        
        return cleaned
    
    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme in ["http", "https"] and parsed.netloc)
        except Exception:
            return False
    
    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)
        
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _error_result(self, url: str, message: str, status: str) -> ScrapedContent:
        if self.logger:
            self.logger.warning(f"Scraping failed: {message}")
        
        return ScrapedContent(
            content="",
            source_url=url,
            status=status,
            timestamp=self._get_timestamp(),
            error_message=message,
        )
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    def scrape_contacts(self, website_url: str, contact_extractor) -> "ExtractedContacts":
        """Scrape contact pages and extract contact information.
        
        Args:
            website_url: Base URL of vendor website
            contact_extractor: ContactExtractor instance for extraction
            
        Returns:
            ExtractedContacts with emails, phones, names
        """
        from .contact_extractor import ExtractedContacts
        
        if not website_url:
            return ExtractedContacts(
                emails=[], phones=[], contact_names=[],
                extraction_method="no_url", confidence=0.0,
                email_sources=[], phone_sources=[]
            )
        
        base_url = self._normalize_url(website_url)
        
        if not self._is_valid_url(base_url):
            return ExtractedContacts(
                emails=[], phones=[], contact_names=[],
                extraction_method="invalid_url", confidence=0.0,
                email_sources=[], phone_sources=[]
            )
        
        if self.logger:
            self.logger.info(f"Scraping contact pages: {base_url}")
        
        contact_text_parts = []
        successful_pages = []
        backoff_multiplier = 1.0
        
        for path in self.CONTACT_PATHS:
            target_url = urljoin(base_url, path)
            
            try:
                page_text = self._fetch_page_with_contacts(target_url)
                
                if page_text and len(page_text) > 50:
                    contact_text_parts.append(page_text)
                    successful_pages.append(path)
                    
                    if self.logger:
                        self.logger.debug(f"  ✓ Scraped contact {path} ({len(page_text)} chars)")
                
                backoff_multiplier = 1.0
                self._rate_limit_delay(target_url)
                
            except requests.Timeout:
                if self.logger:
                    self.logger.debug(f"  ⏱ Timeout on {path}")
                continue
            
            except requests.HTTPError as exc:
                if exc.response and exc.response.status_code in [429, 503]:
                    if self.logger:
                        self.logger.warning(f"  ⚠ Rate limited on {path}, backing off")
                    backoff_multiplier *= 2
                    time.sleep(self.request_delay * backoff_multiplier)
                elif self.logger:
                    self.logger.debug(f"  ✗ Failed {path}: {exc}")
                continue
            
            except requests.RequestException as exc:
                if self.logger:
                    self.logger.debug(f"  ✗ Failed {path}: {exc}")
                continue
        
        if not contact_text_parts:
            if self.logger:
                self.logger.warning(f"No contact pages found, trying homepage footer for {base_url}")
            
            try:
                homepage_text = self._fetch_page_with_contacts(base_url)
                if homepage_text and len(homepage_text) > 50:
                    contact_text_parts.append(homepage_text)
                    successful_pages.append("/")
                    if self.logger:
                        self.logger.debug(f"  ✓ Scraped homepage ({len(homepage_text)} chars)")
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"  ✗ Failed homepage: {e}")
            
            if not contact_text_parts:
                return ExtractedContacts(
                    emails=[], phones=[], contact_names=[],
                    extraction_method="no_contact_page", confidence=0.0,
                    email_sources=[], phone_sources=[]
                )
        
        combined_text = " ".join(contact_text_parts)
        
        if self.logger:
            self.logger.info(
                f"Scraped {len(successful_pages)} contact pages, "
                f"extracting contacts from {len(combined_text)} chars"
            )
        
        contacts = contact_extractor.extract(combined_text, use_llm_fallback=True)
        
        return contacts
    
    def _fetch_page_with_contacts(self, url: str) -> str:
        """Fetch page preserving contact information."""
        headers = {
            "User-Agent": self.USER_AGENTS[self._request_count % len(self.USER_AGENTS)],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        self._request_count += 1
        
        response = requests.get(
            url,
            headers=headers,
            timeout=self.timeout,
            allow_redirects=True,
        )
        
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        for element in soup(["script", "style", "iframe"]):
            element.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        
        cleaned = " ".join(text.split())
        
        return cleaned
