from __future__ import annotations

import logging
import os
from typing import List, Optional, Set, TYPE_CHECKING
from urllib.parse import urlparse

from ..models import TenderProfile, VendorRecord
from .base import BaseVendorSource

if TYPE_CHECKING:
    from ..config import RuntimeConfig
    from ..enrichment_providers.serper_client import SerperClient


IGNORE_DOMAINS = {
    'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'youtube.com', 'indeed.com', 'glassdoor.com', 'monster.com',
    'wikipedia.org', 'merx.com', 'buyandsell.gc.ca', 'sam.gov',
    'amazon.com', 'ebay.com', 'alibaba.com', 'thomasnet.com',
    'reddit.com', 'quora.com', 'pinterest.com',
}

NON_VENDOR_DOMAINS = {
    'thefirearmblog.com', 'ploughshares.ca', 'iq.govwin.com',
    'ammobin.ca', 'canadianarmytoday.com', 'govwin.com',
    'tactical-life.com', 'defensenews.com', 'shootingillustrated.com',
    'canadabuys.canada.ca', 'supportontariomade.ca', 'ammoterra.com',
    'canada.ca', 'govconexec.com', 'ruralroutes.com', '211ontario.ca',
    'tripadvisor.com', 'archive.org', 'pdfcoffee.com', 'govinfo.gov',
    'webgen1files1.revize.com', 'yellowpages.ca', 'canpages.ca',
    'norwalkpatriot.squarespace.com',
    'travel.gc.ca', 'gc.ca',
}

NON_VENDOR_KEYWORDS = {
    'blog', 'news', 'article', 'analysis', 'contract award',
    'tender', 'bid', 'report', 'insight'
}

COMPANY_HINT_KEYWORDS = {
    'inc', 'ltd', 'llc', 'corporation', 'company', 'co.', 'group',
    'systems', 'solutions', 'industries', 'manufacturing', 'manufacturer',
    'consulting', 'services', 'agency', 'enterprise'
}

ARTICLE_PATH_TOKENS = {'/blog', '/news', '/article', '/insight', '/stories'}


class SerperVendorSource(BaseVendorSource):
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        query_limit: int = 10,
        results_per_query: int = 10,
        config: Optional["RuntimeConfig"] = None
    ):
        super().__init__(name="serper_search")
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        self.query_limit = query_limit
        self.results_per_query = results_per_query
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key:
            self.logger.warning("SERPER_API_KEY not found. SerperVendorSource will be disabled.")
        
        self.client: Optional["SerperClient"] = None
    
    def is_compatible(self, profile: TenderProfile) -> bool:
        if not self.api_key:
            return False
        
        if not self.config or not self.config.discovery.enable_serper_discovery:
            return False
        
        country = profile.dynamic_context.country if profile.dynamic_context else None
        
        if country == "Canada":
            return self.config.discovery.serper_discovery_always_canada
        return True

    def _process_search_result(self, result: dict, query: str, position: int, seen_domains: Set[str]) -> Optional[VendorRecord]:
        link = result.get("link", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        if not link or not title:
            return None
        
        domain = self._extract_domain(link)
        
        if self._should_filter_domain(domain):
            self.logger.debug(f"  Filtered: {domain} (ignored domain)")
            return None
        
        if not self._is_company_result(title, snippet, domain, link):
            self.logger.debug(f"  Filtered: {domain or link} (non-company result)")
            return None

        if domain in seen_domains:
            self.logger.debug(f"  Filtered: {domain} (duplicate)")
            return None
        
        seen_domains.add(domain)
        
        company_name = self._extract_company_name(title)
        
        vendor = VendorRecord(
            company_name=company_name,
            website=link,
            source=self.name,
            enrichment_flags=["serper_discovery"]
        )
        
        vendor.filtering_metadata["serper_snippet"] = snippet
        vendor.filtering_metadata["serper_position"] = position
        vendor.filtering_metadata["serper_query"] = query
        vendor.filtering_metadata["serper_domain"] = domain
        
        return vendor
    
    def _process_places_result(self, result: dict, query: str, position: int, seen_domains: Set[str]) -> Optional[VendorRecord]:
        title = result.get("title", "")
        address = result.get("address", "")
        phone = result.get("phoneNumber", "")
        website = result.get("website", "")
        rating = result.get("rating")
        latitude = result.get("latitude")
        longitude = result.get("longitude")
        cid = result.get("cid", "")
        
        if not title:
            return None
        
        if not website:
            domain = ""
        else:
            domain = self._extract_domain(website)
            
            if self._should_filter_domain(domain):
                self.logger.debug(f"  Filtered: {domain} (ignored domain)")
                return None
        
        dedup_key = cid if cid else domain if domain else title.lower().replace(" ", "")
        
        if dedup_key in seen_domains:
            self.logger.debug(f"  Filtered: {title} (duplicate)")
            return None
        
        seen_domains.add(dedup_key)
        
        vendor = VendorRecord(
            company_name=title,
            website=website if website else None,
            phone=phone if phone else None,
            source=self.name,
            enrichment_flags=["serper_places"]
        )
        
        vendor.filtering_metadata["serper_address"] = address
        vendor.filtering_metadata["serper_rating"] = rating
        vendor.filtering_metadata["serper_latitude"] = latitude
        vendor.filtering_metadata["serper_longitude"] = longitude
        vendor.filtering_metadata["serper_position"] = position
        vendor.filtering_metadata["serper_query"] = query
        vendor.filtering_metadata["serper_cid"] = cid
        if domain:
            vendor.filtering_metadata["serper_domain"] = domain
        
        return vendor

    
    def search(self, profile: TenderProfile, target_count: Optional[int] = None) -> List[VendorRecord]:
        if not self.client and self.api_key:
            try:
                import sys
                from pathlib import Path
                import importlib.util
                
                serper_path = Path(__file__).parent.parent / "enrichment_providers" / "serper_client.py"
                spec = importlib.util.spec_from_file_location("serper_client", serper_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules["serper_client"] = module
                    spec.loader.exec_module(module)
                    SerperClient = module.SerperClient
                    self.client = SerperClient(api_key=self.api_key)
                    self.logger.info("SerperClient initialized lazily")
                else:
                    raise ImportError("Could not load serper_client.py")
            except Exception as e:
                self.logger.warning(f"Failed to initialize SerperClient: {e}")
                return []
        
        if not self.client:
            self.logger.warning("Serper client not initialized - skipping discovery")
            return []
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("SERPER DISCOVERY SOURCE")
        self.logger.info(f"{'='*60}")
        
        queries = self._generate_queries(profile, target_count)
        
        effective_query_limit = min(len(queries), self.query_limit) if not target_count else len(queries)
        
        all_vendors = []
        seen_domains: Set[str] = set()
        
        use_places_api = self.config and getattr(self.config.discovery, 'serper_use_places_api', True)
        
        location_str = None
        gl_code = None
        
        if profile.api_metadata and profile.api_metadata.place_of_performance:
            pop = profile.api_metadata.place_of_performance
            
            location_parts = []
            if pop.city:
                location_parts.append(pop.city)
            if pop.state_province:
                location_parts.append(pop.state_province)
            if pop.country:
                location_parts.append(pop.country)
            
            if location_parts:
                location_str = ", ".join(location_parts)
        
        if not location_str:
            if profile.dynamic_context and profile.dynamic_context.country:
                location_str = profile.dynamic_context.country
            elif profile.country:
                location_str = profile.country
        
        country_name = None
        if profile.dynamic_context and profile.dynamic_context.country:
            country_name = profile.dynamic_context.country
        elif profile.country:
            country_name = profile.country
        elif profile.api_metadata and profile.api_metadata.place_of_performance:
            country_name = profile.api_metadata.place_of_performance.country
        
        if country_name:
            gl_code = "ca" if "Canada" in country_name else "us"
        
        if location_str:
            self.logger.info(f"Geographic targeting: location='{location_str}', gl='{gl_code}'")
        
        for idx, query in enumerate(queries[:effective_query_limit], 1):
            self.logger.info(f"[Query {idx}/{effective_query_limit}] {query}")
            
            try:
                if use_places_api:
                    response = self.client.places_search(
                        query, 
                        num_results=self.results_per_query,
                        location=location_str,
                        gl=gl_code
                    )
                    results = response.get("places", [])
                else:
                    response = self.client.discovery_search(query, num_results=self.results_per_query)
                    results = response.get("organic", [])
                
                self.logger.info(f"  Received {len(results)} results")
                
                for position, result in enumerate(results, 1):
                    if use_places_api:
                        vendor = self._process_places_result(result, query, position, seen_domains)
                    else:
                        vendor = self._process_search_result(result, query, position, seen_domains)
                    
                    if vendor:
                        all_vendors.append(vendor)
                        self.logger.debug(f"  ✓ Added: {vendor.company_name} ({vendor.filtering_metadata.get('serper_domain', 'N/A')})")
                
            except Exception as e:
                self.logger.error(f"Error processing query '{query}': {e}")
                continue
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Serper Discovery: {len(all_vendors)} unique vendors from {effective_query_limit} queries")
        self.logger.info(f"Cost: ~${effective_query_limit * 0.005:.3f}")
        self.logger.info(f"{'='*60}\n")
        
        return all_vendors
    
    def _generate_queries(self, profile: TenderProfile, target_count: Optional[int] = None) -> List[str]:
        contract_type = None
        fulfillment_model = None
        
        if profile.dynamic_context:
            contract_type = getattr(profile.dynamic_context, 'contract_type', None)
            fulfillment_model = getattr(profile.dynamic_context, 'fulfillment_model', None)
        
        if not contract_type:
            contract_type = "unknown"
        
        self.logger.info(f"Query generation: contract_type={contract_type}, fulfillment_model={fulfillment_model}")
        
        SERVICE_TOXIC_TERMS = {
            'supplier', 'manufacturer', 'distributor', 'equipment', 'oem',
            'training', 'consultant', 'saas', 'rental', 'dealer', 'wholesaler',
            'producer', 'fabricator', 'vendor'
        }
        
        PRODUCT_TOXIC_TERMS = {
            'services', 'contractor', 'consulting', 'advisory', 'maintenance'
        }
        
        CONSULTING_TOXIC_TERMS = {
            'supplier', 'manufacturer', 'equipment', 'contractor'
        }
        
        base_queries = []
        
        if profile.dynamic_context and profile.dynamic_context.search_terms:
            for term in profile.dynamic_context.search_terms:
                term_lower = term.lower()
                
                if self.config and self.config.discovery.serper_contract_aware_queries:
                    
                    if contract_type == "service":
                        if any(toxic in term_lower for toxic in SERVICE_TOXIC_TERMS):
                            self.logger.debug(f"  Filtered (service contract): {term}")
                            continue
                    
                    elif contract_type == "product":
                        if any(toxic in term_lower for toxic in PRODUCT_TOXIC_TERMS):
                            self.logger.debug(f"  Filtered (product contract): {term}")
                            continue
                    
                    elif contract_type == "consulting":
                        if any(toxic in term_lower for toxic in CONSULTING_TOXIC_TERMS):
                            self.logger.debug(f"  Filtered (consulting contract): {term}")
                            continue
                
                base_queries.append(term)
        
        if not base_queries:
            sector = None
            if profile.dynamic_context and profile.dynamic_context.sector:
                sector = profile.dynamic_context.sector
            elif profile.doc_extracted and profile.doc_extracted.structured:
                sector = profile.doc_extracted.structured.project_type or "contractor"
            
            if not sector or sector.lower() in ("unknown", "null", "none", "n/a"):
                sector = "contractor"
            
            if contract_type == "service":
                base_queries = [
                    f"{sector} contractor",
                    f"{sector} services",
                    f"government {sector} contractor"
                ]
            elif contract_type == "product":
                base_queries = [
                    f"{sector} manufacturer",
                    f"{sector} supplier",
                    f"{sector} distributor"
                ]
            elif contract_type == "consulting":
                base_queries = [
                    f"{sector} consultant",
                    f"{sector} advisory services",
                    f"{sector} consulting firm"
                ]
            else:
                base_queries = [f"{sector} contractor", f"{sector} services"]
        
        seen = set()
        unique_base = []
        for q in base_queries:
            q_lower = q.lower().strip()
            if q_lower and q_lower not in seen and len(q_lower) > 10:
                seen.add(q_lower)
                unique_base.append(q)
        
        self.logger.info(f"Generated {len(unique_base)} unique base queries")
        
        geo_sequenced_queries = []
        
        if self.config and self.config.discovery.serper_geo_query_expansion:
            
            city = None
            region = None
            country = None
            
            if profile.api_metadata and profile.api_metadata.place_of_performance:
                pop = profile.api_metadata.place_of_performance
                city = pop.city
                region = pop.state_province
                country = pop.country
            
            if not country and profile.dynamic_context:
                country = profile.dynamic_context.country
            
            geo_levels = []
            if city:
                geo_levels.append(("city", city))
            if region:
                geo_levels.append(("region", region))
            if country:
                geo_levels.append(("country", country))
            
            self.logger.info(f"Geographic expansion: {len(geo_levels)} levels")
            
            for level_name, location in geo_levels:
                for query in unique_base:
                    geo_sequenced_queries.append(f"{query} {location}")
                self.logger.debug(f"  Added {len(unique_base)} {level_name} queries")
            
            geo_sequenced_queries.extend(unique_base)
            self.logger.debug(f"  Added {len(unique_base)} global queries")
            
            final_queries = geo_sequenced_queries
        
        else:
            final_queries = unique_base
        
        if target_count:
            estimated_queries_needed = min(50, (target_count // 10) + 5)
            return final_queries[:estimated_queries_needed]
        
        return final_queries[:50]
    
    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def _should_filter_domain(self, domain: str) -> bool:
        return any(ignored in domain for ignored in IGNORE_DOMAINS)

    def _extract_company_name(self, title: str) -> str:
        common_suffixes = [
            ' - Home', ' | Home', ' - Official Site', ' | Official Site',
            ' - Wikipedia', ' | About Us', ' - Company Profile',
            ' - Contact', ' | Contact', ' - Products', ' | Products',
            ' - Official Website', ' | Official Website'
        ]
        
        cleaned = title
        for suffix in common_suffixes:
            if suffix.lower() in cleaned.lower():
                cleaned = cleaned[:cleaned.lower().index(suffix.lower())]
        
        return cleaned.strip() or title

    def _is_company_result(self, title: str, snippet: str, domain: str, url: str) -> bool:
        if not domain:
            return False

        domain_lower = domain.lower()
        if domain_lower in NON_VENDOR_DOMAINS:
            return False

        text = f"{title} {snippet}".lower()
        has_company_hint = any(token in text for token in COMPANY_HINT_KEYWORDS)
        looks_like_article = any(token in text for token in NON_VENDOR_KEYWORDS)

        try:
            path = urlparse(url).path.lower()
        except Exception:
            path = ""
        if path and any(token in path for token in ARTICLE_PATH_TOKENS):
            looks_like_article = True

        if looks_like_article and not has_company_hint:
            return False

        if domain_lower.endswith('.gc.ca') or domain_lower.endswith('.gov'):
            return False

        return True
