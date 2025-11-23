"""Web search vendor source using DuckDuckGo."""
from __future__ import annotations

import logging
import time
from typing import List, Optional
from urllib.parse import urlparse

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

from ..models import TenderProfile, VendorRecord
from .base import BaseVendorSource


class WebSearchVendorSource(BaseVendorSource):
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
        "sam.gov",
        "amazon.com",
        "ebay.com",
        "alibaba.com",
    ]
    
    NEGATIVE_OPERATORS = (
        "-job -career -hiring "
        "-site:linkedin.com "
        "-site:merx.com "
        "-site:buyandsell.gc.ca "
        "-site:sam.gov"
    )

    def __init__(
        self,
        max_results_per_query: int = 10,
        max_queries: int = 5,
        search_delay: float = 2.0,
        enable_logging: bool = True,
    ):
        if DDGS is None:
            raise ImportError("duckduckgo_search is required for WebSearchVendorSource")
        super().__init__(name="web_search")
        self.max_results_per_query = max_results_per_query
        self.max_queries = max_queries
        self.search_delay = search_delay
        self.logger = logging.getLogger(__name__) if enable_logging else None
        
    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        queries = self._build_queries(profile)
        
        if self.logger:
            self.logger.info(f"Generated {len(queries)} search queries")
            for i, q in enumerate(queries[:self.max_queries], 1):
                self.logger.info(f"  Query {i}: {q}")
        
        all_results = []
        for idx, query in enumerate(queries[:self.max_queries], 1):
            if self.logger:
                self.logger.info(f"Executing query {idx}/{min(len(queries), self.max_queries)}: {query}")
            
            try:
                results = self._execute_search(query)
                all_results.extend(results)
                
                if self.logger:
                    self.logger.info(f"  Found {len(results)} results")
                
                if idx < min(len(queries), self.max_queries):
                    time.sleep(self.search_delay)
                    
            except Exception as exc:
                if self.logger:
                    self.logger.error(f"  Search failed: {exc}")
                continue
        
        vendors = self._filter_and_convert(all_results)
        
        if self.logger:
            self.logger.info(f"Total vendors after filtering: {len(vendors)}")
        
        return vendors

    def _build_queries(self, profile: TenderProfile) -> List[str]:
        queries = []
        context = profile.dynamic_context
        loc = profile.doc_extracted.structured.location
        
        city_anchor = f"{loc.city} {loc.state_province}".strip() if loc.city else ""
        region_anchor = loc.state_province or loc.country or "Canada"
        
        business_types = "supplier manufacturer"
        
        if context.search_terms:
            for term in context.search_terms[:2]:
                if region_anchor.lower() not in term.lower():
                    queries.append(f"{term}")
                else:
                    queries.append(term)
        
        if context.technical_keywords and len(queries) < 3:
            for kw in context.technical_keywords[:1]:
                q = f"{kw} {business_types} {region_anchor}"
                queries.append(q)
        
        if city_anchor and len(queries) < 4:
            q = f"{context.sector} {business_types} {city_anchor}"
            queries.append(q)
        
        if not queries:
            queries.append(f"{context.sector} {business_types} {region_anchor}")
        
        return list(dict.fromkeys(queries))[:self.max_queries]

    def _execute_search(self, query: str) -> List[dict]:
        results = []
        
        try:
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    max_results=self.max_results_per_query,
                    region="wt-wt",
                )
                
                search_list = list(search_results)
                if self.logger:
                    self.logger.debug(f"Raw search returned {len(search_list)} results")
                
                for result in search_list:
                    results.append({
                        "title": result.get("title", ""),
                        "href": result.get("href", ""),
                        "body": result.get("body", ""),
                    })
                    
        except Exception as exc:
            if self.logger:
                self.logger.error(f"DuckDuckGo search error: {exc}")
            raise
        
        return results

    def _filter_and_convert(self, results: List[dict]) -> List[VendorRecord]:
        vendors = []
        seen_domains = set()
        
        for result in results:
            href = result.get("href", "")
            title = result.get("title", "")
            body = result.get("body", "")
            
            if not href or not title:
                if self.logger:
                    self.logger.debug(f"Skipped: missing href or title")
                continue
            
            try:
                parsed = urlparse(href)
                domain = parsed.netloc.lower()
                
                if domain.startswith("www."):
                    domain = domain[4:]
                
                if any(ignored in domain for ignored in self.IGNORE_DOMAINS):
                    if self.logger:
                        self.logger.debug(f"Filtered ignored domain: {domain}")
                    continue
                
                if domain in seen_domains:
                    if self.logger:
                        self.logger.debug(f"Filtered duplicate domain: {domain}")
                    continue
                
                seen_domains.add(domain)
                
                company_name = self._extract_company_name(title)
                
                vendor = VendorRecord(
                    company_name=company_name,
                    website=href,
                    source=self.name,
                )
                
                vendors.append(vendor)
                if self.logger:
                    self.logger.debug(f"Added vendor: {company_name} ({domain})")
                
            except Exception as exc:
                if self.logger:
                    self.logger.debug(f"Failed to process result {href}: {exc}")
                continue
        
        return vendors

    def _extract_company_name(self, title: str) -> str:
        common_suffixes = [
            " - Home", " | Home", " - Official Site", " | Official Site",
            " - Wikipedia", " | About Us", " - Company Profile",
        ]
        
        cleaned = title
        for suffix in common_suffixes:
            if suffix.lower() in cleaned.lower():
                cleaned = cleaned[:cleaned.lower().index(suffix.lower())]
        
        return cleaned.strip() or title
