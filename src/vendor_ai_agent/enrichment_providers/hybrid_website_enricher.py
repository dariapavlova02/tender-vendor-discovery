from __future__ import annotations

import logging
import random
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from Levenshtein import ratio

from ..models import VendorRecord
from .base import BaseEnrichmentProvider
from .serper_client import SerperClient


class HybridWebsiteEnricher(BaseEnrichmentProvider):
    
    LEGAL_SUFFIXES = [
        r'\bINC\.?$', r'\bINCORPORATED$', r'\bCORP\.?$', r'\bCORPORATION$',
        r'\bLTD\.?$', r'\bLIMITED$', r'\bLLC\.?$', r'\bLTÉE\.?$', r'\bLIMITÉE$',
        r'\bCO\.?$', r'\bCOMPANY$', r'\bGMBH$', r'\bSA$', r'\bSARL$',
        r'\bPLC$', r'\bPTY$', r'\bLTDA$', r'\bGROUP$', r'\bENTERPRISES?$'
    ]
    
    IGNORE_DOMAINS = [
        "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
        "youtube.com", "pinterest.com", "instagram.com", "reddit.com",
        "indeed.com", "glassdoor.com", "monster.com", "merx.com",
        "buyandsell.gc.ca", "canadabuys.canada.ca", "sam.gov",
        "amazon.com", "ebay.com", "alibaba.com",
        "google.com", "bing.com", "yahoo.com",
    ]
    
    def __init__(
        self,
        serper_api_key: str,
        enable_ddg: bool = True,
        enable_serper_fallback: bool = True,
        ddg_request_delay: float = 3.5,
        min_confidence: float = 0.5,
    ) -> None:
        super().__init__(name="hybrid_website_discovery")
        self.serper_client = SerperClient(api_key=serper_api_key, timeout=10)
        self.enable_ddg = enable_ddg
        self.enable_serper_fallback = enable_serper_fallback
        self.ddg_request_delay = ddg_request_delay
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(__name__)
        
        self.suffix_pattern = re.compile('|'.join(self.LEGAL_SUFFIXES), re.IGNORECASE)
        self._last_ddg_request_time = 0
        self._ddg_banned_until = None
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if vendor.website:
            self.logger.debug(f"Vendor {vendor.company_name} already has website, skipping")
            return vendor
        
        self.logger.info(f"Searching website for {vendor.company_name}")
        
        result = None
        
        if self.enable_ddg and self._is_ddg_available():
            result = self._try_duckduckgo(vendor)
        
        if not result and self.enable_serper_fallback:
            self.logger.info(f"  → Falling back to Serper API")
            result = self._try_serper(vendor)
        
        if result and result.get("website"):
            confidence = result.get("confidence", 0)
            self.logger.info(
                f"  ✓ Found website: {result['website']} "
                f"(confidence: {confidence:.2f}, source: {result.get('source', 'unknown')})"
            )
            self._apply_result(vendor, result)
            vendor.enrichment_flags.append(self.name)
        else:
            self.logger.debug(f"  ✗ No website found via any method")
        
        return vendor
    
    def _is_ddg_available(self) -> bool:
        if self._ddg_banned_until and time.time() < self._ddg_banned_until:
            remaining = int(self._ddg_banned_until - time.time())
            self.logger.debug(f"DDG still banned for {remaining}s, skipping")
            return False
        return True
    
    def _try_duckduckgo(self, vendor: VendorRecord) -> Optional[dict]:
        query = self._build_query(vendor)
        
        self._rate_limit_ddg()
        
        try:
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://duckduckgo.com/",
                "Connection": "close",
            }
            
            response = requests.get(
                url,
                params={"q": query},
                headers=headers,
                allow_redirects=False,
                timeout=15
            )
            
            if response.status_code == 202:
                self.logger.warning(f"  ⚠ DDG HTTP 202 - Rate limited, marking as banned for 5 min")
                self._ddg_banned_until = time.time() + 300
                return None
            
            if response.status_code == 403:
                self.logger.warning(f"  ⚠ DDG 403 Forbidden")
                return None
            
            response.raise_for_status()
            
            results = self._parse_ddg_results(response.text)
            
            if not results:
                return None
            
            best_match = self._score_and_rank_results(vendor, results)
            if best_match:
                best_match['source'] = 'duckduckgo'
            
            return best_match
            
        except Exception as exc:
            self.logger.debug(f"  ✗ DDG search failed: {exc}")
            return None
    
    def _try_serper(self, vendor: VendorRecord) -> Optional[dict]:
        try:
            serper_result = self.serper_client.search_company(
                company_name=vendor.company_name,
                include_contacts=True
            )
            
            if not serper_result.website:
                return None
            
            result = {
                'website': serper_result.website,
                'confidence': 0.9,
                'source': 'serper'
            }
            
            if serper_result.contacts and serper_result.contacts.emails:
                result['emails'] = serper_result.contacts.emails
                result['email_source'] = 'serper_snippet'
                self.logger.info(f"  ✓ Also found {len(serper_result.contacts.emails)} emails from Serper snippets")
            
            if serper_result.contacts and serper_result.contacts.phones:
                result['phones'] = serper_result.contacts.phones
                result['phone_source'] = 'serper_snippet'
                self.logger.info(f"  ✓ Also found {len(serper_result.contacts.phones)} phones from Serper snippets")
            
            return result
            
        except Exception as exc:
            self.logger.error(f"  ✗ Serper search failed: {exc}")
            return None
    
    def _build_query(self, vendor: VendorRecord) -> str:
        name = vendor.company_name
        
        name = self.suffix_pattern.sub('', name).strip()
        
        parts = [name]
        
        if vendor.city and vendor.city not in name:
            parts.append(vendor.city)
        
        if vendor.state and vendor.state not in name:
            parts.append(vendor.state)
        
        if vendor.country and vendor.country not in name:
            parts.append(vendor.country)
        
        query = ' '.join(parts)
        return query
    
    def _rate_limit_ddg(self) -> None:
        elapsed = time.time() - self._last_ddg_request_time
        if elapsed < self.ddg_request_delay:
            jitter = random.uniform(0, 1.0)
            sleep_time = self.ddg_request_delay - elapsed + jitter
            time.sleep(sleep_time)
        self._last_ddg_request_time = time.time()
    
    def _parse_ddg_results(self, html: str) -> list[dict]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            results = []
            
            for result_div in soup.select(".result"):
                link_tag = result_div.select_one(".result__a")
                snippet_tag = result_div.select_one(".result__snippet")
                
                if not link_tag:
                    continue
                
                href = link_tag.get("href", "")
                if not href.startswith("http"):
                    continue
                
                domain = self._extract_domain(href)
                if not domain or any(ignored in domain for ignored in self.IGNORE_DOMAINS):
                    continue
                
                title = link_tag.get_text(strip=True)
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                results.append({
                    "url": href,
                    "domain": domain,
                    "title": title,
                    "snippet": snippet
                })
            
            return results
            
        except Exception as exc:
            self.logger.error(f"Failed to parse DDG results: {exc}")
            return []
    
    def _score_and_rank_results(self, vendor: VendorRecord, results: list[dict]) -> Optional[dict]:
        if not results:
            return None
        
        company_clean = self._normalize_name(vendor.company_name)
        
        scored_results = []
        for result in results:
            domain_clean = self._normalize_name(result['domain'])
            title_clean = self._normalize_name(result['title'])
            
            domain_similarity = ratio(company_clean, domain_clean)
            title_similarity = ratio(company_clean, title_clean)
            
            score = max(domain_similarity, title_similarity * 0.7)
            
            if vendor.city and vendor.city.lower() in result['snippet'].lower():
                score += 0.1
            
            if vendor.state and vendor.state.lower() in result['snippet'].lower():
                score += 0.1
            
            scored_results.append({
                'website': result['url'],
                'confidence': score,
                'domain': result['domain'],
                'title': result['title']
            })
        
        scored_results.sort(key=lambda x: x['confidence'], reverse=True)
        
        best = scored_results[0]
        if best['confidence'] >= self.min_confidence:
            return best
        
        return None
    
    def _normalize_name(self, name: str) -> str:
        name = self.suffix_pattern.sub('', name)
        name = re.sub(r'[^a-z0-9]', '', name.lower())
        return name
    
    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain
        except Exception:
            return None
    
    def _apply_result(self, vendor: VendorRecord, result: dict) -> None:
        vendor.website = result['website']
        vendor.filtering_metadata['website_confidence'] = result.get('confidence', 0.0)
        vendor.filtering_metadata['website_source'] = result.get('source', 'unknown')
        
        if 'emails' in result and result['emails']:
            vendor.filtering_metadata['serper_backup_emails'] = result['emails']
            vendor.filtering_metadata['serper_backup_email_confidence'] = 0.7
            self.logger.info(f"  📦 Saved {len(result['emails'])} backup emails from snippets")
        
        if 'phones' in result and result['phones']:
            vendor.filtering_metadata['serper_backup_phones'] = result['phones']
            vendor.filtering_metadata['serper_backup_phone_confidence'] = 0.7
            self.logger.info(f"  📦 Saved {len(result['phones'])} backup phones from snippets")
