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

    
    def search(
        self, 
        profile: TenderProfile, 
        target_count: Optional[int] = None,
        seen_domains: Optional[Set[str]] = None,
        executed_queries: Optional[Set[str]] = None
    ) -> List[VendorRecord]:
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
        
        if seen_domains is None:
            seen_domains = set()
        if executed_queries is None:
            executed_queries = set()
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("SERPER DISCOVERY SOURCE")
        self.logger.info(f"{'='*60}")
        
        if target_count:
            self.logger.info(f"Target: {target_count} vendors, Already have: {len(seen_domains)} unique domains")
        
        base_queries = self._generate_base_queries(profile)
        all_vendors = []
        
        all_vendors = self._execute_cascading_search(
            base_queries, 
            profile, 
            seen_domains, 
            executed_queries
        )
        
        self.logger.info(f"After base queries: {len(all_vendors)} vendors from {len(executed_queries)} queries")
        
        if not target_count:
            return all_vendors
        
        deficit = target_count - len(seen_domains)
        if deficit <= 0:
            self.logger.info(f"Target reached: {len(seen_domains)}/{target_count} vendors")
            return all_vendors
        
        if len(executed_queries) == 0 or len(seen_domains) == 0:
            self.logger.warning("No successful queries yet, cannot calculate adaptive expansion")
            return all_vendors
        
        avg_unique_per_query = len(seen_domains) / len(executed_queries)
        queries_needed = int((deficit / avg_unique_per_query) * 1.3)
        
        self.logger.info(
            f"Deficit: {deficit} vendors. "
            f"Avg efficiency: {avg_unique_per_query:.1f} vendors/query. "
            f"Need ~{queries_needed} more queries."
        )
        
        SYNONYM_BATCH_SIZE = 5
        queries_generated = 0
        
        for batch_start in range(0, len(base_queries), SYNONYM_BATCH_SIZE):
            if queries_generated >= queries_needed:
                self.logger.info("Generated enough queries, stopping synonym expansion")
                break
            
            if len(seen_domains) >= target_count:
                self.logger.info("Target reached during synonym expansion")
                break
            
            batch = base_queries[batch_start:batch_start + SYNONYM_BATCH_SIZE]
            self.logger.info(f"Expanding synonym batch {batch_start//SYNONYM_BATCH_SIZE + 1}: {len(batch)} queries")
            
            synonyms = self._expand_with_synonyms(batch, executed_queries)
            queries_generated += len(synonyms)
            
            new_vendors = self._execute_cascading_search(synonyms, profile, seen_domains, executed_queries)
            all_vendors.extend(new_vendors)
            
            self.logger.info(
                f"After synonym batch: {len(seen_domains)}/{target_count} vendors (+{len(new_vendors)} new)"
            )
        
        if len(seen_domains) < target_count * 0.8:
            self.logger.info("Synonyms insufficient, trying keyword recombination...")
            recombined = self._recombine_keywords(base_queries, executed_queries)
            new_vendors = self._execute_cascading_search(recombined, profile, seen_domains, executed_queries)
            all_vendors.extend(new_vendors)
            self.logger.info(
                f"After recombination: {len(seen_domains)}/{target_count} vendors (+{len(new_vendors)} new)"
            )
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Serper Discovery Complete: {len(all_vendors)} total vendors, {len(seen_domains)} unique domains")
        self.logger.info(f"Queries executed: {len(executed_queries)}")
        self.logger.info(f"Cost: ~${len(executed_queries) * 0.005:.3f}")
        self.logger.info(f"{'='*60}\n")
        
        return all_vendors
    
    def _generate_base_queries(self, profile: TenderProfile) -> List[str]:
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
        return unique_base
    
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
    
    def _execute_cascading_search(
        self,
        base_queries: List[str],
        profile: TenderProfile,
        seen_domains: Set[str],
        executed_queries: Set[str]
    ) -> List[VendorRecord]:
        """Execute queries with cascading geographic search."""
        if not base_queries:
            return []
        
        use_places_api = self.config and getattr(self.config.discovery, 'serper_use_places_api', True)
        enable_geo_cascade = self.config and self.config.discovery.serper_geo_query_expansion
        
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
        
        country_name = None
        if profile.dynamic_context and profile.dynamic_context.country:
            country_name = profile.dynamic_context.country
        elif profile.country:
            country_name = profile.country
        elif profile.api_metadata and profile.api_metadata.place_of_performance:
            country_name = profile.api_metadata.place_of_performance.country
        
        gl_code = None
        if country_name:
            gl_code = "ca" if "Canada" in country_name else "us"
        
        all_vendors = []
        
        if enable_geo_cascade and (city or region or country):
            geo_levels = []
            if city:
                geo_levels.append(("city", city))
            if region:
                geo_levels.append(("region", region))
            if country:
                geo_levels.append(("country", country))
            geo_levels.append(("global", None))
            
            self.logger.info(f"Cascading geo search: {len(geo_levels)} levels for {len(base_queries)} base queries")
            
            for level_name, location in geo_levels:
                level_queries = []
                for query in base_queries:
                    if location:
                        full_query = f"{query} {location}"
                    else:
                        full_query = query
                    
                    if full_query.lower() not in executed_queries:
                        level_queries.append(full_query)
                
                if not level_queries:
                    self.logger.debug(f"  {level_name}: no new queries (all already executed)")
                    continue
                
                self.logger.info(f"  {level_name} level: {len(level_queries)} queries")
                
                new_vendors = self._execute_query_batch(
                    level_queries,
                    location if location else None,
                    gl_code,
                    use_places_api,
                    seen_domains,
                    executed_queries
                )
                
                all_vendors.extend(new_vendors)
                self.logger.info(f"    → {len(new_vendors)} new vendors, {len(seen_domains)} unique total")
        else:
            all_vendors = self._execute_query_batch(
                base_queries,
                None,
                gl_code,
                use_places_api,
                seen_domains,
                executed_queries
            )
        
        return all_vendors
    
    def _execute_query_batch(
        self,
        queries: List[str],
        location: Optional[str],
        gl_code: Optional[str],
        use_places_api: bool,
        seen_domains: Set[str],
        executed_queries: Set[str]
    ) -> List[VendorRecord]:
        """Execute a batch of queries."""
        vendors = []
        
        for query in queries:
            query_lower = query.lower()
            if query_lower in executed_queries:
                continue
            
            executed_queries.add(query_lower)
            
            try:
                if use_places_api:
                    response = self.client.places_search(
                        query,
                        num_results=self.results_per_query,
                        location=location,
                        gl=gl_code
                    )
                    results = response.get("places", [])
                else:
                    response = self.client.discovery_search(query, num_results=self.results_per_query)
                    results = response.get("organic", [])
                
                for position, result in enumerate(results, 1):
                    if use_places_api:
                        vendor = self._process_places_result(result, query, position, seen_domains)
                    else:
                        vendor = self._process_search_result(result, query, position, seen_domains)
                    
                    if vendor:
                        vendors.append(vendor)
            
            except Exception as e:
                self.logger.error(f"Error processing query '{query}': {e}")
                continue
        
        return vendors
    
    def _expand_with_synonyms(self, base_queries: List[str], executed_queries: Set[str]) -> List[str]:
        """Generate synonymous query variations in batches."""
        if not base_queries:
            return []
        
        import sys
        from pathlib import Path
        import importlib.util
        
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            try:
                llm_path = Path(__file__).parent.parent / "modules" / "llm_providers.py"
                spec = importlib.util.spec_from_file_location("llm_providers_module", llm_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.llm_provider = module.OpenAIProvider()
                else:
                    raise ImportError("Could not load llm_providers.py")
            except Exception as e:
                self.logger.warning(f"Could not initialize LLM provider for synonym expansion: {e}")
                return []
        
        all_variations = []
        
        prompt = f"""Generate 3 synonymous search query variations for each query below.
Focus on different word choices while maintaining the same search intent.
Avoid generic terms like "supplier", "vendor", "manufacturer" alone.

Output as JSON array:
[
  {{"original": "query1", "variations": ["var1", "var2", "var3"]}},
  {{"original": "query2", "variations": ["var1", "var2", "var3"]}}
]

Queries:
{chr(10).join(f'{idx+1}. {q}' for idx, q in enumerate(base_queries))}
"""
        
        try:
            response = self.llm_provider.generate(prompt, response_format="json")
            import json
            data = json.loads(response)
            
            for item in data:
                for variation in item.get("variations", []):
                    var_lower = variation.lower().strip()
                    if var_lower and var_lower not in executed_queries and len(var_lower) > 10:
                        if not self._is_toxic_query(variation):
                            all_variations.append(variation)
            
            self.logger.info(f"Generated {len(all_variations)} synonym variations from {len(base_queries)} base queries")
            
        except Exception as e:
            self.logger.warning(f"Failed to expand with synonyms: {e}")
        
        return all_variations
    
    def _recombine_keywords(self, base_queries: List[str], executed_queries: Set[str]) -> List[str]:
        """Generate new queries by recombining keywords from existing queries."""
        if len(base_queries) < 2:
            return []
        
        keywords = set()
        for query in base_queries:
            words = query.lower().split()
            for word in words:
                if len(word) > 3 and word not in {'the', 'and', 'for', 'with'}:
                    keywords.add(word)
        
        keyword_list = sorted(keywords)
        recombined = []
        
        for i in range(len(keyword_list)):
            for j in range(i+1, min(i+4, len(keyword_list))):
                new_query = f"{keyword_list[i]} {keyword_list[j]}"
                query_lower = new_query.lower()
                
                if query_lower not in executed_queries and len(new_query) > 10:
                    if not self._is_toxic_query(new_query):
                        recombined.append(new_query)
                        if len(recombined) >= 20:
                            break
            if len(recombined) >= 20:
                break
        
        self.logger.info(f"Generated {len(recombined)} recombined queries from {len(keywords)} unique keywords")
        return recombined
    
    def _is_toxic_query(self, query: str) -> bool:
        """Check if query contains toxic terms that should be filtered."""
        query_lower = query.lower()
        
        SERVICE_TOXIC_TERMS = {
            'supplier', 'manufacturer', 'distributor', 'equipment', 'oem',
            'training', 'consultant', 'saas', 'rental', 'dealer', 'wholesaler',
            'producer', 'fabricator', 'vendor'
        }
        
        PRODUCT_TOXIC_TERMS = {
            'services', 'contractor', 'consulting', 'advisory', 'maintenance'
        }
        
        toxic_terms = SERVICE_TOXIC_TERMS | PRODUCT_TOXIC_TERMS
        
        return any(toxic in query_lower for toxic in toxic_terms)
