from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from Levenshtein import ratio
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import APICache
from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class DuckDuckGoWebsiteEnricher(BaseEnrichmentProvider):
    
    LEGAL_SUFFIXES = [
        r'\bINC\.?$', r'\bINCORPORATED$', r'\bCORP\.?$', r'\bCORPORATION$',
        r'\bLTD\.?$', r'\bLIMITED$', r'\bLLC\.?$', r'\bLTÉE\.?$', r'\bLIMITÉE$',
        r'\bCO\.?$', r'\bCOMPANY$', r'\bGMBH$', r'\bSA$', r'\bSARL$',
        r'\bPLC$', r'\bPTY$', r'\bLTDA$', r'\bGROUP$', r'\bENTERPRISES?$'
    ]
    
    IGNORE_DOMAINS = [
        "wikipedia.org",
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "youtube.com",
        "pinterest.com",
        "instagram.com",
        "reddit.com",
        "indeed.com",
        "glassdoor.com",
        "monster.com",
        "merx.com",
        "buyandsell.gc.ca",
        "canadabuys.canada.ca",
        "sam.gov",
        "amazon.com",
        "ebay.com",
        "alibaba.com",
        "google.com",
        "bing.com",
        "yahoo.com",
    ]
    
    def __init__(
        self,
        db_session: Session,
        request_delay: float = 3.0,
        cache_ttl_days: int = 7,
        min_confidence: float = 0.5,
    ) -> None:
        super().__init__(name="duckduckgo_website_discovery")
        self.db_session = db_session
        self.request_delay = request_delay
        self.cache_ttl_days = cache_ttl_days
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(__name__)
        
        self.suffix_pattern = re.compile('|'.join(self.LEGAL_SUFFIXES), re.IGNORECASE)
        self._last_request_time = 0
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if vendor.website:
            self.logger.debug(f"Vendor {vendor.company_name} already has website, skipping")
            return vendor
        
        if not vendor.city or not vendor.country:
            self.logger.debug(f"Vendor {vendor.company_name} has no location data, cannot search")
            return vendor
        
        self.logger.info(f"Searching website for {vendor.company_name} ({vendor.city}, {vendor.country})")
        
        cached_result = self._get_cached_result(vendor)
        if cached_result:
            self.logger.info(f"  ✓ Using cached result: {cached_result.get('website')}")
            self._apply_result(vendor, cached_result)
            return vendor
        
        result = self._search_duckduckgo(vendor)
        
        if result and result.get("confidence", 0) >= self.min_confidence:
            self.logger.info(
                f"  ✓ Found website: {result['website']} "
                f"(confidence: {result['confidence']:.2f})"
            )
            self._apply_result(vendor, result)
            self._cache_result(vendor, result)
            vendor.enrichment_flags.append(self.name)
        else:
            self.logger.debug(f"  ✗ No reliable website found")
            self._cache_result(vendor, {"website": None, "confidence": 0.0})
        
        return vendor
    
    def _search_duckduckgo(self, vendor: VendorRecord) -> Optional[dict]:
        query = self._build_query(vendor)
        
        self._rate_limit()
        
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
                self.logger.warning(f"  ⚠ HTTP 202 - Rate limited, pausing 5 minutes")
                time.sleep(300)
                return None
            
            if response.status_code == 403:
                self.logger.warning(f"  ⚠ 403 Forbidden - query may be too complex: {query}")
                return None
            
            response.raise_for_status()
            
            results = self._parse_results(response.text)
            
            if not results:
                return None
            
            best_match = self._score_and_rank_results(vendor, results)
            
            return best_match
            
        except Exception as exc:
            self.logger.error(f"  ✗ DuckDuckGo search failed: {exc}")
            return None
    
    def _build_query(self, vendor: VendorRecord) -> str:
        company_name = vendor.company_name
        city = vendor.city
        country = vendor.country
        
        return f"{company_name} {city} {country}"
    
    def _parse_results(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        
        results = []
        result_divs = soup.find_all("div", class_="result")
        
        for idx, result_div in enumerate(result_divs[:10], 1):
            title_elem = result_div.find("a", class_="result__a")
            snippet_elem = result_div.find("a", class_="result__snippet")
            
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            
            redirect_url = title_elem.get("href", "")
            real_url = self._extract_real_url(redirect_url)
            
            if not real_url:
                continue
            
            domain = self._extract_domain(real_url)
            
            if self._is_ignored_domain(domain):
                continue
            
            results.append({
                "url": real_url,
                "domain": domain,
                "title": title,
                "snippet": snippet,
                "position": idx,
            })
        
        return results
    
    def _extract_real_url(self, redirect_url: str) -> Optional[str]:
        if not redirect_url:
            return None
        
        try:
            if redirect_url.startswith("//duckduckgo.com/l/"):
                parsed = urlparse("https:" + redirect_url)
                query_params = parse_qs(parsed.query)
                
                if "uddg" in query_params:
                    return query_params["uddg"][0]
            
            if redirect_url.startswith("http"):
                return redirect_url
            
            return None
            
        except Exception:
            return None
    
    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            if domain.startswith("www."):
                domain = domain[4:]
            
            return domain
        except Exception:
            return ""
    
    def _is_ignored_domain(self, domain: str) -> bool:
        return any(ignored in domain for ignored in self.IGNORE_DOMAINS)
    
    def _score_and_rank_results(
        self, 
        vendor: VendorRecord, 
        results: list[dict]
    ) -> Optional[dict]:
        if not results:
            return None
        
        company_normalized = self._normalize_name(vendor.company_name)
        company_tokens = self._get_tokens(vendor.company_name)
        
        scored_results = []
        
        for result in results:
            domain = result["domain"]
            domain_tokens = self._get_tokens(domain.replace(".", " "))
            
            token_match_score = self._calculate_token_match(company_tokens, domain_tokens)
            
            tld_bonus = 0.2 if domain.endswith(".ca") else 0.0
            
            position_bonus = 0.1 if result["position"] == 1 else 0.05 if result["position"] <= 3 else 0.0
            
            snippet_bonus = 0.0
            snippet_lower = result["snippet"].lower()
            title_lower = result["title"].lower()
            company_lower = vendor.company_name.lower()
            
            if company_lower in snippet_lower or company_lower in title_lower:
                snippet_bonus = 0.1
            
            total_score = (
                token_match_score * 0.6 +
                tld_bonus +
                position_bonus +
                snippet_bonus
            )
            
            scored_results.append({
                "website": result["url"],
                "domain": domain,
                "confidence": min(total_score, 1.0),
                "token_match": token_match_score,
                "position": result["position"],
                "title": result["title"],
            })
        
        scored_results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return scored_results[0] if scored_results else None
    
    def _calculate_token_match(self, company_tokens: set[str], domain_tokens: set[str]) -> float:
        if not company_tokens or not domain_tokens:
            return 0.0
        
        common_tokens = company_tokens & domain_tokens
        
        if not common_tokens:
            return 0.0
        
        match_score = len(common_tokens) / max(len(company_tokens), len(domain_tokens))
        
        return match_score
    
    def _normalize_name(self, name: str) -> str:
        if not name:
            return ""
        
        name = name.upper().strip()
        
        if '/' in name:
            parts = name.split('/')
            name = parts[0].strip()
        
        name = self.suffix_pattern.sub('', name).strip()
        
        name = re.sub(r'[^\w\s]', '', name)
        
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _get_tokens(self, name: str) -> set[str]:
        normalized = self._normalize_name(name)
        tokens = set(normalized.split())
        tokens.discard('')
        return tokens
    
    def _apply_result(self, vendor: VendorRecord, result: dict) -> None:
        vendor.website = result.get("website")
        vendor.filtering_metadata["website_source"] = self.name
        vendor.filtering_metadata["website_confidence"] = result.get("confidence", 0.0)
        vendor.filtering_metadata["website_search_position"] = result.get("position", 0)
    
    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        
        jitter = random.uniform(0, 1.0)
        delay = self.request_delay + jitter
        
        if elapsed < delay:
            sleep_time = delay - elapsed
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _get_cached_result(self, vendor: VendorRecord) -> Optional[dict]:
        cache_key = self._build_cache_key(vendor)
        
        stmt = select(APICache).where(
            APICache.source == self.name,
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.utcnow()
        )
        
        result = self.db_session.execute(stmt).scalar_one_or_none()
        
        if result:
            result.hit_count += 1
            result.last_accessed_at = datetime.utcnow()
            self.db_session.commit()
            
            return result.response_data
        
        return None
    
    def _cache_result(self, vendor: VendorRecord, result: dict) -> None:
        cache_key = self._build_cache_key(vendor)
        
        stmt = select(APICache).where(
            APICache.source == self.name,
            APICache.cache_key == cache_key
        )
        
        existing = self.db_session.execute(stmt).scalar_one_or_none()
        
        expires_at = datetime.utcnow() + timedelta(days=self.cache_ttl_days)
        
        if existing:
            existing.response_data = result
            existing.expires_at = expires_at
            existing.last_accessed_at = datetime.utcnow()
        else:
            cache_entry = APICache(
                source=self.name,
                cache_key=cache_key,
                response_data=result,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                hit_count=0,
                last_accessed_at=datetime.utcnow()
            )
            self.db_session.add(cache_entry)
        
        self.db_session.commit()
    
    def _build_cache_key(self, vendor: VendorRecord) -> str:
        key_parts = [
            vendor.company_name.lower().strip(),
            vendor.city.lower().strip() if vendor.city else "",
            vendor.country.lower().strip() if vendor.country else "",
        ]
        
        key_string = "|".join(key_parts)
        
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]
